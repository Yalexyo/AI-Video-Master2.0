#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试视频生成完整流程

包含测试从Demo视频分析、候选视频处理、片段匹配到最终视频合成的全流程
"""

# 设置完全离线模式，阻止连接Hugging Face
import os
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1' 
os.environ['DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

import sys
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
import copy

# 添加项目根目录到Python路径，确保可以导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,  # 使用DEBUG级别记录更多信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(project_root, 'logs', f'video_pipeline_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'))
    ]
)
logger = logging.getLogger(__name__)

# 导入项目模块
from src.core.magic_video_service import MagicVideoService
from src.core.hot_words_service import HotWordsService
from utils.processor import VideoProcessor

async def test_process_demo_video(demo_video_path: str):
    """
    测试Demo视频处理功能
    """
    logger.info(f"开始测试Demo视频处理: {demo_video_path}")
    
    # 初始化服务
    hot_words_service = HotWordsService()
    magic_video_service = MagicVideoService()
    
    # 获取当前热词ID
    current_hotword_id = hot_words_service.get_current_hotword_id()
    logger.info(f"当前使用的热词ID: {current_hotword_id}")
    
    try:
        # 处理Demo视频
        result = await magic_video_service.process_demo_video(demo_video_path, current_hotword_id)
        
        if result.get("error"):
            logger.error(f"处理Demo视频出错: {result['error']}")
            return None
        
        logger.info(f"Demo视频处理成功，识别 {len(result['stages'])} 个语义段落")
        return result
    except Exception as e:
        logger.exception(f"测试Demo视频处理时出错: {str(e)}")
        return None

async def test_process_candidate_videos(video_paths: List[str]):
    """
    测试候选视频处理功能
    """
    logger.info(f"开始测试候选视频处理，视频数量: {len(video_paths)}")
    
    # 初始化服务
    hot_words_service = HotWordsService()
    magic_video_service = MagicVideoService()
    
    # 获取当前热词ID
    current_hotword_id = hot_words_service.get_current_hotword_id()
    
    try:
        # 处理候选视频
        candidate_subtitles = await magic_video_service.process_candidate_videos(video_paths, current_hotword_id)
        
        if not candidate_subtitles:
            logger.error("处理候选视频失败，未返回字幕数据")
            return None
        
        logger.info(f"候选视频处理成功，处理 {len(candidate_subtitles)} 个视频")
        
        # 记录字幕信息以供调试
        for video_id, subtitle_df in candidate_subtitles.items():
            if subtitle_df is None or subtitle_df.empty:
                logger.warning(f"视频 {video_id} 未能提取到字幕")
            else:
                logger.info(f"视频 {video_id} 成功提取 {len(subtitle_df)} 条字幕")
        
        return candidate_subtitles
    except Exception as e:
        logger.exception(f"测试候选视频处理时出错: {str(e)}")
        return None

async def optimize_match_results(demo_segments: List[Dict[str, Any]], match_results: Dict[str, List[Dict[str, Any]]], min_video_sources: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """
    优化匹配结果，确保从多个不同的视频中选择片段
    
    参数:
        demo_segments: Demo视频的分段信息
        match_results: 原始匹配结果
        min_video_sources: 最少使用的不同视频源数量
        
    返回:
        优化后的匹配结果
    """
    logger.info(f"开始优化匹配结果，确保使用至少{min_video_sources}个不同视频源")
    
    # 深复制一份匹配结果以避免修改原始结果
    optimized_results = copy.deepcopy(match_results)
    
    try:
        # 记录已选择的视频ID
        selected_video_ids = set()
        
        # 获取每个阶段可用的视频ID列表
        all_available_videos = set()
        for matches in match_results.values():
            for match in matches:
                all_available_videos.add(match['video_id'])
        
        logger.info(f"总共有 {len(all_available_videos)} 个可用的视频源")
        
        # 如果可用视频源少于要求的最少源数，则放宽限制
        if len(all_available_videos) < min_video_sources:
            logger.warning(f"可用视频源数量({len(all_available_videos)})少于要求的最少数量({min_video_sources})，将使用所有可用视频源")
            min_video_sources = len(all_available_videos)
        
        # 标记包含关键品牌词或作为片尾的段落
        brand_segments = set()
        last_segment_id = None
        
        # 确定哪些段落包含品牌关键词或是最后一个段落
        sorted_stages = sorted(match_results.keys(), key=lambda x: int(x) if x.isdigit() else float('inf'))
        if sorted_stages:
            last_segment_id = sorted_stages[-1]
            
        for stage_id, segment in zip([s['stage'] for s in demo_segments], demo_segments):
            stage_id_str = str(stage_id)
            # 检查文本是否包含品牌关键词
            segment_text = segment.get('text', '').lower()
            if "启赋蕴淳" in segment_text or "启赋" in segment_text:
                brand_segments.add(stage_id_str)
                logger.info(f"标记阶段 {stage_id_str} 为品牌关键段落")
                
        # 如果最后一个段落存在，也标记为需要保护的段落
        if last_segment_id:
            brand_segments.add(last_segment_id)
            logger.info(f"标记阶段 {last_segment_id} 为片尾段落")
            
        # 第一轮：优先选择有品牌关键词的段落的最佳匹配
        for stage_id in sorted_stages:
            matches = match_results[stage_id]
            if not matches:
                continue
                
            if stage_id in brand_segments:
                # 对于品牌段落，优先选择已增强过相似度的匹配项
                boosted_matches = [m for m in matches if m.get('boosted', False)]
                
                if boosted_matches:
                    best_boosted = boosted_matches[0]  # 取相似度最高的增强匹配
                    optimized_results[stage_id] = [best_boosted]
                    selected_video_ids.add(best_boosted['video_id'])
                    logger.info(f"阶段 {stage_id} (品牌/片尾): 选择已增强的匹配 {best_boosted['video_id']}，相似度: {best_boosted['similarity']}%")
                else:
                    # 如果没有增强过的匹配项，选择最佳匹配
                    best_match = matches[0]
                    optimized_results[stage_id] = [best_match]
                    selected_video_ids.add(best_match['video_id'])
                    logger.info(f"阶段 {stage_id} (品牌/片尾): 选择最佳匹配 {best_match['video_id']}，相似度: {best_match['similarity']}%（无增强匹配）")
            
        # 第二轮：为非品牌段落选择视频源，确保多样性
        for stage_id in sorted_stages:
            matches = match_results[stage_id]
            if not matches or stage_id in brand_segments:  # 已处理过的品牌段落跳过
                continue
                
            # 检查当前是否已经达到了最少视频源数量
            if len(selected_video_ids) >= min_video_sources:
                # 已经满足最少视频源要求，可以选择最佳匹配
                best_match = matches[0]
                optimized_results[stage_id] = [best_match]
                selected_video_ids.add(best_match['video_id'])
                logger.info(f"阶段 {stage_id}: 已达到最少视频源要求，选择最佳匹配 {best_match['video_id']}，相似度: {best_match['similarity']}%")
                continue
                
            # 尝试找到未使用过的视频中相似度最高的
            unused_matches = [match for match in matches 
                             if match['video_id'] not in selected_video_ids]
            
            if unused_matches:
                # 为了确保多样性，降低相似度要求
                best_similarity = matches[0]['similarity']
                # 当还没达到最少视频源要求时，降低相似度阈值以确保能找到足够的不同视频源
                threshold = max(30, best_similarity * 0.65)  # 降低到65%，最低不低于30%
                
                # 过滤低于阈值的匹配
                valid_matches = [match for match in unused_matches 
                                if match['similarity'] >= threshold]
                
                if valid_matches:
                    # 选择未使用视频中相似度最高的
                    best_unused_match = valid_matches[0]
                    optimized_results[stage_id] = [best_unused_match]
                    selected_video_ids.add(best_unused_match['video_id'])
                    logger.info(f"阶段 {stage_id}: 选择未使用的视频 {best_unused_match['video_id']}，相似度: {best_unused_match['similarity']}%")
                else:
                    # 如果没有符合阈值的未使用视频，但我们需要满足最少视频源数量
                    # 则进一步降低要求，选择任何未使用的视频
                    if unused_matches and len(selected_video_ids) < min_video_sources:
                        forced_match = unused_matches[0]  # 选择未使用中相似度最高的
                        optimized_results[stage_id] = [forced_match]
                        selected_video_ids.add(forced_match['video_id'])
                        logger.info(f"阶段 {stage_id}: 强制选择未使用的视频 {forced_match['video_id']}，相似度: {forced_match['similarity']}%（为满足多样性要求）")
                    else:
                        # 如果实在没有未使用的视频，则选择最佳匹配
                        best_match = matches[0]
                        optimized_results[stage_id] = [best_match]
                        selected_video_ids.add(best_match['video_id'])
                        logger.info(f"阶段 {stage_id}: 没有合适的未使用视频，选择最佳匹配 {best_match['video_id']}，相似度: {best_match['similarity']}%")
            else:
                # 如果所有视频都已使用，选择最佳匹配
                best_match = matches[0]
                optimized_results[stage_id] = [best_match]
                selected_video_ids.add(best_match['video_id'])
                logger.info(f"阶段 {stage_id}: 所有视频已使用，选择最佳匹配 {best_match['video_id']}，相似度: {best_match['similarity']}%")
        
        # 如果选择的视频源数量仍然少于要求，尝试强制替换一些阶段的选择
        if len(selected_video_ids) < min_video_sources:
            logger.warning(f"第一轮选择后只有 {len(selected_video_ids)} 个视频源，少于要求的 {min_video_sources} 个，尝试强制替换")
            
            # 找出所有未使用的视频ID
            unused_videos = all_available_videos - selected_video_ids
            
            # 如果有未使用的视频，为其中一些阶段强制指定这些视频
            if unused_videos:
                # 首先收集每个阶段中每个视频的最高相似度
                video_similarity = {}
                for stage_id, matches in match_results.items():
                    # 跳过品牌/片尾段落，避免替换关键内容
                    if stage_id in brand_segments:
                        continue
                        
                    for match in matches:
                        video_id = match['video_id']
                        if video_id in unused_videos:
                            key = (stage_id, video_id)
                            if key not in video_similarity or match['similarity'] > video_similarity[key][0]:
                                video_similarity[key] = (match['similarity'], match)
                
                # 按相似度对未使用视频排序
                best_unused = []
                for (stage_id, video_id), (similarity, match) in video_similarity.items():
                    best_unused.append((stage_id, video_id, similarity, match))
                
                # 按相似度降序排序
                best_unused.sort(key=lambda x: x[2], reverse=True)
                
                # 强制替换已选择的阶段，确保使用未使用的视频
                videos_to_add = min(len(unused_videos), min_video_sources - len(selected_video_ids))
                for i in range(min(videos_to_add, len(best_unused))):
                    stage_id, video_id, similarity, match = best_unused[i]
                    
                    # 替换该阶段的选择
                    optimized_results[stage_id] = [match]
                    selected_video_ids.add(video_id)
                    logger.info(f"强制替换阶段 {stage_id} 的选择为视频 {video_id}，相似度: {similarity}%")
        
        if len(selected_video_ids) < min_video_sources:
            logger.warning(f"最终只能使用 {len(selected_video_ids)} 个不同的视频源，少于要求的 {min_video_sources} 个")
        else:
            logger.info(f"匹配结果优化完成，使用了 {len(selected_video_ids)} 个不同的视频源: {', '.join(sorted(selected_video_ids))}")
        
        # 保存有关视频多样性的详细信息
        video_usage = {}
        for stage_id, matches in optimized_results.items():
            if matches:
                video_id = matches[0]['video_id']
                if video_id not in video_usage:
                    video_usage[video_id] = []
                # 确保添加的stage_id是字符串类型
                video_usage[video_id].append(str(stage_id))
        
        logger.info("视频使用情况:")
        for video_id, stages in video_usage.items():
            # 因为stages中的所有元素已经是字符串，这里不需要再转换
            logger.info(f"  视频 {video_id} 用于阶段: {', '.join(stages)}")
        
        return optimized_results
        
    except Exception as e:
        logger.exception(f"优化匹配结果时出错: {str(e)}")
        return match_results  # 出错时返回原始匹配结果

async def test_match_video_segments(demo_segments: List[Dict[str, Any]], candidate_subtitles: Dict[str, Any], similarity_threshold: int = 40):
    """
    测试视频片段匹配功能
    """
    logger.info(f"开始测试视频片段匹配，相似度阈值: {similarity_threshold}")
    
    # 初始化服务
    magic_video_service = MagicVideoService()
    
    try:
        # 匹配视频片段
        match_results = await magic_video_service.match_video_segments(
            demo_segments, candidate_subtitles, similarity_threshold
        )
        
        if not match_results:
            logger.error("视频片段匹配失败，未返回匹配结果")
            return None
        
        logger.info(f"视频片段匹配成功，共匹配 {len(match_results)} 个阶段")
        
        # 记录匹配结果以供调试
        for stage_id, matches in match_results.items():
            logger.info(f"阶段 {stage_id} 找到 {len(matches)} 个匹配片段")
            if matches:
                best_match = matches[0]
                logger.info(f"  最佳匹配: 视频={best_match['video_id']}, 相似度={best_match['similarity']:.2f}, 时间={best_match['start_time']:.2f}-{best_match['end_time']:.2f}")
        
        # 优化匹配结果以增加多样性，强制使用至少3个不同的视频源
        optimized_results = await optimize_match_results(demo_segments, match_results, min_video_sources=3)
        
        # 保存优化后的匹配结果
        matches_json_path = os.path.join('data', 'processed', 'analysis', 'results', f"optimized_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(matches_json_path, 'w', encoding='utf-8') as f:
            json.dump(optimized_results, f, ensure_ascii=False, indent=2)
        
        return optimized_results
    except Exception as e:
        logger.exception(f"测试视频片段匹配时出错: {str(e)}")
        return None

async def test_compose_magic_video(demo_video_path: str, match_results: Dict[str, List[Dict[str, Any]]], output_filename: str, use_demo_audio: bool = True):
    """
    测试魔法视频合成功能
    """
    logger.info(f"开始测试魔法视频合成，使用Demo音频: {use_demo_audio}")
    
    # 初始化服务
    magic_video_service = MagicVideoService()
    
    try:
        # 计算视频使用情况
        video_usage = {}
        for stage_id, matches in match_results.items():
            if matches:
                video_id = matches[0]['video_id']
                if video_id not in video_usage:
                    video_usage[video_id] = []
                video_usage[video_id].append(stage_id)
        
        # 修复视频使用情况输出格式的错误 - 确保所有的stage_id都是字符串类型
        for video_id, stages in video_usage.items():
            video_usage[video_id] = [str(stage) for stage in stages]
        
        # 记录使用情况
        logger.info("合成视频使用的视频源情况:")
        for video_id, stages in video_usage.items():
            logger.info(f"  视频 {video_id} 用于阶段: {', '.join(stages)}")
        
        # 确保音频处理的安全性
        # 1. 预处理Demo视频音频，检查其有效性
        if use_demo_audio:
            # 检查Demo视频的音频是否可提取
            processor = VideoProcessor()
            demo_audio_path = processor.extract_audio(demo_video_path)
            if not demo_audio_path or not os.path.exists(demo_audio_path):
                logger.warning(f"无法从Demo视频提取音频，将回退到使用候选视频音频")
                use_demo_audio = False
                
        # 合成魔法视频
        output_path = await magic_video_service.compose_magic_video(
            demo_video_path, match_results, output_filename, use_demo_audio
        )
        
        if not output_path:
            logger.error("魔法视频合成失败，未返回输出路径")
            return None
        
        logger.info(f"魔法视频合成成功，输出路径: {output_path}")
        return output_path
    except Exception as e:
        logger.exception(f"测试魔法视频合成时出错: {str(e)}")
        return None

async def run_full_test():
    """
    运行完整的视频生成流水线测试
    这个函数测试从视频分析到最终合成的整个流程
    """
    try:
        # 测试参数设置
        demo_video_path = os.path.join(project_root, 'data', 'input', '通用-保护薄弱期-HMO&自御力-启赋-CTA4修改.mp4')  # 使用绝对路径
        
        # 本地视频库路径
        local_video_dir = os.path.join(project_root, 'data', 'test_samples', 'input', 'video')
        local_video_files = [f for f in os.listdir(local_video_dir) if f.endswith(('.mp4', '.mov', '.avi', '.MOV'))]
        candidate_video_paths = [os.path.join(local_video_dir, file) for file in local_video_files]
        
        # 处理前确认文件存在
        if not os.path.exists(demo_video_path):
            logger.error(f"Demo视频文件不存在: {demo_video_path}")
            return
        
        logger.info(f"开始完整视频生成流水线测试，Demo视频: {demo_video_path}")
        logger.info(f"候选视频数量: {len(candidate_video_paths)}")
        
        # 步骤1：处理Demo视频
        logger.info("=== 步骤1：处理Demo视频 ===")
        demo_result = await test_process_demo_video(demo_video_path)
        if not demo_result:
            logger.error("Demo视频处理失败，终止测试")
            return
        
        # 步骤2：处理候选视频
        logger.info("=== 步骤2：处理候选视频 ===")
        candidate_subtitles = await test_process_candidate_videos(candidate_video_paths)
        if not candidate_subtitles:
            logger.error("候选视频处理失败，终止测试")
            return
        
        # 步骤3：匹配视频片段 (降低相似度阈值以增加匹配范围)
        logger.info("=== 步骤3：匹配视频片段 ===")
        match_results = await test_match_video_segments(
            demo_result['stages'], candidate_subtitles, similarity_threshold=30  # 降低相似度阈值，确保找到足够匹配
        )
        if not match_results:
            logger.error("视频片段匹配失败，终止测试")
            return
        
        # 步骤4：合成魔法视频
        logger.info("=== 步骤4：合成魔法视频 ===")
        output_filename = f"pipeline_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = await test_compose_magic_video(
            demo_video_path, match_results, output_filename, use_demo_audio=True
        )
        if not output_path:
            logger.error("魔法视频合成失败")
            return
        
        logger.info(f"完整视频生成流水线测试成功，输出视频: {output_path}")
        
    except Exception as e:
        logger.exception(f"视频生成流水线测试出错: {str(e)}")

if __name__ == "__main__":
    # 运行异步测试函数
    asyncio.run(run_full_test()) 