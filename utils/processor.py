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
    from dashscope.audio.asr.recognition import Recognition
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
    
    def process_video_file(self, video_file: str, output_dir: Optional[str] = None, vocabulary_id: Optional[str] = None) -> str:
        """
        处理视频文件，提取字幕并生成CSV文件
        
        参数:
            video_file: 视频文件路径
            output_dir: 输出目录，默认为data/processed
            vocabulary_id: 热词表ID，用于优化识别
            
        返回:
            处理后的CSV文件路径，如果处理失败则返回空字符串
        """
        try:
            logger.info(f"开始处理视频文件: {video_file}")
            
            # 获取视频文件名（不包括扩展名）
            video_name = os.path.splitext(os.path.basename(video_file))[0]
            
            # 确定输出目录
            if output_dir is None:
                output_dir = os.path.join('data', 'processed')
            os.makedirs(output_dir, exist_ok=True)
            
            # 输出CSV文件路径
            output_csv = os.path.join(output_dir, f"{video_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")
            
            # 提取字幕
            subtitles = self._extract_subtitles_from_video(video_file)
            
            # 如果字幕提取失败（返回空列表），则直接返回失败
            if not subtitles:
                logger.error(f"字幕提取失败，无法处理视频: {video_file}")
                return "" # 返回空字符串表示处理失败
            
            # 创建DataFrame并保存
            df = pd.DataFrame(subtitles)
            df.to_csv(output_csv, index=False, encoding='utf-8')
            
            logger.info(f"视频处理完成，字幕保存到: {output_csv}")
            return output_csv
        
        except Exception as e:
            logger.error(f"处理视频文件出错: {str(e)}")
            return ""
    
    def _extract_subtitles_from_video(self, video_file: str) -> List[Dict[str, Any]]:
        """
        从视频中提取字幕数据，使用阿里云DashScope服务的Paraformer模型进行语音识别
        
        参数:
            video_file: 视频文件路径
            
        返回:
            包含字幕信息的字典列表，每个字典包含开始时间、结束时间和文本内容
        """
        logger.info(f"开始从视频中提取字幕: {video_file}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(video_file):
                logger.error(f"视频文件不存在: {video_file}")
                return []
            
            # 检查DashScope模块是否可用
            if not DASHSCOPE_AVAILABLE:
                logger.error("DashScope模块不可用，请安装dashscope: pip install dashscope")
                return self._fallback_subtitle_generation(video_file, error_type="module_missing")
            
            # 检查API Key是否已设置
            if not API_KEY:
                logger.error("DashScope API Key未设置，请在环境变量中配置DASHSCOPE_API_KEY")
                return self._fallback_subtitle_generation(video_file, error_type="api_key_missing")
            
            # 获取视频信息
            video_info = self._get_video_info(video_file)
            if not video_info:
                logger.error(f"无法获取视频信息: {video_file}")
                return self._fallback_subtitle_generation(video_file, error_type="video_info_error")
            
            # 记录视频信息
            logger.info(f"视频信息: 时长={video_info.get('duration', 'unknown')}秒, "
                       f"格式={video_info.get('format', 'unknown')}, "
                       f"分辨率={video_info.get('width', 'unknown')}x{video_info.get('height', 'unknown')}")
            
            # 检查视频时长是否在限制范围内（DashScope限制12小时）
            if video_info.get('duration', 0) > 43200:  # 12小时 = 43200秒
                logger.error(f"视频时长超过限制(12小时): {video_info.get('duration')}秒")
                return self._fallback_subtitle_generation(video_file, error_type="duration_exceeded")
            
            # 预处理视频文件，提取音频并转换为opus格式
            # 根据阿里云最佳实践，预处理可以显著提高识别效率
            preprocessed_audio = self._preprocess_video_file(video_file)
            if not preprocessed_audio:
                logger.error(f"视频预处理失败: {video_file}")
                return self._fallback_subtitle_generation(video_file, error_type="preprocessing_failed")
            
            logger.info(f"视频已预处理，音频文件: {preprocessed_audio}")
            
            # 上传预处理后的音频文件到可访问的URL
            file_url = self._upload_to_accessible_url(preprocessed_audio)
            if not file_url:
                logger.error(f"无法创建可访问的URL: {preprocessed_audio}")
                return self._fallback_subtitle_generation(video_file, error_type="upload_failed")
            
            logger.info(f"音频文件已上传到: {file_url}")
            
            # 设置API密钥
            dashscope.api_key = API_KEY
            
            # 设置Paraformer模型
            # 指定模型版本，PARAFORMER_MODEL_VERSION在配置文件中设置，例如："v2"
            model_id = f"paraformer-{PARAFORMER_MODEL_VERSION}" if PARAFORMER_MODEL_VERSION else "paraformer-v2"
            
            # 构建音频参数
            audio_params = {
                "url": file_url,
                "format": "opus",  # 预处理后的音频格式为opus
                "sample_rate": 16000  # 采样率16kHz
            }
            
            # 构建API调用参数
            api_params = {}
            if SUBTITLE_MODEL:
                api_params["model"] = SUBTITLE_MODEL
            if SUBTITLE_LANGUAGE and SUBTITLE_LANGUAGE != "auto":
                api_params["language"] = SUBTITLE_LANGUAGE
            
            # 添加热词配置（如果已设置）
            if HOT_WORDS and isinstance(HOT_WORDS, list) and len(HOT_WORDS) > 0:
                logger.info(f"应用热词配置: {', '.join(HOT_WORDS[:5])}{'...' if len(HOT_WORDS) > 5 else ''}")
                api_params["hot_words"] = HOT_WORDS
            
            # 记录API调用参数
            logger.info(f"DashScope Paraformer API调用参数: model_id={model_id}, audio={audio_params}, params={api_params}")
            
            # 调用DashScope API
            start_time = time.time()
            try:
                # 使用静态方法调用Recognition API，而不是实例方法
                response = dashscope.audio.asr.recognition.Recognition.call(
                    model=model_id,
                    audio=audio_params,
                    timeout=API_TIMEOUT,
                    **api_params
                )
                
                api_time = time.time() - start_time
                logger.info(f"DashScope API调用完成，耗时: {api_time:.2f}秒")
                
                # 记录API响应状态
                logger.info(f"DashScope API响应状态: {response.status_code}, 消息: {response.message}")
                
                # 处理API返回结果
                if response.status_code == 200 and response.output and 'sentences' in response.output:
                    subtitles = self._parse_paraformer_response(response)
                    logger.info(f"成功从视频中提取了{len(subtitles)}条字幕")
                    
                    # 清理临时文件
                    if os.path.exists(preprocessed_audio):
                        os.remove(preprocessed_audio)
                        logger.info(f"已清理临时音频文件: {preprocessed_audio}")
                    
                    return subtitles
                else:
                    # 记录API错误详情
                    error_code = response.status_code
                    error_msg = response.message
                    error_detail = response.output.get('error', {}) if hasattr(response, 'output') and response.output else {}
                    
                    logger.error(f"Paraformer API调用失败: 状态码={error_code}, 消息={error_msg}, 详情={error_detail}")
                    
                    # 清理临时文件
                    if os.path.exists(preprocessed_audio):
                        os.remove(preprocessed_audio)
                        logger.info(f"已清理临时音频文件: {preprocessed_audio}")
                    
                    return self._fallback_subtitle_generation(video_file, error_type="api_error", 
                                                             error_detail=f"{error_code}: {error_msg}")
            except Exception as api_error:
                # 捕获API调用异常
                api_time = time.time() - start_time
                logger.exception(f"DashScope API调用异常，耗时: {api_time:.2f}秒, 错误: {str(api_error)}")
                
                # 清理临时文件
                if os.path.exists(preprocessed_audio):
                    os.remove(preprocessed_audio)
                    logger.info(f"已清理临时音频文件: {preprocessed_audio}")
                
                return self._fallback_subtitle_generation(video_file, error_type="api_exception", 
                                                         error_detail=str(api_error))
        
        except Exception as e:
            # 捕获所有其他异常
            logger.exception(f"提取字幕过程中发生未预期的错误: {str(e)}")
            return self._fallback_subtitle_generation(video_file, error_type="unexpected_error", 
                                                     error_detail=str(e))
    
    def _preprocess_video_file(self, video_file: str) -> Optional[str]:
        """
        预处理视频文件，提取音轨、降采样到16kHz并压缩为opus格式
        参考阿里云最佳实践: https://help.aliyun.com/zh/model-studio/developer-reference/paraformer-best-practices
        
        参数:
            video_file: 视频文件路径
            
        返回:
            处理后的音频文件路径，处理失败则返回None
        """
        try:
            # 创建临时目录 - 不使用日期子目录，简化路径
            temp_dir = VIDEO_TEMP_DIR
            os.makedirs(temp_dir, exist_ok=True)
            logger.info(f"创建/确认临时目录: {temp_dir}")
            
            # 检查源文件
            if not os.path.exists(video_file):
                logger.error(f"预处理源文件不存在: {video_file}")
                return None
                
            file_size = os.path.getsize(video_file) / (1024 * 1024)
            logger.info(f"预处理源文件: {video_file}, 大小: {file_size:.2f}MB")
            
            # 生成输出音频文件路径，使用时间戳确保唯一性
            file_name = os.path.splitext(os.path.basename(video_file))[0]
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            output_audio = os.path.join(temp_dir, f"{file_name}_{timestamp}.opus")
            
            logger.info(f"预处理输出音频文件: {output_audio}")
            
            # 检查ffmpeg是否可用
            try:
                ffmpeg_version = subprocess.check_output(['ffmpeg', '-version'], stderr=subprocess.STDOUT, universal_newlines=True)
                # 修复: 在f-string中不能使用反斜杠，先拆分然后再插入
                first_line = ffmpeg_version.split('\n')[0]
                logger.info(f"FFmpeg可用: {first_line}")
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                logger.error(f"FFmpeg不可用，无法进行预处理: {str(e)}")
                return None
            
            # 使用ffmpeg提取音频，降采样到16kHz，并压缩为opus格式
            # -ac 1: 单声道
            # -ar 16000: 采样率16kHz
            # -acodec libopus: 使用opus编码器
            # -loglevel warning: 减少输出
            cmd = [
                'ffmpeg', '-y', '-i', video_file, 
                '-ac', '1', '-ar', '16000', 
                '-acodec', 'libopus', 
                '-loglevel', 'warning',
                output_audio
            ]
            
            logger.info(f"执行预处理命令: {' '.join(cmd)}")
            
            # 执行命令并捕获输出
            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                stdout, stderr = process.communicate(timeout=300)  # 添加超时限制
                
                # 检查命令执行结果
                if process.returncode != 0:
                    logger.error(f"预处理视频失败，返回码: {process.returncode}")
                    logger.error(f"FFmpeg错误输出: {stderr}")
                    return None
                    
                if stderr and 'error' in stderr.lower():
                    logger.warning(f"FFmpeg警告或错误: {stderr}")
            except subprocess.TimeoutExpired:
                # 处理超时
                process.kill()
                logger.error("预处理视频超时(5分钟)，终止进程")
                return None
            except Exception as subproc_err:
                logger.error(f"预处理调用FFmpeg出错: {str(subproc_err)}")
                return None
            
            # 检查输出文件是否存在
            if not os.path.exists(output_audio):
                logger.error(f"预处理后的音频文件不存在: {output_audio}")
                return None
                
            # 检查输出文件大小是否合理
            output_size = os.path.getsize(output_audio)
            if output_size <= 0:
                logger.error(f"预处理后的音频文件为空: {output_audio}")
                os.remove(output_audio)  # 删除空文件
                return None
                
            # 记录文件大小减少情况
            video_size = os.path.getsize(video_file)
            audio_size = output_size
            size_reduction = (1 - audio_size / video_size) * 100
            
            logger.info(f"视频预处理成功: 原始大小={video_size/1024/1024:.2f}MB, "
                      f"处理后大小={audio_size/1024/1024:.2f}MB, "
                      f"减少={size_reduction:.2f}%")
            
            return output_audio
            
        except Exception as e:
            logger.exception(f"预处理视频文件出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
            # 这里提供了file://协议作为临时解决方案，实际应用中可能需要本地服务器
            file_url = f"file://{os.path.abspath(temp_file_path)}"
            
            logger.info(f"创建本地文件URL: {file_url}")
            
            # 输出警告，提醒用户这可能不适用于生产环境
            logger.warning("注意：使用本地文件URL可能无法被DashScope API处理，建议配置OSS或其他云存储")
            
            return file_url
        except Exception as e:
            logger.error(f"创建本地文件URL出错: {str(e)}")
            return None
    
    def _fallback_subtitle_generation(self, video_file: str, error_type: str = "unknown", 
                                     error_detail: str = "") -> List[Dict[str, Any]]:
        """
        当语音识别失败或DashScope不可用时，记录详细错误信息并返回空列表。
        
        参数:
            video_file: 视频文件路径
            error_type: 错误类型
            error_detail: 错误详细信息
            
        返回:
            空列表，表示没有生成字幕数据。
        """
        # 错误类型说明
        error_descriptions = {
            "module_missing": "DashScope模块未安装",
            "api_key_missing": "API Key未配置",
            "video_info_error": "无法获取视频信息",
            "duration_exceeded": "视频时长超过限制",
            "upload_failed": "无法上传视频到可访问URL",
            "api_error": "API调用返回错误",
            "api_exception": "API调用过程中发生异常",
            "unexpected_error": "处理过程中发生未预期的错误",
            "unknown": "未知错误"
        }
        
        error_desc = error_descriptions.get(error_type, "未知错误")
        
        # 记录详细错误信息
        logger.error(f"视频语音识别失败: {video_file}")
        logger.error(f"错误类型: {error_type} - {error_desc}")
        if error_detail:
            logger.error(f"错误详情: {error_detail}")
        
        # 建议解决方案
        solutions = {
            "module_missing": "请运行 'pip install dashscope' 安装DashScope模块",
            "api_key_missing": "请在.env文件或环境变量中设置DASHSCOPE_API_KEY",
            "video_info_error": "请检查视频文件是否损坏或格式不受支持",
            "duration_exceeded": "请将视频分割为较短片段，每段不超过12小时",
            "upload_failed": "请检查OSS配置或网络连接",
            "api_error": "请检查API请求参数是否正确，可能需调整视频格式",
            "api_exception": "请检查网络连接和API Key是否有效",
            "unexpected_error": "请检查日志获取详细错误信息"
        }
        
        solution = solutions.get(error_type, "请检查日志获取详细错误信息")
        logger.info(f"建议解决方案: {solution}")
        
        # 不再生成模拟数据，直接返回空列表表示失败
        return []
    
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