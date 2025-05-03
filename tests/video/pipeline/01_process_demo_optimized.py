#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试优化后的Demo视频处理流程
使用BERT模型进行广告视频语义分段
"""

import os
import json
import asyncio
import logging
import argparse
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 将项目根目录添加到路径
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

# 导入服务
from src.core.magic_video_service import MagicVideoService
from src.core.hot_words_service import HotWordsService
from utils.processor import VideoProcessor

async def main():
    """处理Demo视频，展示热词和语义分段功能"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='处理视频并进行分析')
    parser.add_argument('--video', type=str, 
                        default='data/input/通用-保护薄弱期-HMO&自御力-启赋-CTA4修改.mp4',
                        help='视频文件路径')
    parser.add_argument('--strategy', type=str, default='hybrid',
                        choices=['bert', 'llm', 'hybrid'],
                        help='分析策略 (bert/llm/hybrid)')
    args = parser.parse_args()
    
    # 清除缓存
    processor = VideoProcessor()
    processor.clear_cache(args.video)
    logger.info(f"已清除视频缓存: {args.video}")
    
    # 初始化热词服务
    hot_words_service = HotWordsService()
    vocabulary_id = hot_words_service.get_current_hotword_id()
    logger.info(f"当前热词ID: {vocabulary_id}")
    
    # 初始化语义分析服务（使用指定策略）
    from src.core.semantic_service import SemanticAnalysisService
    semantic_service = SemanticAnalysisService(analysis_strategy=args.strategy)
    
    # 初始化视频服务
    video_service = MagicVideoService()
    
    # 处理视频
    logger.info(f"开始处理Demo视频: {args.video}")
    result = await video_service.process_demo_video(args.video, vocabulary_id)
    
    # 输出分段结果
    logger.info(f"处理完成，结果: {result}")
    
    segments = result.get("stages", [])
    logger.info(f"分段结果 ({len(segments)} 个段落):")
    
    for i, segment in enumerate(segments):
        logger.info(f"段落 {i+1}: {segment.get('phase')} - {segment.get('title')}")
        logger.info(f"  时间: {segment.get('start_time'):.2f}s - {segment.get('end_time'):.2f}s ({segment.get('duration'):.2f}s)")
        logger.info(f"  关键词: {', '.join(segment.get('keywords', []))}")
        logger.info(f"  意图: {segment.get('primary_intent')}")
        logger.info(f"  文本: {segment.get('text')[:100]}...")
        logger.info("---")
    
    # 生成分析报告
    report = {
        "视频标题": Path(args.video).stem,
        "视频时长": segments[-1]["end_time"] if segments else 0,
        "视频类型": "广告视频",
        "品牌关键词": [kw for segment in segments for kw in segment.get("keywords", [])],
        "总体意图": segments[0].get("primary_intent") if segments else "未知"
    }
    
    logger.info("分析报告:")
    for key, value in report.items():
        if isinstance(value, list):
            logger.info(f"  {key}: {', '.join(value[:5])}")
        else:
            logger.info(f"  {key}: {value}")

if __name__ == "__main__":
    asyncio.run(main()) 