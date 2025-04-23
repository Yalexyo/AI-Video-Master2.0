#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化版字幕生成模块
----------------
直接从CSV文件中读取视频URL列表，使用DashScope API提交转录任务，
并将转录结果转换为SRT格式的字幕文件。

功能说明:
    1. 从 Input/OSS_VideoList/export_urls.csv 文件中读取视频文件 URL 列表。
    2. 针对给定的视频文件 URL 列表，提交转录任务（使用 DashScope API）。
    3. 等待任务完成（状态为 SUCCEEDED 或 FAILED）。
    4. 如果转录任务成功，则生成 SRT 字幕文件。

输入:
    - CSV文件路径: Input/OSS_VideoList/export_urls.csv，包含 'url' 列。
    - DashScope API Key（通过 config.ini 文件配置）。
    - 热词列表ID（通过 config.ini 文件配置）。

输出:
    - SRT 文件: 保存路径为 Output/Subtitles/<base_name>.srt。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http import HTTPStatus
import dashscope
import json
import requests
import time
import csv
import logging
from utils import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("subtitle_generator_simplified")

class SubtitleGeneratorSimplified:
    """
    简化版字幕生成器类
    """
    def __init__(self, batch_mode=False):
        """
        初始化字幕生成器
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 从配置文件获取API Key和热词列表ID
        api_key = config.get_config("Paraformer.api_key")
        if not api_key:
            api_key = os.getenv('DASHSCOPE_API_KEY')
        
        # 设置API Key
        dashscope.api_key = api_key
        
        # 从配置获取热词列表ID
        self.vocabulary_id = config.get_config("Paraformer.vocabulary_id")
        
        # 获取路径配置
        self.input_dir = os.path.join(config.get_path('root_input_dir'), 'OSS_VideoList')
        self.output_dir = os.path.join(config.get_path('root_output_dir'), 'Subtitles')
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # ASR模型配置
        self.asr_model = config.get_config("Paraformer.default_model", "paraformer-v2")
    
    def read_urls_from_csv(self, csv_path):
        """
        从CSV文件中读取URL列表。
        
        参数:
            csv_path: CSV文件的路径。
        
        返回:
            URL列表。
        """
        urls = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'url' not in reader.fieldnames:
                    logger.error(f"CSV文件中缺少'url'列。可用列: {reader.fieldnames}")
                    return []
                
                for row in reader:
                    url = row['url'].strip()
                    if url:  # 确保URL不为空
                        urls.append(url)
        except FileNotFoundError:
            logger.error(f"文件不存在: {csv_path}")
        except Exception as e:
            logger.error(f"读取CSV文件失败: {e}")
        
        return urls
    
    def transcribe_and_save_srt(self, urls):
        """
        针对URL列表提交转录任务，并将结果保存为SRT字幕文件。
        
        参数:
            urls: 视频URL列表。
        
        返回:
            成功处理的URL数量。
        """
        if not urls:
            logger.error("没有可处理的URL")
            return 0
        
        success_count = 0
        
        for url in urls:
            # 获取基本文件名（不含扩展名）
            base_name = os.path.splitext(os.path.basename(url))[0]
            srt_path = os.path.join(self.output_dir, f"{base_name}.srt")
            
            # 检查字幕文件是否已存在
            if os.path.exists(srt_path) and not self.batch_mode:
                logger.info(f"字幕文件已存在: {srt_path}")
                if input("是否覆盖？(y/n): ").lower() != 'y':
                    logger.info(f"跳过处理 {url}")
                    success_count += 1  # 已有文件且选择不覆盖，视为成功
                    continue
            
            logger.info(f"处理URL: {url}")
            
            try:
                # 提交转录任务
                logger.info("提交转录任务...")
                response = dashscope.audio.asr.Transcription.async_call(
                    model=self.asr_model,
                    file_urls=[url],
                    language_hints=['zh', 'en'],
                    vocabulary_id=self.vocabulary_id
                )
                
                # 等待任务完成
                while True:
                    if response.output.task_status in ['SUCCEEDED', 'FAILED']:
                        break
                    logger.info("任务处理中，等待3秒...")
                    time.sleep(3)
                    response = dashscope.audio.asr.Transcription.fetch(
                        task=response.output.task_id
                    )
                
                # 检查任务是否成功
                if response.status_code == HTTPStatus.OK:
                    logger.info(f"转录任务完成: {url}")
                    
                    # 获取转录结果
                    results = response.output.get("results", [])
                    if results:
                        transcription_url = results[0].get("transcription_url")
                        if transcription_url:
                            # 下载转录JSON文件
                            resp = requests.get(transcription_url)
                            if resp.status_code == 200:
                                # 转换为SRT格式
                                srt_content = self.json_to_srt(resp.json())
                                
                                # 保存SRT文件
                                with open(srt_path, 'w', encoding='utf-8') as f:
                                    f.write(srt_content)
                                
                                logger.info(f"SRT文件保存成功: {srt_path}")
                                success_count += 1
                            else:
                                logger.error(f"下载转录文件失败，状态码: {resp.status_code}")
                        else:
                            logger.error("未找到转录URL")
                    else:
                        logger.error("未找到转录结果")
                else:
                    logger.error(f"转录任务失败，状态码: {response.status_code}")
            
            except Exception as e:
                logger.error(f"处理URL失败: {e}")
        
        return success_count
    
    def json_to_srt(self, json_data):
        """
        将转录结果JSON数据转换为SRT格式的字符串。
        
        参数:
            json_data: 转录结果JSON数据。
        
        返回:
            SRT格式的字符串。
        """
        srt_content = []
        counter = 1
        
        for transcript in json_data.get("transcripts", []):
            for sentence in transcript.get("sentences", []):
                # 时间单位：毫秒转秒
                start_time = sentence['begin_time'] / 1000.0
                end_time = sentence['end_time'] / 1000.0
                text = sentence['text']
                
                # 格式化时间
                start_str = self.format_time(start_time)
                end_str = self.format_time(end_time)
                
                # SRT格式
                srt_content.append(f"{counter}\n{start_str} --> {end_str}\n{text}\n")
                counter += 1
        
        return "\n".join(srt_content)
    
    def format_time(self, seconds):
        """
        将秒数转换为SRT格式的时间字符串（HH:MM:SS,mmm）。
        
        参数:
            seconds: 时间，单位为秒。
        
        返回:
            格式化的时间字符串。
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02}:{minutes:02}:{seconds_int:02},{milliseconds:03}"
    
    def process(self):
        """
        处理CSV文件中的URL列表。
        
        返回:
            成功返回True，否则返回False。
        """
        # 检查API Key
        if not dashscope.api_key:
            logger.error("未设置DashScope API Key")
            return False
        
        # 检查CSV文件
        csv_path = os.path.join(self.input_dir, 'export_urls.csv')
        if not os.path.exists(csv_path):
            logger.error(f"CSV文件不存在: {csv_path}")
            return False
        
        # 读取URL列表
        urls = self.read_urls_from_csv(csv_path)
        if not urls:
            logger.error("未找到有效的URL")
            return False
        
        # 处理URL列表
        logger.info(f"开始处理 {len(urls)} 个URL...")
        success_count = self.transcribe_and_save_srt(urls)
        
        # 输出处理结果
        logger.info(f"处理完成！共 {len(urls)} 个URL，{success_count} 个成功，{len(urls) - success_count} 个失败")
        
        return success_count > 0

# 单独运行时的入口
def generate_subtitles():
    """
    生成字幕的主函数。
    
    返回:
        成功返回True，否则返回False。
    """
    generator = SubtitleGeneratorSimplified()
    return generator.process()

# 直接运行脚本时
if __name__ == "__main__":
    # 初始化配置
    config.init()
    
    # 运行字幕生成器
    result = generate_subtitles()
    
    # 输出结果
    if result:
        print("字幕生成成功！")
    else:
        print("字幕生成失败，请检查日志。")
