import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import tempfile
import re
import requests
import urllib.parse
from pathlib import Path
import asyncio
import nest_asyncio
import time
import subprocess
import cv2
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
    ENABLE_OSS, VIDEO_TEMP_DIR, API_KEY, PARAFORMER_MODEL_VERSION,
    SUBTITLE_MODEL, SUBTITLE_LANGUAGE, HOT_WORDS, API_TIMEOUT
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
        处理视频文件，提取字幕并保存为CSV文件
        
        参数:
            video_file: 视频文件路径或URL
            vocabulary_id: 热词表ID（可选），用于语音识别中的热词支持
            
        返回:
            CSV文件路径或空字符串（处理失败时）
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
            
            logger.info(f"成功提取字幕，共 {len(subtitles)} 条记录，准备保存到CSV文件")
            
            # 保存字幕数据到CSV文件
            output_csv = self._save_subtitles_to_csv(video_file, subtitles)
            
            if not output_csv:
                logger.error(f"保存字幕到CSV文件失败: {video_file}")
                # 即使失败也要尝试清理临时文件
                self.cleanup_downloaded_videos(video_file)
                return ""
            
            logger.info(f"视频处理完成，字幕保存到: {output_csv}")
            
            # 清理临时文件
            self.cleanup_downloaded_videos(video_file)
            
            return output_csv
        
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
        # 如果是URL，获取URL中的文件名
        if video_file.startswith('http'):
            # 从URL中提取文件名
            filename = os.path.basename(urlparse(video_file).path)
            if not filename:
                # 如果URL没有明确的文件名，则无法清理
                logger.warning(f"无法从URL提取文件名: {video_file}")
                return
                
            # 检查temp/downloaded和temp/videos/downloaded目录
            possible_dirs = ['temp/downloaded', 'temp/videos/downloaded']
            for dir_path in possible_dirs:
                if os.path.exists(dir_path):
                    # 查找该目录下与URL文件名匹配的文件
                    for file in os.listdir(dir_path):
                        if file == filename or (file.endswith(os.path.splitext(filename)[1]) and 
                                             urlparse(video_file).netloc in file):
                            file_path = os.path.join(dir_path, file)
                            self._cleanup_temp_files(file_path)
                            
        # 如果是本地路径但在临时目录中
        elif 'temp' in video_file and os.path.exists(video_file):
            self._cleanup_temp_files(video_file)
            
        logger.info(f"视频文件清理完成: {video_file}")

    def _extract_subtitles_from_video(self, video_file: str, vocabulary_id: str = None) -> List[Dict[str, Any]]:
        """
        从视频中提取字幕数据，使用阿里云DashScope服务的Paraformer模型进行语音识别
        
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
                
            # 判断是否为URL链接
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
                return []
            
            # 检查API Key是否已设置
            if not API_KEY:
                logger.error("DashScope API Key未设置，请在环境变量中配置DASHSCOPE_API_KEY")
                return []
            
            # 设置API密钥
            dashscope.api_key = API_KEY
            
            # 首先预处理提取音频文件
            preprocess_start = time.time()
            audio_file = self._preprocess_video_file(video_file)
            preprocess_time = time.time() - preprocess_start
            logger.info(f"预处理视频文件完成，耗时: {preprocess_time:.2f}秒")
            
            if not audio_file:
                logger.error(f"预处理视频失败，无法提取音频: {video_file}")
                return []
            
            if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                logger.error(f"生成的音频文件不存在或为空: {audio_file}")
                return []
            
            # 使用Paraformer录音文件识别API
            logger.info(f"使用DashScope Paraformer录音文件识别API进行语音识别: {audio_file}")
            
            # 构建API调用参数
            api_kwargs = {
                'model': f"paraformer-v2",  # 使用录音文件识别模型
                'format': self._get_audio_format(audio_file),
                'sample_rate': 16000
            }
            
            # 添加语言设置
            if SUBTITLE_LANGUAGE and SUBTITLE_LANGUAGE != "auto":
                api_kwargs['language_hints'] = [SUBTITLE_LANGUAGE]
            else:
                api_kwargs['language_hints'] = ["zh", "en"]  # 默认支持中英文
            
            # 添加热词配置（如果已设置）
            if vocabulary_id and isinstance(vocabulary_id, str) and len(vocabulary_id) > 0:
                logger.info(f"应用热词配置: {vocabulary_id[:5]}{'...' if len(vocabulary_id) > 5 else ''}")
                api_kwargs['vocabulary_id'] = vocabulary_id
            
            # 上传音频文件到可访问的URL
            audio_url = None
            if ENABLE_OSS and OSS_AVAILABLE:
                audio_url = self._upload_to_accessible_url(audio_file)
                if not audio_url:
                    logger.warning("上传音频文件到OSS失败，尝试直接使用本地文件")
            
            if not audio_url:
                # 如果无法上传到OSS，创建一个临时的HTTP服务来提供音频文件
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                temp_dir = os.path.join('data', 'temp', 'audio_server', timestamp)
                os.makedirs(temp_dir, exist_ok=True)
                
                temp_audio_file = os.path.join(temp_dir, os.path.basename(audio_file))
                import shutil
                shutil.copy2(audio_file, temp_audio_file)
                
                # 创建公网可访问的临时URL
                # 注意：这里需要有一个可公网访问的服务来提供这个文件
                # 在实际应用中，应当使用OSS或其他云存储
                logger.warning("无法创建可公网访问的音频URL，语音识别可能会失败")
                return []
            
            # 设置文件URL
            api_kwargs['file_urls'] = [audio_url]
            
            try:
                # 使用录音文件识别API
                api_start_time = time.time()
                
                logger.info(f"开始调用DashScope录音文件识别API... 参数: {api_kwargs}")
                
                # 调用Transcription.async_call方法提交任务
                from dashscope.audio.asr import Transcription
                task_response = Transcription.async_call(**api_kwargs)
                
                if task_response.status_code != 200:
                    logger.error(f"DashScope API调用失败: 状态码={task_response.status_code}, 消息={task_response.message}")
                    return []
                
                # 获取任务ID
                task_id = task_response.output.task_id
                logger.info(f"成功提交语音识别任务，任务ID: {task_id}")
                
                # 等待任务完成
                logger.info("等待语音识别任务完成...")
                transcribe_response = Transcription.wait(task=task_id)
                
                api_time = time.time() - api_start_time
                logger.info(f"DashScope API调用完成，耗时: {api_time:.2f}秒")
                
                # 检查任务状态
                if transcribe_response.status_code != 200:
                    logger.error(f"DashScope API响应错误: 状态码={transcribe_response.status_code}, 消息={transcribe_response.message}")
                    return []
                
                # 验证任务是否成功
                if transcribe_response.output.task_status != "SUCCEEDED":
                    logger.error(f"语音识别任务未成功完成: 状态={transcribe_response.output.task_status}")
                    return []
                
                # 处理结果
                process_start = time.time()
                subtitles = []
                
                # 检查结果是否存在
                if not hasattr(transcribe_response.output, 'results') or not transcribe_response.output.results:
                    logger.error("API响应中没有results字段")
                    return []
                
                # 获取转写结果URL
                results = transcribe_response.output.results
                if not results or len(results) == 0:
                    logger.error("API响应中results为空")
                    return []
                
                # 处理每个文件的结果
                for file_result in results:
                    # 检查子任务状态
                    if file_result.get('subtask_status') != "SUCCEEDED":
                        logger.warning(f"文件处理未成功: {file_result.get('file_url')}, 状态: {file_result.get('subtask_status')}")
                        continue
                    
                    # 获取转写结果URL
                    transcription_url = file_result.get('transcription_url')
                    if not transcription_url:
                        logger.warning(f"文件没有转写结果URL: {file_result.get('file_url')}")
                        continue
                    
                    # 下载转写结果
                    try:
                        logger.info(f"下载转写结果: {transcription_url}")
                        response = requests.get(transcription_url, timeout=30)
                        response.raise_for_status()
                        
                        # 解析JSON结果
                        transcript_data = response.json()
                        
                        # 提取字幕数据
                        if 'transcripts' not in transcript_data:
                            logger.warning(f"转写结果中没有transcripts字段: {file_result.get('file_url')}")
                            continue
                        
                        # 处理每个转写结果
                        for transcript in transcript_data['transcripts']:
                            channel_id = transcript.get('channel_id', 0)
                            
                            # 处理每个句子
                            for i, sentence in enumerate(transcript.get('sentences', [])):
                                # 计算开始和结束时间（毫秒转秒）
                                begin_time_ms = sentence.get('begin_time', 0)
                                end_time_ms = sentence.get('end_time', 0)
                                
                                # 转换为秒
                                start_time_sec = begin_time_ms / 1000.0
                                end_time_sec = end_time_ms / 1000.0
                                
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
                                
                                # 获取说话人ID
                                speaker_id = sentence.get('speaker_id', 0)
                                
                                subtitles.append({
                                    "index": i,
                                    "start": start_time_sec,
                                    "end": end_time_sec,
                                    "start_formatted": start_formatted,
                                    "end_formatted": end_formatted,
                                    "timestamp": start_formatted,
                                    "duration": end_time_sec - start_time_sec,
                                    "text": text,
                                    "speaker_id": speaker_id,
                                    "channel_id": channel_id
                                })
                    except Exception as e:
                        logger.error(f"下载或解析转写结果失败: {str(e)}")
                        continue
                
                process_time = time.time() - process_start
                
                if len(subtitles) == 0:
                    logger.warning("处理后的字幕列表为空")
                    return []
                
                # 按时间排序
                subtitles.sort(key=lambda x: x['start'])
                
                total_time = time.time() - start_time
                logger.info(f"成功从视频中提取了{len(subtitles)}条字幕，总耗时: {total_time:.2f}秒 (预处理: {preprocess_time:.2f}秒, API调用: {api_time:.2f}秒, 结果处理: {process_time:.2f}秒)")
                
                return subtitles
            
            except Exception as api_error:
                # 捕获API调用异常
                logger.exception(f"DashScope API调用异常: {str(api_error)}")
                return []
            
        except Exception as e:
            # 捕获所有其他异常
            logger.exception(f"提取字幕过程中发生未预期的错误: {str(e)}")
            return []
        finally:
            # 确保清理临时文件，无论是否发生异常
            self._cleanup_temp_files(audio_file)
    
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
        上传文件到OSS并获取公网可访问的URL
        
        参数:
            file_path: 本地文件路径
            
        返回:
            公网可访问的URL，上传失败则返回None
        """
        try:
            # 使用OssHandler上传文件
            from utils.oss_handler import OssHandler
            
            # 初始化OssHandler
            oss_handler = OssHandler()
            
            # 创建可访问URL
            logger.info(f"开始上传文件到OSS: {file_path}")
            url = oss_handler.create_accessible_url(file_path)
            
            if url:
                logger.info(f"成功上传文件到OSS: {url}")
                return url
            else:
                logger.error("通过OssHandler上传文件失败")
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

    def _save_subtitles_to_csv(self, video_file: str, subtitles: List[Dict[str, Any]]) -> str:
        """
        将字幕数据保存为CSV文件
        
        参数:
            video_file: 视频文件路径或URL
            subtitles: 字幕数据列表
            
        返回:
            保存的CSV文件路径，如果保存失败则返回空字符串
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
            output_dir = os.path.join(settings.OUTPUT_DIR, 'subtitles')
            logger.info(f"字幕将保存到目录: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名（添加时间戳）
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"{video_name}_{timestamp}.csv"
            output_csv = os.path.join(output_dir, output_filename)
            
            logger.info(f"将保存 {len(subtitles)} 条字幕到文件: {output_csv}")
            
            # 将字幕数据转换为DataFrame
            data = []
            for subtitle in subtitles:
                data.append({
                    'index': subtitle.get('index', 0),
                    'start': subtitle.get('start', 0),
                    'end': subtitle.get('end', 0),
                    'start_formatted': subtitle.get('start_formatted', '00:00:00'),
                    'end_formatted': subtitle.get('end_formatted', '00:00:00'),
                    'timestamp': subtitle.get('timestamp', '00:00:00'),
                    'duration': subtitle.get('duration', 0),
                    'text': subtitle.get('text', '')
                })
            
            # 保存为CSV
            df = pd.DataFrame(data)
            df.to_csv(output_csv, index=False, encoding='utf-8')
            
            # 验证文件是否成功保存
            if os.path.exists(output_csv) and os.path.getsize(output_csv) > 0:
                logger.info(f"字幕数据成功保存到CSV: {output_csv}")
                return output_csv
            else:
                logger.error(f"字幕CSV文件创建失败或为空: {output_csv}")
                return ""
        
        except Exception as e:
            logger.exception(f"保存字幕到CSV失败: {str(e)}")
            return ""
    
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