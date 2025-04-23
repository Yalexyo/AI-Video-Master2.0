#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件和目录操作模块
---------------
提供统一的文件和目录操作函数，包括列出文件、备份文件等。
同时管理视频片段索引，追踪已处理片段的信息。
"""

import os
import re
import json
import shutil
import logging
import glob
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("io_handlers")

# 全局片段索引
_CLIP_INDEX = {}

# 视频文件扩展名
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.m4v', '.mkv', '.flv', '.wmv', '.MOV', '.MP4']

# 音频文件扩展名
AUDIO_EXTENSIONS = ['.wav', '.mp3', '.aac', '.m4a', '.flac', '.ogg']

# 字幕文件扩展名
SUBTITLE_EXTENSIONS = ['.srt', '.vtt', '.ass', '.ssa']

def list_files(directory, extensions=None, recursive=False):
    """
    列出目录中的文件
    
    参数:
        directory: 目录路径
        extensions: 文件扩展名列表，如果为None则列出所有文件
        recursive: 是否递归列出子目录中的文件
    
    返回:
        文件路径列表
    """
    if not os.path.isdir(directory):
        logger.warning(f"目录不存在: {directory}")
        return []
    
    files = []
    
    if recursive:
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                if extensions is None or any(filename.lower().endswith(ext.lower()) for ext in extensions):
                    files.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path) and (extensions is None or any(filename.lower().endswith(ext.lower()) for ext in extensions)):
                files.append(file_path)
    
    return sorted(files)

def list_videos(directory, recursive=False):
    """
    列出目录中的视频文件
    
    参数:
        directory: 目录路径
        recursive: 是否递归列出子目录中的文件
    
    返回:
        视频文件路径列表
    """
    return list_files(directory, VIDEO_EXTENSIONS, recursive)

def list_audios(directory, recursive=False):
    """
    列出目录中的音频文件
    
    参数:
        directory: 目录路径
        recursive: 是否递归列出子目录中的文件
    
    返回:
        音频文件路径列表
    """
    return list_files(directory, AUDIO_EXTENSIONS, recursive)

def list_subtitles(directory, recursive=False):
    """
    列出目录中的字幕文件
    
    参数:
        directory: 目录路径
        recursive: 是否递归列出子目录中的文件
    
    返回:
        字幕文件路径列表
    """
    return list_files(directory, SUBTITLE_EXTENSIONS, recursive)

def backup_file(file_path, backup_dir=None, timestamp=True):
    """
    备份文件
    
    参数:
        file_path: 文件路径
        backup_dir: 备份目录，如果为None则在原目录中创建backup子目录
        timestamp: 是否在备份文件名中添加时间戳
    
    返回:
        备份文件路径，如果备份失败则返回None
    """
    if not os.path.exists(file_path):
        logger.warning(f"要备份的文件不存在: {file_path}")
        return None
    
    try:
        # 确定备份目录
        if backup_dir is None:
            backup_dir = os.path.join(os.path.dirname(file_path), "backup")
        
        # 创建备份目录
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名
        file_name = os.path.basename(file_path)
        if timestamp:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name, ext = os.path.splitext(file_name)
            backup_file_name = f"{base_name}_{timestamp_str}{ext}"
        else:
            backup_file_name = file_name
        
        backup_file_path = os.path.join(backup_dir, backup_file_name)
        
        # 复制文件
        shutil.copy2(file_path, backup_file_path)
        logger.info(f"文件已备份: {file_path} -> {backup_file_path}")
        
        return backup_file_path
    
    except Exception as e:
        logger.error(f"备份文件失败: {e}")
        return None

def load_clip_index(index_file=None):
    """
    加载片段索引
    
    参数:
        index_file: 索引文件路径，如果为None则使用默认路径
    
    返回:
        片段索引字典
    """
    global _CLIP_INDEX
    
    if index_file is None:
        # 从项目根目录导入配置模块
        from utils import config
        temp_dir = config.get_path('temp_dir')
        index_file = os.path.join(temp_dir, "clip_index.json")
    
    # 如果索引已加载，直接返回
    if _CLIP_INDEX:
        return _CLIP_INDEX
    
    # 加载索引文件
    if os.path.exists(index_file):
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                _CLIP_INDEX = json.load(f)
            logger.info(f"片段索引已加载: {index_file}")
        except Exception as e:
            logger.error(f"加载片段索引失败: {e}")
            _CLIP_INDEX = {}
    else:
        logger.info(f"片段索引文件不存在，创建新索引")
        _CLIP_INDEX = {}
    
    return _CLIP_INDEX

def save_clip_index(index_file=None):
    """
    保存片段索引
    
    参数:
        index_file: 索引文件路径，如果为None则使用默认路径
    
    返回:
        成功返回True，否则返回False
    """
    if index_file is None:
        # 从项目根目录导入配置模块
        from utils import config
        temp_dir = config.get_path('temp_dir')
        index_file = os.path.join(temp_dir, "clip_index.json")
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        
        # 保存索引
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(_CLIP_INDEX, f, ensure_ascii=False, indent=2)
        
        logger.info(f"片段索引已保存: {index_file}")
        return True
    except Exception as e:
        logger.error(f"保存片段索引失败: {e}")
        return False

def add_clip_to_index(clip_path, clip_info):
    """
    向索引中添加片段信息
    
    参数:
        clip_path: 片段文件路径
        clip_info: 片段信息字典
    
    返回:
        成功返回True，否则返回False
    """
    global _CLIP_INDEX
    
    # 确保索引已加载
    if not _CLIP_INDEX:
        load_clip_index()
    
    try:
        # 标准化路径
        norm_path = os.path.normpath(clip_path)
        
        # 添加到索引
        _CLIP_INDEX[norm_path] = clip_info
        
        # 保存索引
        save_clip_index()
        
        logger.debug(f"片段已添加到索引: {norm_path}")
        return True
    except Exception as e:
        logger.error(f"添加片段到索引失败: {e}")
        return False

def get_clip_info(clip_path):
    """
    获取片段信息
    
    参数:
        clip_path: 片段文件路径
    
    返回:
        片段信息字典，如果不存在则返回None
    """
    global _CLIP_INDEX
    
    # 确保索引已加载
    if not _CLIP_INDEX:
        load_clip_index()
    
    # 标准化路径
    norm_path = os.path.normpath(clip_path)
    
    # 查找精确匹配
    if norm_path in _CLIP_INDEX:
        return _CLIP_INDEX[norm_path]
    
    # 尝试查找文件名匹配
    filename = os.path.basename(norm_path)
    for path, info in _CLIP_INDEX.items():
        if os.path.basename(path) == filename:
            return info
    
    logger.debug(f"索引中未找到片段信息: {clip_path}")
    return None

def find_clips_by_category(category, clips_dir=None):
    """
    查找特定类别的片段
    
    参数:
        category: 类别名称
        clips_dir: 片段目录，如果为None则从索引中查找
    
    返回:
        符合条件的片段路径列表
    """
    # 确保索引已加载
    if not _CLIP_INDEX:
        load_clip_index()
    
    # 如果提供了片段目录，则从文件系统查找
    if clips_dir is not None:
        category_dir = os.path.join(clips_dir, f"Category_{category}")
        if os.path.isdir(category_dir):
            return list_videos(category_dir)
        else:
            logger.warning(f"类别目录不存在: {category_dir}")
            return []
    
    # 从索引中查找
    clips = []
    for path, info in _CLIP_INDEX.items():
        if info.get('category') == category:
            clips.append(path)
    
    return clips

def ensure_directory(directory):
    """
    确保目录存在，如果不存在则创建
    
    参数:
        directory: 目录路径
    
    返回:
        目录路径
    """
    os.makedirs(directory, exist_ok=True)
    return directory

def copy_file_with_logging(src, dst, overwrite=False):
    """
    复制文件并记录日志
    
    参数:
        src: 源文件路径
        dst: 目标文件路径
        overwrite: 如果目标文件已存在，是否覆盖
    
    返回:
        成功返回True，否则返回False
    """
    try:
        # 检查源文件
        if not os.path.exists(src):
            logger.error(f"源文件不存在: {src}")
            return False
        
        # 检查目标文件
        if os.path.exists(dst) and not overwrite:
            logger.info(f"目标文件已存在，跳过复制: {dst}")
            return True
        
        # 确保目标目录存在
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        
        # 复制文件
        shutil.copy2(src, dst)
        logger.info(f"文件已复制: {src} -> {dst}")
        return True
    
    except Exception as e:
        logger.error(f"复制文件失败: {e}")
        return False

def clean_directory(directory, file_pattern=None, dry_run=False):
    """
    清理目录中的文件
    
    参数:
        directory: 目录路径
        file_pattern: 文件模式，如果为None则清理所有文件
        dry_run: 如果为True，则只显示要删除的文件，不实际删除
    
    返回:
        成功返回True，否则返回False
    """
    try:
        if not os.path.isdir(directory):
            logger.warning(f"目录不存在: {directory}")
            return False
        
        if file_pattern:
            pattern = os.path.join(directory, file_pattern)
            files = glob.glob(pattern)
        else:
            files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        
        logger.info(f"准备清理目录: {directory}，匹配到 {len(files)} 个文件")
        
        if dry_run:
            for file_path in files:
                logger.info(f"将删除文件: {file_path}")
            return True
        
        for file_path in files:
            try:
                os.remove(file_path)
                logger.debug(f"已删除文件: {file_path}")
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
        
        logger.info(f"目录清理完成: {directory}")
        return True
    
    except Exception as e:
        logger.error(f"清理目录失败: {e}")
        return False
