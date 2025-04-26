#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置文件，从环境变量或默认值加载配置项
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime
import uuid

load_dotenv()

# 获取项目根目录的绝对路径
ROOT_DIR = Path(__file__).parents[2].absolute()

# 视频与音频相关路径
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

AUDIO_CACHE_DIR = CACHE_DIR / "audio"
AUDIO_CACHE_DIR.mkdir(exist_ok=True)

VIDEO_CACHE_DIR = CACHE_DIR / "videos"
VIDEO_CACHE_DIR.mkdir(exist_ok=True)

OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

EXPORT_DIR = DATA_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# 分析维度相关路径
DIMENSIONS_DIR = DATA_DIR / "dimensions"
DIMENSIONS_DIR.mkdir(exist_ok=True)

# 热词与词典路径
HOTWORDS_DIR = DATA_DIR / "hotwords"
HOTWORDS_DIR.mkdir(exist_ok=True)

# 日志相关配置
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO
LOG_FILE = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

# 错误视频日志目录
ERROR_VIDEO_LOG_DIR = LOG_DIR / "video_errors"
ERROR_VIDEO_LOG_DIR.mkdir(exist_ok=True)

# API配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# 服务配置
DEFAULT_PORT = 8506
MAX_VIDEO_DURATION = 600  # 最大视频处理时长（秒）
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 最大视频大小（字节）
DEFAULT_VIDEO_SEGMENT_DURATION = 5  # 默认视频分段时长（秒）
ASR_OUTPUT_FORMAT = "vtt"

# 特性开关
ENABLE_OSS = False  # 是否启用阿里云OSS
ENABLE_DASHSCOPE = True  # 是否启用DashScope
ENABLE_LOCAL_CHUNK = True  # 是否开启本地分段处理
ENABLE_AUTO_SEGMENT = True  # 是否自动分段视频

# 会话ID
SESSION_ID = str(uuid.uuid4())

# API 模型配置
DASHSCOPE_ASR_MODEL = "paraformer-v2"
DASHSCOPE_ASR_SAMPLE_RATE = 16000

# 文件导出配置
CSV_DELIMITER = ","
CSV_QUOTECHAR = '"'

# 基础目录设置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_DIR = os.path.join(DATA_DIR, 'temp')

# 确保必要目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 上传目录设置
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 上传配置
MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', '200'))  # 默认最大200MB
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 转换为字节

# 视频上传配置
VIDEO_UPLOAD_DIR = os.path.join(UPLOAD_DIR, 'videos')
os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)
VIDEO_STORAGE_TYPE = os.environ.get('VIDEO_STORAGE_TYPE', 'local')  # 'local' 或 'oss'
VIDEO_FILE_CHUNK_SIZE = int(os.environ.get('VIDEO_FILE_CHUNK_SIZE', '8192'))  # 文件读取块大小(KB)
VIDEO_THUMB_SIZE = (320, 180)  # 视频缩略图尺寸
VIDEO_ALLOWED_FORMATS = {
    'mp4': {'mimetype': 'video/mp4', 'extension': '.mp4'},
    'avi': {'mimetype': 'video/x-msvideo', 'extension': '.avi'},
    'mov': {'mimetype': 'video/quicktime', 'extension': '.mov'},
    'mkv': {'mimetype': 'video/x-matroska', 'extension': '.mkv'},
    'wmv': {'mimetype': 'video/x-ms-wmv', 'extension': '.wmv'},
    'flv': {'mimetype': 'video/x-flv', 'extension': '.flv'},
    'webm': {'mimetype': 'video/webm', 'extension': '.webm'}
}
VIDEO_TEMP_DIR = os.path.join(TEMP_DIR, 'videos')
os.makedirs(VIDEO_TEMP_DIR, exist_ok=True)

# 视频缩略图配置
VIDEO_THUMB_DIR = os.path.join(VIDEO_UPLOAD_DIR, 'thumbnails')
os.makedirs(VIDEO_THUMB_DIR, exist_ok=True)
VIDEO_THUMB_FORMAT = 'jpg'  # 缩略图格式
VIDEO_THUMB_QUALITY = 90    # 缩略图质量 (1-100)
VIDEO_THUMB_GENERATE = os.environ.get('VIDEO_THUMB_GENERATE', 'True').lower() in ('true', '1', 't')  # 是否生成缩略图

# 视频处理配置
VIDEO_PROCESSING_DIR = os.path.join(DATA_DIR, 'processed')
os.makedirs(VIDEO_PROCESSING_DIR, exist_ok=True)
VIDEO_SUBTITLE_DIR = os.path.join(VIDEO_PROCESSING_DIR, 'subtitles')
os.makedirs(VIDEO_SUBTITLE_DIR, exist_ok=True)
VIDEO_ANALYSIS_DIR = os.path.join(VIDEO_PROCESSING_DIR, 'analysis')
os.makedirs(VIDEO_ANALYSIS_DIR, exist_ok=True)

# 视频错误日志目录
VIDEO_ERROR_LOG_DIR = os.path.join(LOG_DIR, 'video_errors')
os.makedirs(VIDEO_ERROR_LOG_DIR, exist_ok=True)

# 视频处理选项
VIDEO_SPEECH_RECOGNITION_ENGINE = os.environ.get('VIDEO_SPEECH_RECOGNITION_ENGINE', 'whisper')  # 'whisper' 或 'ali_asr'
VIDEO_MAX_RECOGNITION_SEGMENTS = int(os.environ.get('VIDEO_MAX_RECOGNITION_SEGMENTS', '500'))  # 最大语音识别片段数
VIDEO_RECOGNITION_CHUNK_SIZE = int(os.environ.get('VIDEO_RECOGNITION_CHUNK_SIZE', '10'))  # 语音识别分块大小(秒)
VIDEO_RECOGNITION_MIN_SILENCE = float(os.environ.get('VIDEO_RECOGNITION_MIN_SILENCE', '0.5'))  # 最小静音间隔(秒)

# 允许的视频文件扩展名
ALLOWED_VIDEO_EXTENSIONS = {
    'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 
    'webm', 'm4v', 'mpeg', 'mpg', '3gp'
}

# 允许的图片文件扩展名
ALLOWED_IMAGE_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'
}

# 阿里云OSS配置
OSS_ACCESS_KEY_ID = os.environ.get('OSS_ACCESS_KEY_ID', '')
OSS_ACCESS_KEY_SECRET = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
OSS_BUCKET_NAME = os.environ.get('OSS_BUCKET_NAME', 'ai-video-master')
OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com')
OSS_UPLOAD_DIR = os.environ.get('OSS_UPLOAD_DIR', 'videos')
OSS_PUBLIC_URL_TEMPLATE = os.environ.get(
    'OSS_PUBLIC_URL_TEMPLATE',
    'https://{bucket}.{endpoint}/{key}'
)
ENABLE_OSS = os.environ.get('ENABLE_OSS', 'False').lower() in ('true', '1', 't')

# API密钥配置
API_KEY = os.environ.get('API_KEY', 'default_key_for_development')

# 语音识别配置
PARAFORMER_MODEL_VERSION = os.environ.get('PARAFORMER_MODEL_VERSION', 'v2')  # 'v1', 'v2' 等版本
SUBTITLE_MODEL = os.environ.get('SUBTITLE_MODEL', 'maximal-punctuation')  # 字幕模型类型
SUBTITLE_LANGUAGE = os.environ.get('SUBTITLE_LANGUAGE', 'zh')  # 语言：zh, en, auto 等
HOT_WORDS = os.environ.get('HOT_WORDS', '').split(',') if os.environ.get('HOT_WORDS') else []  # 热词列表
API_TIMEOUT = int(os.environ.get('API_TIMEOUT', '300'))  # API超时时间(秒)

# 视频分析配置
VIDEO_ANALYSIS_TIMEOUT = int(os.environ.get('VIDEO_ANALYSIS_TIMEOUT', '600'))
VIDEO_FRAME_SAMPLE_RATE = int(os.environ.get('VIDEO_FRAME_SAMPLE_RATE', '5'))
VIDEO_MAX_DURATION = int(os.environ.get('VIDEO_MAX_DURATION', '7200'))  # 最大视频时长(秒)，默认2小时

# 视频上传处理配置
VIDEO_UPLOAD_HANDLERS = int(os.environ.get('VIDEO_UPLOAD_HANDLERS', '2'))  # 上传处理线程数
VIDEO_UPLOAD_RETRY = int(os.environ.get('VIDEO_UPLOAD_RETRY', '3'))  # 上传失败重试次数
VIDEO_UPLOAD_TIMEOUT = int(os.environ.get('VIDEO_UPLOAD_TIMEOUT', '300'))  # 上传超时时间(秒)
VIDEO_UPLOAD_CHUNK_SIZE = int(os.environ.get('VIDEO_UPLOAD_CHUNK_SIZE', '1048576'))  # 上传分块大小(字节)，默认1MB
VIDEO_UPLOAD_PROGRESS_INTERVAL = float(os.environ.get('VIDEO_UPLOAD_PROGRESS_INTERVAL', '0.2'))  # 上传进度更新间隔(秒)
VIDEO_UPLOAD_DEFAULT_LOCAL = os.environ.get('VIDEO_UPLOAD_DEFAULT_LOCAL', 'True').lower() in ('true', '1', 't')  # 默认使用本地存储
VIDEO_UPLOAD_UI_THEME = os.environ.get('VIDEO_UPLOAD_UI_THEME', 'light')  # 上传组件UI主题 'light'或'dark'

# 热词配置
HOT_WORDS_FILE = os.path.join(DATA_DIR, 'hot_words.json')

# 分析维度配置
DIMENSIONS_FILE = os.path.join(DATA_DIR, 'dimensions.json')

# 应用设置
APP_NAME = "AI视频大师"
APP_VERSION = "2.0.0"
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# 功能开关
ENABLE_ANALYTICS = os.environ.get('ENABLE_ANALYTICS', 'True').lower() in ('true', '1', 't')
ENABLE_SUBTITLE_DOWNLOAD = os.environ.get('ENABLE_SUBTITLE_DOWNLOAD', 'True').lower() in ('true', '1', 't')
ENABLE_VIDEO_PREVIEW = os.environ.get('ENABLE_VIDEO_PREVIEW', 'True').lower() in ('true', '1', 't')
ENABLE_ERROR_REPORTING = os.environ.get('ENABLE_ERROR_REPORTING', 'True').lower() in ('true', '1', 't')

# 进度显示设置
PROGRESS_UPDATE_INTERVAL = float(os.environ.get('PROGRESS_UPDATE_INTERVAL', '0.5'))  # 进度条更新间隔(秒)

class Config:
    # 处理流程配置
    PROCESS_STEPS = [
        'subtitles',
        'analysis', 
        'matching',
        'compilation'
    ]
    
    # 视频参数
    TRANSITION_TYPES = {
        'fade': {'duration': 1.0},
        'slide': {'direction': 'right', 'duration': 0.8},
        'zoom': {'factor': 1.2, 'duration': 1.2}
    }
    
    # 默认维度结构 - 调整为只有两个层级的结构
    DEFAULT_DIMENSIONS = {
        'title': '品牌认知',  # 之前的level1变成标题
        'level1': ['产品特性', '用户需求'],  # 之前的level2变成level1
        'level2': {  # 之前的level3变成level2
            '产品特性': ['功能', '外观', '性能'],
            '用户需求': ['场景', '痛点', '期望']
        }
    }
    
    # API配置
    @property
    def DASHSCOPE_API_KEY(self):
        return os.getenv('DASHSCOPE_API_KEY', '')
    
    # 路径配置
    INPUT_DIR = 'data/raw'
    OUTPUT_DIR = 'data/processed'
    CACHE_DIR = 'data/cache'
    DIMENSIONS_DIR = os.path.join('data', 'dimensions')
    HOTWORDS_DIR = os.path.join('data', 'hotwords')
    INITIAL_DIMENSION_FILENAME = 'initial_dimension.json'

config = Config()

# 导出常用配置项供直接导入
DIMENSIONS_DIR = config.DIMENSIONS_DIR
HOTWORDS_DIR = config.HOTWORDS_DIR
INITIAL_DIMENSION_FILENAME = config.INITIAL_DIMENSION_FILENAME
