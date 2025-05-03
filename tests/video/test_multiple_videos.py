#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试多种匹配策略并行生成不同风格的视频
"""

import os
import sys
import logging
import asyncio
import time
from datetime import datetime

# 确保可以导入项目模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.magic_video_service import MagicVideoService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_multiple_videos')

async def test_multiple_videos():
    """测试使用多种策略生成视频"""
    try:
        logger.info("开始测试多种策略视频生成")
        
        # 初始化视频服务，设置并发任务数
        service = MagicVideoService(max_concurrent_tasks=6)
        
        # 定义测试视频路径
        demo_video_path = os.path.join('data', 'input', '通用-保护薄弱期-HMO&自御力-启赋-CTA4修改.mp4')
        if not os.path.exists(demo_video_path):
            logger.error(f"示范视频不存在: {demo_video_path}")
            return

        # 处理示范视频
        logger.info(f"处理示范视频: {demo_video_path}")
        demo_result = await service.process_demo_video(demo_video_path)
        if 'error' in demo_result and demo_result['error']:
            logger.error(f"处理示范视频失败: {demo_result['error']}")
            return
        
        demo_segments = demo_result['stages']
        logger.info(f"示范视频分段完成，共 {len(demo_segments)} 个段落")
        
        # 处理候选视频
        # 查找 data/input 目录下的所有视频文件
        input_dir = os.path.join('data', 'input')
        if not os.path.exists(input_dir):
            logger.error(f"输入目录不存在: {input_dir}")
            return
        
        # 获取输入视频文件列表
        video_files = []
        for filename in os.listdir(input_dir):
            filepath = os.path.join(input_dir, filename)
            if os.path.isfile(filepath) and filename.lower().endswith(('.mp4', '.mov', '.avi')):
                # 排除Demo视频
                if '通用-保护薄弱期-HMO&自御力-启赋-CTA4修改.mp4' not in filename:
                    video_files.append(filepath)
        
        if not video_files:
            logger.error("未找到候选视频文件")
            return
        
        logger.info(f"找到 {len(video_files)} 个候选视频")
        
        # 处理候选视频
        logger.info("处理候选视频中，提取字幕和视觉标签...")
        candidate_subtitles = await service.process_candidate_videos(video_files)
        logger.info(f"完成 {len(candidate_subtitles)} 个候选视频的处理")
        
        # 定义不同的匹配策略
        match_strategies = [
            {
                "name": "语言匹配优先",
                "similarity_threshold": 35,  # 较低的阈值允许更多匹配
                "brand_boost": 15,  # 中等程度关注品牌
                "ending_boost": 10,  # 中等程度关注片尾
                "visual_weight": 0   # 不使用视觉匹配
            },
            {
                "name": "视觉匹配优先",
                "similarity_threshold": 30,  # 更低的阈值
                "brand_boost": 10,  # 较低的品牌关注
                "ending_boost": 8,   # 较低的片尾关注
                "visual_weight": 25  # 高度关注视觉内容
            },
            {
                "name": "品牌优先",
                "similarity_threshold": 35,
                "brand_boost": 25,   # 高度关注品牌
                "ending_boost": 15,  # 高度关注片尾
                "visual_weight": 15  # 中等程度关注视觉
            },
            {
                "name": "意图分析优化",
                "similarity_threshold": 33,  # 较低阈值
                "brand_boost": 18,   # 较高品牌关注
                "ending_boost": 12,  # 中等片尾关注
                "visual_weight": 20  # 较高视觉权重，基于段落意图匹配
            },
            {
                "name": "宝宝场景优先",
                "similarity_threshold": 32,  # 较低阈值
                "brand_boost": 15,   # 中等品牌关注
                "ending_boost": 10,  # 中等片尾关注
                "visual_weight": 28  # 极高视觉关注（偏向婴儿场景）
            },
            {
                "name": "连贯性优先",
                "similarity_threshold": 35,  # 中等阈值
                "brand_boost": 15,   # 中等品牌关注
                "ending_boost": 10,  # 中等片尾关注
                "visual_weight": 22  # 高视觉权重（偏向场景连贯）
            }
        ]
        
        # 生成输出文件名基础
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_basename = f"magic_video_{timestamp}"
        
        # 并行生成多个视频
        logger.info(f"开始并行生成 {len(match_strategies)} 个不同风格的视频...")
        start_time = time.time()
        
        results = await service.generate_multiple_videos(
            demo_video_path,
            candidate_subtitles,
            demo_segments,
            output_basename,
            match_strategies
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 输出结果
        successful_videos = [r for r in results if r['status'] == 'success']
        logger.info(f"视频生成完成，总耗时: {total_time:.2f}秒，成功: {len(successful_videos)}/{len(match_strategies)}")
        
        for result in successful_videos:
            strategy = result['strategy']
            output_path = result['output_path']
            logger.info(f"策略 '{strategy['name']}' 生成的视频: {output_path}")
            
        return results
    
    except Exception as e:
        logger.exception(f"测试多种策略视频生成时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_multiple_videos()) 