#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
魔法视频服务：负责视频处理、分析和合成的核心服务
"""

import os
import uuid
import time
import json
import shutil
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

from utils.processor import VideoProcessor
from utils import video_fix_tools
from src.core.semantic_service import SemanticAnalysisService

# 配置日志
logger = logging.getLogger(__name__)

class MagicVideoService:
    """魔法视频服务，处理视频分析与合成"""
    
    def __init__(self):
        """初始化服务"""
        self.processor = VideoProcessor()
        self.semantic_service = SemanticAnalysisService()

    async def process_demo_video(self, video_path: str, vocabulary_id: str = None) -> Dict[str, Any]:
        """
        处理Demo视频，提取音频、生成字幕、进行语义分段
        
        参数:
            video_path: 视频文件路径
            vocabulary_id: 热词表ID（可选）
            
        返回:
            处理结果，包含语义段落、标签等信息
        """
        try:
            logger.info(f"开始处理Demo视频: {video_path}")
            
            # 1. 提取音频并生成字幕
            subtitles_files = self.processor.process_video_file(video_path, vocabulary_id)
            
            # 检查是否成功提取字幕
            if not subtitles_files or 'json' not in subtitles_files:
                return {"error": "无法提取字幕"}
                
            # 2. 加载字幕数据
            subtitles_json = subtitles_files['json']
            try:
                with open(subtitles_json, 'r', encoding='utf-8') as f:
                    subtitles = json.load(f)
            except Exception as e:
                logger.error(f"加载字幕文件失败: {str(e)}")
                return {"error": f"加载字幕文件失败: {str(e)}"}
                
            # 3. 语义分段
            logger.info(f"进行语义分段，共 {len(subtitles)} 条字幕")
            stages = await self.semantic_service.analyze_and_segment(subtitles)
            
            # 4. 提取关键词和生成标签
            logger.info(f"为 {len(stages)} 个段落生成标签和关键词")
            for stage in stages:
                # 生成段落标签
                stage['label'] = await self.semantic_service.generate_title(stage['text'])
                
                # 提取关键词
                stage['keywords'] = await self.semantic_service.extract_keywords(stage['text'])
                
                # 记录时间戳
                stage['start_timestamp'] = stage['subtitles'][0]['timestamp']
                stage['end_timestamp'] = stage['subtitles'][-1]['timestamp']
            
            # 5. 保存分段结果到文件
            video_name = os.path.basename(video_path)
            video_name_without_ext = os.path.splitext(video_name)[0]
            
            # 创建目录
            segments_dir = os.path.join('data', 'processed', 'analysis', 'results')
            reports_dir = os.path.join('data', 'processed', 'analysis', 'reports')
            os.makedirs(segments_dir, exist_ok=True)
            os.makedirs(reports_dir, exist_ok=True)
            
            # 保存段落分析结果
            segments_file = os.path.join(segments_dir, f"{video_name_without_ext}.mp4_segments.json")
            with open(segments_file, 'w', encoding='utf-8') as f:
                json.dump(stages, f, ensure_ascii=False, indent=2)
            logger.info(f"成功保存段落分析结果: {segments_file}")
            
            # 生成分析报告
            report = {
                "title": video_name_without_ext,
                "duration": stages[-1]['end_time'] if stages else 0,
                "video_type": "广告视频",
                "timestamp": datetime.now().isoformat(),
                "segments_count": len(stages),
                "brand_keywords": list(set(sum([stage.get('keywords', []) for stage in stages], []))),
                "overall_intent": stages[0].get('primary_intent', "一般内容") if stages else "未知"
            }
            
            # 保存分析报告
            report_file = os.path.join(reports_dir, f"{video_name_without_ext}_analysis_report.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"成功保存分析报告: {report_file}")
            
            # 6. 返回结果
            result = {
                "video_path": video_path,
                "subtitles_count": len(subtitles),
                "stages": stages,
                "subtitles_file": subtitles_json,
                "segments_file": segments_file,
                "report_file": report_file
            }
            
            logger.info(f"Demo视频处理完成，识别 {len(stages)} 个语义段落")
            return result
            
        except Exception as e:
            logger.exception(f"处理Demo视频时出错: {str(e)}")
            return {"error": f"处理Demo视频时出错: {str(e)}"}

    async def compose_magic_video(self, demo_video_path: str, match_results: Dict[str, List[Dict[str, Any]]], 
                             output_filename: str = None, use_demo_audio: bool = True) -> Optional[str]:
        """
        根据匹配结果合成魔法视频
        
        参数:
            demo_video_path: Demo视频路径
            match_results: 匹配结果，格式为 {stage_id: [匹配片段列表]}
            output_filename: 输出文件名（不含扩展名）
            use_demo_audio: 是否使用Demo视频的音频，默认为True
            
        返回:
            合成后的视频路径，如果失败则返回None
        """
        try:
            # 确保所有stage_id都是字符串类型
            normalized_results = {}
            for stage_id, matches in match_results.items():
                normalized_results[str(stage_id)] = matches
            match_results = normalized_results
            
            logger.info("开始合成魔法视频")
            
            # 输出文件路径
            output_dir = os.path.join('data', 'output', 'videos')
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, f"{output_filename}.mp4") if output_filename else os.path.join(output_dir, f"magic_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            temp_dir = os.path.join('data', 'temp', 'videos', str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # 首先计算Demo视频的总时长作为基准
                try:
                    # 使用修复工具安全加载视频
                    demo_clip, error = video_fix_tools.safe_get_video_clip(demo_video_path)
                    if demo_clip is None:
                        logger.error(f"无法加载Demo视频: {error}")
                        demo_duration = None
                        demo_audio = None
                    else:
                        demo_duration = demo_clip.duration
                        logger.info(f"Demo视频总时长: {demo_duration:.2f}秒")
                        
                        # 延迟加载音频：先不从 demo_clip 直接获取，避免关闭 demo_clip 后 reader 失效
                        demo_audio = None  # 占位，在关闭 demo_clip 之后再单独加载 AudioFileClip
                        
                        # 关闭 Demo 视频（仅视频流），减少内存占用
                        demo_clip.close()
                        
                        # 如果需要使用 Demo 音频，则单独加载音频流，避免与已关闭的 VideoFileClip 关联
                        if use_demo_audio:
                            try:
                                demo_audio = AudioFileClip(demo_video_path)
                                logger.info("已从 Demo 视频单独加载音频流")
                            except Exception as audio_load_err:
                                logger.warning(f"加载 Demo 视频音频流失败，将回退为片段音频: {str(audio_load_err)}")
                                demo_audio = None
                except Exception as e:
                    logger.error(f"无法获取Demo视频时长: {str(e)}")
                    demo_duration = None
                    demo_audio = None
                
                # 提取示范视频的音频（如果需要）
                demo_audio_path = None
                if use_demo_audio and demo_audio is None:
                    try:
                        processor = VideoProcessor()
                        demo_audio_path = processor.extract_audio(demo_video_path)
                        if not demo_audio_path or not os.path.exists(demo_audio_path):
                            logger.warning("无法从示范视频中提取音频，将不使用音频")
                    except Exception as audio_error:
                        logger.warning(f"提取示范视频音频时出错: {str(audio_error)}，将不使用音频")
                
                # 1. 提取每个阶段的最佳匹配片段
                clips_to_concat = []
                total_duration = 0
                
                # 首先按阶段排序处理匹配结果
                sorted_stages = sorted(match_results.keys(), key=lambda x: int(x) if x.isdigit() else float('inf'))
                
                for stage_id in sorted_stages:
                    matches = match_results[stage_id]
                    if not matches:
                        logger.warning(f"阶段 {stage_id} 没有匹配片段，跳过")
                        continue
                    
                    # 获取该阶段的最佳匹配
                    best_match = matches[0]
                    video_id = best_match['video_id']
                    start_time = best_match['start_time']
                    end_time = best_match['end_time']
                    segment_duration = end_time - start_time
                    
                    # 检查是否会超出Demo视频总时长
                    if demo_duration is not None:
                        if total_duration + segment_duration > demo_duration:
                            # 如果添加当前片段会超出总时长，需要裁剪或跳过
                            remaining_time = demo_duration - total_duration
                            if remaining_time < 1.0:  # 如果剩余时间太短，就跳过这个片段
                                logger.warning(f"跳过阶段 {stage_id}，剩余时间不足: {remaining_time:.2f}秒")
                                break
                            
                            # 裁剪片段以适应剩余时长
                            logger.info(f"裁剪阶段 {stage_id} 的片段，从 {segment_duration:.2f}秒 到 {remaining_time:.2f}秒")
                            end_time = start_time + remaining_time
                            segment_duration = remaining_time
                    
                    # 验证数据有效性
                    if not video_id:
                        logger.error(f"视频ID无效: {video_id}")
                        continue
                    
                    if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
                        logger.error(f"无效的时间范围: start_time={start_time}, end_time={end_time}")
                        continue
                    
                    # 确保时间范围有效
                    if start_time >= end_time:
                        logger.error(f"无效的时间范围: start_time({start_time}) >= end_time({end_time})")
                        continue
                    
                    # 查找视频文件的完整路径
                    # 首先尝试在test_samples目录中查找
                    video_path = None
                    search_paths = [
                        os.path.join('data', 'test_samples', 'input', 'video', video_id),
                        os.path.join('data', 'input', video_id),
                        os.path.join('data', 'uploads', 'videos', video_id),
                        video_id  # 万一传入的就是完整路径
                    ]
                    
                    for path in search_paths:
                        if os.path.exists(path) and os.path.isfile(path):
                            video_path = path
                            logger.info(f"找到视频文件: {video_path}")
                            break
                    
                    if not video_path:
                        logger.error(f"找不到视频文件: {video_id}")
                        continue
                    
                    # 处理时间范围，确保不超出视频长度
                    try:
                        # 使用安全的视频加载方法
                        temp_clip, error = video_fix_tools.safe_get_video_clip(video_path)
                        if temp_clip is None:
                            logger.error(f"无法加载视频 {video_id} (路径: {video_path}): {error}")
                            continue
                        
                        video_duration = temp_clip.duration
                        temp_clip.close()
                        
                        # 如果结束时间超出视频长度，则调整为视频长度
                        if end_time > video_duration:
                            logger.warning(f"结束时间 {end_time} 超出视频长度 {video_duration}，将调整为视频长度")
                            end_time = video_duration
                    except Exception as clip_error:
                        logger.error(f"获取视频时长时出错: {str(clip_error)}")
                        continue
                    
                    # 裁剪视频片段
                    logger.info(f"裁剪视频 {video_id}，时间范围: {start_time:.2f} - {end_time:.2f}，时长: {segment_duration:.2f}秒")
                    temp_clip_path = os.path.join(temp_dir, f"stage_{stage_id}_{video_id}_{start_time:.2f}_{end_time:.2f}.mp4")
                    
                    try:
                        # 使用FFmpeg精确裁剪
                        ffmpeg_cmd = [
                            "ffmpeg", "-y",
                            "-i", video_path,
                            "-ss", str(start_time),
                            "-to", str(end_time),
                            "-c:v", "libx264", "-c:a", "aac",
                            "-preset", "fast", "-crf", "22",
                            temp_clip_path
                        ]
                        
                        process = subprocess.run(
                            ffmpeg_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        
                        if process.returncode != 0:
                            logger.error(f"裁剪视频失败: {process.stderr}")
                            continue
                            
                        if not os.path.exists(temp_clip_path) or os.path.getsize(temp_clip_path) == 0:
                            logger.error(f"裁剪后的视频文件不存在或为空: {temp_clip_path}")
                            continue
                        
                        # 验证裁剪出的片段是否有效
                        valid, error_msg = video_fix_tools.validate_video_file(temp_clip_path)
                        if not valid:
                            logger.error(f"裁剪后的视频片段无效: {error_msg}")
                            continue
                        
                        # 添加到待合成列表
                        clips_to_concat.append({
                            'stage': stage_id,
                            'path': temp_clip_path,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': segment_duration
                        })
                        
                        total_duration += segment_duration
                        logger.info(f"当前累计时长: {total_duration:.2f}秒")
                        
                        # 如果已经达到或接近Demo视频时长，停止添加更多片段
                        if demo_duration is not None and total_duration >= demo_duration * 0.98:
                            logger.info(f"已达到目标时长({total_duration:.2f}秒 >= {demo_duration:.2f}秒)，停止添加更多片段")
                            break
                        
                    except Exception as e:
                        logger.exception(f"裁剪视频时出错: {str(e)}")
                        continue
                
                if not clips_to_concat:
                    raise ValueError("没有有效的视频片段可合成")
                
                # 按阶段排序
                clips_to_concat.sort(key=lambda x: int(x['stage']) if isinstance(x['stage'], str) and x['stage'].isdigit() else float('inf'))
                
                # 2. 使用MoviePy合成视频
                video_clips = []
                
                for clip_info in clips_to_concat:
                    clip_path = clip_info['path']
                    try:
                        # 使用安全的方法加载视频片段
                        video_clip, error = video_fix_tools.safe_get_video_clip(clip_path)
                        if video_clip is None:
                            logger.error(f"无法加载视频片段: {clip_path}, 错误: {error}")
                            continue
                    
                        # 如果使用Demo视频的音频，则将片段音量设为0
                        if use_demo_audio:
                            video_clip = video_clip.without_audio()
                    
                        video_clips.append(video_clip)
                    except Exception as e:
                        logger.error(f"加载视频片段出错: {clip_path}, 错误: {str(e)}")
                
                if not video_clips:
                    raise ValueError("所有视频片段加载失败")
                
                # 合成视频
                logger.info(f"合成 {len(video_clips)} 个视频片段，总时长预计: {total_duration:.2f}秒")
                
                # 确保传递给concatenate_videoclips的所有片段都有效
                valid_clips = []
                for i, clip in enumerate(video_clips):
                    try:
                        # 再次检查每个片段
                        _ = clip.duration
                        _ = clip.fps
                        _ = clip.get_frame(0)
                        valid_clips.append(clip)
                    except Exception as e:
                        logger.error(f"片段 {i} 无效，将跳过: {str(e)}")
                
                if not valid_clips:
                    raise ValueError("没有有效的视频片段可合成")
                
                final_clip = concatenate_videoclips(valid_clips, method="compose")
                logger.info(f"合成视频实际时长: {final_clip.duration:.2f}秒")
                
                # 处理音频部分
                if use_demo_audio and demo_audio is not None:
                    logger.info("使用Demo视频的音频")
                    
                    # 检查时长匹配情况
                    duration_diff = abs(final_clip.duration - demo_audio.duration)
                    
                    # 调整处理策略，优先确保生成视频尽可能接近原始demo视频时长
                    if demo_duration is not None and demo_duration > final_clip.duration + 0.5:
                        # 视频明显短于期望时长，需要进行填充
                        shortfall = demo_duration - final_clip.duration
                        logger.warning(f"生成视频({final_clip.duration:.2f}秒)远短于原视频({demo_duration:.2f}秒)，差距{shortfall:.2f}秒，尝试填充")
                        
                        # 方法1：确保音频能够覆盖原始时长
                        if demo_audio.duration >= demo_duration:
                            # 重新设置clip的持续时间，并在结尾保持最后一帧
                            # 获取最后一帧
                            try:
                                last_frame = final_clip.get_frame(final_clip.duration - 0.01)
                                # 创建一个填充静态片段
                                from moviepy.video.VideoClip import ImageClip
                                padding_clip = ImageClip(last_frame).set_duration(shortfall)
                                # 合并原视频和填充片段
                                final_clip = concatenate_videoclips([final_clip, padding_clip], method="compose")
                                logger.info(f"已添加{shortfall:.2f}秒的静态画面填充，新视频时长: {final_clip.duration:.2f}秒")
                            except Exception as pad_error:
                                logger.error(f"添加填充画面时出错: {str(pad_error)}")
                    
                    # 根据调整后的视频时长，重新处理时长匹配情况
                    duration_diff = abs(final_clip.duration - demo_audio.duration)
                    if duration_diff > 0.1:  # 如果时长差异超过0.1秒
                        # 调整视频或音频以匹配
                        if final_clip.duration > demo_audio.duration:
                            # 如果视频较长，裁剪视频
                            logger.info(f"视频({final_clip.duration:.2f}秒)比音频({demo_audio.duration:.2f}秒)长，裁剪视频")
                            final_clip = final_clip.subclip(0, demo_audio.duration)
                        else:
                            # 如果音频较长，裁剪音频
                            logger.info(f"音频({demo_audio.duration:.2f}秒)比视频({final_clip.duration:.2f}秒)长，裁剪音频")
                            demo_audio = demo_audio.subclip(0, final_clip.duration)
                    
                    # 设置音频
                    final_clip = final_clip.set_audio(demo_audio)
                    logger.info(f"已设置Demo音频，最终合成视频时长: {final_clip.duration:.2f}秒")
                    
                    # 最后的校验：确保视频时长精确匹配demo_duration
                    if demo_duration is not None and abs(final_clip.duration - demo_duration) > 0.5:
                        logger.warning(f"最终视频时长({final_clip.duration:.2f}秒)与目标时长({demo_duration:.2f}秒)不匹配，强制调整")
                        final_clip = final_clip.set_duration(demo_duration)
                        logger.info(f"已强制设置视频时长为 {demo_duration:.2f}秒")
                else:
                    logger.info("使用原视频片段的音频")
                    
                    # 如果视频没有有效的音频轨道，添加静音
                    if final_clip.audio is None:
                        logger.warning("合成视频没有音频轨道，将使用静音")
                        # 创建一个空的音频片段
                        from moviepy.audio.AudioClip import AudioClip
                        silent_audio = AudioClip(lambda t: 0, duration=final_clip.duration)
                        final_clip = final_clip.set_audio(silent_audio)
                
                # 导出合成视频
                logger.info(f"导出魔法视频到: {output_path}")
                try:
                    final_clip.write_videofile(
                        output_path,
                        codec="libx264",
                        audio_codec="aac",
                        temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"),
                        remove_temp=True,
                        threads=4,
                        preset="fast",
                        ffmpeg_params=["-crf", "22"]
                    )
                except Exception as e:
                    logger.exception(f"导出视频时出错: {str(e)}")
                    raise
                
                # 关闭所有视频片段
                for clip in video_clips:
                    try:
                        clip.close()
                    except:
                        pass
                    
                try:
                    final_clip.close()
                except:
                    pass
                
                logger.info(f"魔法视频合成完成: {output_path}")
                
                # 清理临时文件
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录时出错: {str(e)}")
                
                return output_path
                
            except Exception as e:
                logger.exception(f"合成魔法视频时出错: {str(e)}")
                
                # 尝试清理临时文件
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass
                    
                return None
                
        except Exception as e:
            logger.exception(f"合成魔法视频时出错: {str(e)}")
            
            # 尝试清理临时文件
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass
            
            return None