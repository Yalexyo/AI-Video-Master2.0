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

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 测试输入输出目录
TEST_INPUT_DIR = os.path.join("data", "test_samples", "input", "video")
TEST_OUTPUT_DIR = os.path.join("data", "test_samples", "output", "video")

# 加载环境变量
load_dotenv(os.path.join(project_root, '.env'))
api_key = os.getenv('DASHSCOPE_API_KEY')
if api_key:
    os.environ['DASHSCOPE_API_KEY'] = api_key
    masked_key = api_key[:3] + "..." + api_key[-4:]
    print(f"已加载API密钥: {masked_key}")
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("data", "test_samples", "logs", f"test_e2e_{datetime.now().strftime('%Y%m%d')}.log"), 'a', 'utf-8')
    ]
)
logger = logging.getLogger(__name__)

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
    debug_history_file = os.path.join(project_root, "data", "test_samples", "debug_history", "debug_history.md")
    
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
            with open(debug_history_file, 'r', encoding='utf-8') as rf:
                content = rf.read()
            
            # 定位待验证清单位置
            checklist_pos = content.find("## 待验证清单")
            if checklist_pos != -1:
                # 找到下一个标题
                next_section_pos = content.find("##", checklist_pos + 1)
                if next_section_pos == -1:
                    next_section_pos = len(content)
                
                # 在待验证清单和下一个标题之间插入新项目
                today = datetime.now().strftime("%Y-%m-%d")
                new_item = f"\n1. [{today}] 待验证：{step_name} - [链接到章节](#{step_name.replace(' ', '-').lower()})\n"
                
                # 更新文件内容
                new_content = content[:next_section_pos] + new_item + content[next_section_pos:]
                with open(debug_history_file, 'w', encoding='utf-8') as wf:
                    wf.write(new_content)

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
    
    # 从映射关系中获取对应的热词表ID
    vocab_id = VIDEO_VOCABULARY_MAPPING.get(video_filename, DEFAULT_VOCABULARY_ID)
    logger.info(f"视频 {video_filename} 使用热词表ID: {vocab_id}")
    
    return vocab_id

def test_video_processing(video_path, test_type='all', vocabulary_id=None):
    """
    测试视频处理流程
    
    参数:
        video_path: 测试视频文件路径
        test_type: 测试类型，可选 'all', 'info', 'audio', 'subtitle', 'intent', 'matching'
        vocabulary_id: DashScope API的热词表ID
    """
    # 初始化处理器
    logger.info(f"初始化处理器，准备测试视频: {video_path}")
    processor = VideoProcessor()
    analyzer = VideoAnalyzer()
    
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        logger.error(f"测试视频文件不存在: {video_path}")
        return False
    
    # 获取热词表ID
    vocab_id = get_vocabulary_id(video_path, vocabulary_id)
    logger.info(f"使用热词表ID: {vocab_id}")
    
    # 确保输出目录存在
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    
    # 1. 测试视频信息获取
    if test_type in ['all', 'info']:
        logger.info("=== 步骤1: 测试视频信息获取 ===")
        start_time = time.time()
        try:
            video_info = processor._get_video_info(video_path)
            if video_info:
                logger.info(f"视频信息获取成功: {json.dumps(video_info, ensure_ascii=False)}")
                append_to_debug_history(
                    "视频信息获取测试", 
                    "VideoProcessor._get_video_info方法能正确获取视频基本信息",
                    f"调用_get_video_info方法处理视频文件: {os.path.basename(video_path)}",
                    f"成功获取视频信息，宽度: {video_info.get('width')}，高度: {video_info.get('height')}，"
                    f"时长: {video_info.get('duration')}秒，FPS: {video_info.get('fps')}",
                    "✅"
                )
            else:
                logger.error("视频信息获取失败")
                append_to_debug_history(
                    "视频信息获取测试", 
                    "VideoProcessor._get_video_info方法能正确获取视频基本信息",
                    f"调用_get_video_info方法处理视频文件: {os.path.basename(video_path)}",
                    "获取视频信息失败，返回空字典",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"视频信息获取异常: {str(e)}")
            append_to_debug_history(
                "视频信息获取测试", 
                "VideoProcessor._get_video_info方法能正确获取视频基本信息",
                f"调用_get_video_info方法处理视频文件: {os.path.basename(video_path)}",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        logger.info(f"视频信息获取耗时: {time.time() - start_time:.2f}秒")
    
    # 2. 测试音频提取
    if test_type in ['all', 'audio']:
        logger.info("=== 步骤2: 测试音频提取 ===")
        start_time = time.time()
        try:
            audio_file = processor._preprocess_video_file(video_path)
            if audio_file:
                logger.info(f"音频提取成功: {audio_file}")
                append_to_debug_history(
                    "音频提取测试", 
                    "VideoProcessor._preprocess_video_file方法能正确从视频文件中提取音频",
                    f"调用_preprocess_video_file方法处理视频文件: {os.path.basename(video_path)}",
                    f"成功提取音频，输出文件: {os.path.basename(audio_file)}",
                    "✅"
                )
            else:
                logger.error("音频提取失败")
                append_to_debug_history(
                    "音频提取测试", 
                    "VideoProcessor._preprocess_video_file方法能正确从视频文件中提取音频",
                    f"调用_preprocess_video_file方法处理视频文件: {os.path.basename(video_path)}",
                    "提取音频失败，返回None",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"音频提取异常: {str(e)}")
            append_to_debug_history(
                "音频提取测试", 
                "VideoProcessor._preprocess_video_file方法能正确从视频文件中提取音频",
                f"调用_preprocess_video_file方法处理视频文件: {os.path.basename(video_path)}",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        logger.info(f"音频提取耗时: {time.time() - start_time:.2f}秒")
    else:
        # 如果不测试音频提取，但后续步骤需要音频文件，直接模拟音频文件路径
        audio_file = None
    
    # 3. 测试字幕提取
    if test_type in ['all', 'subtitle']:
        logger.info("=== 步骤3: 测试字幕提取 ===")
        start_time = time.time()
        
        # 如果前面没有提取音频，现在提取
        if not audio_file:
            try:
                audio_file = processor._preprocess_video_file(video_path)
            except Exception as e:
                logger.exception(f"音频提取异常: {str(e)}")
                return False
        
        try:
            subtitles = processor._extract_subtitles_from_video(audio_file, vocabulary_id=vocab_id)
            if subtitles:
                logger.info(f"字幕提取成功，共{len(subtitles)}条")
                # 记录前5条字幕示例
                for i, subtitle in enumerate(subtitles[:5]):
                    logger.info(f"字幕{i+1}: {subtitle.get('text', '')}")
                
                # 保存字幕文件
                srt_file = processor._save_subtitles_to_srt(video_path, subtitles)
                if srt_file:
                    logger.info(f"字幕保存成功: {srt_file}")
                
                append_to_debug_history(
                    "字幕提取测试", 
                    "VideoProcessor._extract_subtitles_from_video方法能正确提取字幕",
                    f"调用_extract_subtitles_from_video方法处理音频文件，"
                    f"使用热词表ID: {vocab_id if vocab_id else '无'}",
                    f"成功提取字幕，共{len(subtitles)}条，"
                    f"前3条示例: {'; '.join([s.get('text', '') for s in subtitles[:3]])}",
                    "✅"
                )
            else:
                logger.error("字幕提取失败")
                append_to_debug_history(
                    "字幕提取测试", 
                    "VideoProcessor._extract_subtitles_from_video方法能正确提取字幕",
                    f"调用_extract_subtitles_from_video方法处理音频文件，"
                    f"使用热词表ID: {vocab_id if vocab_id else '无'}",
                    "字幕提取失败，返回空列表",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"字幕提取异常: {str(e)}")
            append_to_debug_history(
                "字幕提取测试", 
                "VideoProcessor._extract_subtitles_from_video方法能正确提取字幕",
                f"调用_extract_subtitles_from_video方法处理音频文件，"
                f"使用热词表ID: {vocab_id if vocab_id else '无'}",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        
        logger.info(f"字幕提取耗时: {time.time() - start_time:.2f}秒")
        
        # 创建DataFrame用于后续分析
        subtitle_df = pd.DataFrame([{
            'timestamp': item.get('start_formatted', '00:00:00'),
            'text': item.get('text', '')
        } for item in subtitles if item.get('text')])
    else:
        # 如果不测试字幕提取，但需要字幕数据，使用模拟数据
        subtitle_df = None
    
    # 4. 测试意图服务
    if test_type in ['all', 'intent']:
        logger.info("=== 步骤4: 测试意图服务 ===")
        start_time = time.time()
        try:
            # 初始化意图服务
            intent_service = IntentService()
            intents = intent_service.get_all_intents()
            
            if intents and len(intents) > 0:
                logger.info(f"意图服务加载成功，共加载 {len(intents)} 个意图")
                
                # 展示所有意图
                for i, intent in enumerate(intents, 1):
                    logger.info(f"{i}. ID: {intent.get('id')} | " +
                             f"名称: {intent.get('name')} | " +
                             f"描述: {intent.get('description')} | " +
                             f"关键词数量: {len(intent.get('keywords', []))}")
                
                # 测试根据ID获取意图
                if intents[0]['id']:
                    test_intent_id = intents[0]['id']
                    retrieved_intent = intent_service.get_intent_by_id(test_intent_id)
                    if retrieved_intent:
                        logger.info(f"成功根据ID获取意图: {retrieved_intent.get('name')}")
                        append_to_debug_history(
                            "意图服务测试", 
                            "IntentService能正确加载意图数据并根据ID检索意图",
                            f"加载意图服务并测试获取ID为'{test_intent_id}'的意图",
                            f"成功加载{len(intents)}个意图，并能根据ID检索到具体意图",
                            "✅"
                        )
                    else:
                        logger.warning(f"根据ID '{test_intent_id}' 检索意图失败")
                        append_to_debug_history(
                            "意图服务测试", 
                            "IntentService能正确加载意图数据并根据ID检索意图",
                            f"加载意图服务并测试获取ID为'{test_intent_id}'的意图",
                            f"意图ID检索失败",
                            "❌"
                        )
            else:
                logger.warning("意图服务未加载到任何意图")
                append_to_debug_history(
                    "意图服务测试", 
                    "IntentService能正确加载意图数据并根据ID检索意图",
                    "加载意图服务并获取所有意图",
                    "未加载到任何意图，请检查意图配置文件",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"意图服务测试异常: {str(e)}")
            append_to_debug_history(
                "意图服务测试", 
                "IntentService能正确加载意图数据并根据ID检索意图",
                "加载意图服务并获取所有意图",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        
        logger.info(f"意图服务测试耗时: {time.time() - start_time:.2f}秒")

    # 5. 测试关键词分析
    if test_type in ['all', 'keywords']:
        logger.info("=== 步骤5: 测试关键词分析 ===")
        start_time = time.time()
        try:
            # 准备测试关键词
            keywords = ["产品", "质量", "价格", "服务", "体验", "品牌"]
            logger.info(f"使用关键词: {', '.join(keywords)}")
            
            # 执行关键词分析
            if subtitle_df is not None and not subtitle_df.empty:
                keyword_results = analyzer.analyze_keywords(subtitle_df, keywords)
                if keyword_results and 'matches' in keyword_results:
                    match_count = len(keyword_results['matches'])
                    logger.info(f"关键词分析成功，共匹配 {match_count} 条记录")
                    
                    # 保存分析结果
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    result_file = os.path.join(TEST_OUTPUT_DIR, f'keyword_results_{timestamp}.json')
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(keyword_results, f, ensure_ascii=False, indent=2)
                    logger.info(f"关键词分析结果已保存到: {result_file}")
                    
                    # 输出前3条匹配作为示例
                    if match_count > 0:
                        logger.info("前3条匹配示例:")
                        for i, match in enumerate(keyword_results['matches'][:3], 1):
                            logger.info(f"{i}. 关键词: {match.get('keyword', '无')} | " +
                                     f"相似度: {match.get('score', 0):.2f} | " +
                                     f"文本: {match.get('text', '')[:50]}...")
                    
                    append_to_debug_history(
                        "关键词分析测试", 
                        "VideoAnalyzer.analyze_keywords方法能正确识别字幕中的关键词",
                        f"使用关键词 '{', '.join(keywords)}' 分析字幕内容",
                        f"成功匹配 {match_count} 条记录，结果已保存到: {os.path.basename(result_file)}",
                        "✅"
                    )
                else:
                    logger.warning("关键词分析未找到匹配结果")
                    append_to_debug_history(
                        "关键词分析测试", 
                        "VideoAnalyzer.analyze_keywords方法能正确识别字幕中的关键词",
                        f"使用关键词 '{', '.join(keywords)}' 分析字幕内容",
                        "未找到匹配结果",
                        "🤔️"
                    )
            else:
                logger.error("缺少字幕数据，无法进行关键词分析")
                append_to_debug_history(
                    "关键词分析测试", 
                    "VideoAnalyzer.analyze_keywords方法能正确识别字幕中的关键词",
                    "尝试使用关键词分析字幕内容",
                    "缺少字幕数据，无法执行分析",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"关键词分析异常: {str(e)}")
            append_to_debug_history(
                "关键词分析测试", 
                "VideoAnalyzer.analyze_keywords方法能正确识别字幕中的关键词",
                "尝试使用关键词分析字幕内容",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        
        logger.info(f"关键词分析耗时: {time.time() - start_time:.2f}秒")

    # 5. 测试内容匹配
    if test_type in ['all', 'matching']:
        logger.info("=== 步骤5: 测试内容匹配 ===")
        start_time = time.time()
        try:
            # 初始化意图服务和视频段落服务
            intent_service = IntentService()
            segment_service = VideoSegmentService()
            
            # 获取第一个意图作为测试用例
            intents = intent_service.get_all_intents()
            if intents and len(intents) > 0:
                selected_intent = intents[0]
                logger.info(f"使用意图 '{selected_intent.get('name')}' 测试内容匹配")
                
                # 测试用户描述
                user_description = f"查找关于{selected_intent.get('keywords', [''])[0]}的内容"
                logger.info(f"测试用户描述: '{user_description}'")
                
                # 执行内容匹配
                if subtitle_df is not None and not subtitle_df.empty:
                    # 异步执行匹配
                    import asyncio
                    match_results = asyncio.run(segment_service.get_video_segments(
                        video_id=os.path.basename(video_path).split('.')[0],
                        subtitle_df=subtitle_df,
                        selected_intent=selected_intent,
                        user_description=user_description
                    ))
                    
                    if match_results and "matches" in match_results:
                        match_count = len(match_results["matches"])
                        logger.info(f"内容匹配成功，共找到 {match_count} 个相关片段")
                        
                        # 保存匹配结果
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        result_file = os.path.join(TEST_OUTPUT_DIR, f'segment_results_{timestamp}.json')
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(match_results, f, ensure_ascii=False, indent=2)
                        logger.info(f"内容匹配结果已保存到: {result_file}")
                        
                        # 输出使用的匹配方法
                        analysis_method = match_results.get("analysis_method", "未知")
                        logger.info(f"使用的匹配方法: {analysis_method}")
                        
                        # 输出前3条匹配作为示例
                        if match_count > 0:
                            logger.info("前3条匹配示例:")
                            for i, match in enumerate(match_results["matches"][:3], 1):
                                # 适配不同格式的匹配结果
                                if "start_timestamp" in match:  # LLM精确匹配格式
                                    logger.info(f"{i}. 时间段: {match.get('start_timestamp', '00:00:00')} - " +
                                            f"{match.get('end_timestamp', '00:00:00')} | " +
                                            f"得分: {match.get('score', 0)} | " +
                                            f"核心内容: {match.get('core_text', '')[:50]}...")
                                else:  # 关键词匹配格式
                                    logger.info(f"{i}. 时间点: {match.get('timestamp', '00:00:00')} | " +
                                            f"关键词: {match.get('keyword', '无')} | " +
                                            f"得分: {match.get('score', 0)*100:.0f}% | " +
                                            f"内容: {match.get('text', '')[:50]}...")
                        
                        append_to_debug_history(
                            "内容匹配测试", 
                            "VideoSegmentService.get_video_segments方法能根据用户意图和描述找到相关视频片段",
                            f"使用意图'{selected_intent.get('name')}'和描述'{user_description}'匹配相关内容",
                            f"成功找到{match_count}个相关片段，使用{analysis_method}方法，结果已保存",
                            "✅"
                        )
                    else:
                        logger.warning("内容匹配未找到相关片段")
                        append_to_debug_history(
                            "内容匹配测试", 
                            "VideoSegmentService.get_video_segments方法能根据用户意图和描述找到相关视频片段",
                            f"使用意图'{selected_intent.get('name')}'和描述'{user_description}'匹配相关内容",
                            "未找到相关片段，请检查意图定义或调整匹配阈值",
                            "🤔️"
                        )
                else:
                    logger.error("缺少字幕数据，无法进行内容匹配")
                    append_to_debug_history(
                        "内容匹配测试", 
                        "VideoSegmentService.get_video_segments方法能根据用户意图和描述找到相关视频片段",
                        "尝试匹配视频内容",
                        "缺少字幕数据，无法执行匹配",
                        "❌"
                    )
                    return False
            else:
                logger.error("未找到可用的意图定义，无法进行内容匹配")
                append_to_debug_history(
                    "内容匹配测试", 
                    "VideoSegmentService.get_video_segments方法能根据用户意图和描述找到相关视频片段",
                    "尝试匹配视频内容",
                    "未找到可用的意图定义，请检查意图配置文件",
                    "❌"
                )
                return False
        except Exception as e:
            logger.exception(f"内容匹配异常: {str(e)}")
            append_to_debug_history(
                "内容匹配测试", 
                "VideoSegmentService.get_video_segments方法能根据用户意图和描述找到相关视频片段",
                "尝试匹配视频内容",
                f"发生异常: {str(e)}",
                "❌"
            )
            return False
        
        logger.info(f"内容匹配测试耗时: {time.time() - start_time:.2f}秒")

    return True

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='视频处理端到端测试')
    parser.add_argument('--video', type=str, help='测试视频文件路径')
    parser.add_argument('--type', type=str, choices=['all', 'info', 'audio', 'subtitle', 'intent', 'matching'], 
                        default='all', help='测试类型')
    parser.add_argument('--vocabulary_id', type=str, help='DashScope API的热词表ID')
    
    args = parser.parse_args()
    
    # 使用默认测试视频（如果未指定视频文件）
    if not args.video:
        args.video = os.path.join(TEST_INPUT_DIR, '17.mp4')
        logger.info(f"未指定视频文件，使用默认测试视频: {args.video}")
    
    # 检查视频文件是否存在
    if not os.path.exists(args.video):
        logger.error(f"测试视频文件不存在: {args.video}")
        sys.exit(1)
    
    # 运行测试
    logger.info(f"开始测试视频处理流程: {args.video}, 类型: {args.type}")
    success = test_video_processing(args.video, args.type, args.vocabulary_id)
    
    if success:
        logger.info("==== 测试完成，所有步骤执行成功 ====")
    else:
        logger.error("==== 测试失败 ====")
        sys.exit(1)

if __name__ == "__main__":
    main() 