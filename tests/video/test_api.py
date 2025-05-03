#!/usr/bin/env python3
"""
测试API连接

测试DashScope和其他API的连接是否正常
"""

import os
import sys
import logging
import json

# 添加项目根目录到Python路径，确保可以导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入项目模块
from utils.dashscope_wrapper import dashscope_api
from src.core.hot_words_service import HotWordsService

def test_dashscope_connection():
    """测试DashScope API连接"""
    print("=== 测试DashScope API连接 ===")
    
    # 获取API密钥
    api_key = dashscope_api.api_key
    if not api_key:
        print("❌ 未找到DashScope API密钥")
        return False
    
    print(f"✅ 成功获取DashScope API密钥: {api_key[:3]}...{api_key[-4:]}")
    
    # 测试API连接
    try:
        # 尝试获取热词表列表来验证连接
        result = dashscope_api.call_hot_words_list(page_size=1)
        if result.get('status_code') == 200:
            print("✅ DashScope API连接成功")
            return True
        else:
            error_msg = result.get('error', {}).get('message', '未知错误')
            print(f"❌ DashScope API连接失败: {error_msg}")
            return False
    except Exception as e:
        print(f"❌ DashScope API连接测试异常: {str(e)}")
        return False

def test_hot_words_service():
    """测试热词服务"""
    print("\n=== 测试热词服务 ===")
    
    # 初始化热词服务
    service = HotWordsService()
    
    # 获取当前热词ID
    current_id = service.get_current_hotword_id()
    print(f"当前热词ID: {current_id}")
    
    # 获取热词列表
    try:
        hot_words = service.list_hot_words()
        if hot_words:
            print(f"✅ 成功获取热词列表，共 {len(hot_words)} 个热词")
            # 显示前5个热词
            for i, word in enumerate(hot_words[:5]):
                print(f"  {i+1}. {word}")
            
            if len(hot_words) > 5:
                print(f"  ... 以及其他 {len(hot_words) - 5} 个热词")
        else:
            print("❌ 获取热词列表失败或列表为空")
    except Exception as e:
        print(f"❌ 获取热词列表时出错: {str(e)}")
    
    return True

if __name__ == "__main__":
    print("开始测试API连接...")
    
    # 测试DashScope API连接
    dashscope_ok = test_dashscope_connection()
    
    # 测试热词服务
    hot_words_ok = test_hot_words_service()
    
    # 输出总结果
    print("\n=== 测试结果 ===")
    print(f"DashScope API: {'✅ 正常' if dashscope_ok else '❌ 异常'}")
    print(f"热词服务: {'✅ 正常' if hot_words_ok else '❌ 异常'}")
    
    print("\n测试完成!") 