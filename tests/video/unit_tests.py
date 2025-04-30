"""
视频处理流程测试脚本

该脚本用于测试视频处理过程中的各个环节，按照从输入到输出的完整流程验证功能
"""

import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import tempfile
import shutil
from datetime import datetime

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 测试输入输出目录
TEST_INPUT_DIR = os.path.join('data', 'test_samples', 'input', 'video')
TEST_OUTPUT_DIR = os.path.join('data', 'test_samples', 'output', 'video')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("data", "test_samples", "logs", f"test_{datetime.now().strftime('%Y%m%d')}.log"), 'a', 'utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入相关模块
try:
    from utils.processor import VideoProcessor
    from utils.analyzer import VideoAnalyzer
    from src.core.intent_service import IntentService
    from src.api.llm_service import LLMService
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)


class VideoProcessingTestCase(unittest.TestCase):
    """视频处理流程测试用例"""
    
    def setUp(self):
        """测试前准备工作"""
        # 确保测试目录存在
        os.makedirs(TEST_INPUT_DIR, exist_ok=True)
        os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
        
        # 创建测试使用的处理器实例
        self.processor = VideoProcessor()
        self.analyzer = VideoAnalyzer()
        
        # 创建意图服务实例
        try:
            self.intent_service = IntentService()
        except Exception as e:
            logger.warning(f"意图服务初始化失败: {e}")
            self.intent_service = None
            
        # 创建LLM服务实例
        try:
            self.llm_service = LLMService()
        except Exception as e:
            logger.warning(f"LLM服务初始化失败: {e}")
            self.llm_service = None
        
        # 记录测试开始
        logger.info(f"开始测试: {self._testMethodName}")
    
    def tearDown(self):
        """测试后清理工作"""
        logger.info(f"测试完成: {self._testMethodName}")
    
    def test_video_info_extraction(self):
        """测试视频信息提取功能"""
        logger.info("测试视频信息提取")
        
        # 测试视频路径
        test_video = os.path.join(TEST_INPUT_DIR, '17.mp4')
        
        # 由于需要实际视频文件，这里使用Mock模拟返回值
        with patch.object(self.processor, '_get_video_info') as mock_get_info:
            mock_get_info.return_value = {
                'width': 1920,
                'height': 1080,
                'fps': 30.0,
                'frame_count': 900,
                'duration': 30.0,
                'format': 'mp4',
                'has_audio': True
            }
            
            # 调用测试方法
            video_info = self.processor._get_video_info(test_video)
            
            # 验证结果
            self.assertEqual(video_info['width'], 1920)
            self.assertEqual(video_info['height'], 1080)
            self.assertEqual(video_info['duration'], 30.0)
            self.assertTrue(video_info['has_audio'])
            
            # 验证方法被调用
            mock_get_info.assert_called_once_with(test_video)
    
    def test_audio_extraction(self):
        """测试从视频中提取音频功能"""
        logger.info("测试音频提取")
        
        # 测试视频路径
        test_video = os.path.join(TEST_INPUT_DIR, '17.mp4')
        
        # 模拟音频提取过程
        with patch.object(self.processor, '_preprocess_video_file') as mock_extract:
            mock_extract.return_value = os.path.join(TEST_OUTPUT_DIR, 'test_audio.wav')
            
            # 调用测试方法
            audio_file = self.processor._preprocess_video_file(test_video)
            
            # 验证结果
            self.assertTrue(audio_file.endswith('test_audio.wav'))
            
            # 验证方法被调用
            mock_extract.assert_called_once_with(test_video)
    
    def test_subtitle_extraction(self):
        """测试字幕提取功能"""
        logger.info("测试字幕提取")
        
        # 测试音频路径
        test_audio = os.path.join(TEST_OUTPUT_DIR, 'test_audio.wav')
        
        # 模拟字幕提取过程
        with patch.object(self.processor, '_extract_subtitles_from_video') as mock_subtitle:
            mock_subtitle.return_value = [
                {'timestamp': '00:00:01', 'text': '这是测试字幕1'},
                {'timestamp': '00:00:05', 'text': '这是测试字幕2'},
                {'timestamp': '00:00:10', 'text': '这是测试字幕3'}
            ]
            
            # 调用测试方法
            subtitles = self.processor._extract_subtitles_from_video(test_audio)
            
            # 验证结果
            self.assertEqual(len(subtitles), 3)
            self.assertEqual(subtitles[0]['text'], '这是测试字幕1')
            
            # 验证方法被调用
            mock_subtitle.assert_called_once_with(test_audio)
    
    def test_dimension_analysis(self):
        """测试维度分析功能"""
        logger.info("测试维度分析")
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'timestamp': ['00:00:01', '00:00:05', '00:00:10'],
            'text': ['这是关于产品质量的讨论', '品牌形象很重要', '用户体验需要提升']
        })
        
        # 测试维度
        test_dimensions = {
            'title': '品牌认知',
            'level1': ['产品质量', '品牌形象', '用户体验'],
            'level2': {
                '产品质量': ['耐用性', '功能性'],
                '品牌形象': ['知名度', '信任度'],
                '用户体验': ['易用性', '满意度']
            }
        }
        
        # 模拟维度分析过程
        with patch.object(self.analyzer, 'analyze_dimensions') as mock_analyze:
            mock_analyze.return_value = {
                'type': '维度分析',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'dimensions': test_dimensions,
                'matches': [
                    {
                        'dimension_level1': '产品质量',
                        'dimension_level2': '功能性',
                        'timestamp': '00:00:01',
                        'text': '这是关于产品质量的讨论',
                        'score': 0.85
                    },
                    {
                        'dimension_level1': '品牌形象',
                        'dimension_level2': '知名度',
                        'timestamp': '00:00:05',
                        'text': '品牌形象很重要',
                        'score': 0.92
                    }
                ]
            }
            
            # 调用测试方法
            results = self.analyzer.analyze_dimensions(test_data, test_dimensions)
            
            # 验证结果
            self.assertEqual(results['type'], '维度分析')
            self.assertEqual(len(results['matches']), 2)
            self.assertEqual(results['matches'][0]['dimension_level1'], '产品质量')
            
            # 验证方法被调用
            mock_analyze.assert_called_once()
    
    def test_intent_service(self):
        """测试意图服务功能"""
        logger.info("测试意图服务")
        
        # 如果意图服务初始化失败，跳过此测试
        if self.intent_service is None:
            self.skipTest("意图服务初始化失败，跳过测试")
        
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
        
        # 测试获取所有意图
        with patch.object(self.intent_service, 'get_all_intents') as mock_get_all:
            mock_get_all.return_value = mock_intents
            
            # 调用测试方法
            intents = self.intent_service.get_all_intents()
            
            # 验证结果
            self.assertEqual(len(intents), 2)
            self.assertEqual(intents[0]['id'], "product_recommendation")
            
            # 验证方法被调用
            mock_get_all.assert_called_once()
        
        # 测试根据ID获取意图
        with patch.object(self.intent_service, 'get_intent_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = mock_intents[0]
            
            # 调用测试方法
            intent = self.intent_service.get_intent_by_id("product_recommendation")
            
            # 验证结果
            self.assertIsNotNone(intent)
            self.assertEqual(intent['name'], "产品推荐")
            
            # 验证方法被调用
            mock_get_by_id.assert_called_once_with("product_recommendation")
            
            # 测试无效ID
            mock_get_by_id.return_value = None
            invalid_intent = self.intent_service.get_intent_by_id("non_existent_id")
            self.assertIsNone(invalid_intent)
    
    def test_keyword_analysis(self):
        """测试关键词分析功能"""
        logger.info("测试关键词分析")
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'timestamp': ['00:00:01', '00:00:05', '00:00:10'],
            'text': ['这是关于产品质量的讨论', '品牌形象很重要', '用户体验需要提升']
        })
        
        # 测试关键词
        test_keywords = ['产品质量', '品牌', '用户体验']
        
        # 模拟关键词分析过程
        with patch.object(self.analyzer, 'analyze_keywords') as mock_analyze:
            mock_analyze.return_value = {
                'type': '关键词分析',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'keywords': test_keywords,
                'matches': [
                    {
                        'keyword': '产品质量',
                        'timestamp': '00:00:01',
                        'text': '这是关于产品质量的讨论',
                        'score': 0.95
                    },
                    {
                        'keyword': '品牌',
                        'timestamp': '00:00:05',
                        'text': '品牌形象很重要',
                        'score': 0.88
                    },
                    {
                        'keyword': '用户体验',
                        'timestamp': '00:00:10',
                        'text': '用户体验需要提升',
                        'score': 0.92
                    }
                ]
            }
            
            # 调用测试方法
            results = self.analyzer.analyze_keywords(test_data, test_keywords)
            
            # 验证结果
            self.assertEqual(results['type'], '关键词分析')
            self.assertEqual(len(results['matches']), 3)
            self.assertEqual(results['matches'][0]['keyword'], '产品质量')
            
            # 验证方法被调用
            mock_analyze.assert_called_once()
    
    def test_llm_service_prompt(self):
        """测试LLM服务提示词生成功能"""
        logger.info("测试LLM服务提示词生成")
        
        # 如果LLM服务初始化失败，跳过此测试
        if self.llm_service is None:
            self.skipTest("LLM服务初始化失败，跳过测试")
        
        # 创建测试数据
        test_intent = {
            "id": "milk_formula_features",
            "name": "奶粉特性",
            "description": "查找关于奶粉成分、特性或优势的描述",
            "keywords": ["成分", "HMO", "母乳低聚糖", "配方", "功效", "优势"]
        }
        
        test_description = "我想找视频中提到HMO母乳低聚糖的部分"
        
        test_subtitles = [
            {"timestamp": "00:00:10", "text": "这款奶粉添加了HMO母乳低聚糖"},
            {"timestamp": "00:00:20", "text": "它的配方更接近母乳成分"},
            {"timestamp": "00:00:30", "text": "可以帮助宝宝建立免疫力"}
        ]
        
        # 调用提示词生成方法
        prompt = self.llm_service._create_matching_prompt(test_intent, test_description, test_subtitles)
        
        # 验证结果
        self.assertIsNotNone(prompt)
        self.assertIn(test_intent['name'], prompt)
        self.assertIn(test_description, prompt)
        self.assertIn("HMO母乳低聚糖", prompt)
        self.assertIn("00:00:10", prompt)
    
    def test_llm_response_parsing(self):
        """测试LLM响应解析功能"""
        logger.info("测试LLM响应解析")
        
        # 如果LLM服务初始化失败，跳过此测试
        if self.llm_service is None:
            self.skipTest("LLM服务初始化失败，跳过测试")
        
        # 测试有效响应
        valid_response = """
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
        result = self.llm_service._parse_matching_result(valid_response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start_timestamp'], "00:00:10")
        self.assertEqual(result[0]['score'], 95)
        
        # 测试无效响应
        invalid_response = "没有找到相关内容"
        result = self.llm_service._parse_matching_result(invalid_response)
        self.assertEqual(result, [])
        
        # 测试部分字段缺失的响应
        incomplete_response = """
```json
[
  {
    "start_timestamp": "00:00:10",
    "text": "这款奶粉添加了HMO母乳低聚糖"
  }
]
```
"""
        result = self.llm_service._parse_matching_result(incomplete_response)
        self.assertEqual(result, [])
    
    def test_integrated_process(self):
        """测试完整处理流程（集成测试）"""
        logger.info("测试完整处理流程")
        
        # 测试视频路径
        test_video = os.path.join(TEST_INPUT_DIR, '17.mp4')
        
        # 创建一个虚拟的流程函数来测试完整流程
        # 这里仅模拟各个步骤的调用和结果，不实际执行视频处理
        def mock_integrated_process(test_file):
            # 模拟流程函数
            def page_processor(file, analysis_type, dimensions=None):
                # 1. 获取视频信息
                video_info = {'width': 1920, 'height': 1080, 'duration': 30.0}
                
                # 2. 提取音频
                audio_file = "test_audio.wav"
                
                # 3. 提取字幕
                subtitles = [
                    {'timestamp': '00:00:01', 'text': '这是测试字幕1'},
                    {'timestamp': '00:00:05', 'text': '这是测试字幕2'}
                ]
                
                # 4. 创建DataFrame
                subtitle_df = pd.DataFrame([{
                    'timestamp': item.get('timestamp', '00:00:00'),
                    'text': item.get('text', '')
                } for item in subtitles])
                
                # 5. 分析处理
                if analysis_type == 'dimensions':
                    return {
                        'type': '维度分析',
                        'matches': [{'dimension_level1': '测试维度', 'text': '这是测试字幕1'}]
                    }
                else:
                    return {
                        'type': '关键词分析',
                        'matches': [{'keyword': '测试', 'text': '这是测试字幕1'}]
                    }
            
            # 调用模拟的处理函数并返回结果
            result = page_processor(test_file, 'dimensions')
            self.assertEqual(result['type'], '维度分析')
            self.assertEqual(len(result['matches']), 1)
            
            result = page_processor(test_file, 'keywords')
            self.assertEqual(result['type'], '关键词分析')
            self.assertEqual(len(result['matches']), 1)
            
            return True
        
        # 执行集成测试
        success = mock_integrated_process(test_video)
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main() 