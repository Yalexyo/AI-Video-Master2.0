#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
序列组装模块
-----------
将提取的视频片段按照合理的顺序进行拼接，形成完整的广告片，包括：
1. 从提取的片段中选择并排序组成主序列
2. 根据广告语生成匹配的片尾
3. 将主序列和片尾合成最终广告片
"""

import os
import sys
import json
import logging
import random
import tempfile
from pathlib import Path
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sequence_assembler")

# 导入工具模块
from utils import config, io_handlers, video_utils, text_analysis, model_handlers

class SequenceAssembler:
    """
    序列组装器类
    """
    def __init__(self, batch_mode=False):
        """
        初始化序列组装器
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 获取路径配置
        self.input_dir = config.get_path('root_input_dir')
        self.clips_dir = os.path.join(config.get_path('root_output_dir'), 'Clips')
        self.temp_dir = os.path.join(config.get_path('root_output_dir'), 'Temp')
        self.final_dir = os.path.join(config.get_path('root_output_dir'), 'Final')
        
        # 确保输出目录存在
        io_handlers.ensure_directory(self.temp_dir)
        io_handlers.ensure_directory(self.final_dir)
        
        # 文件路径
        self.slogan_file = os.path.join(self.input_dir, 'slogan.txt')
        self.logo_file = os.path.join(self.input_dir, 'OtherResources', 'logo.png')
        self.main_sequence_file = os.path.join(self.temp_dir, 'main_sequence.mp4')
        self.end_slate_file = os.path.join(self.temp_dir, 'end_slate.mp4')
        self.final_video_file = os.path.join(self.final_dir, 'advertisement_final.mp4')
        
        # 拼接配置
        self.target_duration = 30.0  # 目标持续时间(秒)
        self.duration_tolerance = 5.0  # 持续时间容差(秒)
        self.min_duration = 27.0  # 最小持续时间(秒)
        self.max_duration = 40.0  # 最大持续时间(秒)
        self.end_slate_duration = 5.0  # 片尾持续时间(秒)
        self.transition_duration = 0.5  # 过渡效果持续时间(秒)
        
        # 片尾风格
        self.end_style = config.get_param('end_style', '简约')

    def load_slogan(self):
        """
        加载广告宣传语
        
        返回:
            广告宣传语文本
        """
        if not os.path.exists(self.slogan_file):
            logger.warning(f"广告语文件不存在: {self.slogan_file}")
            
            # 使用默认广告语
            default_slogan = "发现生活的美好，做最好的自己。"
            
            # 创建默认广告语文件
            try:
                io_handlers.ensure_directory(os.path.dirname(self.slogan_file))
                with open(self.slogan_file, 'w', encoding='utf-8') as f:
                    f.write(default_slogan)
                
                logger.info(f"已创建默认广告语文件: {self.slogan_file}")
            except Exception as e:
                logger.error(f"创建默认广告语文件失败: {e}")
            
            return default_slogan
        
        try:
            with open(self.slogan_file, 'r', encoding='utf-8') as f:
                slogan = f.read().strip()
            
            logger.info(f"已加载广告语: {slogan}")
            return slogan
        
        except Exception as e:
            logger.error(f"加载广告语失败: {e}")
            return "发现生活的美好，做最好的自己。"

    def list_video_clips(self):
        """
        列出所有提取的视频片段
        
        返回:
            视频片段列表，按类别分组
        """
        clips_by_category = defaultdict(list)
        
        # 查找所有视频片段
        for root, dirs, files in os.walk(self.clips_dir):
            for file in files:
                if file.endswith('.mp4') or file.endswith('.mov'):
                    file_path = os.path.join(root, file)
                    
                    # 获取类别(从目录名中提取)
                    category_dir = os.path.basename(root)
                    if category_dir.startswith('Category_'):
                        category = category_dir[len('Category_'):]
                    else:
                        category = category_dir
                    
                    # 获取视频元数据
                    metadata = video_utils.get_video_metadata(file_path)
                    
                    # 获取片段索引信息
                    clip_info = io_handlers.get_clip_info(file_path)
                    
                    # 添加到对应类别
                    clips_by_category[category].append({
                        'path': file_path,
                        'category': category,
                        'duration': metadata.get('duration', 0),
                        'width': metadata.get('width', 1280),
                        'height': metadata.get('height', 720),
                        'fps': metadata.get('frame_rate', 30),
                        'score': clip_info.get('score', 0.5) if clip_info else 0.5,
                        'text': clip_info.get('text', '') if clip_info else ''
                    })
        
        # 如果没有找到视频片段，查找示例文本文件
        if not clips_by_category:
            for root, dirs, files in os.walk(self.clips_dir):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        
                        # 获取类别(从目录名中提取)
                        category_dir = os.path.basename(root)
                        if category_dir.startswith('Category_'):
                            category = category_dir[len('Category_'):]
                        else:
                            category = category_dir
                        
                        # 读取文本内容
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                text = f.read()
                        except:
                            text = f"示例片段：{category}"
                        
                        # 添加到对应类别
                        clips_by_category[category].append({
                            'path': file_path,
                            'category': category,
                            'duration': 5.0,  # 假定持续时间
                            'width': 1280,
                            'height': 720,
                            'fps': 30,
                            'score': 0.5,
                            'text': text,
                            'is_example': True
                        })
        
        # 每个类别按得分排序
        for category in clips_by_category:
            clips_by_category[category].sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return clips_by_category

    def select_clips_for_sequence(self, clips_by_category):
        """
        选择片段组成主序列
        
        参数:
            clips_by_category: 按类别分组的视频片段列表
        
        返回:
            选择的片段列表，按播放顺序排列
        """
        # 如果没有片段，返回空列表
        if not clips_by_category:
            return []
        
        # 获取所有类别
        categories = list(clips_by_category.keys())
        
        # 根据类别数量确定每个类别选择的片段数量
        num_categories = len(categories)
        clips_per_category = max(1, min(3, int(9 / num_categories)))
        
        # 根据片段数量和持续时间选择合适的片段
        selected_clips = []
        
        # 每个类别选择若干个片段
        for category in categories:
            clips = clips_by_category[category]
            
            # 按得分排序
            sorted_clips = sorted(clips, key=lambda x: x.get('score', 0), reverse=True)
            
            # 选择得分最高的几个片段
            for i in range(min(clips_per_category, len(sorted_clips))):
                selected_clips.append(sorted_clips[i])
        
        # 根据总时长调整片段数量
        total_duration = sum(clip.get('duration', 0) for clip in selected_clips)
        target_duration = self.target_duration - self.end_slate_duration
        
        # 如果总时长过长，移除一些低分片段
        if total_duration > target_duration + self.duration_tolerance:
            # 按得分排序
            selected_clips.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 保留高分片段
            adjusted_clips = []
            current_duration = 0
            
            for clip in selected_clips:
                if current_duration + clip.get('duration', 0) <= target_duration + self.duration_tolerance:
                    adjusted_clips.append(clip)
                    current_duration += clip.get('duration', 0)
            
            selected_clips = adjusted_clips
        
        # 如果总时长过短，添加一些其他片段
        elif total_duration < target_duration - self.duration_tolerance:
            # 找出所有未选择的片段
            unused_clips = []
            
            for category in categories:
                for clip in clips_by_category[category]:
                    if clip not in selected_clips:
                        unused_clips.append(clip)
            
            # 按得分排序
            unused_clips.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 添加高分片段
            current_duration = total_duration
            
            for clip in unused_clips:
                if current_duration + clip.get('duration', 0) <= target_duration + self.duration_tolerance:
                    selected_clips.append(clip)
                    current_duration += clip.get('duration', 0)
                    
                    # 如果达到目标时长，退出循环
                    if current_duration >= target_duration - self.duration_tolerance:
                        break
        
        # 按主题和内容组织片段顺序
        # 将片段按类别分组
        clips_by_category = defaultdict(list)
        
        for clip in selected_clips:
            clips_by_category[clip['category']].append(clip)
        
        # 重新组织顺序
        ordered_clips = []
        
        # 按照类别添加片段
        for category in categories:
            if category in clips_by_category:
                # 类别内部按得分排序
                category_clips = sorted(clips_by_category[category], key=lambda x: x.get('score', 0), reverse=True)
                ordered_clips.extend(category_clips)
        
        # 计算最终时长
        final_duration = sum(clip.get('duration', 0) for clip in ordered_clips)
        
        logger.info(f"已选择 {len(ordered_clips)} 个片段，总时长: {final_duration:.2f}秒")
        
        return ordered_clips

    def create_main_sequence(self, selected_clips):
        """
        创建主序列视频
        
        参数:
            selected_clips: 选择的片段列表
        
        返回:
            成功返回True，否则返回False
        """
        if not selected_clips:
            logger.warning("没有选择到片段，无法创建主序列")
            return False
        
        # 检查是否存在示例片段
        has_example = any(clip.get('is_example', False) for clip in selected_clips)
        
        if has_example:
            logger.warning("存在示例片段，无法创建真实视频，使用示例视频")
            return self.create_example_main_sequence()
        
        try:
            # 对每个视频片段应用转场效果
            processed_clips = []
            
            for i, clip in enumerate(selected_clips):
                # 创建临时文件存放处理后的片段
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # 应用转场效果(根据位置选择不同效果)
                if i == 0:  # 第一个片段
                    # 开始淡入
                    success = video_utils.add_fade_effect(
                        input_path=clip['path'],
                        output_path=temp_path,
                        fade_in_duration=self.transition_duration,
                        fade_out_duration=self.transition_duration if i < len(selected_clips) - 1 else 0,
                        overwrite=True
                    )
                elif i == len(selected_clips) - 1:  # 最后一个片段
                    # 结束淡出
                    success = video_utils.add_fade_effect(
                        input_path=clip['path'],
                        output_path=temp_path,
                        fade_in_duration=self.transition_duration,
                        fade_out_duration=self.transition_duration,
                        overwrite=True
                    )
                else:  # 中间片段
                    # 淡入淡出
                    success = video_utils.add_fade_effect(
                        input_path=clip['path'],
                        output_path=temp_path,
                        fade_in_duration=self.transition_duration,
                        fade_out_duration=self.transition_duration,
                        overwrite=True
                    )
                
                if success:
                    processed_clips.append({
                        'path': temp_path,
                        'duration': clip['duration'],
                        'is_temp': True
                    })
                else:
                    # 如果添加转场效果失败，使用原始片段
                    processed_clips.append({
                        'path': clip['path'],
                        'duration': clip['duration'],
                        'is_temp': False
                    })
            
            # 创建片段列表文件
            clips_list_path = os.path.join(self.temp_dir, 'clips_list.txt')
            
            with open(clips_list_path, 'w', encoding='utf-8') as f:
                for clip in processed_clips:
                    f.write(f"file '{clip['path']}'\n")
            
            # 拼接视频片段
            success = video_utils.concat_videos(
                clips_list=clips_list_path,
                output_path=self.main_sequence_file,
                method='concat_demuxer',
                overwrite=True
            )
            
            # 删除临时文件
            for clip in processed_clips:
                if clip.get('is_temp', False):
                    try:
                        os.remove(clip['path'])
                    except:
                        pass
            
            try:
                os.remove(clips_list_path)
            except:
                pass
            
            if success:
                logger.info(f"主序列创建成功: {self.main_sequence_file}")
                return True
            else:
                logger.error(f"主序列创建失败: {self.main_sequence_file}")
                return False
        
        except Exception as e:
            logger.error(f"创建主序列失败: {e}")
            return False

    def create_end_slate(self, slogan):
        """
        创建片尾视频
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 创建片尾视频
            end_style = self.end_style
            
            # 根据风格创建不同类型的片尾
            if end_style == '简约':
                return self.create_simple_end_slate(slogan)
            elif end_style == '动感':
                return self.create_dynamic_end_slate(slogan)
            elif end_style == '商务':
                return self.create_business_end_slate(slogan)
            elif end_style == '温馨':
                return self.create_warm_end_slate(slogan)
            elif end_style == '现代':
                return self.create_modern_end_slate(slogan)
            else:
                # 默认风格
                return self.create_simple_end_slate(slogan)
        
        except Exception as e:
            logger.error(f"创建片尾失败: {e}")
            return self.create_example_end_slate(slogan)

    def create_simple_end_slate(self, slogan):
        """
        创建简约风格片尾
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 创建简单的文本画面
            text_image_path = os.path.join(self.temp_dir, 'end_slate_text.png')
            
            # 创建文本图像
            success = video_utils.create_text_image(
                text=slogan,
                output_path=text_image_path,
                width=1920,
                height=1080,
                font_size=60,
                font_color='white',
                background_color='black',
                position='center',
                overwrite=True
            )
            
            if not success:
                logger.error("创建文本图像失败")
                return self.create_example_end_slate(slogan)
            
            # 创建片尾视频
            success = video_utils.create_video_from_image(
                image_path=text_image_path,
                output_path=self.end_slate_file,
                duration=self.end_slate_duration,
                fade_in=True,
                fade_out=True,
                overwrite=True
            )
            
            # 删除临时文件
            try:
                os.remove(text_image_path)
            except:
                pass
            
            if success:
                logger.info(f"片尾创建成功: {self.end_slate_file}")
                return True
            else:
                logger.error(f"片尾创建失败: {self.end_slate_file}")
                return self.create_example_end_slate(slogan)
        
        except Exception as e:
            logger.error(f"创建简约风格片尾失败: {e}")
            return self.create_example_end_slate(slogan)

    def create_dynamic_end_slate(self, slogan):
        """
        创建动感风格片尾
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        # 动感风格更复杂，目前还是使用简约风格替代
        return self.create_simple_end_slate(slogan)

    def create_business_end_slate(self, slogan):
        """
        创建商务风格片尾
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        # 商务风格更复杂，目前还是使用简约风格替代
        return self.create_simple_end_slate(slogan)

    def create_warm_end_slate(self, slogan):
        """
        创建温馨风格片尾
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        # 温馨风格更复杂，目前还是使用简约风格替代
        return self.create_simple_end_slate(slogan)

    def create_modern_end_slate(self, slogan):
        """
        创建现代风格片尾
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        # 现代风格更复杂，目前还是使用简约风格替代
        return self.create_simple_end_slate(slogan)

    def create_example_main_sequence(self):
        """
        创建示例主序列视频
        
        返回:
            成功返回True，否则返回False
        """
        logger.info("创建示例主序列视频")
        
        try:
            # 创建示例文本图像
            text_image_path = os.path.join(self.temp_dir, 'main_sequence_text.png')
            
            text = "示例主序列视频\n\n在实际运行时，这里会是从视频片段中提取的内容拼接而成的视频。"
            
            # 创建文本图像
            success = video_utils.create_text_image(
                text=text,
                output_path=text_image_path,
                width=1920,
                height=1080,
                font_size=48,
                font_color='white',
                background_color='darkblue',
                position='center',
                overwrite=True
            )
            
            if not success:
                logger.error("创建文本图像失败")
                return False
            
            # 创建视频
            success = video_utils.create_video_from_image(
                image_path=text_image_path,
                output_path=self.main_sequence_file,
                duration=25.0,
                fade_in=True,
                fade_out=True,
                overwrite=True
            )
            
            # 删除临时文件
            try:
                os.remove(text_image_path)
            except:
                pass
            
            if success:
                logger.info(f"示例主序列视频创建成功: {self.main_sequence_file}")
                return True
            else:
                logger.error(f"示例主序列视频创建失败: {self.main_sequence_file}")
                return False
        
        except Exception as e:
            logger.error(f"创建示例主序列视频失败: {e}")
            return False

    def create_example_end_slate(self, slogan):
        """
        创建示例片尾视频
        
        参数:
            slogan: 广告宣传语
        
        返回:
            成功返回True，否则返回False
        """
        logger.info("创建示例片尾视频")
        
        try:
            # 创建示例文本图像
            text_image_path = os.path.join(self.temp_dir, 'end_slate_text.png')
            
            text = f"示例片尾视频\n\n{slogan}"
            
            # 创建文本图像
            success = video_utils.create_text_image(
                text=text,
                output_path=text_image_path,
                width=1920,
                height=1080,
                font_size=48,
                font_color='white',
                background_color='black',
                position='center',
                overwrite=True
            )
            
            if not success:
                logger.error("创建文本图像失败")
                return False
            
            # 创建视频
            success = video_utils.create_video_from_image(
                image_path=text_image_path,
                output_path=self.end_slate_file,
                duration=self.end_slate_duration,
                fade_in=True,
                fade_out=True,
                overwrite=True
            )
            
            # 删除临时文件
            try:
                os.remove(text_image_path)
            except:
                pass
            
            if success:
                logger.info(f"示例片尾视频创建成功: {self.end_slate_file}")
                return True
            else:
                logger.error(f"示例片尾视频创建失败: {self.end_slate_file}")
                return False
        
        except Exception as e:
            logger.error(f"创建示例片尾视频失败: {e}")
            return False

    def create_final_video(self):
        """
        创建最终广告视频
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 检查主序列和片尾是否存在
            if not os.path.exists(self.main_sequence_file):
                logger.error(f"主序列文件不存在: {self.main_sequence_file}")
                return False
            
            if not os.path.exists(self.end_slate_file):
                logger.error(f"片尾文件不存在: {self.end_slate_file}")
                return False
            
            # 创建片段列表文件
            clips_list_path = os.path.join(self.temp_dir, 'final_clips_list.txt')
            
            with open(clips_list_path, 'w', encoding='utf-8') as f:
                f.write(f"file '{self.main_sequence_file}'\n")
                f.write(f"file '{self.end_slate_file}'\n")
            
            # 拼接视频
            success = video_utils.concat_videos(
                clips_list=clips_list_path,
                output_path=self.final_video_file,
                method='concat_demuxer',
                overwrite=True
            )
            
            # 删除临时文件
            try:
                os.remove(clips_list_path)
            except:
                pass
            
            if success:
                # 获取视频元数据
                metadata = video_utils.get_video_metadata(self.final_video_file)
                duration = metadata.get('duration', 0)
                
                logger.info(f"最终视频创建成功: {self.final_video_file}")
                logger.info(f"视频时长: {duration:.2f}秒")
                
                # 添加到视频索引
                video_info = {
                    'duration': duration,
                    'width': metadata.get('width', 1920),
                    'height': metadata.get('height', 1080),
                    'fps': metadata.get('frame_rate', 30),
                    'contains_example': not os.path.exists(self.clips_dir) or len(os.listdir(self.clips_dir)) == 0
                }
                
                io_handlers.add_video_to_index(self.final_video_file, video_info)
                
                return True
            else:
                logger.error(f"最终视频创建失败: {self.final_video_file}")
                return False
        
        except Exception as e:
            logger.error(f"创建最终视频失败: {e}")
            return False

    def process(self):
        """
        处理序列组装
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 检查FFmpeg是否可用
            if not video_utils.check_ffmpeg():
                logger.error("FFmpeg未安装或不可用，无法继续")
                
                # 创建示例视频
                self.create_example_main_sequence()
                
                # 加载广告语
                slogan = self.load_slogan()
                
                # 创建示例片尾
                self.create_example_end_slate(slogan)
                
                # 创建最终视频
                self.create_final_video()
                
                return True
            
            # 检查输出文件是否已存在
            if os.path.exists(self.final_video_file) and not self.batch_mode:
                logger.info(f"最终视频文件已存在: {self.final_video_file}")
                
                # 询问是否覆盖
                response = input(f"最终视频文件已存在: {self.final_video_file}，是否覆盖？(y/n): ")
                if response.lower() != 'y':
                    logger.info("跳过序列组装")
                    return True
            
            # 列出所有视频片段
            clips_by_category = self.list_video_clips()
            
            if not clips_by_category:
                logger.warning("没有找到视频片段，创建示例视频")
                
                # 创建示例主序列
                self.create_example_main_sequence()
                
                # 加载广告语
                slogan = self.load_slogan()
                
                # 创建示例片尾
                self.create_example_end_slate(slogan)
                
                # 创建最终视频
                self.create_final_video()
                
                return True
            
            # 选择片段组成主序列
            selected_clips = self.select_clips_for_sequence(clips_by_category)
            
            if not selected_clips:
                logger.warning("没有选择到合适的片段，创建示例视频")
                
                # 创建示例主序列
                self.create_example_main_sequence()
                
                # 加载广告语
                slogan = self.load_slogan()
                
                # 创建示例片尾
                self.create_example_end_slate(slogan)
                
                # 创建最终视频
                self.create_final_video()
                
                return True
            
            # 创建主序列
            main_sequence_success = self.create_main_sequence(selected_clips)
            
            if not main_sequence_success:
                logger.warning("创建主序列失败，使用示例视频")
                
                # 创建示例主序列
                self.create_example_main_sequence()
            
            # 加载广告语
            slogan = self.load_slogan()
            
            # 创建片尾
            end_slate_success = self.create_end_slate(slogan)
            
            if not end_slate_success:
                logger.warning("创建片尾失败，使用示例片尾")
                
                # 创建示例片尾
                self.create_example_end_slate(slogan)
            
            # 创建最终视频
            final_success = self.create_final_video()
            
            return final_success
        
        except Exception as e:
            logger.error(f"序列组装失败: {e}")
            
            # 尝试创建示例视频
            try:
                # 创建示例主序列
                self.create_example_main_sequence()
                
                # 加载广告语
                slogan = self.load_slogan()
                
                # 创建示例片尾
                self.create_example_end_slate(slogan)
                
                # 创建最终视频
                self.create_final_video()
                
                return True
            
            except Exception as inner_e:
                logger.error(f"创建示例视频也失败了: {inner_e}")
                return False
