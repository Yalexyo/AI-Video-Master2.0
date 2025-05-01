"""
核心模块，包含实现项目核心功能的类和函数
"""
from src.core.hot_words_api import get_api as get_hot_words_api
from src.core.hot_words_service import get_service as get_hot_words_service

__all__ = ['get_hot_words_api', 'get_hot_words_service']
