#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI视频分析与合成系统 - 主程序
------------------------
该系统分析多个视频片段，提取字幕，进行主题建模，
匹配用户需求，并组合成30-40秒的推广视频。

用法:
    python main.py [选项]

选项:
    --help, -h              显示帮助信息
    --config FILE           指定配置文件
    --steps N-M             只执行指定步骤（例如：--steps 2-4）
    --use-hot-words         启用热词优化
    --vocabulary-id ID      指定热词列表ID
    --debug                 启用调试模式
    --output-dir DIR        指定输出目录
    --input-dir DIR         指定输入目录
    --slogan FILE           指定宣传语文件
    --logo FILE             指定Logo文件

示例:
    python main.py                         # 执行完整处理流程
    python main.py --steps 1-3             # 只执行步骤1到3
    python main.py --use-hot-words         # 启用热词优化
    python main.py --debug                 # 启用调试模式
"""

import os
import sys
import json
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path

# 配置根日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'main.log'), encoding='utf-8', mode='w')
    ]
)
logger = logging.getLogger("main")

# 添加项目根目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# 导入工具模块
from utils import config

def show_banner():
    """显示程序横幅"""
    banner = """
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║        AI 视频分析与合成系统                          ║
║                                                       ║
║  将多个视频片段分析、组合，生成30-40秒的推广视频      ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝    
    """
    print(banner)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='AI视频分析与合成系统')
    
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--steps', type=str, default='1-6', help='执行步骤范围（例如：2-4）')
    parser.add_argument('--use-hot-words', action='store_true', help='启用热词优化')
    parser.add_argument('--vocabulary-id', type=str, help='指定热词列表ID')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--output-dir', type=str, help='指定输出目录')
    parser.add_argument('--input-dir', type=str, help='指定输入目录')
    parser.add_argument('--slogan', type=str, help='指定宣传语文件')
    parser.add_argument('--logo', type=str, help='指定Logo文件')
    
    args = parser.parse_args()
    
    # 解析步骤范围
    try:
        start_step, end_step = map(int, args.steps.split('-'))
        if start_step < 1 or end_step > 6 or start_step > end_step:
            raise ValueError("步骤范围无效")
    except Exception:
        logger.error(f"无效的步骤范围: {args.steps}，应为类似 '1-6' 的格式")
        parser.print_help()
        sys.exit(1)
    
    return args, start_step, end_step

def setup_logging(debug_mode):
    """设置日志级别"""
    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("已启用调试模式")
    else:
        logging.getLogger().setLevel(logging.INFO)

def load_user_configuration(args):
    """加载用户配置"""
    # 初始化默认配置
    config.init(args.config)
    
    # 根据命令行参数更新配置
    if args.output_dir:
        config.set_path("root_output_dir", args.output_dir)
    
    if args.input_dir:
        config.set_path("root_input_dir", args.input_dir)
    
    # 配置热词优化
    if args.use_hot_words:
        config.set_config("asr.use_hot_words", True)
        if args.vocabulary_id:
            config.set_config("asr.vocabulary_id", args.vocabulary_id)
        logger.info("已启用热词优化")
    
    # 配置宣传语文件
    if args.slogan:
        slogan_path = args.slogan
        if not os.path.isabs(slogan_path):
            slogan_path = os.path.join(script_dir, slogan_path)
        
        if os.path.exists(slogan_path):
            config.set_config("slogan_file", slogan_path)
            logger.info(f"使用自定义宣传语文件: {slogan_path}")
        else:
            logger.warning(f"宣传语文件不存在: {slogan_path}")
    
    # 配置Logo文件
    if args.logo:
        logo_path = args.logo
        if not os.path.isabs(logo_path):
            logo_path = os.path.join(script_dir, logo_path)
        
        if os.path.exists(logo_path):
            config.set_config("logo_file", logo_path)
            logger.info(f"使用自定义Logo文件: {logo_path}")
        else:
            logger.warning(f"Logo文件不存在: {logo_path}")
    
    # 记录最终配置
    logger.debug("最终配置:")
    for key, value in config.get_config().items():
        logger.debug(f"  {key}: {value}")

def execute_step(step_num, module_name, function_name, step_description):
    """执行单个处理步骤"""
    logger.info(f"开始执行步骤 {step_num}: {step_description}")
    
    step_start_time = time.time()
    result = False
    
    try:
        # 动态导入模块
        module_path = f"scripts.{module_name}"
        logger.debug(f"导入模块: {module_path}")
        
        try:
            module = __import__(module_path, fromlist=[function_name])
            function = getattr(module, function_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"无法导入模块或函数: {e}")
            logger.info("使用演示流程代替")
            
            # 导入演示模块
            from demo_workflow import run_workflow
            result = run_workflow(step_num, step_num)
            return result
        
        # 执行函数
        result = function()
        
        # 计算耗时
        step_elapsed_time = time.time() - step_start_time
        logger.info(f"步骤 {step_num} 执行完成，耗时 {step_elapsed_time:.2f} 秒")
        
        return result
    
    except Exception as e:
        logger.exception(f"步骤 {step_num} 执行失败: {e}")
        return False

def run_workflow(start_step, end_step):
    """运行工作流"""
    # 步骤定义
    steps = [
        {
            "num": 1,
            "module": "subtitle_generator",
            "function": "generate_subtitles",
            "description": "字幕生成 - 从视频中提取音频并生成字幕"
        },
        {
            "num": 2,
            "module": "2_dimension_analyzer",
            "function": "analyze_dimensions",
            "description": "维度分析 - 生成初始关键词维度"
        },
        {
            "num": 3,
            "module": "3_user_interface",
            "function": "adjust_dimensions",
            "description": "用户调整 - 调整关键词维度和权重"
        },
        {
            "num": 4,
            "module": "4_segment_matcher",
            "function": "match_segments",
            "description": "段落匹配 - 对字幕段落进行评分匹配"
        },
        {
            "num": 5,
            "module": "5_clip_extractor",
            "function": "extract_clips",
            "description": "片段提取 - 从原始视频中提取高分片段"
        },
        {
            "num": 6,
            "module": "6_sequence_assembler",
            "function": "assemble_sequence",
            "description": "序列组装 - 组装主序列和片尾，生成最终视频"
        }
    ]
    
    # 运行选定的步骤
    start_time = time.time()
    success = True
    
    for step in steps:
        if start_step <= step["num"] <= end_step:
            if step["module"] == "subtitle_generator":
                from scripts.subtitle_generator_simplified import SubtitleGeneratorSimplified
                generator = SubtitleGeneratorSimplified()
                step_success = generator.process()
            else:
                step_success = execute_step(
                    step["num"],
                    step["module"],
                    step["function"],
                    step["description"]
                )
            
            if not step_success:
                logger.error(f"步骤 {step['num']} 执行失败，中止后续步骤")
                success = False
                break
    
    # 计算总耗时
    total_elapsed_time = time.time() - start_time
    logger.info(f"工作流执行完成，总耗时 {total_elapsed_time:.2f} 秒")
    
    return success

def main():
    """主函数"""
    # 显示横幅
    show_banner()
    
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 解析命令行参数
    args, start_step, end_step = parse_args()
    
    # 设置日志级别
    setup_logging(args.debug)
    
    # 加载用户配置
    load_user_configuration(args)
    
    # 记录开始信息
    logger.info(f"AI视频分析与合成系统启动 - 版本 {config.get_config('version', '1.0.0')}")
    logger.info(f"执行步骤: {start_step} 至 {end_step}")
    
    # 检查环境
    dashscope_api_key = config.get_env('DASHSCOPE_API_KEY')
    if not dashscope_api_key and start_step <= 1 <= end_step:
        logger.warning("未设置DASHSCOPE_API_KEY环境变量，字幕生成功能可能不可用")
    
    # 运行工作流
    try:
        success = run_workflow(start_step, end_step)
        
        if success:
            # 计算最终视频路径
            final_video_path = os.path.join(
                config.get_path("final_dir"),
                "advertisement_final.mp4"
            )
            
            logger.info("=" * 60)
            logger.info("处理成功完成！")
            logger.info("=" * 60)
            logger.info(f"最终广告视频路径: {os.path.abspath(final_video_path)}")
            
            return 0
        else:
            logger.error("=" * 60)
            logger.error("处理失败，请检查上述错误信息")
            logger.error("=" * 60)
            
            return 1
            
    except KeyboardInterrupt:
        logger.warning("\n程序已被用户中断")
        return 1
    except Exception as e:
        logger.exception("程序执行过程中出现未处理的异常")
        return 1

if __name__ == "__main__":
    sys.exit(main())
