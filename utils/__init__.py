"""
AI视频大师工具包

提供视频分析和处理相关的工具类，包括：
- VideoAnalyzer: 视频内容分析和语义匹配
- VideoProcessor: 视频处理和字幕提取

此模块用于pages目录下的视频分析功能。
"""

from utils.analyzer import VideoAnalyzer
from utils.processor import VideoProcessor

__all__ = ['VideoAnalyzer', 'VideoProcessor'] 