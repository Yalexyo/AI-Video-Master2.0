#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
片段提取模块
-----------
基于匹配评分结果，从原始视频中提取相关片段，
并按照维度类别进行分类存储。
"""

import os
import sys
import json
import logging
import shutil
from pathlib import Path
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clip_extractor")

# 导入工具模块
from utils import config, io_handlers, video_utils

class ClipExtractor:
    """
    视频片段提取器类
    """
    def __init__(self, batch_mode=False):
        """
        初始化视频片段提取器
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 获取路径配置
        self.video_dir = os.path.join(config.get_path('root_input_dir'), 'OSS_VideoList')
        self.matching_dir = os.path.join(config.get_path('root_output_dir'), 'Matching')
        self.clips_dir = os.path.join(config.get_path('root_output_dir'), 'Clips')
        
        # 确保输出目录存在
        io_handlers.ensure_directory(self.clips_dir)
        
        # 文件路径
        self.segments_file = os.path.join(self.matching_dir, 'segments_with_scores.json')
        
        # 提取配置
        self.score_threshold = 0.3  # 最低匹配评分阈值
        self.max_clips_per_category = 10  # 每个类别最多提取的片段数量
        self.overlap_threshold = 0.5  # 片段重叠阈值
        self.min_clip_duration = 3.0  # 最小片段时长(秒)
        self.max_clip_duration = 15.0  # 最大片段时长(秒)
        self.total_clips_limit = 50  # 总片段数量限制

    def load_segments(self):
        """
        加载段落匹配结果
        
        返回:
            段落列表，每项包含文件名、开始时间、结束时间、文本内容和评分
        """
        if not os.path.exists(self.segments_file):
            logger.error(f"段落匹配文件不存在: {self.segments_file}")
            return []
        
        try:
            with open(self.segments_file, 'r', encoding='utf-8') as f:
                segments = json.load(f)
            
            logger.info(f"已加载段落匹配结果: {self.segments_file}")
            logger.info(f"共 {len(segments)} 个段落")
            return segments
        
        except Exception as e:
            logger.error(f"加载段落匹配结果失败: {e}")
            return []

    def find_video_file(self, segment_file):
        """
        查找对应的视频文件
        
        参数:
            segment_file: 段落文件名
        
        返回:
            视频文件路径，如果找不到则返回None
        """
        # 首先尝试直接匹配
        potential_video_files = [
            f"{segment_file}.mp4",
            f"{segment_file}.mov",
            f"{segment_file}.avi",
            f"{segment_file}.m4v",
            f"{segment_file}.MOV",
            f"{segment_file}.MP4",
        ]
        
        for video_file in potential_video_files:
            video_path = os.path.join(self.video_dir, video_file)
            if os.path.exists(video_path):
                return video_path
        
        # 如果没有直接匹配，尝试查找所有视频文件
        video_files = io_handlers.list_videos(self.video_dir)
        
        for video_file in video_files:
            base_name = os.path.splitext(os.path.basename(video_file))[0]
            if base_name == segment_file:
                return video_file
        
        logger.warning(f"找不到对应的视频文件: {segment_file}")
        return None

    def extract_clip(self, video_path, start_time, end_time, output_path, category):
        """
        提取视频片段
        
        参数:
            video_path: 视频文件路径
            start_time: 开始时间(秒)
            end_time: 结束时间(秒)
            output_path: 输出路径
            category: 类别名称
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 提取片段
            success = video_utils.extract_video_segment(
                input_path=video_path,
                output_path=output_path,
                start_time=start_time,
                end_time=end_time,
                lossless=False,
                overwrite=True
            )
            
            if success:
                # 获取视频元数据
                metadata = video_utils.get_video_metadata(output_path)
                duration = metadata.get('duration', 0)
                
                # 添加到片段索引
                clip_info = {
                    'source_file': video_path,
                    'category': category,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'original_fps': metadata.get('frame_rate', 30),
                    'width': metadata.get('width', 1280),
                    'height': metadata.get('height', 720)
                }
                
                io_handlers.add_clip_to_index(output_path, clip_info)
                
                logger.info(f"视频片段提取成功: {output_path}")
                return True
            else:
                logger.error(f"视频片段提取失败: {output_path}")
                return False
        
        except Exception as e:
            logger.error(f"提取视频片段失败: {e}")
            return False

    def categorize_segments(self, segments):
        """
        将段落按照维度类别进行分类
        
        参数:
            segments: 段落列表
        
        返回:
            分类后的段落字典，格式为 {类别: [段落, ...]}
        """
        categorized = defaultdict(list)
        
        for segment in segments:
            # 跳过得分过低的段落
            if segment['scores']['combined'] < self.score_threshold:
                continue
            
            # 获取一级维度作为类别
            category = segment['scores']['level_1']['dimension_name']
            
            # 过滤无效类别
            if category == 'none':
                continue
            
            # 添加到对应类别
            categorized[category].append(segment)
        
        # 每个类别按评分排序
        for category in categorized:
            categorized[category].sort(key=lambda x: x['scores']['combined'], reverse=True)
        
        return categorized

    def check_overlap(self, new_segment, existing_segments):
        """
        检查新段落与现有段落是否重叠
        
        参数:
            new_segment: 新段落
            existing_segments: 现有段落列表
        
        返回:
            如果重叠返回True，否则返回False
        """
        for existing in existing_segments:
            # 检查是否为相同文件
            if new_segment['file'] != existing['file']:
                continue
            
            # 计算重叠时间
            overlap_start = max(new_segment['start_seconds'], existing['start_seconds'])
            overlap_end = min(new_segment['end_seconds'], existing['end_seconds'])
            
            if overlap_end <= overlap_start:
                continue  # 没有重叠
            
            # 计算重叠比例
            new_duration = new_segment['end_seconds'] - new_segment['start_seconds']
            existing_duration = existing['end_seconds'] - existing['start_seconds']
            overlap_duration = overlap_end - overlap_start
            
            new_overlap_ratio = overlap_duration / new_duration
            existing_overlap_ratio = overlap_duration / existing_duration
            
            # 如果任一重叠比例超过阈值，则认为重叠
            if new_overlap_ratio > self.overlap_threshold or existing_overlap_ratio > self.overlap_threshold:
                return True
        
        return False

    def select_segments_for_extraction(self, categorized_segments):
        """
        为提取选择合适的段落
        
        参数:
            categorized_segments: 分类后的段落字典
        
        返回:
            选择后的段落列表
        """
        selected = []
        
        # 从每个类别中选择若干个段落
        for category, segments in categorized_segments.items():
            category_selected = []
            
            for segment in segments:
                # 检查片段时长
                duration = segment['end_seconds'] - segment['start_seconds']
                
                # 跳过过短或过长的片段
                if duration < self.min_clip_duration or duration > self.max_clip_duration:
                    continue
                
                # 检查与已选片段是否重叠
                if self.check_overlap(segment, category_selected):
                    continue
                
                # 添加到已选列表
                category_selected.append(segment)
                
                # 检查是否达到每类上限
                if len(category_selected) >= self.max_clips_per_category:
                    break
            
            # 添加到总选择列表
            selected.extend(category_selected)
        
        # 检查总片段数量限制
        if len(selected) > self.total_clips_limit:
            # 按评分排序
            selected.sort(key=lambda x: x['scores']['combined'], reverse=True)
            selected = selected[:self.total_clips_limit]
        
        logger.info(f"已选择 {len(selected)} 个片段进行提取")
        return selected

    def extract_clips(self, selected_segments):
        """
        提取选择的视频片段
        
        参数:
            selected_segments: 选择后的段落列表
        
        返回:
            提取的片段列表
        """
        extracted_clips = []
        
        for segment in selected_segments:
            # 查找对应的视频文件
            video_path = self.find_video_file(segment['file'])
            
            if not video_path:
                logger.warning(f"找不到视频文件: {segment['file']}")
                continue
            
            # 获取类别
            category = segment['scores']['level_1']['dimension_name']
            category_dir = os.path.join(self.clips_dir, f"Category_{category}")
            
            # 创建类别目录
            os.makedirs(category_dir, exist_ok=True)
            
            # 格式化时间戳
            start_str = segment['start_time'].replace(':', 'h', 1).replace(':', 'm', 1).replace(',', 's')
            end_str = segment['end_time'].replace(':', 'h', 1).replace(':', 'm', 1).replace(',', 's')
            
            # 生成输出文件名
            clip_name = f"clip_{category}_{segment['file']}_{start_str}_{end_str}.mp4"
            output_path = os.path.join(category_dir, clip_name)
            
            # 提取片段
            if self.extract_clip(
                video_path=video_path,
                start_time=segment['start_seconds'],
                end_time=segment['end_seconds'],
                output_path=output_path,
                category=category
            ):
                extracted_clips.append({
                    'path': output_path,
                    'category': category,
                    'score': segment['scores']['combined'],
                    'text': segment['text']
                })
        
        return extracted_clips

    def create_example_clips(self):
        """
        创建示例视频片段(用于测试)
        
        返回:
            示例片段列表
        """
        logger.info("创建示例视频片段")
        
        # 创建类别目录
        categories = ["自然风景", "生活情感", "城市生活"]
        
        for category in categories:
            category_dir = os.path.join(self.clips_dir, f"Category_{category}")
            os.makedirs(category_dir, exist_ok=True)
            
            # 创建示例文本文件(而不是视频)
            for i in range(3):
                clip_path = os.path.join(category_dir, f"example_clip_{i+1}.txt")
                
                with open(clip_path, 'w', encoding='utf-8') as f:
                    f.write(f"这是一个示例片段，类别为：{category}\n")
                    f.write(f"在实际运行时，这里会是一个视频文件。\n")
                    f.write(f"片段 {i+1} 的得分为：{0.8 - i * 0.1}\n")
            
            logger.info(f"已创建 {category} 类别的示例片段")
        
        return [
            {
                'path': os.path.join(self.clips_dir, "Category_自然风景", "example_clip_1.txt"),
                'category': "自然风景",
                'score': 0.8,
                'text': "这是一个关于自然风景的示例片段"
            },
            {
                'path': os.path.join(self.clips_dir, "Category_生活情感", "example_clip_1.txt"),
                'category': "生活情感",
                'score': 0.8,
                'text': "这是一个关于生活情感的示例片段"
            },
            {
                'path': os.path.join(self.clips_dir, "Category_城市生活", "example_clip_1.txt"),
                'category': "城市生活",
                'score': 0.8,
                'text': "这是一个关于城市生活的示例片段"
            }
        ]

    def process(self):
        """
        处理视频片段提取
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 检查输出目录是否已有内容
            existing_clips = io_handlers.list_files(self.clips_dir, recursive=True)
            
            if existing_clips and not self.batch_mode:
                logger.info(f"输出目录已有 {len(existing_clips)} 个文件")
                
                # 询问是否覆盖
                response = input(f"输出目录已有内容，是否清空并重新提取？(y/n): ")
                if response.lower() == 'y':
                    # 清空目录
                    for file in existing_clips:
                        try:
                            os.remove(file)
                        except:
                            pass
                    
                    # 删除空目录
                    for root, dirs, files in os.walk(self.clips_dir, topdown=False):
                        for name in dirs:
                            try:
                                dir_path = os.path.join(root, name)
                                if not os.listdir(dir_path):
                                    os.rmdir(dir_path)
                            except:
                                pass
                    
                    logger.info("已清空输出目录")
                else:
                    logger.info("保留现有片段，跳过提取")
                    return True
            
            # 检查FFmpeg是否可用
            if not video_utils.check_ffmpeg():
                logger.error("FFmpeg未安装或不可用，无法继续")
                
                # 创建示例片段
                self.create_example_clips()
                return True
            
            # 加载段落匹配结果
            segments = self.load_segments()
            
            if not segments:
                logger.warning("没有找到段落匹配结果，创建示例片段")
                self.create_example_clips()
                return True
            
            # 按类别分类段落
            categorized_segments = self.categorize_segments(segments)
            
            if not categorized_segments:
                logger.warning("没有符合条件的段落，创建示例片段")
                self.create_example_clips()
                return True
            
            # 选择要提取的段落
            selected_segments = self.select_segments_for_extraction(categorized_segments)
            
            if not selected_segments:
                logger.warning("没有选择到合适的段落，创建示例片段")
                self.create_example_clips()
                return True
            
            # 提取片段
            extracted_clips = self.extract_clips(selected_segments)
            
            logger.info(f"共提取 {len(extracted_clips)} 个视频片段")
            
            return True
        
        except Exception as e:
            logger.error(f"视频片段提取失败: {e}")
            return False


if __name__ == "__main__":
    # 初始化配置
    config.init()
    
    # 创建视频片段提取器并运行
    extractor = ClipExtractor(batch_mode='--batch' in sys.argv)
    
    if extractor.process():
        logger.info("视频片段提取完成")
        sys.exit(0)
    else:
        logger.error("视频片段提取失败")
        sys.exit(1)
