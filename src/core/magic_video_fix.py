#!/usr/bin/env python3
"""
魔法视频修复工具

提供用于修复魔法视频生成过程中常见错误的工具函数
"""

import os
import logging
import cv2
from moviepy.editor import VideoFileClip
import tempfile
import subprocess
import shutil

# 设置日志
logger = logging.getLogger(__name__)

class VideoFixTools:
    """视频修复工具集"""
    
    @staticmethod
    def validate_video_file(video_path):
        """
        验证视频文件是否可正常打开和读取
        
        参数:
            video_path: 视频文件路径
            
        返回:
            (bool, str): 是否有效, 错误信息
        """
        if not os.path.exists(video_path):
            return False, f"文件不存在: {video_path}"
        
        # 尝试用OpenCV打开
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False, f"无法用OpenCV打开视频: {video_path}"
            
            # 读取第一帧测试
            success, frame = cap.read()
            if not success or frame is None:
                cap.release()
                return False, f"无法从视频读取帧: {video_path}"
            
            cap.release()
        except Exception as e:
            return False, f"OpenCV打开视频异常: {str(e)}"
        
        # 尝试用MoviePy打开
        try:
            clip = VideoFileClip(video_path)
            if clip.reader is None:
                return False, f"MoviePy无法打开视频阅读器: {video_path}"
            
            # 尝试获取一帧
            frame = clip.get_frame(0)
            if frame is None:
                clip.close()
                return False, f"MoviePy无法获取视频帧: {video_path}"
            
            clip.close()
        except Exception as e:
            return False, f"MoviePy打开视频异常: {str(e)}"
        
        return True, "视频文件有效"
    
    @staticmethod
    def repair_video_file(video_path, output_path=None):
        """
        尝试修复视频文件
        
        参数:
            video_path: 原始视频文件路径
            output_path: 修复后的输出路径，如果为None则覆盖原文件
            
        返回:
            (bool, str): 是否修复成功, 输出文件路径或错误信息
        """
        if not os.path.exists(video_path):
            return False, f"文件不存在: {video_path}"
        
        # 如果未指定输出路径，则创建临时文件
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp_file.close()
            output_path = temp_file.name
        
        try:
            # 使用FFmpeg尝试修复
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-c:v", "libx264", "-crf", "23",
                "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
            
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                return False, f"FFmpeg修复失败: {process.stderr}"
            
            # 验证修复后的文件
            valid, error_msg = VideoFixTools.validate_video_file(output_path)
            if not valid:
                os.remove(output_path)
                return False, f"修复后的文件仍然无效: {error_msg}"
            
            # 如果是覆盖模式，替换原文件
            if output_path != video_path:
                # 备份原文件
                backup_path = f"{video_path}.bak"
                shutil.copy2(video_path, backup_path)
                
                # 替换原文件
                shutil.move(output_path, video_path)
                output_path = video_path
                
                logger.info(f"已备份原文件到: {backup_path}")
            
            return True, output_path
            
        except Exception as e:
            if os.path.exists(output_path) and output_path != video_path:
                try:
                    os.remove(output_path)
                except:
                    pass
            return False, f"修复过程出错: {str(e)}"
    
    @staticmethod
    def safe_get_video_clip(video_path):
        """
        安全地获取VideoFileClip，确保返回有效的视频片段
        
        参数:
            video_path: 视频文件路径
            
        返回:
            (clip, error_msg): 视频片段或None, 错误信息
        """
        # 首先验证文件
        valid, error_msg = VideoFixTools.validate_video_file(video_path)
        if not valid:
            logger.warning(f"视频文件无效: {error_msg}")
            
            # 尝试修复
            logger.info(f"尝试修复视频文件: {video_path}")
            fixed, result = VideoFixTools.repair_video_file(video_path)
            if not fixed:
                logger.error(f"修复失败: {result}")
                return None, f"无法使用的视频文件: {error_msg}"
            
            logger.info(f"视频文件修复成功: {result}")
        
        # 尝试加载视频
        try:
            clip = VideoFileClip(video_path)
            
            # 检查视频是否有效
            try:
                # 尝试获取视频的基本属性
                _ = clip.duration
                _ = clip.fps
                frame = clip.get_frame(0)  # 获取第一帧
                if frame is None:
                    raise ValueError("无法获取第一帧")
                
                return clip, None
                
            except Exception as attr_error:
                # 如果获取属性失败，关闭并返回错误
                try:
                    clip.close()
                except:
                    pass
                    
                return None, f"视频属性访问失败: {str(attr_error)}"
                
        except Exception as e:
            return None, f"加载视频失败: {str(e)}"

# 创建一个实例方便直接导入使用
video_fix_tools = VideoFixTools() 