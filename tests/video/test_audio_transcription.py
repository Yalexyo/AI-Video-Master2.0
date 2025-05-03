#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试音频转写功能

验证DashScope API异步转写功能是否正常工作
"""

import os
import sys
import logging
import time
from pathlib import Path

# 添加项目根目录到Python路径，确保可以导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入项目模块
from utils.processor import VideoProcessor
# from utils.dashscope_wrapper import dashscope_api
from utils.dashscope_sdk_wrapper import dashscope_sdk
from src.core.hot_words_service import HotWordsService

def test_extract_audio():
    """测试从视频中提取音频功能"""
    try:
        # 初始化处理器
        processor = VideoProcessor()
        
        # 测试视频路径
        video_dir = os.path.join(project_root, 'data', 'test_samples', 'input', 'video')
        video_files = [f for f in os.listdir(video_dir) if f.endswith(('.mp4', '.mov', '.avi', '.MOV'))]
        
        if not video_files:
            logger.error("未找到测试视频文件")
            return False
        
        # 选择第一个视频文件
        video_path = os.path.join(video_dir, video_files[0])
        logger.info(f"使用视频文件: {video_path}")
        
        # 提取音频
        audio_path = processor.extract_audio(video_path)
        
        if audio_path:
            logger.info(f"音频提取成功: {audio_path}")
            return audio_path
        else:
            logger.error("音频提取失败")
            return False
    
    except Exception as e:
        logger.exception(f"测试音频提取时出错: {str(e)}")
        return False

def test_upload_to_oss(audio_path):
    """测试上传音频到OSS"""
    try:
        # 初始化处理器
        processor = VideoProcessor()
        
        # 上传音频文件
        audio_url = processor._upload_to_accessible_url(audio_path)
        
        if audio_url:
            logger.info(f"音频上传成功: {audio_url}")
            return audio_url
        else:
            logger.error("音频上传失败")
            return False
    
    except Exception as e:
        logger.exception(f"测试OSS上传时出错: {str(e)}")
        return False

def test_async_transcription(audio_url):
    """测试异步转写API"""
    try:
        # 获取当前热词ID
        hot_words_service = HotWordsService()
        vocabulary_id = hot_words_service.get_current_hotword_id()
        
        logger.info(f"使用热词ID: {vocabulary_id}")
        
        # 调用API
        result = dashscope_sdk.transcribe_audio(
            file_url=audio_url,
            model="paraformer-v2",
            vocabulary_id=vocabulary_id,
            sample_rate=16000,
            punctuation=True
        )
        
        # 检查响应
        if result.get("status") == "success":
            sentences = result.get("sentences", [])
            logger.info(f"转写成功，共 {len(sentences)} 条字幕")
            
            # 打印前5条字幕
            for i, sentence in enumerate(sentences[:5]):
                text = sentence.get("text", "")
                begin = sentence.get("begin_time", 0) / 1000
                end = sentence.get("end_time", 0) / 1000
                logger.info(f"字幕 {i+1}: [{begin:.2f}-{end:.2f}] {text}")
            
            return True
        else:
            error = result.get("error", "未知错误")
            logger.error(f"转写失败: {error}")
            return False
    
    except Exception as e:
        logger.exception(f"测试异步转写API时出错: {str(e)}")
        return False

def test_extract_subtitles():
    """测试字幕提取功能"""
    try:
        # 初始化处理器
        processor = VideoProcessor()
        hot_words_service = HotWordsService()
        
        # 获取当前热词ID
        vocabulary_id = hot_words_service.get_current_hotword_id()
        
        # 测试视频路径
        video_dir = os.path.join(project_root, 'data', 'test_samples', 'input', 'video')
        video_files = [f for f in os.listdir(video_dir) if f.endswith(('.mp4', '.mov', '.avi', '.MOV'))]
        
        if not video_files:
            logger.error("未找到测试视频文件")
            return False
        
        # 选择第一个视频文件
        video_path = os.path.join(video_dir, video_files[0])
        logger.info(f"使用视频文件: {video_path}")
        
        # 提取字幕
        subtitles = processor._extract_subtitles_from_video(video_path, vocabulary_id)
        
        if subtitles:
            logger.info(f"字幕提取成功，共 {len(subtitles)} 条字幕")
            
            # 打印前5条字幕，确保字幕是正确的字典格式
            try:
                for i, subtitle in enumerate(subtitles[:5]):
                    if isinstance(subtitle, dict) and 'start' in subtitle and 'end' in subtitle and 'text' in subtitle:
                        logger.info(f"字幕 {i+1}: [{subtitle['start']:.2f}-{subtitle['end']:.2f}] {subtitle['text']}")
                    else:
                        logger.warning(f"字幕 {i+1} 格式不正确: {type(subtitle)} - {subtitle}")
            except Exception as e:
                logger.error(f"处理字幕数据时出错: {str(e)}")
            
            return True
        else:
            logger.error("字幕提取失败")
            return False
    
    except Exception as e:
        logger.exception(f"测试字幕提取时出错: {str(e)}")
        return False

def test_sdk_transcription(audio_url):
    """测试SDK方式的转写"""
    try:
        # 获取当前热词ID
        hot_words_service = HotWordsService()
        vocabulary_id = hot_words_service.get_current_hotword_id()
        
        logger.info(f"使用热词ID: {vocabulary_id}")
        
        # 调用SDK转写
        result = dashscope_sdk.transcribe_audio(
            file_url=audio_url,
            model="paraformer-v2",
            vocabulary_id=vocabulary_id,
            sample_rate=16000,
            punctuation=True
        )
        
        # 检查结果
        if result.get("status") == "success":
            sentences = result.get("sentences", [])
            logger.info(f"SDK转写成功，共 {len(sentences)} 条字幕")
            
            # 打印前5条字幕
            for i, sentence in enumerate(sentences[:5]):
                text = sentence.get("text", "")
                begin = sentence.get("begin_time", 0) / 1000
                end = sentence.get("end_time", 0) / 1000
                logger.info(f"字幕 {i+1}: [{begin:.2f}-{end:.2f}] {text}")
            
            return True
        else:
            error = result.get("error", "未知错误")
            logger.error(f"SDK转写失败: {error}")
            return False
    
    except Exception as e:
        logger.exception(f"测试SDK转写时出错: {str(e)}")
        return False

def run_tests():
    """运行所有测试"""
    logger.info("===== 开始测试音频转写功能 =====")
    
    # 清除缓存
    processor = VideoProcessor()
    processor.clear_cache()
    logger.info("已清除所有缓存，确保测试从头开始")
    
    # 测试1: 提取音频
    logger.info("=== 测试1: 提取音频 ===")
    audio_path = test_extract_audio()
    if not audio_path:
        logger.error("音频提取测试失败，终止测试")
        return
    
    # 测试2: 上传到OSS
    logger.info("=== 测试2: 上传到OSS ===")
    audio_url = test_upload_to_oss(audio_path)
    if not audio_url:
        logger.error("OSS上传测试失败，终止测试")
        return
    
    # 测试3: 异步转写API
    logger.info("=== 测试3: 异步转写API ===")
    if not test_async_transcription(audio_url):
        logger.error("异步转写API测试失败")
    
    # 测试4: 完整字幕提取
    logger.info("=== 测试4: 完整字幕提取 ===")
    test_extract_subtitles()
    
    # 测试5: SDK转写
    logger.info("=== 测试5: SDK转写 ===")
    if not test_sdk_transcription(audio_url):
        logger.error("SDK转写测试失败")
    
    logger.info("===== 测试完成 =====")

if __name__ == "__main__":
    run_tests() 