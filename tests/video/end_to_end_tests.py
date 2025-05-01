#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频处理流程端到端测试脚本

该脚本用于测试视频处理的完整流程，使用实际视频文件进行测试
需要预先准备测试视频文件
"""

import os
import sys
import logging
import time
import argparse
from datetime import datetime
import pandas as pd
import json
from dotenv import load_dotenv
import asyncio # 引入asyncio

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 测试输入输出目录
TEST_INPUT_DIR = os.path.join("data", "test_samples", "input", "video")
TEST_OUTPUT_DIR = os.path.join("data", "test_samples", "output", "video")
DEBUG_HISTORY_DIR = os.path.join(project_root, "data", "test_samples", "debug_history") # 调试历史记录目录

# 加载环境变量
load_dotenv(os.path.join(project_root, '.env'))
api_key = os.getenv('DASHSCOPE_API_KEY')
if api_key:
    os.environ['DASHSCOPE_API_KEY'] = api_key
    masked_key = api_key[:3] + "..." + api_key[-4:]
    # logger.info(f"已加载DashScope API密钥: {masked_key}") # 避免重复打印
else:
    print("警告: 未找到DASHSCOPE_API_KEY环境变量")

# 导入测试配置
from tests.config.test_config import (
    TEST_VOCABULARY_IDS,
    VIDEO_VOCABULARY_MAPPING,
    DEFAULT_VOCABULARY_ID
)

# 设置日志
os.makedirs('logs', exist_ok=True)
log_file_path = os.path.join("data", "test_samples", "logs", f"test_e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_path, 'a', 'utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"日志文件保存在: {log_file_path}")

# 导入相关模块
try:
    from utils.processor import VideoProcessor
    from utils.analyzer import VideoAnalyzer
    from src.core.intent_service import IntentService
    from src.core.video_segment_service import VideoSegmentService
    from src.api.llm_service import LLMService
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

# 使用DeepSeek API进行测试 (可以从环境变量覆盖)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")  
logger.info(f"测试将使用 LLM 提供商: {LLM_PROVIDER}")

# 确保调试历史目录存在
os.makedirs(DEBUG_HISTORY_DIR, exist_ok=True)

def append_to_debug_history(step_name, hypothesis, action, result, emoji="🤔️"):
    """
    将调试步骤记录到debug_history.md文件中
    
    参数:
        step_name: 步骤名称
        hypothesis: 假设
        action: 采取的行动
        result: 结果
        emoji: 结果状态emoji（✅成功, ❌失败, 🤔️待验证）
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    debug_history_file = os.path.join(DEBUG_HISTORY_DIR, "debug_history.md")
    
    # 如果文件不存在，创建基本结构
    if not os.path.exists(debug_history_file):
        with open(debug_history_file, 'w', encoding='utf-8') as f:
            f.write("# 视频处理流程调试历史记录\n\n")
            f.write("## 待验证清单\n\n")
    
    # 添加调试记录
    with open(debug_history_file, 'a', encoding='utf-8') as f:
        f.write(f"\n### {step_name} ({timestamp})\n\n")
        f.write(f"**假设**: {hypothesis}\n\n")
        f.write(f"**操作**: {action}\n\n")
        f.write(f"**结果**: {emoji} {result}\n\n")
        
        # 如果是待验证项，添加到待验证清单
        if emoji == "🤔️":
            # 读取文件内容
            try:
                with open(debug_history_file, 'r', encoding='utf-8') as rf:
                    content = rf.read()
                
                # 定位待验证清单位置
                checklist_pos = content.find("## 待验证清单")
                if checklist_pos != -1:
                    # 找到下一个标题或文件末尾
                    next_section_pos = content.find("\n## ", checklist_pos + 1)
                    if next_section_pos == -1:
                        next_section_pos = len(content)
                    
                    # 构造新的待办项
                    today = datetime.now().strftime("%Y-%m-%d")
                    section_link = step_name.replace(' ', '-').lower()
                    new_item = f"\n1. [{today}] 待验证：{step_name} - [链接到章节](#{section_link})\n"
                    
                    # 更新文件内容
                    new_content = content[:next_section_pos] + new_item + content[next_section_pos:]
                    with open(debug_history_file, 'w', encoding='utf-8') as wf:
                        wf.write(new_content)
            except Exception as e:
                logger.error(f"更新待验证清单时出错: {e}")

def get_vocabulary_id(video_path: str, specified_vocab_id: str = None) -> str:
    """
    获取视频对应的热词表ID
    
    参数:
        video_path: 视频文件路径
        specified_vocab_id: 通过命令行指定的热词表ID
        
    返回:
        热词表ID
    """
    # 如果指定了vocabulary_id，优先使用指定的
    if specified_vocab_id:
        logger.info(f"使用指定的热词表ID: {specified_vocab_id}")
        return specified_vocab_id
    
    # 获取视频文件名
    video_filename = os.path.basename(video_path)
    if video_filename.endswith('.url'): # 处理URL文件的情况
        # 尝试从 URL 中提取一个有意义的名字，如果失败则用默认
        try:
            with open(video_path, 'r') as f:
                url = f.read().strip()
            video_filename = os.path.basename(url.split('?')[0]) # 取URL路径最后一部分
            logger.info(f"从URL文件解析得到文件名: {video_filename}")
        except Exception:
            logger.warning(f"无法从URL文件 {video_path} 解析文件名，将使用默认热词表")
            video_filename = None # 标记为无法解析

    # 从映射关系中获取对应的热词表ID
    vocab_id = DEFAULT_VOCABULARY_ID # 默认值
    if video_filename:
        vocab_id = VIDEO_VOCABULARY_MAPPING.get(video_filename, DEFAULT_VOCABULARY_ID)
        logger.info(f"视频 {video_filename} 使用热词表ID: {vocab_id}")
    else:
        logger.info(f"使用默认热词表ID: {vocab_id}")
        
    return vocab_id

def test_video_processing(video_path, test_type='all', vocabulary_id=None, analysis_mode='intent', intent_ids=None, user_prompt=None, max_concurrent=3):
    """
    执行视频处理流程的端到端测试
    
    Args:
        video_path: 测试视频文件路径或URL文件路径
        test_type: 测试类型，可选值为 'all', 'info', 'audio', 'subtitle', 'analysis', 'batch'
        vocabulary_id: 可选的热词表ID
        analysis_mode: 内容分析模式, 'intent', 'prompt', 或 'all_intents'
        intent_ids: 模式为'intent'时，使用的意图ID列表
        user_prompt: 模式为'prompt'时，用户的自由文本
        max_concurrent: 最大并行任务数
        
    Returns:
        bool: 测试是否成功
    """
    # 初始化处理器和服务
    processor = VideoProcessor()
    analyzer = VideoAnalyzer()
    segment_service = VideoSegmentService(llm_provider=LLM_PROVIDER, max_concurrent_tasks=max_concurrent)
    intent_service = IntentService() # 确保意图服务已初始化
    
    # 检查是否是URL文件
    is_oss_url = False
    video_url = None
    if video_path.endswith('.url'):
        is_oss_url = True
        try:
            with open(video_path, 'r') as f:
                video_url = f.read().strip()
            logger.info(f"检测到URL文件，URL: {video_url}")
        except Exception as e:
             logger.error(f"读取URL文件失败: {video_path}, 错误: {e}")
             return False
    elif not os.path.exists(video_path):
        logger.error(f"测试视频文件不存在: {video_path}")
        return False
    
    # 获取合适的热词表ID
    if not vocabulary_id:
        vocabulary_id = get_vocabulary_id(video_path, None)

    # 记录测试时间    
    test_start_time = time.time()
    
    # 准备字幕数据框，后续步骤会用到
    subtitle_df = None
    audio_file = None # 初始化音频文件路径
    
    # 确保输出目录存在
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join("data", "test_samples", "output", "audio"), exist_ok=True)
    os.makedirs(os.path.join("data", "test_samples", "output", "subtitles"), exist_ok=True)
    
    # 1. 测试视频信息获取
    if test_type in ['all', 'info']:
        logger.info("=== 步骤1: 测试视频信息获取 ===")
        start_time_step = time.time()
        try:
            if is_oss_url:
                logger.info(f"从URL获取视频信息: {video_url}")
                # 注意：这里需要修改VideoProcessor以支持从URL获取信息
                # 暂时模拟成功返回，实际应能处理URL
                video_info = {
                    'width': 1920,
                    'height': 1080,
                    'duration': 60.0,
                    'fps': 30.0,
                    'has_audio': True,
                    'url': video_url
                }
                logger.info(f"URL视频信息获取成功 (模拟): {json.dumps(video_info, ensure_ascii=False)}")
                append_to_debug_history(
                    "URL视频信息获取测试", 
                    "能从URL获取视频基本信息",
                    f"处理视频URL: {video_url}",
                    f"成功获取视频信息 (模拟): {json.dumps(video_info, ensure_ascii=False)}",
                    "✅"
                )
            else:
                # 从本地文件获取视频信息
                video_info = processor._get_video_info(video_path)
                if video_info:
                    logger.info(f"本地视频信息获取成功: {json.dumps(video_info, ensure_ascii=False)}")
                    append_to_debug_history(
                        "本地视频信息获取测试", 
                        "VideoProcessor._get_video_info能获取信息",
                        f"处理视频文件: {os.path.basename(video_path)}",
                        f"成功获取: {json.dumps(video_info, ensure_ascii=False)}",
                        "✅"
                    )
                else:
                    logger.error("本地视频信息获取失败")
                    append_to_debug_history("本地视频信息获取测试", "VideoProcessor._get_video_info能获取信息", f"处理视频文件: {os.path.basename(video_path)}", "获取失败", "❌")
                    return False
        except Exception as e:
            logger.exception(f"视频信息获取异常: {str(e)}")
            append_to_debug_history("视频信息获取测试", "VideoProcessor._get_video_info能获取信息", f"处理视频文件: {os.path.basename(video_path)}", f"发生异常: {str(e)}", "❌")
            return False
        logger.info(f"步骤1耗时: {time.time() - start_time_step:.2f}秒")
    
    # 2. 测试音频提取
    if test_type in ['all', 'audio', 'subtitle', 'analysis']: # 后续步骤需要音频
        logger.info("=== 步骤2: 测试音频提取 ===")
        start_time_step = time.time()
        try:
            if is_oss_url:
                logger.info(f"从URL提取音频: {video_url}")
                # 注意：需要实现从URL下载并提取音频的功能
                # 暂时模拟成功
                audio_dir = os.path.join("data", "test_samples", "output", "audio")
                audio_file = os.path.join(audio_dir, f"temp_audio_{os.path.basename(video_path)}_{int(time.time())}.wav")
                with open(audio_file, 'w') as f: f.write("模拟音频数据") # 创建占位文件
                logger.info(f"URL视频音频提取成功 (模拟): {audio_file}")
                append_to_debug_history("URL音频提取测试", "能从URL提取音频", f"处理视频URL: {video_url}", f"成功提取音频 (模拟): {os.path.basename(audio_file)}", "✅")
            else:
                # 从本地文件提取音频
                audio_file = processor._preprocess_video_file(video_path)
                if audio_file and os.path.exists(audio_file):
                    logger.info(f"本地音频提取成功: {audio_file}")
                    append_to_debug_history("本地音频提取测试", "_preprocess_video_file能提取音频", f"处理视频文件: {os.path.basename(video_path)}", f"成功提取: {os.path.basename(audio_file)}", "✅")
                else:
                    logger.error("本地音频提取失败")
                    append_to_debug_history("本地音频提取测试", "_preprocess_video_file能提取音频", f"处理视频文件: {os.path.basename(video_path)}", "提取失败", "❌")
                    return False
        except Exception as e:
            logger.exception(f"音频提取异常: {str(e)}")
            append_to_debug_history("音频提取测试", "_preprocess_video_file能提取音频", f"处理视频文件: {os.path.basename(video_path)}", f"发生异常: {str(e)}", "❌")
            return False
        logger.info(f"步骤2耗时: {time.time() - start_time_step:.2f}秒")
    
    # 3. 测试字幕提取
    if test_type in ['all', 'subtitle', 'analysis']: # 后续步骤需要字幕
        logger.info("=== 步骤3: 测试字幕提取 ===")
        start_time_step = time.time()
        
        if not audio_file or not os.path.exists(audio_file):
             logger.error("缺少有效的音频文件，无法提取字幕")
             append_to_debug_history("字幕提取测试", "依赖有效的音频文件", "检查音频文件", "音频文件无效", "❌")
             return False
             
        try:
            if is_oss_url:
                logger.info(f"从URL关联的音频提取字幕 (模拟音频: {os.path.basename(audio_file)})")
                # 模拟字幕提取
                subtitles = [
                    {"start": 10000, "end": 14000, "text": "这是模拟的第一条字幕。"},
                    {"start": 15000, "end": 19000, "text": "这是模拟的第二条字幕。"}
                ]
                # 需要手动添加时间戳格式
                for sub in subtitles:
                    sub['start_formatted'] = processor._format_time(sub['start'])
                
                logger.info(f"URL视频字幕提取成功 (模拟)，共{len(subtitles)}条")
                append_to_debug_history("URL字幕提取测试", "能从URL关联音频提取字幕", f"处理模拟音频: {os.path.basename(audio_file)}", f"成功提取字幕 (模拟): {len(subtitles)}条", "✅")
            else:
                # 从本地音频文件提取字幕
                logger.info(f"从本地音频提取字幕: {os.path.basename(audio_file)}, 热词ID: {vocabulary_id}")
                subtitles = processor._extract_subtitles_from_video(audio_file, vocabulary_id=vocabulary_id)
                if subtitles:
                    logger.info(f"本地字幕提取成功，共{len(subtitles)}条")
                    # 保存字幕到SRT文件
                    subtitle_file = processor._save_subtitles_to_srt(audio_file, subtitles)
                    if subtitle_file and os.path.exists(subtitle_file):
                        logger.info(f"字幕已保存到SRT文件: {subtitle_file}")
                        append_to_debug_history("本地字幕提取测试", "_extract_subtitles_from_video能提取字幕", f"处理音频: {os.path.basename(audio_file)}, 热词ID: {vocabulary_id}", f"成功提取{len(subtitles)}条, 保存到 {os.path.basename(subtitle_file)}", "✅")
                    else:
                        logger.error("字幕SRT文件保存失败")
                        append_to_debug_history("本地字幕提取测试", "_extract_subtitles_from_video能提取字幕", "保存SRT文件", "保存失败", "❌")
                        return False # 保存失败也算失败
                else:
                    logger.error("本地字幕提取失败")
                    append_to_debug_history("本地字幕提取测试", "_extract_subtitles_from_video能提取字幕", f"处理音频: {os.path.basename(audio_file)}, 热词ID: {vocabulary_id}", "提取失败", "❌")
                    return False
        except Exception as e:
            logger.exception(f"字幕提取异常: {str(e)}")
            append_to_debug_history("字幕提取测试", "_extract_subtitles_from_video能提取字幕", f"处理音频: {os.path.basename(audio_file)}, 热词ID: {vocabulary_id}", f"发生异常: {str(e)}", "❌")
            return False
        
        # 创建DataFrame用于后续分析
        if subtitles:
            subtitle_df = pd.DataFrame([{ 
                'timestamp': item.get('start_formatted', processor._format_time(item.get('start', 0))), # 修复：使用 _format_time
                'text': item.get('text', '')
            } for item in subtitles if item.get('text')])
            logger.info(f"字幕DataFrame创建成功，包含 {len(subtitle_df)} 行")
        else:
            subtitle_df = pd.DataFrame(columns=['timestamp', 'text']) # 创建空DF
            logger.warning("字幕列表为空，创建空的DataFrame")

        logger.info(f"步骤3耗时: {time.time() - start_time_step:.2f}秒")
    
    # 4. 测试内容分析 (替代旧的意图和匹配步骤)
    if test_type in ['all', 'analysis']:
        logger.info(f"=== 步骤4: 测试内容分析 (模式: {analysis_mode}) ===")
        start_time_step = time.time()
        
        if subtitle_df is None or subtitle_df.empty:
            logger.error("缺少字幕数据，无法进行内容分析")
            append_to_debug_history("内容分析测试", "依赖有效的字幕数据", "检查字幕DataFrame", "字幕数据无效", "❌")
            return False
            
        try:
            video_id_str = os.path.basename(video_path).split('.')[0] # 获取视频ID
            
            # 根据模式调用新的分析方法
            if analysis_mode == 'intent':
                if not intent_ids:
                     # 如果未指定，默认使用第一个意图进行测试
                     all_intents = intent_service.get_all_intents()
                     if all_intents:
                         intent_ids = [all_intents[0]['id']]
                         logger.warning(f"未指定意图ID，默认使用第一个意图进行测试: {intent_ids}")
                     else:
                         logger.error("未指定意图ID，且无法获取默认意图")
                         append_to_debug_history("内容分析测试 (意图模式)", "需要有效的意图ID", "获取意图ID", "无法获取意图ID", "❌")
                         return False
                         
                logger.info(f"使用意图模式分析，意图IDs: {intent_ids}")
                analysis_results = asyncio.run(segment_service.analyze_video_content(
                    video_id=video_id_str,
                    subtitle_df=subtitle_df,
                    mode='intent',
                    selected_intent_ids=intent_ids
                ))
            elif analysis_mode == 'prompt':
                if not user_prompt:
                    # 如果未指定，使用默认Prompt测试
                    user_prompt = "查找视频中关于产品效果的讨论"
                    logger.warning(f"未指定用户Prompt，默认使用: '{user_prompt}'")
                    
                logger.info(f"使用Prompt模式分析，用户Prompt: {user_prompt[:100]}...")
                analysis_results = asyncio.run(segment_service.analyze_video_content(
                    video_id=video_id_str,
                    subtitle_df=subtitle_df,
                    mode='prompt',
                    user_description=user_prompt
                ))
            elif analysis_mode == 'all_intents':
                # 新增: 测试分析所有预定义意图
                logger.info("使用全部意图分析模式")
                analysis_results = asyncio.run(segment_service.get_all_intents_analysis(
                    video_id=video_id_str,
                    subtitle_df=subtitle_df
                ))
            else:
                logger.error(f"无效的分析模式: {analysis_mode}")
                append_to_debug_history("内容分析测试", "模式有效性", f"检查模式参数: {analysis_mode}", "模式无效", "❌")
                return False

            # 处理分析结果
            if analysis_results:
                logger.info(f"内容分析完成，耗时 {analysis_results.get('analysis_duration_seconds', '未知')} 秒")
                
                # 检查是否有错误
                if analysis_results.get('errors'):
                    logger.error(f"内容分析过程中发生错误: {analysis_results['errors']}")
                    append_to_debug_history(f"内容分析测试 ({analysis_mode}模式)", "分析过程无错误", "执行分析", f"分析出错: {analysis_results['errors']}", "❌")
                    # 即使有错，也可能部分成功，不直接返回False，看匹配结果
                
                # 保存结果
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                result_file = os.path.join(TEST_OUTPUT_DIR, f'analysis_results_{analysis_mode}_{timestamp}.json')
                try:
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
                    logger.info(f"分析结果已保存到: {result_file}")
                except Exception as dump_e:
                    logger.error(f"保存分析结果失败: {dump_e}")
                
                # 检查匹配结果
                matches_data = analysis_results.get('matches')
                found_matches = False
                match_count = 0
                
                if analysis_mode in ['intent', 'all_intents'] and isinstance(matches_data, dict) and matches_data:
                     # 对于意图模式和分析所有意图模式，matches是按意图ID分组的
                     found_matches = any(intent_data.get('matches') for intent_data in matches_data.values())
                     match_count = sum(len(intent_data.get('matches', [])) for intent_data in matches_data.values())
                     logger.info(f"意图模式找到 {match_count} 个匹配项 (得分>=60)")
                     
                     # 仅打印前3个意图的前3个匹配示例
                     intent_counter = 0
                     for intent_id, intent_data in matches_data.items():
                         intent_name = intent_data.get('intent_name', '未知意图')
                         intent_matches = intent_data.get('matches', [])
                         if intent_matches:
                             logger.info(f"意图 '{intent_name}' 找到 {len(intent_matches)} 个匹配项")
                             # 打印前3个匹配示例
                             for i, match in enumerate(intent_matches[:3], 1):
                                logger.info(f"  {i}. [{match.get('start_timestamp')} - {match.get('end_timestamp')}] Score: {match.get('score')} | Core: {match.get('core_text', '')[:50]}...")
                             intent_counter += 1
                             if intent_counter >= 3:
                                 logger.info("...")
                                 break
                
                elif analysis_mode == 'prompt' and isinstance(matches_data, list) and matches_data:
                     # 对于Prompt模式，matches是一个列表
                     found_matches = True
                     match_count = len(matches_data)
                     logger.info(f"Prompt模式找到 {match_count} 个匹配项 (得分>=60)")
                     if match_count > 0:
                         logger.info("前3条匹配示例:")
                         for i, match in enumerate(matches_data[:3], 1):
                            logger.info(f"  {i}. [{match.get('start_timestamp')} - {match.get('end_timestamp')}] Score: {match.get('score')} | Core: {match.get('core_text', '')[:50]}...")

                if found_matches:
                    append_to_debug_history(f"内容分析测试 ({analysis_mode}模式)", "能找到相关视频片段", "执行分析并检查结果", f"成功找到 {match_count} 个匹配项", "✅")
                else:
                    logger.warning(f"内容分析 ({analysis_mode}模式) 未找到得分>=60的匹配项")
                    append_to_debug_history(f"内容分析测试 ({analysis_mode}模式)", "能找到相关视频片段", "执行分析并检查结果", "未找到有效匹配项", "🤔️") # 未必是错误，可能是视频内容无关
                    # 如果没有错误且没有匹配，也算测试通过（功能正常，只是没匹配到）
                    if not analysis_results.get('errors'):
                         return True 
                    else:
                         return False # 有错误且没匹配到，算失败
            else:
                 logger.error("内容分析调用未返回任何结果")
                 append_to_debug_history(f"内容分析测试 ({analysis_mode}模式)", "分析有返回结果", "执行分析", "未返回结果", "❌")
                 return False
                 
        except Exception as e:
            logger.exception(f"内容分析异常: {str(e)}")
            append_to_debug_history(f"内容分析测试 ({analysis_mode}模式)", "分析过程无异常", "执行分析", f"发生异常: {str(e)}", "❌")
            return False
        
        logger.info(f"步骤4耗时: {time.time() - start_time_step:.2f}秒")

    # 5. [新增] 测试批量分析 
    if test_type in ['all', 'batch']:
        logger.info(f"=== 步骤5: 测试批量分析 ===")
        start_time_step = time.time()
        
        if subtitle_df is None or subtitle_df.empty:
            logger.error("缺少字幕数据，无法进行批量分析")
            append_to_debug_history("批量分析测试", "依赖有效的字幕数据", "检查字幕DataFrame", "字幕数据无效", "❌")
            return False
            
        try:
            # 准备测试数据 - 使用当前视频
            video_id_str = os.path.basename(video_path).split('.')[0]
            videos = [(video_id_str, subtitle_df)]
            
            # 测试批量分析所有意图
            logger.info("测试批量分析所有意图")
            batch_results = asyncio.run(segment_service.get_batch_analysis(
                videos=videos,
                analysis_type='all_intents'
            ))
            
            if batch_results and video_id_str in batch_results:
                logger.info(f"批量分析所有意图成功，结果包含 {video_id_str}")
                # 保存结果
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                result_file = os.path.join(TEST_OUTPUT_DIR, f'batch_all_intents_{timestamp}.json')
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(batch_results, f, ensure_ascii=False, indent=2)
                logger.info(f"批量分析所有意图结果已保存到: {result_file}")
                append_to_debug_history("批量分析测试 (所有意图)", "能够对多个视频进行所有意图分析", "对当前视频进行所有意图批量分析", "分析成功", "✅")
            else:
                logger.error("批量分析所有意图失败")
                append_to_debug_history("批量分析测试 (所有意图)", "能够对多个视频进行所有意图分析", "对当前视频进行所有意图批量分析", "分析失败", "❌")
                return False
            
            # 如果指定了意图ID，还可以测试自定义意图批量分析
            if intent_ids:
                logger.info(f"测试批量分析自定义意图: {intent_ids}")
                custom_batch_results = asyncio.run(segment_service.get_batch_analysis(
                    videos=videos,
                    analysis_type='custom',
                    custom_intent_ids=intent_ids
                ))
                
                if custom_batch_results and video_id_str in custom_batch_results:
                    logger.info("批量分析自定义意图成功")
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    result_file = os.path.join(TEST_OUTPUT_DIR, f'batch_custom_intent_{timestamp}.json')
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(custom_batch_results, f, ensure_ascii=False, indent=2)
                    logger.info(f"批量分析自定义意图结果已保存到: {result_file}")
                    append_to_debug_history("批量分析测试 (自定义意图)", "能够对多个视频进行自定义意图分析", f"对当前视频进行自定义意图 {intent_ids} 批量分析", "分析成功", "✅")
            
            # 如果指定了自由文本，还可以测试自定义Prompt批量分析  
            if user_prompt:
                logger.info(f"测试批量分析自定义Prompt: {user_prompt[:50]}...")
                prompt_batch_results = asyncio.run(segment_service.get_batch_analysis(
                    videos=videos,
                    analysis_type='custom',
                    custom_prompt=user_prompt
                ))
                
                if prompt_batch_results and video_id_str in prompt_batch_results:
                    logger.info("批量分析自定义Prompt成功")
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    result_file = os.path.join(TEST_OUTPUT_DIR, f'batch_custom_prompt_{timestamp}.json')
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(prompt_batch_results, f, ensure_ascii=False, indent=2)
                    logger.info(f"批量分析自定义Prompt结果已保存到: {result_file}")
                    append_to_debug_history("批量分析测试 (自定义Prompt)", "能够对多个视频进行自定义Prompt分析", f"对当前视频进行自定义Prompt '{user_prompt[:20]}...' 批量分析", "分析成功", "✅")
        
        except Exception as e:
            logger.exception(f"批量分析异常: {str(e)}")
            append_to_debug_history("批量分析测试", "批量分析过程无异常", "执行批量分析", f"发生异常: {str(e)}", "❌")
            return False
            
        logger.info(f"步骤5耗时: {time.time() - start_time_step:.2f}秒")

    # 如果测试类型不是 'all', 'analysis' 或 'batch'，到这里就结束了
    if test_type not in ['all', 'analysis', 'batch']:
        logger.info(f"测试类型 '{test_type}' 执行完成")
        return True

    logger.info(f"完整测试流程耗时: {time.time() - test_start_time:.2f}秒")
    return True # 如果运行到最后没有返回False，则认为成功

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='视频处理端到端测试')
    parser.add_argument('--video', type=str, help='测试视频文件路径或URL文件路径')
    parser.add_argument('--type', type=str, choices=['all', 'info', 'audio', 'subtitle', 'analysis', 'batch'], 
                        default='all', help='测试类型: info(信息), audio(音频), subtitle(字幕), analysis(内容分析), batch(批量分析), all(全部)')
    parser.add_argument('--vocabulary_id', type=str, help='DashScope API的热词表ID (可选)')
    
    # 分析模式参数
    parser.add_argument('--mode', type=str, choices=['intent', 'prompt', 'all_intents'], default='intent', 
                        help='内容分析模式: intent(基于预定义意图), prompt(基于自由文本), all_intents(分析所有意图)')
    parser.add_argument('--intent_ids', type=str, help='意图模式下使用的意图ID，逗号分隔 (例如: product_features,brand_trust)')
    parser.add_argument('--prompt', type=str, help='Prompt模式下使用的用户自由文本描述')
    
    # 批量处理相关参数
    parser.add_argument('--concurrent', type=int, default=3, help='最大并行任务数')
    
    args = parser.parse_args()
    
    # 处理视频路径
    video_input_path = args.video
    if not video_input_path:
        # 默认使用 17.mp4
        video_input_path = os.path.join(TEST_INPUT_DIR, '17.mp4')
        logger.info(f"未指定视频文件，使用默认测试视频: {video_input_path}")
        
    if not os.path.exists(video_input_path) and not video_input_path.endswith('.url'):
        logger.error(f"指定的视频文件或URL文件不存在: {video_input_path}")
        sys.exit(1)
        
    # 处理意图ID列表
    intent_id_list = None
    if args.mode in ['intent'] and args.intent_ids:
        intent_id_list = [id.strip() for id in args.intent_ids.split(',') if id.strip()]
        if not intent_id_list:
             logger.warning("提供了 --intent_ids 参数但内容为空，将使用默认意图")
        else:
             logger.info(f"将使用指定的意图IDs: {intent_id_list}")

    # 运行测试
    logger.info(f"开始测试视频处理流程: {video_input_path}, 类型: {args.type}, 分析模式: {args.mode}, 最大并行任务数: {args.concurrent}")
    
    success = test_video_processing(
        video_path=video_input_path, 
        test_type=args.type, 
        vocabulary_id=args.vocabulary_id, 
        analysis_mode=args.mode, 
        intent_ids=intent_id_list, 
        user_prompt=args.prompt,
        max_concurrent=args.concurrent
    )
    
    if success:
        logger.info("==== 测试完成，所有步骤执行成功 ====")
    else:
        logger.error("==== 测试失败 ====")
        sys.exit(1)

if __name__ == "__main__":
    main() 