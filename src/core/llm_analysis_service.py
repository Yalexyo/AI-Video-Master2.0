#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM分析服务：基于DeepSeek V3大语言模型的高级文本分析能力
"""

import os
import json
import logging
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable, Coroutine

from src.api.llm_service import LLMService

# 配置日志
logger = logging.getLogger(__name__)

class LLMAnalysisService:
    """基于DeepSeek V3的大语言模型分析服务"""
    
    def __init__(self):
        """初始化LLM分析服务"""
        try:
            self.llm_service = LLMService()
            self.is_available = True
            logger.info("LLM分析服务初始化成功，使用DeepSeek V3模型")
        except Exception as e:
            self.is_available = False
            logger.error(f"LLM分析服务初始化失败: {str(e)}")
    
    async def analyze_ad_phase(self, text: str) -> Optional[str]:
        """
        分析广告文本属于哪个阶段（问题引入、产品介绍、效果展示、促销信息）
        
        参数:
            text: 广告文本
            
        返回:
            广告阶段，如果分析失败则返回None
        """
        if not self.is_available:
            logger.warning("LLM分析服务不可用，无法分析广告阶段")
            return None
            
        try:
            # 构建提示词
            prompt = f"""
你是一位广告文案分析专家，需要将以下广告文本段落分类为以下阶段之一：
- 问题引入：介绍用户面临的问题或痛点
- 产品介绍：描述产品特性、成分或技术
- 效果展示：展示产品的效果或好处
- 促销信息：包含购买信息、优惠或行动号召

请特别注意：
- 促销信息通常包含「限时」「专享」「零元」「福利」「库存」「新客」等购买相关词语
- 即使文本很短，只要包含促销和购买信息相关内容，就应判定为"促销信息"
- 若文本提到"限时给到新客专享零元"或类似内容，必须判定为"促销信息"
- 明确的价格、优惠标签或购买方式都属于"促销信息"

文本段落: "{text}"

仅返回一个分类结果，不要有任何额外解释。格式为: {{"category": "分类结果"}}
"""
            
            # 调用LLM服务
            llm_result = await self.llm_service._call_deepseek_api(prompt)
            
            if not llm_result:
                logger.warning("LLM分析返回空结果")
                return None
                
            # 解析JSON响应
            try:
                result_json = json.loads(llm_result)
                if isinstance(result_json, dict) and "category" in result_json:
                    category = result_json["category"]
                    # 验证类别是否有效
                    valid_categories = ["问题引入", "产品介绍", "效果展示", "促销信息"]
                    if category in valid_categories:
                        logger.info(f"LLM分析成功: {category}")
                        return category
                    else:
                        logger.warning(f"LLM返回了无效的类别: {category}")
                else:
                    logger.warning(f"LLM返回了无效的JSON结构: {llm_result[:100]}...")
            except json.JSONDecodeError:
                logger.warning(f"无法解析LLM返回的JSON: {llm_result[:100]}...")
                
            return None
            
        except Exception as e:
            logger.exception(f"LLM分析广告阶段时出错: {str(e)}")
            return None
            
    async def extract_brand_keywords(self, text: str) -> List[str]:
        """
        从文本中提取品牌关键词
        
        参数:
            text: 广告文本
            
        返回:
            品牌关键词列表
        """
        if not self.is_available:
            logger.warning("LLM分析服务不可用，无法提取品牌关键词")
            return []
            
        try:
            # 构建提示词
            prompt = f"""
分析以下广告文本，提取出其中的品牌名称、产品名称、核心卖点关键词和促销信息关键词：

文本: "{text}"

注意同时提取:
1. 品牌词：如"启赋"、"蕴醇"等
2. 产品特性：如"HMO"、"低聚糖"、"活性蛋白"、"乳铁蛋白"等
3. 效果词：如"自御力"、"保护力"、"免疫"等
4. 促销词：如"限时"、"专享"、"零元"、"福利"等

仅返回关键词列表，不要有任何额外解释。格式为: {{"keywords": ["关键词1", "关键词2", ...]}}
"""
            
            # 调用LLM服务
            llm_result = await self.llm_service._call_deepseek_api(prompt)
            
            if not llm_result:
                logger.warning("LLM分析返回空结果")
                return []
                
            # 解析JSON响应
            try:
                result_json = json.loads(llm_result)
                if isinstance(result_json, dict) and "keywords" in result_json:
                    keywords = result_json["keywords"]
                    if isinstance(keywords, list):
                        logger.info(f"LLM提取到 {len(keywords)} 个关键词")
                        return keywords
                    else:
                        logger.warning(f"LLM返回的keywords不是列表: {keywords}")
                else:
                    logger.warning(f"LLM返回了无效的JSON结构: {llm_result[:100]}...")
            except json.JSONDecodeError:
                logger.warning(f"无法解析LLM返回的JSON: {llm_result[:100]}...")
                
            return []
            
        except Exception as e:
            logger.exception(f"LLM提取品牌关键词时出错: {str(e)}")
            return []
    
    def run_async_in_thread(self, coroutine: Callable[[], Coroutine]) -> Any:
        """
        在单独的线程中运行异步协程，解决事件循环嵌套问题
        
        参数:
            coroutine: 要运行的协程函数
            
        返回:
            协程的结果
        """
        result = None
        
        def run_in_thread():
            nonlocal result
            # 在新线程中创建一个新的事件循环
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                # 在新事件循环中运行协程
                result = new_loop.run_until_complete(coroutine())
            finally:
                new_loop.close()
        
        # 创建线程并执行
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()  # 等待线程完成
        
        return result
    
    def analyze_sync(self, text: str, analysis_type: str) -> Any:
        """
        同步方式调用LLM分析（适用于非异步上下文）
        
        参数:
            text: 要分析的文本
            analysis_type: 分析类型，可选值：'ad_phase', 'keywords'
            
        返回:
            分析结果，类型取决于analysis_type
        """
        try:
            # 获取事件循环
            loop = asyncio.get_event_loop()
            
            # 如果事件循环已经运行，使用新方法在独立线程中执行
            if loop.is_running():
                logger.info("事件循环已在运行，使用线程执行LLM分析")
                if analysis_type == 'ad_phase':
                    return self.run_async_in_thread(lambda: self.analyze_ad_phase(text))
                elif analysis_type == 'keywords':
                    return self.run_async_in_thread(lambda: self.extract_brand_keywords(text))
                else:
                    logger.error(f"未知的分析类型: {analysis_type}")
                    return None
            else:
                # 如果事件循环未运行，直接使用它
                if analysis_type == 'ad_phase':
                    return loop.run_until_complete(self.analyze_ad_phase(text))
                elif analysis_type == 'keywords':
                    return loop.run_until_complete(self.extract_brand_keywords(text))
                else:
                    logger.error(f"未知的分析类型: {analysis_type}")
                    return None
                
        except Exception as e:
            logger.exception(f"同步调用LLM分析时出错: {str(e)}")
            return None if analysis_type == 'ad_phase' else [] 