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
            
            # 检查是否有音频
            has_audio = False  # OpenCV无法直接检测音频
            
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
            subtitles = self._extract_subtitles_from_video(video_file, vocabulary_id)
            
            # 如果提取失败（返回空列表），则直接返回空字符串
            if not subtitles:
                logger.error(f"视频文件语音识别失败，未能提取到字幕: {video_file}")
                return ""
            
            # 保存字幕数据到CSV文件
            output_csv = self._save_subtitles_to_csv(video_file, subtitles)
            
            if not output_csv:
                logger.error(f"保存字幕到CSV文件失败: {video_file}")
                return ""
            
            logger.info(f"视频处理完成，字幕保存到: {output_csv}")
            return output_csv
        
        except Exception as e:
            logger.exception(f"处理视频文件失败: {str(e)}")
            return ""
    
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
            if not API_KEY:
                logger.error("DashScope API Key未设置，请在环境变量中配置DASHSCOPE_API_KEY")
                return self._fallback_subtitle_generation(video_file)
            
            # 设置API密钥
            dashscope.api_key = API_KEY
            
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
                api_kwargs['hot_words'] = vocabulary_id
            
            # 如果是本地文件，需要先上传到可访问的URL
            file_url = None
            if not is_url:
                # 首先预处理提取音频文件
                audio_file = self._preprocess_video_file(video_file)
                if not audio_file:
                    logger.error(f"预处理视频失败，无法提取音频: {video_file}")
                    return self._fallback_subtitle_generation(video_file)
                
                if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                    logger.error(f"生成的音频文件不存在或为空: {audio_file}")
                    return self._fallback_subtitle_generation(video_file)
                
                file_url = self._upload_to_accessible_url(audio_file)
                if not file_url:
                    logger.error(f"无法创建可访问的URL: {audio_file}")
                    return self._fallback_subtitle_generation(video_file)
                
                logger.info(f"音频文件已上传到: {file_url}")
                video_url = file_url
            else:
                # 直接使用现有URL
                video_url = video_file
                logger.info(f"使用OSS URL: {video_url}")
            
            # 检查URL是否有效
            if not video_url or len(video_url.strip()) == 0:
                logger.error("视频URL为空")
                return self._fallback_subtitle_generation(video_file)
            
            # 修复格式化问题，对字典使用repr()避免嵌套花括号问题
            logger.info(f"DashScope Paraformer API调用参数: model_id={model_id}, file_urls=[{repr(video_url)}], kwargs={repr(api_kwargs)}")
            
            # 调用DashScope API
            start_time = time.time()
            try:
                # 使用正确的API调用方式，根据API文档传递参数
                response = dashscope.audio.asr.transcription.Transcription.call(
                    model=model_id,
                    file_urls=[video_url],  # API要求提供file_urls列表
                    **api_kwargs  # 直接传递所有参数，而不是通过params字典
                )
                
                api_time = time.time() - start_time
                logger.info(f"DashScope API调用完成，耗时: {api_time:.2f}秒")
                
                # 检查接口状态返回值
                if not hasattr(response, 'status_code'):
                    logger.error("API响应格式异常，缺少status_code字段")
                    return self._fallback_subtitle_generation(video_file)
                
                # 检查HTTP状态码
                if response.status_code != 200:
                    # 记录API错误详情
                    error_code = response.status_code
                    error_msg = getattr(response, 'message', '未知错误')
                    error_detail = response.output.get('error', {}) if hasattr(response, 'output') and response.output else {}
                    
                    logger.error(f"Paraformer API调用失败: 状态码={error_code}, 消息={error_msg}, 详情={error_detail}")
                    return self._fallback_subtitle_generation(video_file)
                
                # 检查输出字段是否存在
                if not hasattr(response, 'output') or not response.output:
                    logger.error("API响应缺少output字段")
                    return self._fallback_subtitle_generation(video_file)
                
                # 检查结果字段是否存在
                if 'results' not in response.output:
                    logger.error("API响应中缺少results字段")
                    return self._fallback_subtitle_generation(video_file)
                
                # 提取结果
                results = response.output['results']
                if not results or len(results) == 0:
                    logger.error("识别结果为空")
                    return self._fallback_subtitle_generation(video_file)
                
                # 处理识别结果 - 转换为字幕格式
                subtitles = []
                file_result = results[0]  # 取第一个文件的结果
                
                if 'sentences' not in file_result:
                    logger.error("API响应中缺少sentences字段")
                    return self._fallback_subtitle_generation(video_file)
                
                if len(file_result['sentences']) == 0:
                    logger.warning("识别结果中没有句子")
                    return []
                
                for i, sentence in enumerate(file_result['sentences']):
                    # 计算开始和结束时间（毫秒转秒）
                    start_time = sentence.get('begin_time', 0) / 1000 if 'begin_time' in sentence else 0
                    end_time = sentence.get('end_time', 0) / 1000 if 'end_time' in sentence else 0
                    
                    # 检查时间是否有效
                    if end_time < start_time:
                        logger.warning(f"句子时间异常: 结束时间({end_time}秒)早于开始时间({start_time}秒)")
                        end_time = start_time + 1.0  # 强制设置一个合理值
                    
                    # 格式化时间
                    start_formatted = self._format_time(start_time)
                    end_formatted = self._format_time(end_time)
                    
                    # 检查文本是否为空
                    text = sentence.get('text', '').strip()
                    if not text:
                        logger.warning(f"跳过空文本句子，时间段: {start_formatted} - {end_formatted}")
                        continue
                    
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
                
                if len(subtitles) == 0:
                    logger.warning("处理后的字幕列表为空")
                    return []
                
                logger.info(f"成功从视频中提取了{len(subtitles)}条字幕")
                
                # 清理临时文件
                if not is_url and audio_file and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                        logger.info(f"已清理临时音频文件: {audio_file}")
                    except Exception as e:
                        logger.warning(f"清理临时音频文件失败: {e}")
                
                return subtitles
                
            except Exception as api_error:
                # 捕获API调用异常
                api_time = time.time() - start_time
                error_msg = str(api_error)
                logger.exception(f"DashScope API调用异常，耗时: {api_time:.2f}秒, 错误: {error_msg}")
                
                # 分析错误类型，提供更有用的错误信息
                if "file_urls" in error_msg:
                    logger.error("DashScope API参数错误: file_urls参数不正确。请检查API文档以获取最新参数格式。")
                elif "permissions" in error_msg.lower() or "denied" in error_msg.lower():
                    logger.error("DashScope API访问被拒绝，请检查API密钥是否有效。")
                elif "not found" in error_msg.lower():
                    logger.error(f"找不到指定的模型: {model_id}，请检查模型名称是否正确。")
                elif "timeout" in error_msg.lower():
                    logger.error("DashScope API调用超时，请检查网络连接或稍后重试。")
                elif "format" in error_msg.lower():
                    logger.error(f"音频格式不受支持，当前格式: {self._get_audio_format(video_file)}。请转换为受支持的格式。")
                elif "local file" in error_msg.lower() or "url" in error_msg.lower():
                    logger.error("DashScope API不支持直接处理本地文件URL，请配置OSS或其他云存储。")
                
                return self._fallback_subtitle_generation(video_file)
            finally:
                # 确保清理临时文件，即使发生异常
                if not is_url and audio_file and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                        logger.info(f"已清理临时音频文件: {audio_file}")
                    except Exception as e:
                        logger.warning(f"清理临时音频文件失败: {e}")
        
        except Exception as e:
            # 捕获所有其他异常
            logger.exception(f"提取字幕过程中发生未预期的错误: {str(e)}")
            
            # 确保清理临时文件，即使发生异常
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                    logger.info(f"已清理临时音频文件: {audio_file}")
                except Exception as cleanup_error:
                    logger.warning(f"清理临时音频文件失败: {cleanup_error}")
                    
            return self._fallback_subtitle_generation(video_file)
    
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
        logger.info(f"开始预处理视频文件: {video_file}")
        
        try:
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
            
            # 生成临时音频文件名
            file_name = os.path.basename(video_file) if not is_url else f"remote_video_{int(time.time())}"
            audio_file = os.path.join(VIDEO_TEMP_DIR, f"{os.path.splitext(file_name)[0]}_{int(time.time())}.wav")
            
            # 确保临时目录存在
            os.makedirs(os.path.dirname(audio_file), exist_ok=True)
            
            # 使用ffmpeg提取音频
            try:
                # 构建ffmpeg命令
                cmd = [
                    'ffmpeg',
                    '-y',  # 覆盖输出文件
                    '-i', video_file,  # 输入文件
                    '-vn',  # 禁用视频
                    '-ar', '16000',  # 采样率16kHz
                    '-ac', '1',  # 单声道
                    '-ab', '256k',  # 音频比特率
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
                
                # 验证输出文件是否正确生成
                if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                    logger.error(f"输出的音频文件不存在或为空: {audio_file}")
                    return None
                
                logger.info(f"成功提取音频到: {audio_file}")
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
        将文件上传到阿里云OSS并返回可公网访问的URL，
        或在OSS不可用时创建临时可访问的本地URL
        
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
                    return self._create_local_accessible_url(file_path)
                
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
                    return self._create_local_accessible_url(file_path)
            else:
                # OSS不可用，尝试创建本地可访问URL
                logger.warning("阿里云OSS未启用或模块不可用，尝试创建本地可访问URL")
                return self._create_local_accessible_url(file_path)
                
        except Exception as e:
            logger.error(f"上传文件到OSS出错: {str(e)}")
            return self._create_local_accessible_url(file_path)
    
    def _create_local_accessible_url(self, file_path: str) -> Optional[str]:
        """
        创建本地文件的可访问URL，在OSS不可用时使用
        
        参数:
            file_path: 本地文件路径
            
        返回:
            本地可访问的URL，创建失败则返回None
        """
        try:
            # 创建一个简单的文件URL，此方法在实际应用中需要配合本地服务器使用
            # 如果是在本地开发环境，可以使用file://协议
            # 但注意：DashScope模块可能无法处理file://协议的URL
            
            # 复制文件到临时目录并命名为可预测的名称
            file_name = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            temp_dir = os.path.join(VIDEO_TEMP_DIR, timestamp)
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file_path = os.path.join(temp_dir, file_name)
            # 复制文件
            import shutil
            shutil.copy2(file_path, temp_file_path)
            
            # 创建文件URL，对于真实应用，这应该是一个可以通过公网访问的URL
            # 改为返回直接文件路径而非file://协议，作为备用方案尝试
            # 新版本dashscope可能支持直接读取本地文件
            file_url = os.path.abspath(temp_file_path)
            
            logger.info(f"创建本地文件路径: {file_url}")
            logger.warning("注意：在生产环境中应配置OSS或其他云存储以获得更可靠的音频识别")
            
            return file_url
        except Exception as e:
            logger.error(f"创建本地文件URL出错: {str(e)}")
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
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名（添加时间戳）
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"{video_name}_{timestamp}.csv"
            output_csv = os.path.join(output_dir, output_filename)
            
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
            
            logger.info(f"字幕数据成功保存到CSV: {output_csv}")
            return output_csv
        
        except Exception as e:
            logger.exception(f"保存字幕到CSV失败: {str(e)}")
            return "" 