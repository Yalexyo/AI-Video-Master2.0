#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频上传组件 - 提供视频上传功能，支持本地存储和OSS存储
"""

import os
import uuid
import tempfile
import logging
from typing import Tuple, Dict, Any, Optional, List
import streamlit as st
import cv2
# 尝试导入oss2模块，如果失败则记录警告日志
try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    
from datetime import datetime
import traceback

from src.config.settings import (
    VIDEO_ALLOWED_FORMATS, MAX_UPLOAD_SIZE, ALLOWED_VIDEO_EXTENSIONS,
    VIDEO_UPLOAD_DIR, OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
    OSS_BUCKET_NAME, OSS_ENDPOINT, OSS_UPLOAD_DIR, OSS_PUBLIC_URL_TEMPLATE,
    ENABLE_OSS, VIDEO_TEMP_DIR, VIDEO_FILE_CHUNK_SIZE
)

# 配置日志
logger = logging.getLogger(__name__)

# 记录OSS模块可用性
if not OSS_AVAILABLE:
    logger.warning("无法导入阿里云OSS模块 oss2，云存储功能将不可用。尝试使用 'pip install oss2' 安装该模块。")
else:
    logger.info("成功导入阿里云OSS模块")

def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    获取视频文件信息
    
    Args:
        video_path: 视频文件路径
    
    Returns:
        包含视频信息的字典
    """
    try:
        # 使用OpenCV打开视频
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")
            
        # 获取基本信息
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        # 检查是否有音频
        has_audio = False
        # OpenCV无法直接检测音频，这里简单通过读取一帧来判断视频是否可用
        ret, _ = cap.read()
        
        # 释放资源
        cap.release()
        
        # 检查视频是否有效
        if not ret or frame_count <= 0:
            logger.warning(f"视频文件无效或损坏: {video_path}")
            return {
                "valid": False,
                "error": "视频文件无效或损坏"
            }
            
        # 获取视频旋转信息
        rotation = 0  # 默认无旋转
        
        return {
            "valid": True,
            "duration": duration,
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "rotation": rotation,
            "has_audio": has_audio
        }
    except Exception as e:
        logger.error(f"获取视频信息失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "valid": False,
            "error": f"获取视频信息失败: {str(e)}"
        }

def save_uploaded_video(uploaded_file) -> Tuple[bool, str, Dict[str, Any]]:
    """
    保存上传的视频文件到临时目录
    
    Args:
        uploaded_file: Streamlit上传的文件对象
    
    Returns:
        成功标志, 临时文件路径, 视频信息字典
    """
    if uploaded_file is None:
        return False, "请选择要上传的视频文件", {}
        
    # 检查文件类型
    file_ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
    if file_ext not in ALLOWED_VIDEO_EXTENSIONS:
        return False, f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}", {}
        
    # 检查文件大小
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        max_size_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
        return False, f"文件大小超过限制: {max_size_mb:.1f}MB", {}
    
    try:
        # 创建临时文件
        temp_file_path = os.path.join(VIDEO_TEMP_DIR, f"{uuid.uuid4()}.{file_ext}")
        
        # 保存上传的文件
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        # 分块读取和写入大文件
        with open(temp_file_path, 'wb') as f:
            chunk_size = VIDEO_FILE_CHUNK_SIZE * 1024
            for chunk in iter(lambda: uploaded_file.read(chunk_size), b''):
                f.write(chunk)
        
        # 获取视频信息
        video_info = get_video_info(temp_file_path)
        
        if not video_info.get("valid", False):
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return False, video_info.get("error", "无效的视频文件"), {}
            
        return True, temp_file_path, video_info
        
    except Exception as e:
        logger.error(f"保存上传视频失败: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 清理临时文件
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        return False, f"保存视频失败: {str(e)}", {}

def store_video_file(temp_path: str, use_oss: bool) -> Tuple[bool, str, Optional[str]]:
    """
    存储视频文件(本地或OSS)
    
    Args:
        temp_path: 临时文件路径
        use_oss: 是否使用OSS存储
    
    Returns:
        成功标志, URL或错误信息, OSS对象键(如果使用OSS)
    """
    if not os.path.exists(temp_path):
        return False, "临时文件不存在", None
        
    file_name = os.path.basename(temp_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    try:
        # 根据存储方式选择不同的存储策略
        if use_oss and ENABLE_OSS:
            # 使用OSS存储
            try:
                # 验证OSS配置
                if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, OSS_ENDPOINT]):
                    return False, "OSS配置不完整，请检查环境变量", None
                
                # 初始化OSS对象
                auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
                bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
                
                # 生成OSS对象键
                current_date = datetime.now().strftime('%Y%m%d')
                object_key = f"{OSS_UPLOAD_DIR}/{current_date}/{uuid.uuid4()}{file_ext}"
                
                # 上传到OSS
                with open(temp_path, 'rb') as f:
                    bucket.put_object(object_key, f)
                
                # 生成访问URL
                url = OSS_PUBLIC_URL_TEMPLATE.format(
                    bucket=OSS_BUCKET_NAME,
                    endpoint=OSS_ENDPOINT,
                    key=object_key
                )
                
                # 清理临时文件
                os.remove(temp_path)
                
                return True, url, object_key
                
            except Exception as e:
                logger.error(f"OSS存储视频失败: {str(e)}")
                logger.error(traceback.format_exc())
                return False, f"云存储失败: {str(e)}", None
        else:
            # 使用本地存储
            # 确保上传目录存在
            os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)
            
            # 生成唯一文件名
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            target_path = os.path.join(VIDEO_UPLOAD_DIR, unique_filename)
            
            # 移动文件
            os.rename(temp_path, target_path)
            
            return True, target_path, None
            
    except Exception as e:
        logger.error(f"存储视频文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return False, f"存储视频失败: {str(e)}", None

def video_upload_component(callback=None, key=None):
    """
    视频上传组件
    
    Args:
        callback: 上传成功后的回调函数，会传入视频信息
        key: Streamlit组件key
    
    Returns:
        上传结果信息
    """
    # 计算上传大小限制
    max_upload_size_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
    
    # 设置组件容器
    upload_container = st.container()
    
    with upload_container:
        st.subheader("视频上传")
        
        # 创建上传表单
        with st.form(key=f"video_upload_form_{key or ''}"):
            # 文件上传组件
            uploaded_file = st.file_uploader(
                "选择要上传的视频文件", 
                type=list(ALLOWED_VIDEO_EXTENSIONS),
                help=f"支持的视频格式: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}。最大上传大小: {max_upload_size_mb:.1f}MB。"
            )
            
            # 存储选项
            col1, col2 = st.columns([3, 1])
            with col1:
                use_cloud_storage = st.checkbox(
                    "使用云存储", 
                    value=False, 
                    help="选择是否将视频存储在云端。云存储可提供更好的访问性能，但可能产生额外费用。",
                    disabled=not ENABLE_OSS
                )
                if not ENABLE_OSS and use_cloud_storage:
                    st.warning("云存储功能未启用，请检查系统配置")
            
            with col2:
                # 上传限制提示
                st.markdown(f"**上传限制**")
                st.markdown(f"最大: {max_upload_size_mb:.1f}MB")
            
            # 提交按钮
            submit_button = st.form_submit_button("上传视频")
            
        # 处理上传
        if submit_button and uploaded_file is not None:
            # 显示进度条
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 步骤1: 显示上传进度
            status_text.text("步骤1/3: 上传文件中...")
            progress_bar.progress(25)
            
            # 步骤2: 保存上传的文件
            status_text.text("步骤2/3: 处理上传文件...")
            success, temp_path_or_error, video_info = save_uploaded_video(uploaded_file)
            
            if not success:
                st.error(temp_path_or_error)
                return {
                    "success": False,
                    "error": temp_path_or_error
                }
            
            progress_bar.progress(50)
            
            # 步骤3: 存储文件(本地或OSS)
            status_text.text("步骤3/3: 存储视频文件...")
            storage_success, url_or_error, oss_key = store_video_file(
                temp_path_or_error, 
                use_cloud_storage
            )
            
            if not storage_success:
                st.error(url_or_error)
                return {
                    "success": False,
                    "error": url_or_error
                }
            
            progress_bar.progress(100)
            status_text.text("上传完成！")
            
            # 构建结果信息
            result = {
                "success": True,
                "file_path": url_or_error,
                "file_name": os.path.basename(url_or_error),
                "oss_key": oss_key,
                "is_cloud_storage": use_cloud_storage and ENABLE_OSS,
                "upload_time": datetime.now().isoformat(),
                "file_size": uploaded_file.size,
                "video_info": video_info
            }
            
            # 显示成功消息
            st.success(f"视频上传成功！时长: {video_info.get('duration', 0):.1f}秒，分辨率: {video_info.get('resolution', 'N/A')}")
            
            # 如果提供了回调函数，则调用
            if callback is not None and callable(callback):
                callback(result)
            
            return result
            
    # 默认返回空结果
    return {"success": False, "error": "未上传文件"} 