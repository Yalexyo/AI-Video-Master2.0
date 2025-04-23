#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频处理工具模块
---------------
提供视频处理相关的函数，包括提取音频、视频剪辑、拼接等操作。
主要基于FFmpeg进行视频处理。
"""

import os
import json
import subprocess
import logging
import shutil
import tempfile
import re
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("video_utils")

# 检查FFmpeg是否可用
def check_ffmpeg():
    """
    检查FFmpeg是否可用
    
    返回:
        成功返回True，否则返回False
    """
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg未安装或不可用，请确保FFmpeg已正确安装并添加到系统环境变量")
        return False

def run_ffmpeg_command(command, silent=False):
    """
    运行FFmpeg命令
    
    参数:
        command: FFmpeg命令列表
        silent: 是否静默执行(不输出日志)
    
    返回:
        成功返回True，否则返回False
    """
    if not check_ffmpeg():
        return False
    
    try:
        if not silent:
            logger.debug(f"执行FFmpeg命令: {' '.join(command)}")
        
        # 运行命令
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 读取输出
        stdout, stderr = process.communicate()
        
        # 检查返回码
        if process.returncode != 0:
            logger.error(f"FFmpeg命令执行失败: {stderr}")
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"FFmpeg命令执行异常: {e}")
        return False

def extract_audio(video_path, audio_path, audio_format='wav', sample_rate=16000, overwrite=False):
    """
    从视频中提取音频
    
    参数:
        video_path: 视频文件路径
        audio_path: 输出音频文件路径
        audio_format: 音频格式
        sample_rate: 采样率
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 如果输出文件已存在且不覆盖，则直接返回成功
    if os.path.exists(audio_path) and not overwrite:
        logger.info(f"音频文件已存在: {audio_path}")
        return True
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    # 构建命令
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", video_path,
        "-vn",  # 禁用视频
        "-acodec", "pcm_s16le" if audio_format == 'wav' else audio_format,
        "-ar", str(sample_rate),
        "-ac", "1",  # 单声道
        audio_path
    ]
    
    # 执行命令
    result = run_ffmpeg_command(command)
    
    if result:
        logger.info(f"音频提取成功: {audio_path}")
    else:
        logger.error(f"音频提取失败: {video_path}")
    
    return result

def get_video_metadata(video_path):
    """
    获取视频元数据
    
    参数:
        video_path: 视频文件路径
    
    返回:
        包含元数据的字典，如果失败则返回空字典
    """
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return {}
    
    try:
        # 使用FFprobe获取视频信息
        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if result.returncode != 0:
            logger.error(f"获取视频元数据失败: {result.stderr}")
            return {}
        
        # 解析JSON输出
        metadata = json.loads(result.stdout)
        
        # 提取关键信息
        info = {}
        
        # 格式信息
        if 'format' in metadata:
            info['format'] = metadata['format'].get('format_name', '')
            info['duration'] = float(metadata['format'].get('duration', 0))
            info['size'] = int(metadata['format'].get('size', 0))
            info['bit_rate'] = int(metadata['format'].get('bit_rate', 0))
        
        # 视频流信息
        video_stream = None
        audio_stream = None
        
        for stream in metadata.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_stream:
                video_stream = stream
            elif stream.get('codec_type') == 'audio' and not audio_stream:
                audio_stream = stream
        
        # 视频信息
        if video_stream:
            info['video_codec'] = video_stream.get('codec_name', '')
            info['width'] = int(video_stream.get('width', 0))
            info['height'] = int(video_stream.get('height', 0))
            info['frame_rate'] = eval(video_stream.get('r_frame_rate', '0/1'))
        
        # 音频信息
        if audio_stream:
            info['audio_codec'] = audio_stream.get('codec_name', '')
            info['sample_rate'] = int(audio_stream.get('sample_rate', 0))
            info['channels'] = int(audio_stream.get('channels', 0))
        
        return info
    
    except Exception as e:
        logger.error(f"解析视频元数据失败: {e}")
        return {}

def get_video_duration(video_path):
    """
    获取视频时长
    
    参数:
        video_path: 视频文件路径
    
    返回:
        视频时长(秒)，如果失败则返回0
    """
    metadata = get_video_metadata(video_path)
    return metadata.get('duration', 0)

def extract_video_segment(input_path, output_path, start_time=0, end_time=None, lossless=False, overwrite=True):
    """
    提取视频片段
    
    参数:
        input_path: 输入视频文件路径
        output_path: 输出视频文件路径
        start_time: 开始时间(秒)
        end_time: 结束时间(秒)，如果为None则提取到结尾
        lossless: 是否使用无损模式
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 如果输出文件已存在且不覆盖，则直接返回成功
    if os.path.exists(output_path) and not overwrite:
        logger.info(f"输出文件已存在: {output_path}")
        return True
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 构建命令
    command = ["ffmpeg"]
    
    # 覆盖选项
    if overwrite:
        command.append("-y")
    else:
        command.append("-n")
    
    # 输入文件
    command.extend(["-i", input_path])
    
    # 开始时间
    if start_time > 0:
        command.extend(["-ss", str(start_time)])
    
    # 结束时间
    if end_time is not None:
        duration = end_time - start_time
        if duration > 0:
            command.extend(["-t", str(duration)])
    
    # 编码选项
    if lossless:
        # 无损模式
        command.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "0",
            "-c:a", "aac",
            "-b:a", "320k"
        ])
    else:
        # 标准模式
        command.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k"
        ])
    
    # 输出文件
    command.append(output_path)
    
    # 执行命令
    result = run_ffmpeg_command(command)
    
    if result:
        logger.info(f"视频片段提取成功: {output_path}")
    else:
        logger.error(f"视频片段提取失败: {input_path}")
    
    return result

def concat_videos(input_files, output_file, transition_type='none', transition_duration=1.0, overwrite=True):
    """
    拼接多个视频
    
    参数:
        input_files: 输入视频文件路径列表
        output_file: 输出视频文件路径
        transition_type: 转场效果类型，可选值: none, fade, crossfade, wipe
        transition_duration: 转场效果持续时间(秒)
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 检查输入文件
    if not input_files:
        logger.error("没有输入文件")
        return False
    
    for input_file in input_files:
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return False
    
    # 如果只有一个输入文件，则直接复制
    if len(input_files) == 1:
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            shutil.copy2(input_files[0], output_file)
            logger.info(f"只有一个输入文件，已复制: {output_file}")
            return True
        except Exception as e:
            logger.error(f"复制文件失败: {e}")
            return False
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 根据转场类型选择拼接方法
        if transition_type == 'none':
            # 使用concat demuxer (无转场)
            return concat_videos_simple(input_files, output_file, temp_dir, overwrite)
        else:
            # 使用filter_complex (有转场)
            return concat_videos_with_transition(
                input_files, output_file, temp_dir, 
                transition_type, transition_duration, overwrite
            )

def concat_videos_simple(input_files, output_file, temp_dir, overwrite=True):
    """
    简单拼接多个视频(无转场)
    
    参数:
        input_files: 输入视频文件路径列表
        output_file: 输出视频文件路径
        temp_dir: 临时目录
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 创建concat文件
    concat_file = os.path.join(temp_dir, "concat.txt")
    
    try:
        with open(concat_file, 'w', encoding='utf-8') as f:
            for input_file in input_files:
                f.write(f"file '{os.path.abspath(input_file)}'\n")
    except Exception as e:
        logger.error(f"创建concat文件失败: {e}")
        return False
    
    # 构建命令
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_file
    ]
    
    # 执行命令
    result = run_ffmpeg_command(command)
    
    if result:
        logger.info(f"视频拼接成功: {output_file}")
    else:
        logger.error(f"视频拼接失败")
    
    return result

def concat_videos_with_transition(input_files, output_file, temp_dir, 
                                 transition_type='crossfade', transition_duration=1.0, 
                                 overwrite=True):
    """
    带转场效果的视频拼接
    
    参数:
        input_files: 输入视频文件路径列表
        output_file: 输出视频文件路径
        temp_dir: 临时目录
        transition_type: 转场效果类型
        transition_duration: 转场效果持续时间(秒)
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 构建复杂的filter_complex表达式
    inputs = []
    filter_complex = []
    
    # 添加输入
    for i, input_file in enumerate(input_files):
        inputs.extend(["-i", input_file])
    
    # 视频转场
    v_transitions = []
    
    for i in range(len(input_files)):
        # 每个视频的标签
        v_transitions.append(f"[{i}:v]")
    
    # 音频转场
    a_transitions = []
    
    for i in range(len(input_files)):
        # 每个音频的标签
        a_transitions.append(f"[{i}:a]")
    
    # 构建命令
    command = ["ffmpeg", "-y" if overwrite else "-n"]
    command.extend(inputs)
    
    # 只有一个输入文件的情况
    if len(input_files) == 1:
        command.extend(["-c", "copy", output_file])
        result = run_ffmpeg_command(command)
        return result
    
    # 多个输入文件的情况
    # 创建复杂的filter_complex脚本
    filter_script = os.path.join(temp_dir, "filter_complex.txt")
    
    try:
        with open(filter_script, 'w', encoding='utf-8') as f:
            # 视频转场
            if transition_type == 'fade':
                # 淡入淡出
                for i in range(len(input_files) - 1):
                    f.write(f"[{i}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i}];\n")
                    f.write(f"[{i+1}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i+1}];\n")
                    f.write(f"[v{i}][v{i+1}]xfade=transition=fade:duration={transition_duration}:offset={transition_duration}[vt{i}];\n")
            
            elif transition_type == 'crossfade':
                # 交叉淡入淡出
                for i in range(len(input_files) - 1):
                    f.write(f"[{i}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i}];\n")
                    f.write(f"[{i+1}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i+1}];\n")
                    f.write(f"[v{i}][v{i+1}]xfade=transition=dissolve:duration={transition_duration}:offset={transition_duration}[vt{i}];\n")
            
            elif transition_type == 'wipe':
                # 擦除效果
                for i in range(len(input_files) - 1):
                    f.write(f"[{i}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i}];\n")
                    f.write(f"[{i+1}:v]format=yuv420p,setpts=PTS-STARTPTS[v{i+1}];\n")
                    f.write(f"[v{i}][v{i+1}]xfade=transition=wiperight:duration={transition_duration}:offset={transition_duration}[vt{i}];\n")
            
            # 连接视频转场
            if len(input_files) > 2:
                video_chain = ""
                for i in range(len(input_files) - 2):
                    video_chain += f"[vt{i}][vt{i+1}]concat=n=2:v=1:a=0[vt{i+2}];\n"
                f.write(video_chain)
            
            # 音频转场
            for i in range(len(input_files)):
                f.write(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}];\n")
            
            # 连接音频
            audio_chain = ""
            for i in range(len(input_files)):
                audio_chain += f"[a{i}]"
            audio_chain += f"concat=n={len(input_files)}:v=0:a=1[aout];\n"
            f.write(audio_chain)
            
            # 最终输出
            f.write(f"[vt{len(input_files)-2}][aout]concat=n=1:v=1:a=1[vout][aout]")
    
    except Exception as e:
        logger.error(f"创建filter_complex脚本失败: {e}")
        return False
    
    # 构建命令
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n"
    ]
    
    # 添加输入
    for input_file in input_files:
        command.extend(["-i", input_file])
    
    # 添加filter_complex
    command.extend([
        "-filter_complex_script", filter_script,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_file
    ])
    
    # 执行命令
    result = run_ffmpeg_command(command)
    
    if result:
        logger.info(f"带转场的视频拼接成功: {output_file}")
    else:
        logger.error(f"带转场的视频拼接失败")
        
        # 如果复杂拼接失败，尝试简单拼接
        logger.info("尝试使用简单拼接方式")
        return concat_videos_simple(input_files, output_file, temp_dir, overwrite)
    
    return result

def add_text_overlay(video_path, output_path, text, font_size=24, 
                    position='bottom', bg_color='black', bg_opacity=0.5, 
                    font_color='white', duration=None, start_time=0, overwrite=True):
    """
    向视频添加文字叠加
    
    参数:
        video_path: 输入视频文件路径
        output_path: 输出视频文件路径
        text: 要添加的文字
        font_size: 字体大小
        position: 位置，可选值: top, bottom, center
        bg_color: 背景颜色
        bg_opacity: 背景不透明度 (0-1)
        font_color: 字体颜色
        duration: 文字显示时长，如果为None则显示整个视频
        start_time: 文字开始显示的时间(秒)
        overwrite: 是否覆盖已存在的文件
    
    返回:
        成功返回True，否则返回False
    """
    # 如果输出文件已存在且不覆盖，则直接返回成功
    if os.path.exists(output_path) and not overwrite:
        logger.info(f"输出文件已存在: {output_path}")
        return True
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 转义文字中的特殊字符
    text = text.replace("'", "\\'").replace('"', '\\"').replace(':', '\\:').replace(',', '\\,')
    
    # 确定文字位置
    if position == 'top':
        position_str = "x=(w-text_w)/2:y=h*0.1"
    elif position == 'center':
        position_str = "x=(w-text_w)/2:y=(h-text_h)/2"
    else:  # bottom
        position_str = "x=(w-text_w)/2:y=h*0.9-text_h"
    
    # 构建命令
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", video_path
    ]
    
    # 构建filter_complex
    filter_complex = ""
    
    # 如果有持续时间限制
    if duration is not None:
        enable_expr = f"between(t,{start_time},{start_time+duration})"
    else:
        enable_expr = "1"
    
    # 添加文字叠加
    filter_complex = (
        f"drawtext=text='{text}':fontsize={font_size}:fontcolor={font_color}:"
        f"{position_str}:box=1:boxcolor={bg_color}@{bg_opacity}:boxborderw=5:"
        f"enable='{enable_expr}'"
    )
    
    command.extend([
        "-vf", filter_complex,
        "-c:a", "copy",
        output_path
    ])
    
    # 执行命令
    result = run_ffmpeg_command(command)
    
    if result:
        logger.info(f"添加文字叠加成功: {output_path}")
    else:
        logger.error(f"添加文字叠加失败: {video_path}")
    
    return result
