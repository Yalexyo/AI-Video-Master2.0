#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试UI组件功能
"""

import os
import sys
import unittest
import streamlit as st
from unittest.mock import patch, MagicMock

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.ui_elements.intent_selector import render_intent_selector, render_description_input

class TestUIComponents(unittest.TestCase):
    """测试UI组件功能"""
    
    @patch('src.core.intent_service.IntentService.get_all_intents')
    @patch('src.core.intent_service.IntentService.get_intent_by_id')
    @patch('streamlit.radio')
    @patch('streamlit.success')
    def test_intent_selector_with_intents(self, mock_success, mock_radio, mock_get_intent, mock_get_all):
        """测试有意图数据时的意图选择器"""
        # 模拟意图数据
        mock_intents = [
            {
                "id": "product_recommendation",
                "name": "产品推荐",
                "description": "推荐特定产品或品牌",
                "keywords": ["推荐", "建议", "选择", "品牌"]
            },
            {
                "id": "milk_formula_features",
                "name": "奶粉特性",
                "description": "查找关于奶粉成分、特性或优势的描述",
                "keywords": ["成分", "HMO", "母乳低聚糖", "配方", "功效", "优势"]
            }
        ]
        
        # 模拟意图服务
        mock_get_all.return_value = mock_intents
        mock_get_intent.return_value = mock_intents[0]
        
        # 模拟streamlit交互
        mock_radio.return_value = "product_recommendation"
        
        # 调用测试功能
        selected_intent = render_intent_selector()
        
        # 验证结果
        self.assertIsNotNone(selected_intent)
        self.assertEqual(selected_intent["id"], "product_recommendation")
        
        # 验证调用
        mock_get_all.assert_called_once()
        mock_get_intent.assert_called_once_with("product_recommendation")
        mock_success.assert_called_once()
    
    @patch('src.core.intent_service.IntentService.get_all_intents')
    @patch('streamlit.warning')
    def test_intent_selector_no_intents(self, mock_warning, mock_get_all):
        """测试无意图数据时的意图选择器"""
        # 模拟空意图列表
        mock_get_all.return_value = []
        
        # 调用测试功能
        selected_intent = render_intent_selector()
        
        # 验证结果
        self.assertIsNone(selected_intent)
        mock_warning.assert_called_once()
    
    @patch('src.core.intent_service.IntentService.get_all_intents')
    @patch('src.core.intent_service.IntentService.get_intent_by_id')
    @patch('streamlit.radio')
    @patch('streamlit.info')
    def test_intent_selector_no_selection(self, mock_info, mock_radio, mock_get_intent, mock_get_all):
        """测试用户未选择意图时的情况"""
        # 模拟意图数据
        mock_intents = [
            {
                "id": "product_recommendation",
                "name": "产品推荐",
                "description": "推荐特定产品或品牌",
                "keywords": ["推荐", "建议", "选择", "品牌"]
            }
        ]
        
        # 模拟意图服务
        mock_get_all.return_value = mock_intents
        mock_get_intent.return_value = None  # 未找到对应意图
        
        # 模拟streamlit交互
        mock_radio.return_value = None  # 用户未选择
        
        # 调用测试功能
        selected_intent = render_intent_selector()
        
        # 验证结果
        self.assertIsNone(selected_intent)
        mock_info.assert_called_once()
    
    @patch('streamlit.text_area')
    def test_description_input(self, mock_text_area):
        """测试详细描述输入框"""
        # 模拟用户输入
        expected_description = "我想找视频中提到HMO母乳低聚糖的部分"
        mock_text_area.return_value = expected_description
        
        # 调用测试功能
        user_description = render_description_input()
        
        # 验证结果
        self.assertEqual(user_description, expected_description)
        mock_text_area.assert_called_once()

def main():
    """运行测试的主函数"""
    unittest.main()

if __name__ == "__main__":
    main() 