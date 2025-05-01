import os
import sys
import time
import json
import uuid
import shutil
import logging
import hashlib
import requests
import subprocess
import numpy as np
import pandas as pd
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import tempfile
import asyncio
import nest_asyncio
import cv2
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from urllib.parse import urlparse

# 配置日志
logger = logging.getLogger(__name__)

# 导入OSS模块，如果可用
try:
    import oss2
    OSS_AVAILABLE = True
    logger.info("成功导入阿里云OSS模块")
except ImportError as e:
    OSS_AVAILABLE = False
    logger.warning(f"无法导入阿里云OSS模块: {str(e)}")

# 导入DashScope模块
try:
    import dashscope
    # 导入录音文件识别API，而非实时语音识别API
    from dashscope.audio.asr.transcription import Transcription
    DASHSCOPE_AVAILABLE = True
    logger.info("成功导入DashScope模块")
except ImportError as e:
    DASHSCOPE_AVAILABLE = False
    logger.warning(f"无法导入DashScope模块: {str(e)}")

# 使用nest_asyncio解决jupyter等环境中的asyncio循环问题
nest_asyncio.apply()

# 导入配置
from src.config.settings import (
    OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, 
    OSS_ENDPOINT, OSS_UPLOAD_DIR, OSS_PUBLIC_URL_TEMPLATE,
    ENABLE_OSS, VIDEO_TEMP_DIR, DASHSCOPE_API_KEY, PARAFORMER_MODEL_VERSION,
    SUBTITLE_MODEL, SUBTITLE_LANGUAGE, HOT_WORDS, API_TIMEOUT, OUTPUT_DIR
)

# 如果DashScope模块不可用，定义备用类
if not DASHSCOPE_AVAILABLE:
    # 定义备用API响应类
    class DashscopeResponse:
        def __init__(self):
            self.status_code = 500
            self.message = "DashScope模块未安装"
            self.output = {}
    
    # 定义备用回调类
    class RecognitionCallback:
        def on_open(self):
            pass
        
        def on_event(self, result):
            pass
            
        def on_error(self, result):
            pass
            
        def on_close(self):
            pass
            
        def on_complete(self):
            pass

class VideoProcessor:
    """视频处理器类，处理视频文件的基本操作及预处理功能"""
    
    def __init__(self, config: Dict = None):
        """
        初始化视频处理器
        
        参数:
            config: 配置字典，包含处理参数
        """
        self.config = config or {}
        # 不在初始化时创建Recognition实例，而是在需要时创建
        
        if not DASHSCOPE_AVAILABLE:
            logger.warning("DashScope模块不可用，语音识别功能将使用备用方案")
            
        logger.info("视频处理器初始化完成")
        
        # 确保输出目录存在
        self._ensure_directories()
        
        # 初始化音频缓存字典
        self.audio_cache = {}
        # 加载已处理的视频音频缓存记录
        self._load_audio_cache()
        
        # 初始化视频缓存字典
        self.video_cache = {}
        # 加载已下载的视频缓存记录
        self._load_video_cache()
    
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        dirs = [
            os.path.join('data', 'raw'),
            os.path.join('data', 'processed'),
            os.path.join('data', 'cache'),
            os.path.join('data', 'temp'),
            os.path.join('data', 'uploads')
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"创建目录: {dir_path}")
    
    def _load_audio_cache(self):
        """加载已处理的视频音频缓存记录"""
        cache_path = os.path.join('data', 'cache', 'audio_cache.json')
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self.audio_cache = json.load(f)
                logger.info(f"已加载{len(self.audio_cache)}条音频缓存记录")
            else:
                self.audio_cache = {}
        except Exception as e:
            logger.warning(f"加载音频缓存记录失败: {str(e)}")
            self.audio_cache = {}
    
    def _save_audio_cache(self):
        """保存音频缓存记录"""
        cache_path = os.path.join('data', 'cache', 'audio_cache.json')
        try:
            # 确保缓存目录存在
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.audio_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存{len(self.audio_cache)}条音频缓存记录")
        except Exception as e:
            logger.warning(f"保存音频缓存记录失败: {str(e)}")
            
    def _get_cache_key(self, video_file: str) -> str:
        """获取视频文件的缓存键"""
        # 如果是URL，使用URL作为键
        if video_file.startswith(('http://', 'https://')):
            return video_file
        # 如果是本地文件，使用文件名和大小作为键
        else:
            try:
                file_size = os.path.getsize(video_file)
                file_name = os.path.basename(video_file)
                return f"{file_name}_{file_size}"
            except:
                # 如果获取文件大小失败，直接使用文件路径
                return video_file
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        获取视频文件信息
        
        参数:
            video_path: 视频文件路径
            
        返回:
            包含视频信息的字典
        """
        try:
            # 使用OpenCV打开视频
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"无法打开视频文件: {video_path}")
                return {}
                
            # 获取基本信息
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            # 检查视频格式
            format = os.path.splitext(video_path)[1].lstrip('.').lower()
            
            # 读取一帧以验证视频是否可用
            ret, _ = cap.read()
            
            # 释放资源
            cap.release()
            
            # 检查视频是否有效
            if not ret or frame_count <= 0:
                logger.error(f"视频文件无效或损坏: {video_path}")
                return {}
            
            # 使用ffmpeg检查是否有音频轨道
            has_audio = True  # 默认假设有音频，除非确认没有
            try:
                # 使用FFprobe检查音频流
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-select_streams', 'a',
                    '-show_streams',
                    '-of', 'json',
                    video_path
                ]
                
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    output = json.loads(result.stdout)
                    # 如果没有音频流，streams列表为空
                    has_audio = len(output.get('streams', [])) > 0
                    logger.info(f"视频{video_path}{'有' if has_audio else '没有'}音频轨道")
                else:
                    logger.warning(f"ffprobe检查音频失败: {result.stderr}，假设视频有音频轨道")
            except Exception as e:
                logger.warning(f"检查音频轨道时出错: {str(e)}，假设视频有音频轨道")
                
            return {
                "duration": duration,
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}",
                "format": format,
                "has_audio": has_audio
            }
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    def process_video_file(self, video_file: str, vocabulary_id: str = None) -> str:
        """
        处理视频文件，提取字幕并保存为SRT文件
        
        参数:
            video_file: 视频文件路径或URL
            vocabulary_id: 热词表ID（可选），用于语音识别中的热词支持
            
        返回:
            SRT文件路径或空字符串（处理失败时）
        """
        logger.info(f"开始处理视频文件: {video_file}")
        
        try:
            # 从视频中提取字幕
            logger.info(f"开始从视频中提取字幕: {video_file}")
            subtitles = self._extract_subtitles_from_video(video_file, vocabulary_id)
            
            # 如果提取失败（返回空列表），则直接返回空字符串
            if not subtitles:
                logger.error(f"视频文件语音识别失败，未能提取到字幕: {video_file}")
                # 即使失败也要尝试清理临时文件
                self.cleanup_downloaded_videos(video_file)
                return ""
            
            logger.info(f"成功提取字幕，共 {len(subtitles)} 条记录，准备保存到SRT文件")
            
            # 保存字幕数据到SRT文件
            output_srt = self._save_subtitles_to_srt(video_file, subtitles)
            
            if not output_srt:
                logger.error(f"保存字幕到SRT文件失败: {video_file}")
                # 即使失败也要尝试清理临时文件
                self.cleanup_downloaded_videos(video_file)
                return ""
            
            logger.info(f"视频处理完成，字幕保存到: {output_srt}")
            
            # 清理临时文件
            self.cleanup_downloaded_videos(video_file)
            
            return output_srt
        
        except Exception as e:
            logger.exception(f"处理视频文件失败: {str(e)}")
            # 即使处理失败也尝试清理临时文件
            self.cleanup_downloaded_videos(video_file)
            return ""
    
    def _cleanup_temp_files(self, temp_file: str) -> None:
        """
        清理临时文件
        
        参数:
            temp_file: 临时文件路径
        """
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.info(f"已清理临时文件: {temp_file}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {temp_file}, 错误: {str(e)}")

    def cleanup_downloaded_videos(self, video_file: str) -> None:
        """
        清理下载的视频文件
        
        参数:
            video_file: 视频文件路径或URL
        """
        try:
            if not video_file:
                return
            
            # 判断是否为URL
            if video_file.startswith(('http://', 'https://')):
                # 尝试获取下载的本地文件路径
                video_cache_key = self._get_video_cache_key(video_file)
                logger.info(f"清理视频，缓存键: {video_cache_key}")
                
                # 从缓存中获取本地文件路径
                if video_cache_key in self.video_cache:
                    local_path = self.video_cache[video_cache_key]
                    logger.info(f"尝试清理下载的视频文件(从缓存): {local_path}")
                    
                    # 检查文件是否存在
                    if os.path.exists(local_path):
                        os.remove(local_path)
                        logger.info(f"已成功删除下载的视频文件: {local_path}")
                        
                        # 从缓存中删除记录
                        del self.video_cache[video_cache_key]
                        self._save_video_cache()
                        logger.info(f"已从视频缓存中移除记录: {video_cache_key}")
                    else:
                        logger.warning(f"视频文件不存在，无需清理: {local_path}")
                else:
                    logger.warning(f"视频缓存中没有找到记录: {video_cache_key}")
                
                # 尝试直接根据URL构造可能的文件路径
                url_path = urllib.parse.urlparse(video_file).path
                file_name = os.path.basename(url_path)
                logger.info(f"URL路径分析: {url_path} -> 文件名: {file_name}")
                
                # 检查多个可能的位置
                possible_paths = [
                    os.path.join('data', 'temp', 'videos', 'downloaded', file_name),
                    os.path.join(os.getcwd(), 'data', 'temp', 'videos', 'downloaded', file_name),
                    os.path.abspath(os.path.join('data', 'temp', 'videos', 'downloaded', file_name))
                ]
                
                for possible_path in possible_paths:
                    logger.info(f"检查临时文件位置: {possible_path}")
                    if os.path.exists(possible_path):
                        try:
                            os.remove(possible_path)
                            logger.info(f"已成功删除下载的视频文件(直接路径): {possible_path}")
                            break
                        except Exception as e:
                            logger.warning(f"删除文件失败: {possible_path}, 错误: {str(e)}")
                else:
                    logger.warning(f"未找到下载的视频文件: {file_name}")
            
            # 对于本地文件，不需要清理
            else:
                logger.debug(f"本地视频文件无需清理: {video_file}")
            
        except Exception as e:
            logger.warning(f"清理下载视频文件时出错: {str(e)}")
    
    def _extract_subtitles_from_video(self, video_file: str, vocabulary_id: str = None) -> List[Dict[str, Any]]:
        """
        从视频中提取字幕数据，使用阿里云DashScope服务的Paraformer模型进行语音识别
        支持直接使用OSS URL进行识别，无需下载到本地
        
        参数:
            video_file: 视频文件路径或URL
            vocabulary_id: 热词表ID（可选），用于语音识别中的热词支持
            
        返回:
            包含字幕信息的字典列表，每个字典包含开始时间、结束时间和文本内容
        """
        start_time = time.time()
        logger.info(f"开始从视频中提取字幕: {video_file}")
        audio_file = None
        
        try:
            # 检查输入参数
            if not video_file:
                logger.error("视频文件路径为空")
                return []
                
            # 判断是否为OSS URL链接
            is_url = video_file.startswith(('http://', 'https://'))
            
            # 如果不是URL，检查文件是否存在
            if not is_url:
                if not os.path.exists(video_file):
                    logger.error(f"视频文件不存在: {video_file}")
                    return []
                if not os.access(video_file, os.R_OK):
                    logger.error(f"无权限读取视频文件: {video_file}")
                    return []
            else:
                # 对URL进行检查
                try:
                    response = requests.head(video_file, timeout=5)
                    if response.status_code >= 400:
                        logger.error(f"视频URL无法访问: {video_file}, 状态码: {response.status_code}")
                        return []
                except requests.RequestException as e:
                    logger.error(f"视频URL请求异常: {video_file}, 错误: {str(e)}")
                    return []
            
            # 检查DashScope模块是否可用
            if not DASHSCOPE_AVAILABLE:
                logger.error("DashScope模块不可用，请安装dashscope: pip install dashscope")
                return self._fallback_subtitle_generation(video_file)
            
            # 检查API Key是否已设置
            if not DASHSCOPE_API_KEY:
                logger.error("DashScope API Key未设置，请在环境变量中配置DASHSCOPE_API_KEY")
                return []  # 直接返回空列表
            
            # 设置API密钥
            dashscope.api_key = DASHSCOPE_API_KEY
            
            # 设置Paraformer模型
            model_id = f"paraformer-{PARAFORMER_MODEL_VERSION}" if PARAFORMER_MODEL_VERSION else "paraformer-v2"
            
            # 构建API调用参数
            api_kwargs = {}
            
            # 添加基础音频参数
            api_kwargs['format'] = self._get_audio_format(video_file)
            api_kwargs['sample_rate'] = 16000
            
            # 添加额外参数
            if SUBTITLE_LANGUAGE and SUBTITLE_LANGUAGE != "auto":
                api_kwargs['language'] = SUBTITLE_LANGUAGE
            
            # 添加热词配置（如果已设置）
            if vocabulary_id and isinstance(vocabulary_id, str) and len(vocabulary_id) > 0:
                logger.info(f"应用热词配置: {vocabulary_id[:5]}{'...' if len(vocabulary_id) > 5 else ''}")
                api_kwargs['vocabulary_id'] = vocabulary_id
            
            # 首先预处理提取音频文件
            preprocess_start = time.time()
            audio_file = self._preprocess_video_file(video_file)
            preprocess_time = time.time() - preprocess_start
            logger.info(f"预处理视频文件完成，耗时: {preprocess_time:.2f}秒")
            
            if not audio_file:
                logger.error(f"预处理视频失败，无法提取音频: {video_file}")
                return []  # 直接返回空列表
            
            if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                logger.error(f"生成的音频文件不存在或为空: {audio_file}")
                return []  # 直接返回空列表
            
            # 对于本地音频文件，需要创建可访问的URL或使用文件路径
            logger.info(f"使用音频文件: {audio_file}")
            
            # 上传文件到OSS（直接使用OSS备选方案，跳过DashScope上传）
            audio_file_url = None
            file_id = None
            try:
                logger.info(f"使用OSS上传音频文件: {audio_file}")
                
                # 直接调用OSS上传方法
                audio_file_url = self._upload_to_accessible_url(audio_file)
                
                if audio_file_url:
                    logger.info(f"成功上传到OSS，获得URL: {audio_file_url}")
                    logger.debug(f"完整的API参数: model={model_id}, file_urls={audio_file_url}, api_kwargs={repr(api_kwargs)}")
                else:
                    logger.error(f"OSS上传失败，尝试使用备选方案")
                    
                    # 检查如果有热词配置，尝试使用file_content直接发送音频
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) < 10 * 1024 * 1024:  # 限制在10MB以内
                        logger.info("尝试使用file_content参数直接发送音频数据")
                        try:
                            with open(audio_file, 'rb') as f:
                                audio_content = f.read()
                                logger.info(f"读取音频文件内容，大小: {len(audio_content)} 字节")
                                
                                # 使用文件内容直接调用API
                                api_start_time = time.time()
                                response = dashscope.audio.asr.transcription.Transcription.call(
                                    model=model_id,
                                    file_content=audio_content,
                                    **api_kwargs
                                )
                                api_time = time.time() - api_start_time
                                logger.info(f"使用file_content参数的API调用完成，耗时: {api_time:.2f}秒")
                                
                                # 检查响应
                                if hasattr(response, 'output') and 'results' in response.output:
                                    logger.info("使用file_content参数成功获取识别结果")
                                    return self._parse_paraformer_response(response)
                                else:
                                    logger.error("使用file_content参数的API调用失败")
                                    if hasattr(response, 'output') and 'error' in response.output:
                                        error_info = response.output['error']
                                        logger.error(f"错误: {error_info}")
                        except Exception as content_error:
                            logger.error(f"使用file_content参数调用API失败: {str(content_error)}")
                    
                    # 如果直接发送音频内容失败，尝试转换为标准格式
                    logger.info("尝试转换为标准WAV格式后使用file_content参数")
                    try:
                        std_audio_file = self._convert_to_standard_audio(audio_file)
                        if std_audio_file and os.path.exists(std_audio_file) and os.path.getsize(std_audio_file) < 10 * 1024 * 1024:
                            logger.info(f"音频转换成功: {std_audio_file}")
                            with open(std_audio_file, 'rb') as f:
                                std_audio_content = f.read()
                                logger.info(f"读取标准音频文件内容，大小: {len(std_audio_content)} 字节")
                                
                                # 使用标准音频内容调用API
                                std_api_start_time = time.time()
                                response = dashscope.audio.asr.transcription.Transcription.call(
                                    model=model_id,
                                    file_content=std_audio_content,
                                    **api_kwargs
                                )
                                std_api_time = time.time() - std_api_start_time
                                logger.info(f"使用标准音频和file_content参数的API调用完成，耗时: {std_api_time:.2f}秒")
                                
                                # 检查响应
                                if hasattr(response, 'output') and 'results' in response.output:
                                    logger.info("使用标准音频格式和file_content参数成功获取识别结果")
                                    self._cleanup_temp_files(std_audio_file)
                                    return self._parse_paraformer_response(response)
                                else:
                                    logger.error("使用标准音频和file_content参数的API调用失败")
                                    if hasattr(response, 'output') and 'error' in response.output:
                                        error_info = response.output['error']
                                        logger.error(f"错误: {error_info}")
                    except Exception as std_content_error:
                        logger.error(f"转换标准格式后使用file_content参数调用API失败: {str(std_content_error)}")
                    
                    return []  # 直接返回空列表
                
                logger.info(f"最终使用: URL={audio_file_url}")
            
            except Exception as upload_error:
                logger.exception(f"上传文件到OSS时出错: {str(upload_error)}")
                return []  # 直接返回空列表
            
            # 修复格式化问题，对字典使用repr()避免嵌套花括号问题
            logger.info(f"DashScope Paraformer API调用参数: model_id={model_id}, file_urls={audio_file_url}, kwargs={repr(api_kwargs)}")
            
            try:
                # 使用正确的API调用方式，使用上传后的URL
                logger.info(f"开始调用DashScope API进行语音识别... file_urls={audio_file_url}")
                api_start_time = time.time()
                
                # 使用文件URL调用API
                response = dashscope.audio.asr.transcription.Transcription.call(
                    model=model_id,
                    file_urls=[audio_file_url],  # 使用上传后的URL
                    **api_kwargs  # 直接传递所有参数
                )
                
                # 计算API调用耗时
                api_time = time.time() - api_start_time
                logger.info(f"DashScope API调用完成，耗时: {api_time:.2f}秒")
                
                # 记录API响应的内容摘要
                status_code = getattr(response, 'status_code', None)
                request_id = getattr(response, 'request_id', 'unknown')
                
                # 当API失败时可能尝试转换音频格式后重试
                if hasattr(response, 'output') and 'error' in response.output:
                    error_obj = response.output.get('error', {})
                    error_code = error_obj.get('code', '')
                    error_message = error_obj.get('message', '')
                    
                    # 如果遇到文件下载或格式问题，尝试转换后重试
                    if error_code in ['FILE_DOWNLOAD_FAILED', 'PARAM_ERROR', 'AUDIO_FORMAT_ERROR']:
                        logger.warning(f"遇到API错误: {error_code} - {error_message}，尝试转换音频格式后重试")
                        
                        # 转换为标准PCM WAV格式
                        try:
                            std_audio_file = self._convert_to_standard_audio(audio_file)
                            if std_audio_file:
                                logger.info(f"音频转换成功: {std_audio_file}")
                                
                                # 上传标准格式的音频
                                logger.info("上传标准化后的音频文件")
                                std_audio_url = self._upload_to_accessible_url(std_audio_file)
                                
                                if std_audio_url:
                                    logger.info(f"重新上传成功，尝试再次调用API: {std_audio_url}")
                                    logger.info(f"重试API调用参数: model_id={model_id}, file_urls={std_audio_url}, kwargs={repr(api_kwargs)}")
                                    
                                    # 再次调用API，确保使用相同的api_kwargs
                                    retry_api_start_time = time.time()
                                    response = dashscope.audio.asr.transcription.Transcription.call(
                                        model=model_id,
                                        file_urls=[std_audio_url],
                                        **api_kwargs  # 这里会包含之前设置的vocabulary_id
                                    )
                                    
                                    # 更新API调用时间
                                    api_time = time.time() - retry_api_start_time
                                    logger.info(f"重试API调用完成，耗时: {api_time:.2f}秒")
                                    
                                    # 更新状态信息
                                    status_code = getattr(response, 'status_code', None)
                                    request_id = getattr(response, 'request_id', 'unknown')
                                    
                                    # 确保最后清理临时文件
                                    self._cleanup_temp_files(std_audio_file)
                            else:
                                logger.error("音频转换失败")
                                return []  # 直接返回空列表
                        except Exception as convert_error:
                            logger.error(f"转换音频格式失败: {str(convert_error)}")
                            return []  # 直接返回空列表
                
                logger.info(f"API响应: status_code={status_code}, request_id={request_id}")
                
                # 详细打印响应
                if hasattr(response, 'output'):
                    logger.info(f"API响应详细内容: {response.output}")
                    output_keys = response.output.keys() if response.output else []
                    logger.info(f"API响应输出字段: {', '.join(output_keys)}")
                    
                    # 检查是否有错误信息
                    if 'error' in response.output:
                        error_obj = response.output.get('error', {})
                        error_code = error_obj.get('code', '')
                        error_message = error_obj.get('message', '')
                        
                        logger.error(f"DashScope API返回错误: code={error_code}, message={error_message}")
                        
                        # 根据阿里云文档对常见错误码进行处理并提供建议
                        error_suggestions = {
                            "PARAM_ERROR": "请检查参数是否正确，特别是file_urls参数",
                            "FILE_DOWNLOAD_FAILED": "无法下载音频文件，请检查URL是否有效、是否可公网访问，服务是否允许跨域访问",
                            "FILE_404_NOT_FOUND": "需要下载的文件不存在，请检查URL是否正确",
                            "FILE_403_FORBIDDEN": "没有权限下载需要的文件，请检查URL访问权限设置",
                            "FILE_SERVER_ERROR": "文件服务器错误，请检查文件服务器状态",
                            "AUDIO_FORMAT_ERROR": "不支持的音频格式，请转换为支持的音频格式",
                            "AUDIO_DURATION_TOO_LONG": "音频时长超过12小时，请将音频分段处理",
                            "AUDIO_CHANNEL_NOT_SUPPORTED": "不支持的音频通道，请转换为支持的单通道音频",
                            "DECODER_ERROR": "音频解码失败，请检查音频文件是否有效",
                            "INVALID_API_KEY": "API密钥无效，请检查API密钥是否正确",
                            "INVALID_SIGNATURE": "签名无效，请检查签名算法",
                            "QPS_LIMIT_EXCEEDED": "QPS超过限制，请减少请求频率",
                            "INTERNAL_ERROR": "服务内部错误，请稍后重试"
                        }
                        
                        # 提供错误建议
                        suggestion = error_suggestions.get(error_code, "请参考官方文档检查错误原因")
                        logger.error(f"错误处理建议: {suggestion}")
                        
                        # 特别处理FILE_DOWNLOAD_FAILED错误
                        if error_code == 'FILE_DOWNLOAD_FAILED':
                            file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else "文件不存在"
                            logger.error(f"DashScope无法下载上传的音频文件，API错误: {error_code} - {error_message}")
                            logger.error(f"音频文件详情: 路径={audio_file}, 大小={file_size}字节, 上传URL={audio_file_url}")
                            
                            # 尝试获取文件格式信息
                            try:
                                audio_format = self._get_audio_format(audio_file)
                                logger.error(f"音频格式: {audio_format}")
                                
                                # 检查是否为支持的格式
                                supported_formats = ["aac", "amr", "avi", "flac", "flv", "m4a", "mkv", "mov", 
                                                    "mp3", "mp4", "mpeg", "ogg", "opus", "wav", "webm", "wma", "wmv"]
                                if audio_format not in supported_formats:
                                    logger.error(f"音频格式{audio_format}不在官方支持的格式列表中，这可能是错误的原因")
                                    logger.error(f"支持的格式: {', '.join(supported_formats)}")
                                
                            except Exception as format_error:
                                logger.error(f"无法获取音频格式: {str(format_error)}")
                            
                            # 尝试验证URL是否可访问
                            try:
                                import requests
                                response = requests.head(audio_file_url, timeout=5)
                                logger.error(f"URL访问检查: 状态码={response.status_code}, 可访问={response.status_code < 400}")
                                
                                # 检查内容类型
                                content_type = response.headers.get('Content-Type', '')
                                logger.error(f"URL内容类型: {content_type}")
                                
                                if not content_type.startswith(('audio/', 'video/')):
                                    logger.error(f"URL内容类型不是音频或视频，这可能导致下载失败")
                            except Exception as url_error:
                                logger.error(f"URL访问检查失败: {str(url_error)}")
                            
                            # 尝试使用file_content参数替代file_urls参数
                            # 根据文档，对于小文件，可以直接发送文件内容而非URL
                            if os.path.exists(audio_file) and os.path.getsize(audio_file) < 10 * 1024 * 1024:  # 限制在10MB以内
                                logger.info("尝试使用file_content参数直接发送音频数据")
                                try:
                                    with open(audio_file, 'rb') as f:
                                        audio_content = f.read()
                                        logger.info(f"读取音频文件内容，大小: {len(audio_content)} 字节")
                                        # 使用file_content参数的API调用
                                        file_content_response = dashscope.audio.asr.transcription.Transcription.call(
                                            model=model_id,
                                            file_content=audio_content,
                                            **api_kwargs
                                        )
                                        
                                        # 检查响应是否成功
                                        if hasattr(file_content_response, 'output') and 'results' in file_content_response.output:
                                            logger.info("使用file_content参数成功获取识别结果")
                                            return self._parse_paraformer_response(file_content_response)
                                        else:
                                            logger.error("使用file_content参数调用API失败")
                                            if hasattr(file_content_response, 'output') and 'error' in file_content_response.output:
                                                error_info = file_content_response.output['error']
                                                logger.error(f"错误: {error_info}")
                                except Exception as content_error:
                                    logger.error(f"使用file_content参数调用API失败: {str(content_error)}")
                            
                            # 尝试使用标准音频格式后直接发送内容
                            logger.info("尝试转换为标准WAV格式后使用file_content参数")
                            try:
                                std_audio_file = self._convert_to_standard_audio(audio_file)
                                if std_audio_file and os.path.exists(std_audio_file) and os.path.getsize(std_audio_file) < 10 * 1024 * 1024:
                                    logger.info(f"音频转换成功: {std_audio_file}")
                                    with open(std_audio_file, 'rb') as f:
                                        std_audio_content = f.read()
                                        logger.info(f"读取标准音频文件内容，大小: {len(std_audio_content)} 字节")
                                        # 使用file_content参数的API调用
                                        std_file_content_response = dashscope.audio.asr.transcription.Transcription.call(
                                            model=model_id,
                                            file_content=std_audio_content,
                                            **api_kwargs
                                        )
                                        
                                        # 检查响应是否成功
                                        if hasattr(std_file_content_response, 'output') and 'results' in std_file_content_response.output:
                                            logger.info("使用标准音频格式和file_content参数成功获取识别结果")
                                            self._cleanup_temp_files(std_audio_file)
                                            return self._parse_paraformer_response(std_file_content_response)
                            except Exception as std_content_error:
                                logger.error(f"转换标准格式后使用file_content参数调用API失败: {str(std_content_error)}")
                            
                            return []  # 所有方法都失败，返回空列表
                    
                    if 'results' in response.output and response.output['results']:
                        results = response.output['results']
                        logger.info(f"结果详细内容: {results}")
                        result_count = len(results)
                        first_result = results[0]
                        logger.info(f"第一个结果键: {first_result.keys() if hasattr(first_result, 'keys') else 'N/A'}")
                        sentences_count = len(first_result.get('sentences', []))
                        logger.info(f"API返回结果数: {result_count}，第一个结果包含 {sentences_count} 个句子")
            except Exception as api_error:
                logger.exception(f"DashScope API调用失败: {str(api_error)}")
                return []  # 直接返回空列表
            
            # 检查输出字段是否存在
            if not hasattr(response, 'output') or not response.output:
                logger.error("API响应缺少output字段")
                return []  # 直接返回空列表，不使用占位符
            
            # 检查结果字段是否存在
            if 'results' not in response.output:
                logger.error("API响应中缺少results字段")
                return []  # 直接返回空列表，不使用占位符
            
            # 提取结果
            results = response.output['results']
            if not results or len(results) == 0:
                logger.error("识别结果为空")
                return []  # 直接返回空列表，不使用占位符
            
            # 检查是否有transcription_url而非直接的sentences
            first_result = results[0]
            if 'transcription_url' in first_result and 'sentences' not in first_result:
                logger.info(f"检测到transcription_url: {first_result['transcription_url']}")
                
                # 获取视频时长，用于单句文本的时间戳生成
                duration = 0
                try:
                    # 使用ffprobe获取视频时长
                    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_file]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        duration = float(result.stdout.strip())
                        logger.info(f"使用ffprobe获取到视频时长: {duration}秒")
                    else:
                        logger.warning(f"使用ffprobe获取视频时长失败: {result.stderr}")
                        try:
                            # 尝试使用OpenCV获取视频时长
                            cap = cv2.VideoCapture(video_file)
                            if cap.isOpened():
                                fps = cap.get(cv2.CAP_PROP_FPS)
                                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                                duration = frame_count / fps if fps > 0 else 0
                                logger.info(f"使用OpenCV获取到视频时长: {duration}秒")
                            cap.release()
                        except Exception as cv_error:
                            logger.warning(f"使用OpenCV获取视频时长失败: {str(cv_error)}")
                            try:
                                # 尝试使用VideoFileClip获取视频时长
                                with VideoFileClip(video_file) as video:
                                    duration = video.duration
                                    logger.info(f"使用VideoFileClip获取到视频时长: {duration}秒")
                            except Exception as clip_error:
                                logger.warning(f"使用VideoFileClip获取视频时长失败: {str(clip_error)}")
                                duration = 60  # 默认60秒
                except Exception as ffprobe_error:
                    logger.warning(f"使用ffprobe获取视频时长失败: {str(ffprobe_error)}")
                    duration = 60  # 默认60秒
                
                if duration <= 0:
                    logger.warning("无法获取有效的视频时长，使用默认值60秒")
                    duration = 60
                
                # 下载转录结果
                try:
                    # 使用requests获取转录结果
                    logger.info(f"正在下载转录结果...")
                    import requests # 在这里添加导入语句
                    transcript_response = requests.get(first_result['transcription_url'], timeout=10)
                    
                    if transcript_response.status_code == 200:
                        # 解析JSON结果
                        transcript_data = transcript_response.json()
                        logger.info(f"成功下载转录结果，内容长度: {len(transcript_response.text)}")
                        
                        # 转录结果格式调试
                        logger.info(f"转录结果格式: {list(transcript_data.keys()) if isinstance(transcript_data, dict) else 'Not a dict'}")
                        
                        # 检查并提取文本内容
                        if 'transcripts' in transcript_data:
                            transcripts = transcript_data['transcripts']
                            if isinstance(transcripts, list) and len(transcripts) > 0:
                                logger.info(f"找到转录文本，共 {len(transcripts)} 条记录")
                                
                                # 生成字幕列表
                                subtitles = []
                                for transcript in transcripts:
                                    if isinstance(transcript, dict) and 'text' in transcript:
                                        text = transcript.get('text', '').strip()
                                        if text:
                                            # 使用标点符号分割文本
                                            sentences = re.split('[。！？.!?]', text)
                                            sentences = [s.strip() for s in sentences if s.strip()]
                                            
                                            # 计算每个句子的时长
                                            if len(sentences) > 0:
                                                sentence_duration = duration / len(sentences)
                                                
                                                for i, sentence in enumerate(sentences):
                                                    start_time = i * sentence_duration
                                                    end_time = (i + 1) * sentence_duration
                                                    
                                                    subtitle = {
                                                        'index': len(subtitles),
                                                        'start': start_time,
                                                        'end': end_time,
                                                        'start_formatted': self._format_time(start_time),
                                                        'end_formatted': self._format_time(end_time),
                                                        'timestamp': self._format_time(start_time),
                                                        'duration': sentence_duration,
                                                        'text': sentence
                                                    }
                                                    subtitles.append(subtitle)
                                
                                if subtitles:
                                    logger.info(f"成功生成字幕，共 {len(subtitles)} 条")
                                    return subtitles
                            else:
                                logger.error("转录文本列表为空或格式不正确")
                        else:
                            logger.error("转录结果中没有找到可用的文本信息")
                    else:
                        logger.error(f"下载转录结果失败，状态码: {transcript_response.status_code}")
                except Exception as e:
                    logger.exception(f"处理转录结果时出错: {str(e)}")
                
                # 如果处理失败，改为直接返回空列表
                logger.error("处理转录结果失败，返回空字幕列表")
                return []
            
            # 处理识别结果 - 转换为字幕格式
            process_start = time.time()
            subtitles = []
            file_result = results[0]  # 取第一个文件的结果
            
            if 'sentences' not in file_result:
                logger.error("API响应中缺少sentences字段")
                return []  # 直接返回空列表
            
            if len(file_result['sentences']) == 0:
                logger.warning("识别结果中没有句子")
                return []
            
            for i, sentence in enumerate(file_result['sentences']):
                # 计算开始和结束时间（毫秒转秒）
                start_time_ms = sentence.get('begin_time', 0) if 'begin_time' in sentence else 0
                end_time_ms = sentence.get('end_time', 0) if 'end_time' in sentence else 0
                
                # 转换为秒
                start_time_sec = start_time_ms / 1000
                end_time_sec = end_time_ms / 1000
                
                # 检查时间是否有效
                if end_time_sec < start_time_sec:
                    logger.warning(f"句子时间异常: 结束时间({end_time_sec}秒)早于开始时间({start_time_sec}秒)")
                    end_time_sec = start_time_sec + 1.0  # 强制设置一个合理值
                
                # 格式化时间
                start_formatted = self._format_time(start_time_sec)
                end_formatted = self._format_time(end_time_sec)
                
                # 检查文本是否为空
                text = sentence.get('text', '').strip()
                if not text:
                    logger.warning(f"跳过空文本句子，时间段: {start_formatted} - {end_formatted}")
                    continue
                
                subtitles.append({
                    "index": i,
                    "start": start_time_sec,
                    "end": end_time_sec,
                    "start_formatted": start_formatted,
                    "end_formatted": end_formatted,
                    "timestamp": start_formatted,
                    "duration": end_time_sec - start_time_sec,
                    "text": text
                })
            
            process_time = time.time() - process_start
            
            if len(subtitles) == 0:
                logger.warning("处理后的字幕列表为空")
                return []
            
            total_time = time.time() - start_time
            logger.info(f"成功从视频中提取了{len(subtitles)}条字幕，总耗时: {total_time:.2f}秒 (预处理: {preprocess_time:.2f}秒, API调用: {api_time:.2f}秒, 结果处理: {process_time:.2f}秒)")
            
            return subtitles
            
        except Exception as e:
            # 捕获所有其他异常
            logger.exception(f"提取字幕过程中发生未预期的错误: {str(e)}")
            
            # 尝试提供更详细的错误分析
            error_msg = str(e)
            if "InvalidApiKey" in error_msg or "API-key" in error_msg:
                logger.error("API密钥无效或未正确配置")
                logger.error("请在.env文件中设置正确的DASHSCOPE_API_KEY，或检查阿里云账户状态")
            elif "timeout" in error_msg.lower():
                logger.error("API请求超时，可能是网络问题或服务器负载过高")
            elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                logger.error("API使用配额限制，请检查阿里云账户额度")
            elif "file" in error_msg.lower() and ("download" in error_msg.lower() or "access" in error_msg.lower()):
                logger.error("文件访问或下载失败，请检查音频文件格式和可访问性")
                
            # 直接返回空列表，不使用占位符
            return []
        finally:
            # 确保清理临时文件，无论是否发生异常
            self._cleanup_temp_files(audio_file)
            
            # 清理上传到DashScope的文件
            if 'file_id' in locals() and file_id:
                try:
                    logger.info(f"尝试删除DashScope上的文件: {file_id}")
                    delete_response = dashscope.files.Files.delete(file_id=file_id)
                    
                    # 打印响应以便调试
                    logger.info(f"删除文件响应: status_code={delete_response.status_code}")
                    
                    # 检查响应状态码
                    if hasattr(delete_response, 'status_code') and delete_response.status_code == 200:
                        logger.info(f"成功删除DashScope上的文件: {file_id}")
                    else:
                        error_message = getattr(delete_response, 'message', '未知错误')
                        logger.warning(f"删除DashScope上的文件失败: {file_id}, HTTP {delete_response.status_code} - {error_message}")
                except Exception as delete_error:
                    logger.warning(f"删除DashScope上的文件时出错: {str(delete_error)}")
    
    def _fallback_subtitle_generation(self, video_file: str) -> List[Dict[str, Any]]:
        """
        回退方案：当主要字幕提取方法失败时使用
        
        参数:
            video_file: 视频文件路径
            
        返回:
            字幕信息列表，失败时返回带有错误提示的占位字幕
        """
        try:
            logger.warning(f"正在使用回退方案提取字幕: {video_file}")
            
            # 检查输入参数
            if not video_file:
                logger.error("视频文件路径为空")
                return []
            
            # 检查是否为URL
            is_url = video_file.startswith(('http://', 'https://'))
            
            # 如果不是URL，检查文件是否存在
            if not is_url and not os.path.exists(video_file):
                logger.error(f"回退方案：视频文件不存在: {video_file}")
                return []
            
            # 尝试获取视频时长作为占位符数据的参考
            try:
                video_info = self._get_video_info(video_file)
                duration = video_info.get('duration', 0)
                if duration <= 0:
                    logger.warning("视频时长无效，使用默认值60秒")
                    duration = 60
            except Exception as e:
                logger.warning(f"获取视频信息失败: {str(e)}，使用默认时长60秒")
                duration = 60
            
            logger.info(f"生成回退方案的占位符字幕，视频时长: {duration}秒")
            
            # 生成简单的占位符字幕
            num_segments = min(max(int(duration / 10), 1), 10)  # 最少1个，最多10个分段
            segment_duration = duration / num_segments
            
            subtitles = []
            for i in range(num_segments):
                start_time = i * segment_duration
                end_time = (i + 1) * segment_duration
                
                # 格式化时间
                start_formatted = self._format_time(start_time)
                end_formatted = self._format_time(end_time)
                
                subtitles.append({
                    "index": i,
                    "start": start_time,
                    "end": end_time,
                    "start_formatted": start_formatted,
                    "end_formatted": end_formatted,
                    "timestamp": start_formatted,
                    "duration": end_time - start_time,
                    "text": f"[无法识别的内容 #{i+1}]"
                })
            
            logger.info(f"成功生成回退方案占位符字幕，共{len(subtitles)}条")
            return subtitles
            
        except Exception as e:
            logger.exception(f"回退字幕提取也失败了: {str(e)}")
            
            # 返回一个最小的占位符字幕
            return [{
                "index": 0,
                "start": 0,
                "end": 60,
                "start_formatted": "00:00:00.000",
                "end_formatted": "00:01:00.000",
                "timestamp": "00:00:00.000",
                "duration": 60,
                "text": "[语音识别失败，请尝试其他视频或稍后重试]"
            }]
    
    def _preprocess_video_file(self, video_file: str) -> Optional[str]:
        """
        从视频文件中提取音频
        
        参数:
            video_file: 视频文件路径或URL
            
        返回:
            提取的音频文件路径，失败时返回None
        """
        start_time = time.time()
        logger.info(f"开始预处理视频文件: {video_file}")
        
        try:
            # 检查缓存中是否有此视频的处理记录
            cache_key = self._get_cache_key(video_file)
            if cache_key in self.audio_cache:
                cached_audio_path = self.audio_cache[cache_key]
                if os.path.exists(cached_audio_path):
                    logger.info(f"检测到音频缓存，直接使用已处理的音频文件: {cached_audio_path}")
                    return cached_audio_path
                else:
                    # 缓存文件不存在，删除无效记录
                    logger.warning(f"缓存的音频文件不存在，将重新处理: {cached_audio_path}")
                    del self.audio_cache[cache_key]
                    self._save_audio_cache()
            
            # 检查是否为URL
            is_url = video_file.startswith(('http://', 'https://'))
            
            # 检查文件是否存在/可访问
            if is_url:
                # 对URL进行HEAD请求，检查是否可访问
                try:
                    response = requests.head(video_file, timeout=10)
                    if response.status_code >= 400:
                        logger.error(f"视频URL不可访问: {video_file}, 状态码: {response.status_code}")
                        return None
                except requests.RequestException as e:
                    logger.error(f"无法访问视频URL: {video_file}, 错误: {str(e)}")
                    return None
            else:
                # 检查本地文件是否存在
                if not os.path.exists(video_file):
                    logger.error(f"视频文件不存在: {video_file}")
                    return None
                
                # 检查是否有读取权限
                if not os.access(video_file, os.R_OK):
                    logger.error(f"无权限读取视频文件: {video_file}")
                    return None
            
            # 准备文件名和路径
            timestamp = int(time.time())
            
            # 生成临时音频文件名
            if is_url:
                # 检查视频URL是否已缓存
                video_cache_key = self._get_video_cache_key(video_file)
                
                if video_cache_key in self.video_cache:
                    cached_video_path = self.video_cache[video_cache_key]
                    if os.path.exists(cached_video_path):
                        logger.info(f"检测到视频缓存，直接使用已下载的视频文件: {cached_video_path}")
                        video_file = cached_video_path
                    else:
                        # 缓存文件不存在，删除无效记录
                        logger.warning(f"缓存的视频文件不存在，将重新下载: {cached_video_path}")
                        del self.video_cache[video_cache_key]
                        self._save_video_cache()
                
                # 如果需要下载视频
                if video_file.startswith(('http://', 'https://')):
                    # 如果是远程URL，先下载到本地再处理
                    download_dir = os.path.join('data', 'temp', 'videos', 'downloaded')
                    os.makedirs(download_dir, exist_ok=True)
                    
                    # 获取URL中的文件名，如果没有则使用时间戳
                    url_path = urllib.parse.urlparse(video_file).path
                    file_name = os.path.basename(url_path) or f"video_{timestamp}"
                    local_video_path = os.path.join(download_dir, file_name)
                    
                    download_start = time.time()
                    logger.info(f"开始从URL下载视频: {video_file} -> {local_video_path}")
                    
                    # 使用requests下载文件，显示进度
                    try:
                        with requests.get(video_file, stream=True, timeout=30) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            
                            # 显示文件大小
                            size_mb = total_size / (1024 * 1024)
                            logger.info(f"视频文件大小: {size_mb:.2f} MB")
                            
                            # 下载文件，每10%显示一次进度
                            downloaded = 0
                            last_percent = 0
                            with open(local_video_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        
                                        # 计算并显示下载进度
                                        if total_size > 0:
                                            percent = int(downloaded * 100 / total_size)
                                            if percent >= last_percent + 10:
                                                logger.info(f"下载进度: {percent}%")
                                                last_percent = percent
                            
                            download_time = time.time() - download_start
                            logger.info(f"视频下载完成: {local_video_path}，耗时: {download_time:.2f}秒")
                            
                            # 添加到视频缓存
                            self.video_cache[video_cache_key] = local_video_path
                            self._save_video_cache()
                            
                            # 使用本地文件路径替换远程URL
                            video_file = local_video_path
                    except Exception as download_error:
                        logger.error(f"下载视频文件失败: {str(download_error)}")
                        return None
            
            # 生成临时音频文件名 - 使用视频文件名和哈希值作为唯一标识
            file_name = os.path.basename(video_file)
            file_base = os.path.splitext(file_name)[0]
            
            # 将临时音频文件放入缓存目录，而不是临时目录，便于复用
            cache_dir = os.path.join('data', 'cache', 'audio')
            os.makedirs(cache_dir, exist_ok=True)
            audio_file = os.path.join(cache_dir, f"{file_base}_{timestamp}.wav")
            
            # 确保临时目录存在
            os.makedirs(os.path.dirname(audio_file), exist_ok=True)
            
            # 使用ffmpeg提取音频
            try:
                extract_start = time.time()
                # 构建优化的ffmpeg命令
                cmd = [
                    'ffmpeg',
                    '-y',  # 覆盖输出文件
                    '-i', video_file,  # 输入文件
                    '-vn',  # 禁用视频
                    '-ar', '16000',  # 采样率16kHz
                    '-ac', '1',  # 单声道
                    '-c:a', 'pcm_s16le',  # 直接指定编解码器
                    '-q:a', '0',  # 使用质量参数代替比特率
                    '-f', 'wav',  # wav格式
                    audio_file  # 输出文件
                ]
                
                # 执行命令
                logger.info(f"执行音频提取命令: {' '.join(cmd)}")
                
                # 使用subprocess.run而不是os.system，以获取更好的错误处理
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False  # 不自动抛出异常，我们手动处理
                )
                
                # 检查命令执行结果
                if result.returncode != 0:
                    logger.error(f"提取音频失败，错误码: {result.returncode}")
                    logger.error(f"错误输出: {result.stderr}")
                    return None
                
                extract_time = time.time() - extract_start
                logger.info(f"音频提取完成，耗时: {extract_time:.2f}秒")
                
                # 验证输出文件是否正确生成
                if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                    logger.error(f"输出的音频文件不存在或为空: {audio_file}")
                    return None
                
                logger.info(f"成功提取音频到: {audio_file}")
                
                # 将音频文件路径添加到缓存
                self.audio_cache[cache_key] = audio_file
                self._save_audio_cache()
                logger.info(f"已将音频文件添加到缓存: {cache_key} -> {audio_file}")
                
                total_time = time.time() - start_time
                logger.info(f"视频预处理完成，总耗时: {total_time:.2f}秒")
                
                return audio_file
                
            except Exception as e:
                logger.exception(f"执行ffmpeg命令时出错: {str(e)}")
                return None
        
        except Exception as e:
            logger.exception(f"预处理视频文件时出错: {str(e)}")
            return None
    
    def _parse_paraformer_response(self, response) -> List[Dict[str, Any]]:
        """
        解析Paraformer API返回的结果
        
        参数:
            response: API响应对象
            
        返回:
            字幕数据列表
        """
        subtitles = []
        sentences = response.output.get('sentences', [])
        
        for i, sentence in enumerate(sentences):
            # 计算开始和结束时间（毫秒转秒）
            start_time = sentence.get('begin_time', 0) / 1000
            end_time = sentence.get('end_time', 0) / 1000
            
            # 格式化时间
            start_formatted = self._format_time(start_time)
            end_formatted = self._format_time(end_time)
            
            subtitles.append({
                "index": i,
                "start": start_time,
                "end": end_time,
                "start_formatted": start_formatted,
                "end_formatted": end_formatted,
                "timestamp": start_formatted,
                "duration": end_time - start_time,
                "text": sentence.get('text', '')
            })
        
        logger.info(f"成功解析识别结果，共 {len(subtitles)} 条字幕")
        return subtitles
    
    def _upload_to_accessible_url(self, file_path: str) -> Optional[str]:
        """
        将文件上传到阿里云OSS，并返回公网可访问的URL
        
        参数:
            file_path: 本地文件路径
            
        返回:
            公网可访问的URL，上传失败则返回None
        """
        try:
            # 检查是否启用了OSS
            if ENABLE_OSS and OSS_AVAILABLE:
                # 检查OSS配置是否完整
                if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, OSS_ENDPOINT]):
                    logger.error("阿里云OSS配置不完整，请检查环境变量")
                    return None
                
                # 初始化OSS客户端
                auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
                
                # 根据阿里云最佳实践，使用与Paraformer API同地域的OSS端点
                # 当前Paraformer部署地域：华北2（北京，cn-beijing）
                # 使用内网域名，避免产生不必要的OSS网络流量费用
                bucket_endpoint = OSS_ENDPOINT.replace('oss-cn-beijing.aliyuncs.com', 'oss-cn-beijing-internal.aliyuncs.com')
                bucket = oss2.Bucket(auth, bucket_endpoint, OSS_BUCKET_NAME)
                
                # 生成OSS文件路径
                file_name = os.path.basename(file_path)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                oss_file_path = f"{OSS_UPLOAD_DIR}/{timestamp}_{file_name}"
                
                # 上传文件到OSS
                logger.info(f"正在上传文件到阿里云OSS: {oss_file_path}")
                result = bucket.put_object_from_file(oss_file_path, file_path)
                
                # 检查上传结果
                if result.status == 200:
                    # 生成公网访问URL
                    public_url = OSS_PUBLIC_URL_TEMPLATE.format(
                        bucket=OSS_BUCKET_NAME,
                        endpoint=OSS_ENDPOINT,
                        key=oss_file_path
                    )
                    logger.info(f"文件成功上传到OSS: {public_url}")
                    return public_url
                else:
                    logger.error(f"上传文件到OSS失败: {result.status}")
                    return None
            else:
                # OSS不可用
                logger.error("阿里云OSS未启用或模块不可用，无法上传文件")
                return None
                
        except Exception as e:
            logger.error(f"上传文件到OSS出错: {str(e)}")
            return None
    
    def _format_time(self, seconds: float) -> str:
        """
        格式化时间
        
        参数:
            seconds: 秒数
            
        返回:
            格式化后的时间字符串 (HH:MM:SS)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _convert_to_standard_audio(self, audio_file: str) -> Optional[str]:
        """
        将音频转换为标准PCM WAV格式
        
        参数:
            audio_file: 原始音频文件路径
            
        返回:
            转换后的音频文件路径，失败时返回None
        """
        try:
            logger.info(f"正在将音频转换为标准PCM WAV格式: {audio_file}")
            
            # 检查输入音频文件是否存在
            if not os.path.exists(audio_file):
                logger.error(f"音频文件不存在: {audio_file}")
                return None
            
            # 准备输出文件名
            output_dir = os.path.dirname(audio_file)
            basename = os.path.basename(audio_file)
            filename, _ = os.path.splitext(basename)
            output_file = os.path.join(output_dir, f"{filename}_standard.wav")
            
            # 使用ffmpeg转换为标准格式: PCM 16位, 单声道, 16000Hz
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # 覆盖现有文件
                "-i", audio_file,  # 输入文件
                "-acodec", "pcm_s16le",  # 16位PCM
                "-ac", "1",  # 单声道
                "-ar", "16000",  # 16000Hz采样率
                "-f", "wav",  # WAV格式
                output_file  # 输出文件
            ]
            
            logger.info(f"执行命令: {' '.join(ffmpeg_cmd)}")
            
            # 执行命令
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 检查执行结果
            if result.returncode != 0:
                logger.error(f"音频转换失败，错误码: {result.returncode}")
                logger.error(f"错误输出: {result.stderr}")
                return None
            
            # 验证输出文件
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                logger.error(f"输出的标准音频文件不存在或为空: {output_file}")
                return None
            
            logger.info(f"音频格式转换成功: {output_file}")
            return output_file
            
        except Exception as e:
            logger.exception(f"音频格式转换时出错: {str(e)}")
            return None
    
    def convert_from_youtube(self, url: str) -> str:
        """
        从YouTube URL提取字幕数据
        
        参数:
            url: YouTube视频URL
            
        返回:
            处理后的CSV文件路径
        """
        try:
            logger.info(f"开始处理YouTube视频: {url}")
            
            # 提取YouTube视频ID
            video_id = self._extract_youtube_id(url)
            if not video_id:
                logger.error(f"无法从URL提取YouTube视频ID: {url}")
                return ""
            
            # 模拟从YouTube提取字幕
            # 注意：实际项目中应使用youtube-dl或yt-dlp等工具下载字幕
            output_dir = os.path.join('data', 'processed')
            os.makedirs(output_dir, exist_ok=True)
            
            output_csv = os.path.join(output_dir, f"youtube_{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")
            
            # 模拟字幕数据
            subtitles = self._simulate_youtube_subtitles(video_id)
            
            # 创建DataFrame并保存
            df = pd.DataFrame(subtitles)
            df.to_csv(output_csv, index=False, encoding='utf-8')
            
            logger.info(f"YouTube视频处理完成，字幕保存到: {output_csv}")
            return output_csv
        
        except Exception as e:
            logger.error(f"处理YouTube视频出错: {str(e)}")
            return ""
    
    def _extract_youtube_id(self, url: str) -> str:
        """
        从YouTube URL提取视频ID
        
        参数:
            url: YouTube视频URL
            
        返回:
            YouTube视频ID
        """
        # 支持多种格式的YouTube URL
        # 例如: https://www.youtube.com/watch?v=VIDEO_ID
        #      https://youtu.be/VIDEO_ID
        #      https://www.youtube.com/embed/VIDEO_ID
        
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch.*?v=([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""
    
    def _simulate_youtube_subtitles(self, video_id: str) -> List[Dict[str, Any]]:
        """
        模拟YouTube字幕数据
        
        参数:
            video_id: YouTube视频ID
            
        返回:
            字幕数据列表
        """
        # 这是一个模拟方法，实际项目中应使用youtube-dl等工具获取真实字幕
        
        subtitles = []
        video_duration = 600  # 模拟10分钟视频
        
        # 生成20个模拟字幕片段
        for i in range(20):
            start_time = i * 30  # 每30秒一个片段
            end_time = start_time + 30
            
            # 格式化时间
            start_formatted = self._format_time(start_time)
            end_formatted = self._format_time(end_time)
            
            # 生成模拟文本
            if i % 4 == 0:
                text = f"这是来自YouTube的第{i+1}个字幕片段，讨论了产品优势和市场分析。"
            elif i % 4 == 1:
                text = f"第{i+1}个片段介绍了品牌营销和用户需求，以及竞品分析。"
            elif i % 4 == 2:
                text = f"这是关于功能设计和用户体验的第{i+1}个讨论片段。"
            else:
                text = f"第{i+1}个片段详细说明了技术实现和未来规划，以及团队协作。"
            
            subtitles.append({
                "index": i,
                "start": start_time,
                "end": end_time,
                "start_formatted": start_formatted,
                "end_formatted": end_formatted,
                "timestamp": start_formatted,
                "duration": end_time - start_time,
                "text": text
            })
        
        return subtitles
    
    def convert_to_csv(self, input_file: str, output_file: Optional[str] = None) -> str:
        """
        将字幕文件转换为CSV格式
        
        参数:
            input_file: 输入字幕文件路径（.srt, .vtt等）
            output_file: 输出CSV文件路径，如果为None则自动生成
            
        返回:
            输出CSV文件路径
        """
        try:
            logger.info(f"开始转换字幕文件: {input_file}")
            
            # 获取输入文件名和扩展名
            file_name = os.path.splitext(os.path.basename(input_file))[0]
            file_ext = os.path.splitext(input_file)[1].lower()
            
            # 确定输出文件路径
            if output_file is None:
                output_dir = os.path.join('data', 'processed')
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{file_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")
            
            # 根据不同格式处理字幕
            if file_ext == '.srt':
                subtitles = self._parse_srt_file(input_file)
            elif file_ext == '.vtt':
                subtitles = self._parse_vtt_file(input_file)
            else:
                # 如果是未知格式，返回空
                logger.error(f"不支持的字幕文件格式: {file_ext}")
                return ""
            
            # 创建DataFrame并保存
            df = pd.DataFrame(subtitles)
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(f"字幕文件转换完成，保存到: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"转换字幕文件出错: {str(e)}")
            return ""
    
    def _parse_srt_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析SRT字幕文件
        
        参数:
            file_path: SRT文件路径
            
        返回:
            字幕数据列表
        """
        # 实际项目中应该使用pysrt库解析SRT文件
        # 这里简化为模拟结果
        
        logger.info(f"模拟解析SRT文件: {file_path}")
        
        subtitles = []
        # 模拟15个字幕片段
        for i in range(15):
            start_time = i * 20  # 每20秒一个片段
            end_time = start_time + 20
            
            # 格式化时间
            start_formatted = self._format_time(start_time)
            end_formatted = self._format_time(end_time)
            
            # 生成模拟文本
            text = f"这是SRT文件中的第{i+1}个字幕片段，时间范围从{start_formatted}到{end_formatted}。"
            
            subtitles.append({
                "index": i,
                "start": start_time,
                "end": end_time,
                "start_formatted": start_formatted,
                "end_formatted": end_formatted,
                "timestamp": start_formatted,
                "duration": end_time - start_time,
                "text": text
            })
        
        return subtitles
    
    def _parse_vtt_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析VTT字幕文件
        
        参数:
            file_path: VTT文件路径
            
        返回:
            字幕数据列表
        """
        # 实际项目中应该使用webvtt-py库解析VTT文件
        # 这里简化为模拟结果
        
        logger.info(f"模拟解析VTT文件: {file_path}")
        
        subtitles = []
        # 模拟15个字幕片段
        for i in range(15):
            start_time = i * 25  # 每25秒一个片段
            end_time = start_time + 25
            
            # 格式化时间
            start_formatted = self._format_time(start_time)
            end_formatted = self._format_time(end_time)
            
            # 生成模拟文本
            text = f"这是VTT文件中的第{i+1}个字幕片段，包含了视频内容。"
            
            subtitles.append({
                "index": i,
                "start": start_time,
                "end": end_time,
                "start_formatted": start_formatted,
                "end_formatted": end_formatted,
                "timestamp": start_formatted,
                "duration": end_time - start_time,
                "text": text
            })
        
        return subtitles
    
    def _get_audio_format(self, file_path: str) -> str:
        """
        根据文件扩展名获取音频格式，用于DashScope API参数
        
        参数:
            file_path: 文件路径
            
        返回:
            适用于DashScope API的音频格式
        """
        # 获取文件扩展名（去掉点号并转为小写）
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        # DashScope支持的音频格式映射
        format_mapping = {
            'mp4': 'mp4',
            'mp3': 'mp3',
            'wav': 'wav',
            'flac': 'flac',
            'aac': 'aac',
            'amr': 'amr',
            'avi': 'avi',
            'flv': 'flv',
            'm4a': 'm4a',
            'mkv': 'mkv',
            'mov': 'mov',
            'mpeg': 'mpeg',
            'ogg': 'ogg',
            'opus': 'opus',
            'webm': 'webm',
            'wma': 'wma',
            'wmv': 'wmv'
        }
        
        # 如果扩展名在映射中，返回对应格式，否则返回默认格式
        if ext in format_mapping:
            return format_mapping[ext]
        else:
            logger.warning(f"未知的文件格式: {ext}，使用默认格式'auto'")
            return 'auto' 

    def _save_subtitles_to_srt(self, video_file: str, subtitles: List[Dict[str, Any]]) -> str:
        """
        将字幕数据保存为SRT文件
        
        参数:
            video_file: 视频文件路径或URL
            subtitles: 字幕数据列表
            
        返回:
            保存的SRT文件路径，如果保存失败则返回空字符串
        """
        try:
            # 确定视频文件名
            if video_file.startswith(('http://', 'https://')):
                # 从URL中提取文件名
                video_filename = os.path.basename(video_file.split('?')[0])
            else:
                video_filename = os.path.basename(video_file)
            
            video_name, _ = os.path.splitext(video_filename)
            
            # 确定输出目录
            output_dir = os.path.join(OUTPUT_DIR, 'subtitles')
            logger.info(f"字幕将保存到目录: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名（添加时间戳）
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"{video_name}_{timestamp}.srt"
            output_srt = os.path.join(output_dir, output_filename)
            
            logger.info(f"将保存 {len(subtitles)} 条字幕到SRT文件: {output_srt}")
            
            # 将字幕数据保存为SRT格式
            with open(output_srt, 'w', encoding='utf-8') as f:
                for i, subtitle in enumerate(subtitles):
                    # SRT索引从1开始
                    index = i + 1
                    
                    # 获取时间信息
                    start_time = subtitle.get('start', 0)
                    end_time = subtitle.get('end', 0)
                    
                    # 转换为SRT时间格式 (00:00:00,000)
                    start_formatted = self._format_time_srt(start_time)
                    end_formatted = self._format_time_srt(end_time)
                    
                    # 获取字幕文本
                    text = subtitle.get('text', '')
                    
                    # 写入SRT格式
                    f.write(f"{index}\n")
                    f.write(f"{start_formatted} --> {end_formatted}\n")
                    f.write(f"{text}\n\n")
            
            # 验证文件是否成功保存
            if os.path.exists(output_srt) and os.path.getsize(output_srt) > 0:
                logger.info(f"字幕数据成功保存到SRT: {output_srt}")
                return output_srt
            else:
                logger.error(f"字幕SRT文件创建失败或为空: {output_srt}")
                return ""
        
        except Exception as e:
            logger.exception(f"保存字幕到SRT失败: {str(e)}")
            return ""

    def _format_time_srt(self, seconds: float) -> str:
        """
        将秒数转换为SRT格式的时间字符串 (00:00:00,000)
        
        参数:
            seconds: 秒数
            
        返回:
            SRT格式的时间字符串
        """
        # 确保秒数为非负数
        seconds = max(0, seconds)
        
        # 计算时、分、秒和毫秒
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_part = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        # 格式化为SRT时间格式
        return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{milliseconds:03d}"
    
    def _load_video_cache(self):
        """加载已下载的视频缓存记录"""
        cache_path = os.path.join('data', 'cache', 'video_cache.json')
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self.video_cache = json.load(f)
                logger.info(f"已加载{len(self.video_cache)}条视频缓存记录")
            else:
                self.video_cache = {}
        except Exception as e:
            logger.warning(f"加载视频缓存记录失败: {str(e)}")
            self.video_cache = {}
    
    def _save_video_cache(self):
        """保存视频缓存记录"""
        cache_path = os.path.join('data', 'cache', 'video_cache.json')
        try:
            # 确保缓存目录存在
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.video_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存{len(self.video_cache)}条视频缓存记录")
        except Exception as e:
            logger.warning(f"保存视频缓存记录失败: {str(e)}")
    
    def _get_video_cache_key(self, video_url: str) -> str:
        """获取视频URL的缓存键"""
        # 对于URL，使用最后一部分作为键
        try:
            url_path = urllib.parse.urlparse(video_url).path
            file_name = os.path.basename(url_path)
            return file_name
        except:
            # 如果解析失败，使用完整URL
            return video_url 