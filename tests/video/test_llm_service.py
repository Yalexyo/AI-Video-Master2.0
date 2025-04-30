#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试大语言模型服务功能
"""

import os
import sys
import json
import logging
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.api.llm_service import LLMService

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestLLMService(unittest.TestCase):
    """测试LLM服务功能"""
    
    def setUp(self):
        """测试前准备"""
        # 创建LLM服务实例
        self.llm_service = LLMService()
        
        # 创建示例数据
        self.sample_intent = {
            "id": "milk_formula_features",
            "name": "奶粉特性",
            "description": "查找关于奶粉成分、特性或优势的描述",
            "keywords": ["成分", "HMO", "母乳低聚糖", "配方", "功效", "优势"]
        }
        
        self.user_description = "我想找视频中提到HMO母乳低聚糖的部分"
        
        self.sample_subtitles = [
            {"timestamp": "00:00:10", "text": "这款奶粉添加了HMO母乳低聚糖"},
            {"timestamp": "00:00:20", "text": "它的配方更接近母乳成分"},
            {"timestamp": "00:00:30", "text": "可以帮助宝宝建立免疫力"},
            {"timestamp": "00:00:40", "text": "保障肠道健康非常重要"}
        ]
        
        # 示例LLM响应
        self.sample_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": """
```json
[
  {
    "start_timestamp": "00:00:10",
    "end_timestamp": "00:00:20",
    "context": "这款奶粉添加了HMO母乳低聚糖。它的配方更接近母乳成分。",
    "core_text": "这款奶粉添加了HMO母乳低聚糖",
    "score": 95,
    "reason": "直接提到了HMO成分，与用户查询高度相关"
  }
]
```
"""
                    }
                }
            ]
        }
    
    def test_create_matching_prompt(self):
        """测试创建匹配提示词"""
        prompt = self.llm_service._create_matching_prompt(
            self.sample_intent,
            self.user_description,
            self.sample_subtitles
        )
        
        # 验证提示词包含关键信息
        self.assertIn(self.sample_intent['name'], prompt)
        self.assertIn(self.sample_intent['description'], prompt)
        self.assertIn("HMO", prompt)  # 关键词应包含在提示词中
        self.assertIn(self.user_description, prompt)
        self.assertIn("00:00:10", prompt)  # 字幕时间戳
        self.assertIn("这款奶粉添加了HMO母乳低聚糖", prompt)  # 字幕内容
    
    def test_parse_matching_result(self):
        """测试解析LLM响应"""
        # 正常JSON响应
        llm_response = """
```json
[
  {
    "start_timestamp": "00:00:10",
    "end_timestamp": "00:00:20",
    "context": "这款奶粉添加了HMO母乳低聚糖。它的配方更接近母乳成分。",
    "core_text": "这款奶粉添加了HMO母乳低聚糖",
    "score": 95,
    "reason": "直接提到了HMO成分，与用户查询高度相关"
  }
]
```
"""
        parsed_results = self.llm_service._parse_matching_result(llm_response)
        
        # 验证解析结果
        self.assertEqual(len(parsed_results), 1)
        self.assertEqual(parsed_results[0]['start_timestamp'], "00:00:10")
        self.assertEqual(parsed_results[0]['score'], 95)
        
        # 无JSON格式响应
        invalid_response = "没有找到相关内容"
        empty_results = self.llm_service._parse_matching_result(invalid_response)
        self.assertEqual(empty_results, [])
        
        # 缺少必要字段的响应
        incomplete_response = """
```json
[
  {
    "start_timestamp": "00:00:10",
    "context": "这款奶粉添加了HMO母乳低聚糖"
  }
]
```
"""
        invalid_results = self.llm_service._parse_matching_result(incomplete_response)
        self.assertEqual(invalid_results, [])
    
    @patch('httpx.AsyncClient.post')
    async def test_refine_intent_matching(self, mock_post):
        """测试LLM精确匹配"""
        # 模拟httpx响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_llm_response
        
        # 设置异步模拟
        mock_post.return_value = mock_response
        
        # 调用测试方法
        result = await self.llm_service.refine_intent_matching(
            self.sample_intent,
            self.user_description,
            self.sample_subtitles
        )
        
        # 验证结果
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start_timestamp'], "00:00:10")
        self.assertEqual(result[0]['score'], 95)
        
        # 验证API调用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['model'], self.llm_service.model)
        
    @patch('httpx.AsyncClient.post')
    async def test_api_error_handling(self, mock_post):
        """测试API错误处理"""
        # 模拟API错误
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        # 设置异步模拟
        mock_post.return_value = mock_response
        
        # 调用测试方法
        result = await self.llm_service.refine_intent_matching(
            self.sample_intent,
            self.user_description,
            self.sample_subtitles
        )
        
        # 验证错误处理
        self.assertEqual(result, [])
        
    @patch('httpx.AsyncClient.post')
    async def test_exception_handling(self, mock_post):
        """测试异常处理"""
        # 模拟异常
        mock_post.side_effect = Exception("测试异常")
        
        # 调用测试方法
        result = await self.llm_service.refine_intent_matching(
            self.sample_intent,
            self.user_description,
            self.sample_subtitles
        )
        
        # 验证异常处理
        self.assertEqual(result, [])

async def main():
    """运行测试的主函数"""
    # 手动创建测试实例
    test = TestLLMService()
    test.setUp()
    
    # 执行测试
    test.test_create_matching_prompt()
    test.test_parse_matching_result()
    
    # 异步测试
    await test.test_refine_intent_matching()
    await test.test_api_error_handling()
    await test.test_exception_handling()
    
    print("所有LLM服务测试完成")

if __name__ == "__main__":
    asyncio.run(main()) 