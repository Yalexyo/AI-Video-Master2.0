#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
视频修复工具，用于安全加载视频文件并验证视频文件的完整性
"""

import os
import logging
import subprocess
import tempfile
from typing import Tuple, Optional, Dict, Any
from moviepy.editor import VideoFileClip

# 配置日志
logger = logging.getLogger(__name__)

def validate_video_file(video_path: str) -> Tuple[bool, str]:
    """
    验证视频文件是否有效
    
    参数:
        video_path: 视频文件路径
        
    返回:
        (是否有效, 错误信息) 元组
    """
    if not os.path.exists(video_path):
        return False, f"文件不存在: {video_path}"
        
    if os.path.getsize(video_path) == 0:
        return False, f"文件大小为0: {video_path}"
    
    try:
        # 使用ffprobe检查视频文件
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            return False, f"ffprobe检查失败: {error_msg}"
            
        # 检查是否存在视频流
        streams = result.stdout.strip().split('\n')
        if 'video' not in streams:
            return False, "文件中没有视频流"
        
        return True, ""
    except Exception as e:
        return False, f"验证视频文件时出错: {str(e)}"

def safe_get_video_clip(video_path: str) -> Tuple[Optional[VideoFileClip], str]:
    """
    安全地获取视频剪辑对象
    
    参数:
        video_path: 视频文件路径
        
    返回:
        (VideoFileClip对象, 错误信息) 元组，如果失败则返回 (None, 错误信息)
    """
    try:
        # 首先验证文件
        is_valid, error_msg = validate_video_file(video_path)
        if not is_valid:
            logger.error(f"视频文件无效: {error_msg}")
            return None, error_msg
        
        # 尝试加载视频
        clip = VideoFileClip(video_path)
        
        # 检查视频属性
        if clip.duration <= 0:
            clip.close()
            return None, "视频时长为0或无效"
            
        if clip.fps <= 0:
            clip.close()
            return None, "视频帧率为0或无效"
        
        # 尝试获取一帧以确保视频可读
        try:
            clip.get_frame(0)
        except Exception as e:
            clip.close()
            return None, f"无法获取视频帧: {str(e)}"
        
        return clip, ""
    except Exception as e:
        logger.exception(f"加载视频时出错: {str(e)}")
        return None, str(e)

def repair_video_file(video_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    尝试修复损坏的视频文件
    
    参数:
        video_path: 待修复的视频文件路径
        
    返回:
        (是否成功, 消息, 修复后的文件路径) 元组，如果失败则返回 (False, 错误信息, None)
    """
    try:
        # 验证输入文件是否存在
        if not os.path.exists(video_path):
            return False, f"文件不存在: {video_path}", None
            
        # 创建临时文件
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, os.path.basename(video_path))
        
        # 使用ffmpeg修复视频
        cmd = [
            "ffmpeg",
            "-v", "warning",
            "-err_detect", "ignore_err",
            "-i", video_path,
            "-c", "copy",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            return False, f"修复失败: {error_msg}", None
            
        # 验证修复后的文件
        is_valid, error_msg = validate_video_file(output_path)
        if not is_valid:
            return False, f"修复后的文件仍然无效: {error_msg}", None
            
        return True, "视频修复成功", output_path
    except Exception as e:
        logger.exception(f"修复视频时出错: {str(e)}")
        return False, f"修复视频时出错: {str(e)}", None
        
def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    获取视频文件的详细信息
    
    参数:
        video_path: 视频文件路径
        
    返回:
        包含视频信息的字典，包括时长、分辨率、帧率等
    """
    try:
        # 验证文件
        is_valid, error_msg = validate_video_file(video_path)
        if not is_valid:
            return {"error": error_msg}
            
        # 使用ffprobe获取视频信息
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=width,height,codec_name,codec_type,r_frame_rate",
            "-of", "json",
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            return {"error": f"获取视频信息失败: {error_msg}"}
            
        # 解析JSON结果
        import json
        info = json.loads(result.stdout)
        
        # 提取有用的信息
        format_info = info.get("format", {})
        streams = info.get("streams", [])
        
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        
        # 基本信息
        result_info = {
            "duration": float(format_info.get("duration", 0)),
            "size_bytes": int(format_info.get("size", 0)),
            "bitrate": format_info.get("bit_rate"),
            "has_video": len(video_streams) > 0,
            "has_audio": len(audio_streams) > 0,
            "video_info": {},
            "audio_info": {}
        }
        
        # 视频流信息
        if video_streams:
            video_stream = video_streams[0]
            # 处理帧率字符串 "24/1" -> 24.0
            frame_rate = video_stream.get("r_frame_rate", "").split("/")
            fps = float(frame_rate[0]) / float(frame_rate[1]) if len(frame_rate) == 2 and float(frame_rate[1]) != 0 else 0
            
            result_info["video_info"] = {
                "codec": video_stream.get("codec_name"),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": fps
            }
            
        # 音频流信息
        if audio_streams:
            audio_stream = audio_streams[0]
            result_info["audio_info"] = {
                "codec": audio_stream.get("codec_name")
            }
            
        return result_info
    except Exception as e:
        logger.exception(f"获取视频信息时出错: {str(e)}")
        return {"error": f"获取视频信息时出错: {str(e)}"} 