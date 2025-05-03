#!/usr/bin/env python3
"""
测试热词服务功能

验证热词服务的基本功能是否正常工作，包括热词加载和添加
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径中
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.hot_words_service import HotWordsService

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hot_words_loading():
    """测试热词加载功能"""
    logger.info("开始测试热词加载功能")
    
    service = HotWordsService()
    
    # 尝试加载热词
    try:
        hot_words_data = service.load_hotwords()
        
        if hot_words_data:
            categories = hot_words_data.get('categories', {})
            logger.info(f"成功加载热词列表，包含 {len(categories)} 个类别")
            
            # 统计热词总数
            total_words = sum(len(words) for words in categories.values())
            logger.info(f"热词总数: {total_words}")
            
            # 打印前三个类别及其热词数量
            for i, (category, words) in enumerate(categories.items()):
                if i >= 3:
                    break
                logger.info(f"类别 '{category}' 包含 {len(words)} 个热词")
                # 如果该类别有热词，打印前3个
                if words:
                    for j, word in enumerate(words[:3]):
                        logger.info(f"  - 热词样例 {j+1}: {word}")
            
            # 检查最后更新时间
            last_updated = hot_words_data.get('last_updated', 'unknown')
            logger.info(f"热词最后更新时间: {last_updated}")
            
            return True
        else:
            logger.warning("加载的热词数据为空")
            return False
            
    except Exception as e:
        logger.error(f"加载热词时出错: {str(e)}")
        return False

def test_current_hotword_id():
    """测试当前热词ID功能"""
    logger.info("开始测试当前热词ID功能")
    
    service = HotWordsService()
    
    try:
        # 获取当前热词ID
        current_id = service.get_current_hotword_id()
        logger.info(f"当前热词ID: {current_id}")
        
        if current_id:
            # 测试设置当前热词ID (先保存原值，测试后再还原)
            original_id = current_id
            test_success = True
            
            # 尝试设置为相同值（不应该有变化）
            if service.set_current_hotword_id(current_id):
                logger.info("设置相同热词ID成功")
                
                # 验证值未变
                new_id = service.get_current_hotword_id()
                if new_id == original_id:
                    logger.info("当前热词ID未变化，验证成功")
                else:
                    logger.error(f"设置后热词ID不符: 期望={original_id}, 实际={new_id}")
                    test_success = False
            else:
                logger.error("设置相同热词ID失败")
                test_success = False
                
            return test_success
        else:
            logger.warning("当前热词ID为空")
            return False
            
    except Exception as e:
        logger.error(f"测试当前热词ID功能时出错: {str(e)}")
        return False

def test_hotword_operations():
    """测试热词操作功能"""
    logger.info("开始测试热词操作功能")
    
    service = HotWordsService()
    
    try:
        # 加载原始热词数据（稍后用于恢复）
        original_data = service.load_hotwords()
        
        # 测试添加类别
        test_category = f"测试类别_{int(time.time())}"
        add_result = service.add_category(test_category)
        
        if add_result:
            logger.info(f"添加测试类别成功: {test_category}")
            
            # 测试添加热词
            test_hotword = f"测试热词_{int(time.time())}"
            add_word_result = service.add_hotword(test_category, test_hotword)
            
            if add_word_result:
                logger.info(f"添加测试热词成功: {test_hotword}")
                
                # 验证热词已添加
                updated_data = service.load_hotwords()
                if (test_category in updated_data['categories'] and 
                    test_hotword in updated_data['categories'][test_category]):
                    logger.info("验证添加的热词存在: 成功")
                else:
                    logger.error("验证添加的热词存在: 失败")
                
                # 测试删除热词
                delete_word_result = service.delete_hotword(test_category, test_hotword)
                if delete_word_result:
                    logger.info(f"删除测试热词成功: {test_hotword}")
                else:
                    logger.error(f"删除测试热词失败: {test_hotword}")
            else:
                logger.error(f"添加测试热词失败: {test_hotword}")
            
            # 测试删除类别
            delete_result = service.delete_category(test_category)
            if delete_result:
                logger.info(f"删除测试类别成功: {test_category}")
            else:
                logger.error(f"删除测试类别失败: {test_category}")
                
            # 恢复原始数据
            service.save_hotwords(original_data)
            logger.info("已恢复原始热词数据")
            
            return True
        else:
            logger.error(f"添加测试类别失败: {test_category}")
            return False
            
    except Exception as e:
        logger.error(f"测试热词操作功能时出错: {str(e)}")
        # 尝试恢复原始数据
        try:
            service.save_hotwords(original_data)
            logger.info("出错后已恢复原始热词数据")
        except:
            pass
        return False

if __name__ == "__main__":
    logger.info("===== 开始热词服务测试 =====")
    
    # 导入time模块（用于生成唯一测试名称）
    import time
    
    # 测试热词加载功能
    test_hot_words_loading()
    
    # 测试当前热词ID功能
    test_current_hotword_id()
    
    # 测试热词操作功能
    test_hotword_operations()
    
    logger.info("===== 热词服务测试完成 =====") 