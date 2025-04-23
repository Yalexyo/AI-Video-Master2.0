#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置模块
------
提供系统配置管理和环境变量处理功能。
"""

import os
import sys
import json
import logging
import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("config")

# 默认配置
_DEFAULT_CONFIG = {
    "paths": {
        "root_input_dir": "Input",
        "root_output_dir": "Output",
        "logs_dir": "logs",
        "oss_video_dir": "Input/OSS_VideoList",
        "other_resources_dir": "Input/OtherResources",
        "wordlists_dir": "Input/Wordlists",
        "subtitles_dir": "Output/Subtitles",
        "analysis_dir": "Output/Analysis",
        "matching_dir": "Output/Matching",
        "clips_dir": "Output/Clips",
        "temp_dir": "Output/Temp",
        "final_dir": "Output/Final"
    },
    "asr": {
        "default_model": "paraformer-v2",
        "language_hints": ["zh", "en"],
        "timeout": 300,
        "retry_count": 3
    },
    "embedding": {
        "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "device": "cpu",  # 或 "cuda" 如果有GPU
        "batch_size": 32
    },
    "video": {
        "max_duration": 40,
        "min_duration": 30,
        "main_sequence_duration": 35,
        "end_slate_duration": 5,
        "transition_duration": 0.5,
        "fade_in_duration": 0.5,
        "fade_out_duration": 0.5
    }
}

# 全局配置变量
_CONFIG = None
_ENV_VARS = {}

def init(config_path=None):
    """
    初始化配置
    
    参数:
        config_path (str, optional): 配置文件路径
    """
    global _CONFIG, _ENV_VARS
    
    # 设置默认配置
    _CONFIG = _DEFAULT_CONFIG.copy()
    
    # 尝试加载环境变量
    load_env()
    
    # 如果提供了配置文件路径，尝试加载配置
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            
            # 更新配置
            _update_config(_CONFIG, user_config)
            logger.info(f"已加载配置文件: {config_path}")
        
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    
    # 创建必要的目录
    create_directories()
    
    logger.info("配置初始化完成")
    return _CONFIG

def _update_config(config, updates):
    """
    递归更新配置
    
    参数:
        config (dict): 要更新的配置
        updates (dict): 更新内容
    """
    for key, value in updates.items():
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            _update_config(config[key], value)
        else:
            config[key] = value

def load_env(env_file='.env'):
    """
    加载环境变量
    
    参数:
        env_file (str, optional): 环境变量文件路径
    """
    global _ENV_VARS
    
    # 尝试从.env文件加载环境变量
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                        _ENV_VARS[key.strip()] = value.strip()
            
            logger.info(f"已加载环境变量文件: {env_file}")
        
        except Exception as e:
            logger.warning(f"加载环境变量文件失败: {e}")
    
    # 获取特定的环境变量
    _ENV_VARS['DASHSCOPE_API_KEY'] = os.environ.get('DASHSCOPE_API_KEY', '')
    _ENV_VARS['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
    
    if not _ENV_VARS.get('DASHSCOPE_API_KEY'):
        logger.warning("未设置DASHSCOPE_API_KEY环境变量，ASR功能将不可用")
    
    if not _ENV_VARS.get('OPENAI_API_KEY'):
        logger.warning("未设置OPENAI_API_KEY环境变量，某些AI模型功能可能不可用")

def get_config(key=None, default=None):
    """
    获取配置值
    
    参数:
        key (str, optional): 配置键，支持点号分隔的路径
        default (any, optional): 默认值
    
    返回:
        如果提供了key，返回对应的配置值；否则返回整个配置
    """
    global _CONFIG
    
    # 如果配置未初始化，先初始化
    if _CONFIG is None:
        init()
    
    # 如果未提供key，返回整个配置
    if key is None:
        return _CONFIG
    
    # 处理点号分隔的路径
    keys = key.split('.')
    value = _CONFIG
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value

def set_config(key, value):
    """
    设置配置值
    
    参数:
        key (str): 配置键，支持点号分隔的路径
        value (any): 配置值
    """
    global _CONFIG
    
    # 如果配置未初始化，先初始化
    if _CONFIG is None:
        init()
    
    # 处理点号分隔的路径
    keys = key.split('.')
    target = _CONFIG
    
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]
    
    target[keys[-1]] = value
    logger.debug(f"设置配置: {key} = {value}")

def get_path(key, create=False):
    """
    获取路径配置
    
    参数:
        key (str): 路径配置键
        create (bool, optional): 是否创建目录
    
    返回:
        str: 路径
    """
    path = get_config(f"paths.{key}")
    
    if path and create:
        os.makedirs(path, exist_ok=True)
    
    return path

def set_path(key, path):
    """
    设置路径配置
    
    参数:
        key (str): 路径配置键
        path (str): 路径
    """
    set_config(f"paths.{key}", path)

def create_directories():
    """创建必要的目录"""
    paths = get_config("paths")
    
    if not paths:
        return
    
    for path in paths.values():
        try:
            os.makedirs(path, exist_ok=True)
            logger.debug(f"创建目录: {path}")
        except Exception as e:
            logger.error(f"创建目录失败: {path}, 错误: {e}")

def get_env(key, default=None):
    """
    获取环境变量
    
    参数:
        key (str): 环境变量名
        default (str, optional): 默认值
    
    返回:
        str: 环境变量值
    """
    global _ENV_VARS
    
    # 如果环境变量未加载，先加载
    if not _ENV_VARS:
        load_env()
    
    return _ENV_VARS.get(key, os.environ.get(key, default))

def get_current_time_str(format='%Y-%m-%d %H:%M:%S'):
    """
    获取当前时间字符串
    
    参数:
        format (str, optional): 时间格式
    
    返回:
        str: 时间字符串
    """
    return datetime.datetime.now().strftime(format)

# 仅在作为主模块运行时执行
if __name__ == "__main__":
    # 初始化配置
    init()
    
    # 打印配置信息
    print("\n当前配置:")
    print(json.dumps(get_config(), indent=2, ensure_ascii=False))
    
    # 打印环境变量
    print("\n环境变量:")
    env_vars = {}
    for key, value in _ENV_VARS.items():
        if 'key' in key.lower() or 'password' in key.lower() or 'secret' in key.lower():
            # 隐藏敏感信息
            if value:
                value = value[:4] + '*' * (len(value) - 8) + value[-4:]
            else:
                value = '未设置'
        env_vars[key] = value
    
    print(json.dumps(env_vars, indent=2, ensure_ascii=False))
