#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试视频内容意图匹配功能
"""

import os
import sys
import json
import logging
import time
import asyncio
import unittest
import pandas as pd
from unittest.mock import patch, MagicMock

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.core.intent_service import IntentService
from src.core.video_segment_service import VideoSegmentService
from src.api.llm_service import LLMService

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestIntentMatching(unittest.TestCase):
    """测试意图匹配功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建样本字幕数据
        self.sample_subtitles = pd.DataFrame([
            {"timestamp": "00:00:10", "text": "这款奶粉添加了HMO母乳低聚糖"},
            {"timestamp": "00:00:20", "text": "它的配方更接近母乳成分"},
            {"timestamp": "00:00:30", "text": "可以帮助宝宝建立免疫力"},
            {"timestamp": "00:00:40", "text": "保障肠道健康非常重要"},
            {"timestamp": "00:00:50", "text": "你可以选择启赋这个品牌"},
            {"timestamp": "00:01:00", "text": "它已经有七年的市场经验"},
            {"timestamp": "00:01:10", "text": "价格虽然高一些但是品质有保障"},
            {"timestamp": "00:01:20", "text": "很多妈妈都给宝宝选择这款奶粉"}
        ])
        
        # 示例意图
        self.sample_intent = {
            "id": "milk_formula_features",
            "name": "奶粉特性",
            "description": "查找关于奶粉成分、特性或优势的描述",
            "keywords": ["成分", "HMO", "母乳低聚糖", "配方", "功效", "优势"]
        }
        
    def test_intent_service_load(self):
        """测试意图服务加载"""
        intent_service = IntentService()
        intents = intent_service.get_all_intents()
        
        # 验证是否成功加载意图
        self.assertIsNotNone(intents)
        self.assertTrue(len(intents) > 0)
        
        # 验证意图的数据结构
        for intent in intents:
            self.assertIn('id', intent)
            self.assertIn('name', intent)
            self.assertIn('description', intent)
            self.assertIn('keywords', intent)
    
    def test_intent_retrieval(self):
        """测试根据ID获取意图"""
        intent_service = IntentService()
        intents = intent_service.get_all_intents()
        
        if intents:
            first_intent_id = intents[0]['id']
            retrieved_intent = intent_service.get_intent_by_id(first_intent_id)
            
            # 验证能否正确检索到意图
            self.assertIsNotNone(retrieved_intent)
            self.assertEqual(retrieved_intent['id'], first_intent_id)
            
            # 测试无效ID
            invalid_intent = intent_service.get_intent_by_id("non_existent_id")
            self.assertIsNone(invalid_intent)
    
    @patch('utils.analyzer.VideoAnalyzer.analyze_keywords')
    async def test_keyword_matching(self, mock_analyze_keywords):
        """测试关键词匹配"""
        # 模拟关键词匹配结果
        mock_analyze_keywords.return_value = {
            "matches": [
                {"timestamp": "00:00:10", "text": "这款奶粉添加了HMO母乳低聚糖", 
                 "keyword": "母乳低聚糖", "score": 0.95},
                {"timestamp": "00:00:20", "text": "它的配方更接近母乳成分", 
                 "keyword": "配方", "score": 0.8}
            ]
        }
        
        # 创建服务
        segment_service = VideoSegmentService()
        
        # 执行测试
        results = await segment_service.get_video_segments(
            video_id="test_video",
            subtitle_df=self.sample_subtitles,
            selected_intent=self.sample_intent,
            user_description=""  # 空描述使用关键词匹配
        )
        
        # 验证结果
        self.assertIn("matches", results)
        self.assertEqual(len(results["matches"]), 2)
        self.assertEqual(results["analysis_method"], "关键词匹配")
        
        # 验证调用参数
        mock_analyze_keywords.assert_called_once()
        args, kwargs = mock_analyze_keywords.call_args
        self.assertEqual(kwargs["threshold"], 0.6)
        self.assertEqual(args[1], self.sample_intent["keywords"])
    
    @patch('src.api.llm_service.LLMService.refine_intent_matching')
    async def test_llm_matching(self, mock_refine_matching):
        """测试LLM精确匹配"""
        # 模拟LLM匹配结果
        mock_llm_results = [
            {
                "start_timestamp": "00:00:10",
                "end_timestamp": "00:00:20",
                "context": "这款奶粉添加了HMO母乳低聚糖。它的配方更接近母乳成分。",
                "core_text": "这款奶粉添加了HMO母乳低聚糖",
                "score": 90,
                "reason": "直接提到了HMO成分，与用户查询高度相关"
            }
        ]
        mock_refine_matching.return_value = mock_llm_results
        
        # 创建服务
        segment_service = VideoSegmentService()
        
        # 执行测试
        results = await segment_service.get_video_segments(
            video_id="test_video",
            subtitle_df=self.sample_subtitles,
            selected_intent=self.sample_intent,
            user_description="我想找视频中提到HMO母乳低聚糖的部分"  # 有详细描述触发LLM匹配
        )
        
        # 验证结果
        self.assertIn("matches", results)
        self.assertEqual(len(results["matches"]), 1)
        self.assertEqual(results["analysis_method"], "LLM精确匹配")
        
        # 验证LLM服务调用
        mock_refine_matching.assert_called_once()
        
    @patch('src.api.llm_service.LLMService.refine_intent_matching')
    @patch('utils.analyzer.VideoAnalyzer.analyze_keywords')
    async def test_fallback_to_keyword(self, mock_analyze_keywords, mock_refine_matching):
        """测试LLM匹配失败时回退到关键词匹配"""
        # 模拟LLM匹配失败
        mock_refine_matching.return_value = []
        
        # 模拟关键词匹配结果
        mock_analyze_keywords.return_value = {
            "matches": [
                {"timestamp": "00:00:50", "text": "你可以选择启赋这个品牌", 
                 "keyword": "品牌", "score": 0.7}
            ]
        }
        
        # 创建服务
        segment_service = VideoSegmentService()
        
        # 执行测试
        results = await segment_service.get_video_segments(
            video_id="test_video",
            subtitle_df=self.sample_subtitles,
            selected_intent=self.sample_intent,
            user_description="我想知道推荐哪个品牌"  # 有详细描述但LLM匹配失败
        )
        
        # 验证结果
        self.assertIn("matches", results)
        self.assertEqual(len(results["matches"]), 1)
        self.assertEqual(results["analysis_method"], "关键词匹配")
        
        # 验证两个方法都被调用
        mock_refine_matching.assert_called_once()
        mock_analyze_keywords.assert_called_once()

async def main():
    """运行测试的主函数"""
    # 手动创建测试实例
    test = TestIntentMatching()
    test.setUp()
    
    # 测试意图服务功能
    test.test_intent_service_load()
    test.test_intent_retrieval()
    
    # 测试匹配功能
    await test.test_keyword_matching()
    await test.test_llm_matching()
    await test.test_fallback_to_keyword()
    
    print("所有测试完成")

if __name__ == "__main__":
    asyncio.run(main()) 