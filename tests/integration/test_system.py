#!/usr/bin/env python3
"""
系统集成测试

验证AI视频大师3.0系统的核心功能是否正常运行
"""

import os
import sys
import subprocess
import logging
import time
from pathlib import Path

# 添加项目根目录到路径中
sys.path.append(str(Path(__file__).parent.parent.parent))

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_system_imports():
    """测试核心模块导入"""
    logger.info("测试核心模块导入")
    
    try:
        # 导入核心模块
        from src.core.hot_words_service import HotWordsService
        from src.core.magic_video_service import MagicVideoService
        from src.core.magic_video_fix import VideoFixTools
        from src.core.analyze_service import AnalyzeService
        
        logger.info("所有核心模块导入成功")
        return True
    except ImportError as e:
        logger.error(f"导入模块时出错: {str(e)}")
        return False

def test_api_connection():
    """测试API连接状态"""
    logger.info("测试DashScope API连接状态")
    
    try:
        from src.core.hot_words_api import HotWordsAPI
        
        api = HotWordsAPI()
        # 测试API密钥是否有效
        is_valid = api.check_api_key()
        
        if is_valid:
            logger.info("DashScope API密钥有效")
            
            # 尝试获取热词列表，进一步验证连接
            try:
                vocabularies = api.list_vocabularies(page_size=1)
                if vocabularies is not None:
                    logger.info(f"DashScope API连接成功，获取到 {len(vocabularies)} 个热词表")
                    return True
                else:
                    logger.error("DashScope API调用失败，无法获取热词表")
                    return False
            except Exception as e:
                logger.error(f"DashScope API调用异常: {str(e)}")
                return False
        else:
            logger.error("DashScope API密钥无效")
            return False
    except Exception as e:
        logger.error(f"API测试过程中出错: {str(e)}")
        return False

def test_streamlit_startup():
    """测试Streamlit应用启动"""
    logger.info("测试Streamlit应用启动")
    
    try:
        # 使用subprocess启动应用并立即检查，不等待完全启动
        process = subprocess.Popen(
            ["python", "-m", "streamlit", "run", "app.py", "--server.headless", "true"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 给应用5秒钟启动时间
        time.sleep(5)
        
        # 检查进程是否仍在运行
        if process.poll() is None:
            logger.info("Streamlit应用成功启动")
            # 终止进程
            process.terminate()
            return True
        else:
            # 获取错误输出
            _, stderr = process.communicate()
            logger.error(f"Streamlit应用启动失败: {stderr.decode('utf-8')}")
            return False
    except Exception as e:
        logger.error(f"测试Streamlit启动时出错: {str(e)}")
        return False

def run_all_tests():
    """运行所有集成测试"""
    results = {}
    
    # 运行导入测试
    results["imports"] = test_system_imports()
    
    # 运行API连接测试
    results["api"] = test_api_connection()
    
    # 运行Streamlit启动测试
    results["streamlit"] = test_streamlit_startup()
    
    # 输出测试结果摘要
    logger.info("===== 测试结果摘要 =====")
    for test_name, result in results.items():
        status = "通过" if result else "失败"
        logger.info(f"测试 '{test_name}': {status}")
    
    # 计算总体测试结果
    overall = all(results.values())
    logger.info(f"总体测试结果: {'通过' if overall else '失败'}")
    
    return overall

if __name__ == "__main__":
    logger.info("===== 开始系统集成测试 =====")
    run_all_tests()
    logger.info("===== 系统集成测试完成 =====") 