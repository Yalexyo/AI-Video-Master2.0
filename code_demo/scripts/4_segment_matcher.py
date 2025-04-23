#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
段落匹配模块
-----------
基于用户确认的关键词维度，对字幕段落进行语义匹配和评分。
计算各段落与各级关键词的匹配程度，生成综合评分。
"""

import os
import sys
import json
import logging
import numpy as np
from pathlib import Path
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("segment_matcher")

# 导入工具模块
from utils import config, io_handlers, text_analysis, model_handlers

class SegmentMatcher:
    """
    段落匹配器类
    """
    def __init__(self, batch_mode=False):
        """
        初始化段落匹配器
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 获取路径配置
        self.subtitles_dir = os.path.join(config.get_path('root_output_dir'), 'Subtitles')
        self.analysis_dir = os.path.join(config.get_path('root_output_dir'), 'Analysis')
        self.matching_dir = os.path.join(config.get_path('root_output_dir'), 'Matching')
        
        # 确保输出目录存在
        io_handlers.ensure_directory(self.matching_dir)
        
        # 文件路径
        self.dimensions_file = os.path.join(self.analysis_dir, 'modified_key_dimensions.json')
        if not os.path.exists(self.dimensions_file):
            self.dimensions_file = os.path.join(self.analysis_dir, 'initial_key_dimensions.json')
        
        self.output_file = os.path.join(self.matching_dir, 'segments_with_scores.json')
        
        # 匹配配置
        self.min_segment_length = 3  # 最小段落长度(单词数)
        self.similarity_method = 'sentence-bert'  # 相似度计算方法
        self.level_weights = {  # 各级别维度的权重
            1: 0.5,  # 一级维度权重
            2: 0.3,  # 二级维度权重
            3: 0.2   # 三级维度权重
        }

    def load_dimensions(self):
        """
        加载关键词维度结构
        
        返回:
            维度结构字典
        """
        if not os.path.exists(self.dimensions_file):
            logger.error(f"维度文件不存在: {self.dimensions_file}")
            return {}
        
        try:
            with open(self.dimensions_file, 'r', encoding='utf-8') as f:
                dimensions = json.load(f)
            
            logger.info(f"已加载维度结构: {self.dimensions_file}")
            return dimensions
        
        except Exception as e:
            logger.error(f"加载维度结构失败: {e}")
            return {}

    def extract_subtitles_segments(self):
        """
        从字幕文件中提取段落
        
        返回:
            段落列表，每项包含文件名、开始时间、结束时间和文本内容
        """
        subtitle_files = io_handlers.list_subtitles(self.subtitles_dir)
        
        if not subtitle_files:
            logger.warning(f"没有找到字幕文件: {self.subtitles_dir}")
            return []
        
        segments = []
        
        for subtitle_file in subtitle_files:
            try:
                # 提取文件名(不含扩展名)
                base_name = os.path.splitext(os.path.basename(subtitle_file))[0]
                
                # 解析字幕文件
                subtitles = text_analysis.parse_srt_file(subtitle_file)
                
                if not subtitles:
                    logger.warning(f"字幕文件无内容: {subtitle_file}")
                    continue
                
                # 将相邻的字幕合并为段落
                current_segment = {
                    'file': base_name,
                    'subtitles': []
                }
                
                for subtitle in subtitles:
                    text = subtitle['text'].strip()
                    
                    # 跳过过短的字幕
                    if len(text.split()) < self.min_segment_length:
                        if current_segment['subtitles']:
                            # 如果当前字幕太短但与上一个字幕的时间间隔短，则合并
                            last_sub = current_segment['subtitles'][-1]
                            if subtitle['start_seconds'] - last_sub['end_seconds'] < 2.0:
                                last_sub['text'] += ' ' + text
                                last_sub['end_seconds'] = subtitle['end_seconds']
                                last_sub['end_time'] = subtitle['end_time']
                        continue
                    
                    # 判断是否属于当前段落
                    if current_segment['subtitles']:
                        last_sub = current_segment['subtitles'][-1]
                        time_gap = subtitle['start_seconds'] - last_sub['end_seconds']
                        
                        # 如果时间间隔大于阈值，创建新段落
                        if time_gap > 3.0:
                            # 计算段落的开始和结束时间
                            segment_start = current_segment['subtitles'][0]['start_seconds']
                            segment_end = current_segment['subtitles'][-1]['end_seconds']
                            segment_text = ' '.join([s['text'] for s in current_segment['subtitles']])
                            
                            # 添加段落
                            segments.append({
                                'file': base_name,
                                'start_time': text_analysis.seconds_to_time(segment_start),
                                'end_time': text_analysis.seconds_to_time(segment_end),
                                'start_seconds': segment_start,
                                'end_seconds': segment_end,
                                'text': segment_text
                            })
                            
                            # 创建新段落
                            current_segment = {
                                'file': base_name,
                                'subtitles': []
                            }
                    
                    # 添加到当前段落
                    current_segment['subtitles'].append(subtitle)
                
                # 处理最后一个段落
                if current_segment['subtitles']:
                    segment_start = current_segment['subtitles'][0]['start_seconds']
                    segment_end = current_segment['subtitles'][-1]['end_seconds']
                    segment_text = ' '.join([s['text'] for s in current_segment['subtitles']])
                    
                    segments.append({
                        'file': base_name,
                        'start_time': text_analysis.seconds_to_time(segment_start),
                        'end_time': text_analysis.seconds_to_time(segment_end),
                        'start_seconds': segment_start,
                        'end_seconds': segment_end,
                        'text': segment_text
                    })
            
            except Exception as e:
                logger.error(f"处理字幕文件失败 {subtitle_file}: {e}")
        
        logger.info(f"共提取出 {len(segments)} 个段落")
        return segments

    def calculate_segment_scores(self, segments, dimensions):
        """
        计算段落与各级维度的匹配得分
        
        参数:
            segments: 段落列表
            dimensions: 维度结构字典
        
        返回:
            包含得分的段落列表
        """
        if not segments or not dimensions:
            return []
        
        # 提取级别维度的关键词和权重
        level_dimensions = {
            1: [],  # 一级维度
            2: [],  # 二级维度
            3: []   # 三级维度
        }
        
        # 从维度结构中提取关键词和权重
        for dim1_id, dim1_info in dimensions.items():
            # 一级维度
            level_dimensions[1].append({
                'id': dim1_id,
                'name': dim1_info['name'],
                'keywords': dim1_info['keywords'],
                'weight': dim1_info['weight']
            })
            
            # 二级维度
            for dim2_id, dim2_info in dim1_info.get('sub_dimensions', {}).items():
                level_dimensions[2].append({
                    'id': f"{dim1_id}.{dim2_id}",
                    'name': dim2_info['name'],
                    'keywords': dim2_info['keywords'],
                    'weight': dim2_info['weight'] * dim1_info['weight'],
                    'parent': dim1_id
                })
                
                # 三级维度
                for dim3_id, dim3_info in dim2_info.get('sub_dimensions', {}).items():
                    level_dimensions[3].append({
                        'id': f"{dim1_id}.{dim2_id}.{dim3_id}",
                        'name': dim3_info['name'],
                        'keywords': dim3_info['keywords'],
                        'weight': dim3_info['weight'] * dim2_info['weight'] * dim1_info['weight'],
                        'parent': f"{dim1_id}.{dim2_id}"
                    })
        
        # 准备评分
        scored_segments = []
        
        # 对每个段落计算得分
        for segment in segments:
            # 清理文本
            clean_text = text_analysis.clean_text(segment['text'])
            
            # 计算各级别维度的相似度得分
            level_scores = {}
            
            for level, dims in level_dimensions.items():
                level_scores[level] = []
                
                for dim in dims:
                    # 计算与关键词的平均相似度
                    similarities = []
                    
                    for keyword in dim['keywords']:
                        similarity = text_analysis.compute_text_similarity(
                            clean_text, 
                            keyword, 
                            method=self.similarity_method
                        )
                        similarities.append(similarity)
                    
                    # 计算加权平均相似度
                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                    weighted_score = avg_similarity * dim['weight']
                    
                    # 保存得分
                    level_scores[level].append({
                        'dimension_id': dim['id'],
                        'dimension_name': dim['name'],
                        'score': avg_similarity,
                        'weighted_score': weighted_score
                    })
            
            # 计算各级别维度的最佳匹配得分
            best_level_scores = {}
            
            for level, scores in level_scores.items():
                if scores:
                    # 按加权得分排序
                    sorted_scores = sorted(scores, key=lambda x: x['weighted_score'], reverse=True)
                    best_level_scores[level] = sorted_scores[0]
                else:
                    best_level_scores[level] = {
                        'dimension_id': 'none',
                        'dimension_name': 'none',
                        'score': 0,
                        'weighted_score': 0
                    }
            
            # 计算综合得分
            combined_score = sum([
                best_level_scores[level]['weighted_score'] * self.level_weights[level]
                for level in best_level_scores
            ])
            
            # 保存得分
            scored_segment = segment.copy()
            scored_segment['scores'] = {
                'level_1': best_level_scores[1],
                'level_2': best_level_scores[2],
                'level_3': best_level_scores[3],
                'combined': combined_score
            }
            
            scored_segments.append(scored_segment)
        
        # 按综合得分排序
        sorted_segments = sorted(
            scored_segments, 
            key=lambda x: x['scores']['combined'], 
            reverse=True
        )
        
        return sorted_segments

    def create_example_segments(self):
        """
        创建示例段落(用于测试)
        
        返回:
            示例段落列表
        """
        logger.info("创建示例段落")
        
        # 示例段落
        example_segments = [
            {
                "file": "example",
                "start_time": "00:00:01,000",
                "end_time": "00:00:05,000",
                "start_seconds": 1.0,
                "end_seconds": 5.0,
                "text": "在这个快节奏的时代，我们常常忽略生活中的美好。",
                "scores": {
                    "level_1": {
                        "dimension_id": "dimension_1_2",
                        "dimension_name": "生活情感",
                        "score": 0.85,
                        "weighted_score": 0.76
                    },
                    "level_2": {
                        "dimension_id": "dimension_1_2.subtopic_2",
                        "dimension_name": "人生感悟",
                        "score": 0.78,
                        "weighted_score": 0.55
                    },
                    "level_3": {
                        "dimension_id": "dimension_1_2.subtopic_2.keyword_1",
                        "dimension_name": "生活感悟",
                        "score": 0.82,
                        "weighted_score": 0.49
                    },
                    "combined": 0.65
                }
            },
            {
                "file": "example",
                "start_time": "00:00:06,000",
                "end_time": "00:00:10,000",
                "start_seconds": 6.0,
                "end_seconds": 10.0,
                "text": "每一天都有值得珍视的瞬间，需要我们去发现。",
                "scores": {
                    "level_1": {
                        "dimension_id": "dimension_1_2",
                        "dimension_name": "生活情感",
                        "score": 0.82,
                        "weighted_score": 0.74
                    },
                    "level_2": {
                        "dimension_id": "dimension_1_2.subtopic_2",
                        "dimension_name": "人生感悟",
                        "score": 0.80,
                        "weighted_score": 0.56
                    },
                    "level_3": {
                        "dimension_id": "dimension_1_2.subtopic_2.keyword_1",
                        "dimension_name": "生活感悟",
                        "score": 0.79,
                        "weighted_score": 0.47
                    },
                    "combined": 0.63
                }
            },
            {
                "file": "example",
                "start_time": "00:00:11,000",
                "end_time": "00:00:15,000",
                "start_seconds": 11.0,
                "end_seconds": 15.0,
                "text": "阳光、微风、花朵，这些都是大自然给我们的礼物。",
                "scores": {
                    "level_1": {
                        "dimension_id": "dimension_1_1",
                        "dimension_name": "自然风景",
                        "score": 0.92,
                        "weighted_score": 0.92
                    },
                    "level_2": {
                        "dimension_id": "dimension_1_1.subtopic_2",
                        "dimension_name": "花草树木",
                        "score": 0.88,
                        "weighted_score": 0.70
                    },
                    "level_3": {
                        "dimension_id": "dimension_1_1.subtopic_2.keyword_1",
                        "dimension_name": "鲜花",
                        "score": 0.85,
                        "weighted_score": 0.60
                    },
                    "combined": 0.79
                }
            },
            {
                "file": "example",
                "start_time": "00:00:16,000",
                "end_time": "00:00:20,000",
                "start_seconds": 16.0,
                "end_seconds": 20.0,
                "text": "珍惜身边的人，感受身边的爱，生活会更加美好。",
                "scores": {
                    "level_1": {
                        "dimension_id": "dimension_1_2",
                        "dimension_name": "生活情感",
                        "score": 0.90,
                        "weighted_score": 0.81
                    },
                    "level_2": {
                        "dimension_id": "dimension_1_2.subtopic_1",
                        "dimension_name": "家庭关系",
                        "score": 0.87,
                        "weighted_score": 0.70
                    },
                    "level_3": {
                        "dimension_id": "dimension_1_2.subtopic_1.keyword_1",
                        "dimension_name": "亲情",
                        "score": 0.83,
                        "weighted_score": 0.58
                    },
                    "combined": 0.72
                }
            },
            {
                "file": "example",
                "start_time": "00:00:21,000",
                "end_time": "00:00:25,000",
                "start_seconds": 21.0,
                "end_seconds": 25.0,
                "text": "发现生活的美好，做最好的自己。",
                "scores": {
                    "level_1": {
                        "dimension_id": "dimension_1_2",
                        "dimension_name": "生活情感",
                        "score": 0.88,
                        "weighted_score": 0.79
                    },
                    "level_2": {
                        "dimension_id": "dimension_1_2.subtopic_2",
                        "dimension_name": "人生感悟",
                        "score": 0.86,
                        "weighted_score": 0.60
                    },
                    "level_3": {
                        "dimension_id": "dimension_1_2.subtopic_2.keyword_2",
                        "dimension_name": "积极心态",
                        "score": 0.84,
                        "weighted_score": 0.50
                    },
                    "combined": 0.67
                }
            }
        ]
        
        return example_segments

    def process(self):
        """
        处理段落匹配
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 检查输出文件是否已存在
            if os.path.exists(self.output_file) and not self.batch_mode:
                logger.info(f"段落匹配文件已存在: {self.output_file}")
                
                # 询问是否覆盖
                response = input(f"段落匹配文件已存在: {self.output_file}，是否覆盖？(y/n): ")
                if response.lower() != 'y':
                    logger.info("跳过段落匹配")
                    return True
            
            # 加载维度结构
            dimensions = self.load_dimensions()
            
            if not dimensions:
                logger.warning("无法加载维度结构，使用示例段落")
                scored_segments = self.create_example_segments()
            else:
                # 提取字幕段落
                segments = self.extract_subtitles_segments()
                
                if not segments:
                    logger.warning("没有找到字幕段落，使用示例段落")
                    scored_segments = self.create_example_segments()
                else:
                    # 计算段落得分
                    scored_segments = self.calculate_segment_scores(segments, dimensions)
            
            # 保存匹配结果
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(scored_segments, f, ensure_ascii=False, indent=2)
            
            logger.info(f"段落匹配结果已保存: {self.output_file}")
            logger.info(f"共处理 {len(scored_segments)} 个段落")
            
            return True
        
        except Exception as e:
            logger.error(f"段落匹配失败: {e}")
            return False


if __name__ == "__main__":
    # 初始化配置
    config.init()
    
    # 创建段落匹配器并运行
    matcher = SegmentMatcher(batch_mode='--batch' in sys.argv)
    
    if matcher.process():
        logger.info("段落匹配完成")
        sys.exit(0)
    else:
        logger.error("段落匹配失败")
        sys.exit(1)
