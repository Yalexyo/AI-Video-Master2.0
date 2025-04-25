#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频处理工具模块：提供视频下载和基础视频处理功能
"""
import os
import logging
import requests
import cv2
import tempfile
import time
from pathlib import Path
from tqdm import tqdm
from typing import Optional, Tuple, Dict, List, Union, Any
from urllib.parse import urlparse
import shutil
import urllib.parse
import subprocess
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

class VideoUtils:
    """视频处理工具类，提供视频下载、格式检测和URL验证功能"""
    
    @staticmethod
    def download_video(url, output_dir=None, filename=None, timeout=120):
        """
        从URL下载视频到指定目录
        
        参数:
            url (str): 视频URL
            output_dir (str, 可选): 输出目录，默认为 data/temp/downloaded
            filename (str, 可选): 输出文件名，默认从URL中提取
            timeout (int, 可选): 下载超时时间（秒），默认120秒
            
        返回:
            str: 下载视频的本地路径，失败则返回None
        """
        try:
            # 验证URL格式
            if not url.startswith(('http://', 'https://')):
                logger.error(f"无效的URL格式: {url}")
                return None
                
            # 创建临时目录
            if not output_dir:
                output_dir = os.path.join("data", "temp", "downloaded")
            
            os.makedirs(output_dir, exist_ok=True)
            
            # 从URL中提取文件名
            if not filename:
                url_path = urllib.parse.urlparse(url).path
                filename = os.path.basename(urllib.parse.unquote(url_path))
                
                # 如果无法从URL提取文件名，使用时间戳生成
                if not filename:
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    filename = f"video_{timestamp}.mp4"
            
            # 确保文件名有扩展名
            if not os.path.splitext(filename)[1]:
                filename = f"{filename}.mp4"
                
            local_path = os.path.join(output_dir, filename)
            
            # 检查文件是否已存在
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                if file_size > 0:
                    logger.info(f"文件已存在，跳过下载: {local_path} ({file_size} 字节)")
                    return local_path
            
            logger.info(f"开始下载视频: {url} -> {local_path}")
            start_time = time.time()
            
            # 下载文件
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()  # 确保请求成功
                
                # 获取内容长度（如果有）
                total_size = int(response.headers.get('content-length', 0))
                
                # 写入文件
                with open(local_path, 'wb') as file:
                    if total_size > 0:
                        # 如果知道总大小，显示下载进度
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                file.write(chunk)
                                downloaded += len(chunk)
                                
                                # 记录下载进度，每10%记录一次
                                progress = downloaded / total_size
                                if progress % 0.1 < 0.01:  # 约每10%记录一次
                                    logger.info(f"下载进度: {progress:.1%}")
                    else:
                        # 如果不知道总大小，直接写入
                        shutil.copyfileobj(response.raw, file)
            
            download_time = time.time() - start_time
            file_size = os.path.getsize(local_path)
            
            if file_size == 0:
                logger.error(f"下载失败: 文件大小为0 ({url})")
                os.remove(local_path)
                return None
                
            logger.info(f"视频下载完成: {local_path} ({file_size} 字节, 耗时 {download_time:.2f} 秒)")
            return local_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"下载视频失败 - 网络错误: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"下载视频失败: {str(e)}")
            return None
    
    @staticmethod
    def is_valid_video_url(url):
        """
        验证URL是否指向有效的视频文件
        
        参数:
            url (str): 要验证的URL
            
        返回:
            bool: URL有效返回True，否则返回False
        """
        # 检查URL格式
        if not url.startswith(('http://', 'https://')):
            return False
            
        try:
            # 尝试获取文件头，不下载完整内容
            response = requests.head(url, timeout=10)
            
            # 检查状态码
            if response.status_code != 200:
                return False
                
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if content_type.startswith('video/'):
                return True
                
            # 如果内容类型不明确，检查文件扩展名
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']
            url_path = urllib.parse.urlparse(url).path.lower()
            if any(url_path.endswith(ext) for ext in video_extensions):
                return True
                
            return False
            
        except requests.exceptions.RequestException:
            return False
            
    @staticmethod
    def get_video_info(video_path):
        """
        获取视频文件的基本信息（时长、分辨率等）
        
        参数:
            video_path (str): 视频文件的本地路径
            
        返回:
            dict: 包含视频信息的字典，如果失败则返回None
        """
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return None
            
        try:
            # 尝试使用ffprobe获取视频信息
            if shutil.which('ffprobe'):
                cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,duration,bit_rate,codec_name',
                    '-show_entries', 'format=duration,size,bit_rate',
                    '-of', 'json',
                    video_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout:
                    import json
                    info = json.loads(result.stdout)
                    
                    # 提取关键信息
                    video_info = {}
                    
                    # 从stream中提取信息
                    if 'streams' in info and info['streams']:
                        stream = info['streams'][0]
                        video_info['width'] = stream.get('width')
                        video_info['height'] = stream.get('height')
                        video_info['codec'] = stream.get('codec_name')
                        video_info['duration'] = float(stream.get('duration', 0))
                        video_info['bitrate'] = int(stream.get('bit_rate', 0))
                        
                    # 从format中提取信息
                    if 'format' in info:
                        format_info = info['format']
                        if 'duration' not in video_info and 'duration' in format_info:
                            video_info['duration'] = float(format_info.get('duration', 0))
                        if 'size' in format_info:
                            video_info['size'] = int(format_info.get('size', 0))
                        if 'bitrate' not in video_info and 'bit_rate' in format_info:
                            video_info['bitrate'] = int(format_info.get('bit_rate', 0))
                            
                    return video_info
            
            # 如果ffprobe不可用，返回基本文件信息
            file_info = {
                'size': os.path.getsize(video_path),
                'file_name': os.path.basename(video_path),
                'path': video_path
            }
            return file_info
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            return None

def validate_video_file(file_path: str) -> bool:
    """
    验证视频文件是否有效
    
    参数:
        file_path: 视频文件路径
        
    返回:
        文件有效则返回True，否则返回False
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False
            
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"文件大小为0: {file_path}")
            return False
            
        # 使用OpenCV验证视频
        cap = cv2.VideoCapture(file_path)
        
        if not cap.isOpened():
            logger.error(f"无法打开视频文件: {file_path}")
            cap.release()
            return False
            
        # 获取视频信息
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 读取几帧来验证视频是否可读
        frame_valid = False
        for _ in range(min(10, frame_count)):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                frame_valid = True
                break
                
        cap.release()
        
        if not frame_valid:
            logger.error(f"无法从视频中读取有效帧: {file_path}")
            return False
            
        # 记录视频信息
        logger.info(f"视频验证成功: {file_path}, 分辨率: {width}x{height}, "
                   f"FPS: {fps}, 总帧数: {frame_count}")
        
        return True
        
    except Exception as e:
        logger.exception(f"验证视频文件失败: {str(e)}")
        return False

def get_video_info(file_path: str) -> Dict[str, Any]:
    """
    获取视频文件的基本信息
    
    参数:
        file_path: 视频文件路径
        
    返回:
        包含视频信息的字典，失败时返回空字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return {}
            
        # 使用OpenCV获取视频信息
        cap = cv2.VideoCapture(file_path)
        
        if not cap.isOpened():
            logger.error(f"无法打开视频文件: {file_path}")
            cap.release()
            return {}
            
        # 获取视频基本信息
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        # 获取视频格式
        format_name = os.path.splitext(file_path)[1].lstrip('.').lower()
        
        # 检查是否有音频（OpenCV无法直接检测，这里只是占位）
        has_audio = None  # 需要使用ffmpeg或其他工具检测
        
        # 读取一帧作为预览
        ret, _ = cap.read()
        is_valid = ret
        
        # 释放资源
        cap.release()
        
        video_info = {
            "path": file_path,
            "filename": os.path.basename(file_path),
            "format": format_name,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "size_bytes": os.path.getsize(file_path),
            "size_mb": os.path.getsize(file_path) / (1024 * 1024),
            "has_audio": has_audio,
            "is_valid": is_valid,
            "last_modified": os.path.getmtime(file_path)
        }
        
        return video_info
        
    except Exception as e:
        logger.exception(f"获取视频信息失败: {str(e)}")
        return {}

def format_duration(seconds: float) -> str:
    """
    将秒数格式化为时分秒格式
    
    参数:
        seconds: 秒数
        
    返回:
        格式化的时间字符串 (HH:MM:SS)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def extract_frames(video_path: str, 
                  output_dir: str, 
                  frame_interval: int = 1,
                  max_frames: Optional[int] = None) -> List[str]:
    """
    从视频中提取帧并保存为图像
    
    Args:
        video_path: 视频文件路径
        output_dir: 帧图像输出目录
        frame_interval: 提取帧的间隔数量
        max_frames: 最大提取帧数，None表示不限制
        
    Returns:
        保存的帧图像文件路径列表
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return []
            
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频文件: {video_path}")
            return []
            
        frame_paths = []
        frame_count = 0
        saved_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                frame_path = os.path.join(output_dir, f"frame_{saved_count:04d}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)
                saved_count += 1
                
                if max_frames and saved_count >= max_frames:
                    break
                    
            frame_count += 1
            
        cap.release()
        logger.info(f"已从视频提取 {saved_count} 帧图像")
        return frame_paths
        
    except Exception as e:
        logger.error(f"提取视频帧失败: {str(e)}")
        return []

def download_video(url, target_path, filename=None, chunk_size=8192, retries=3, retry_delay=2):
    """
    从URL下载视频文件到指定路径
    
    参数:
        url (str): 视频文件的URL
        target_path (str): 保存视频的目标目录
        filename (str, optional): 指定文件名，如果为None则从URL中提取
        chunk_size (int): 下载时的块大小，默认8192字节
        retries (int): 下载失败时的重试次数
        retry_delay (int): 重试之间的延迟秒数
    
    返回:
        str: 下载完成的视频文件完整路径
    """
    # 确保目标目录存在
    os.makedirs(target_path, exist_ok=True)
    
    # 如果未指定文件名，从URL中提取
    if not filename:
        filename = os.path.basename(url.split('?')[0])
        if not filename:
            filename = f"video_{int(time.time())}.mp4"
    
    # 构建完整的文件路径
    file_path = os.path.join(target_path, filename)
    
    # 检查文件是否已存在，避免重复下载
    if os.path.exists(file_path):
        logging.info(f"文件已存在: {file_path}")
        return file_path
    
    # 下载文件，带有重试机制
    for attempt in range(retries):
        try:
            logging.info(f"开始下载视频: {url} -> {file_path}")
            
            # 发起请求并获取文件大小
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                # 使用tqdm显示下载进度
                with open(file_path, 'wb') as f, tqdm(
                    desc=filename,
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            size = f.write(chunk)
                            bar.update(size)
            
            logging.info(f"视频下载完成: {file_path}")
            return file_path
            
        except (requests.RequestException, IOError) as e:
            logging.error(f"下载失败 (尝试 {attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                logging.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                logging.error(f"所有重试都失败，无法下载视频: {url}")
                raise

def get_video_info(video_path):
    """
    获取视频文件的基本信息（不依赖FFmpeg）
    
    参数:
        video_path (str): 视频文件路径
    
    返回:
        dict: 包含视频文件信息的字典
    """
    file_path = Path(video_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    
    # 获取基本文件信息
    info = {
        "filename": file_path.name,
        "path": str(file_path.absolute()),
        "size_bytes": file_path.stat().st_size,
        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "last_modified": time.ctime(file_path.stat().st_mtime),
    }
    
    return info

def save_analysis_results(results, output_path=None, filename=None, format='json'):
    """
    保存视频分析结果到文件
    
    参数:
        results: 分析结果数据（字典或列表）
        output_path: 输出目录路径，默认为 'data/results'
        filename: 输出文件名，默认根据时间戳自动生成
        format: 输出格式，支持 'json' 或 'csv'
        
    返回:
        str: 保存结果文件的完整路径
    """
    import json
    import pandas as pd
    from datetime import datetime
    
    # 设置默认输出目录
    if not output_path:
        output_path = os.path.join('data', 'results')
    
    # 确保输出目录存在
    os.makedirs(output_path, exist_ok=True)
    
    # 生成默认文件名
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"analysis_result_{timestamp}"
    
    # 确保文件名有正确的扩展名
    if not filename.endswith(f'.{format}'):
        filename = f"{filename}.{format}"
    
    # 完整文件路径
    file_path = os.path.join(output_path, filename)
    
    # 根据格式保存数据
    try:
        if format.lower() == 'json':
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"分析结果已保存为JSON: {file_path}")
            
        elif format.lower() == 'csv':
            # 尝试将结果转换为DataFrame
            if isinstance(results, dict):
                # 如果有matches键，使用它
                if 'matches' in results:
                    df = pd.DataFrame(results['matches'])
                else:
                    # 尝试将字典转换为单行DataFrame
                    df = pd.DataFrame([results])
            elif isinstance(results, list):
                df = pd.DataFrame(results)
            else:
                raise ValueError(f"无法将类型 {type(results)} 转换为CSV格式")
                
            # 保存为CSV
            df.to_csv(file_path, index=False, encoding='utf-8')
            logger.info(f"分析结果已保存为CSV: {file_path}")
            
        else:
            raise ValueError(f"不支持的输出格式: {format}，仅支持 'json' 或 'csv'")
            
        return file_path
        
    except Exception as e:
        logger.error(f"保存分析结果失败: {str(e)}")
        raise

if __name__ == "__main__":
    # 测试代码
    pass