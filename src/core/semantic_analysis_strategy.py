#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语义分析策略：提供统一的广告分析策略接口和实现
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

class AdAnalysisStrategy(ABC):
    """广告分析策略抽象基类"""
    
    @abstractmethod
    def analyze_ad_phase(self, text: str) -> str:
        """
        分析广告文本所属阶段
        
        参数:
            text: 广告文本
            
        返回:
            广告阶段名称
        """
        pass
    
    @abstractmethod
    def extract_keywords(self, text: str) -> List[str]:
        """
        提取广告文本关键词
        
        参数:
            text: 广告文本
            
        返回:
            关键词列表
        """
        pass
        
    @abstractmethod
    def name(self) -> str:
        """返回策略名称"""
        pass


class BertAnalysisStrategy(AdAnalysisStrategy):
    """基于BERT的广告分析策略"""
    
    def __init__(self):
        """初始化BERT分析策略"""
        from src.core.bert_model_service import BertModelService
        
        try:
            self.bert_service = BertModelService()
            self.is_available = True
            logger.info("BERT分析策略初始化成功")
        except Exception as e:
            self.is_available = False
            logger.error(f"BERT分析策略初始化失败: {str(e)}")
    
    def analyze_ad_phase(self, text: str) -> str:
        """使用BERT分析广告阶段"""
        if not self.is_available:
            logger.warning("BERT服务不可用，返回默认阶段")
            return "一般内容"
            
        try:
            # 使用BERT服务分析内容
            content_analysis = self.bert_service.analyze_ad_content(text)
            return content_analysis.get("primary_intent", "一般内容")
        except Exception as e:
            logger.exception(f"BERT分析广告阶段时出错: {str(e)}")
            return "一般内容"
    
    def extract_keywords(self, text: str) -> List[str]:
        """使用BERT提取关键词"""
        if not self.is_available:
            # 备用提取方法
            return self._fallback_extract_keywords(text)
            
        try:
            # 使用jieba提取关键词
            import jieba.analyse
            keywords = jieba.analyse.textrank(text, topK=5)
            return list(keywords)
        except Exception as e:
            logger.exception(f"BERT提取关键词时出错: {str(e)}")
            return self._fallback_extract_keywords(text)
    
    def _fallback_extract_keywords(self, text: str) -> List[str]:
        """关键词提取备用方法"""
        # 使用简单的规则提取一些关键词
        keywords = []
        
        # 预定义的关键词列表
        predefined_keywords = ["启赋", "蕴醇", "HMO", "自御力", "保护", "免疫", "配方"]
        
        # 检查文本中是否存在预定义关键词
        for kw in predefined_keywords:
            if kw in text and kw not in keywords:
                keywords.append(kw)
                
        return keywords[:5]  # 最多返回5个关键词
        
    def name(self) -> str:
        return "BERT"


class LLMAnalysisStrategy(AdAnalysisStrategy):
    """基于大语言模型的广告分析策略"""
    
    def __init__(self):
        """初始化LLM分析策略"""
        from src.core.llm_analysis_service import LLMAnalysisService
        
        try:
            self.llm_service = LLMAnalysisService()
            self.is_available = self.llm_service.is_available
            if self.is_available:
                logger.info("LLM分析策略初始化成功")
            else:
                logger.warning("LLM服务不可用，LLM分析策略降级")
        except Exception as e:
            self.is_available = False
            logger.error(f"LLM分析策略初始化失败: {str(e)}")
    
    def analyze_ad_phase(self, text: str) -> str:
        """使用LLM分析广告阶段"""
        if not self.is_available:
            logger.warning("LLM服务不可用，返回默认阶段")
            return "一般内容"
            
        try:
            # 同步调用LLM服务
            result = self.llm_service.analyze_sync(text, 'ad_phase')
            if result:
                return result
            return "一般内容"
        except Exception as e:
            logger.exception(f"LLM分析广告阶段时出错: {str(e)}")
            return "一般内容"
    
    def extract_keywords(self, text: str) -> List[str]:
        """使用LLM提取关键词"""
        if not self.is_available:
            # 备用提取方法
            return self._fallback_extract_keywords(text)
            
        try:
            # 同步调用LLM服务
            result = self.llm_service.analyze_sync(text, 'keywords')
            if result:
                return result
            return self._fallback_extract_keywords(text)
        except Exception as e:
            logger.exception(f"LLM提取关键词时出错: {str(e)}")
            return self._fallback_extract_keywords(text)
    
    def _fallback_extract_keywords(self, text: str) -> List[str]:
        """关键词提取备用方法"""
        # 使用简单的规则提取一些关键词
        keywords = []
        
        # 预定义的关键词列表
        predefined_keywords = ["启赋", "蕴醇", "HMO", "自御力", "保护", "免疫", "配方"]
        
        # 检查文本中是否存在预定义关键词
        for kw in predefined_keywords:
            if kw in text and kw not in keywords:
                keywords.append(kw)
                
        return keywords[:5]  # 最多返回5个关键词
        
    def name(self) -> str:
        return "LLM"


class HybridAnalysisStrategy(AdAnalysisStrategy):
    """混合广告分析策略，结合BERT和LLM优点"""
    
    def __init__(self, primary: str = "bert"):
        """
        初始化混合分析策略
        
        参数:
            primary: 主要策略，可选值为"llm"或"bert"
        """
        self.bert_strategy = BertAnalysisStrategy()
        self.llm_strategy = LLMAnalysisStrategy()
        
        self.primary = primary.lower()
        logger.info(f"混合分析策略初始化成功，主要策略: {self.primary}")
    
    def analyze_ad_phase(self, text: str) -> str:
        """使用混合策略分析广告阶段"""
        # 根据主要策略优先使用相应的分析方法
        if self.primary == "llm":
            # 优先使用LLM，如果失败则回退到BERT
            llm_result = self.llm_strategy.analyze_ad_phase(text)
            if llm_result != "一般内容":
                logger.info("使用LLM分析结果")
                return llm_result
            
            logger.info("LLM分析未得到有效结果，尝试BERT分析")
            return self.bert_strategy.analyze_ad_phase(text)
        else:
            # 优先使用BERT，如果结果不确定则使用LLM
            bert_result = self.bert_strategy.analyze_ad_phase(text)
            if bert_result != "一般内容":
                logger.info("使用BERT分析结果")
                return bert_result
            
            logger.info("BERT分析未得到有效结果，尝试LLM分析")
            return self.llm_strategy.analyze_ad_phase(text)
    
    def extract_keywords(self, text: str) -> List[str]:
        """使用混合策略提取关键词"""
        bert_keywords = self.bert_strategy.extract_keywords(text)
        llm_keywords = self.llm_strategy.extract_keywords(text)
        
        # 合并两种方法的结果，确保不重复
        combined_keywords = []
        
        # 根据主要策略决定关键词顺序
        if self.primary == "llm":
            primary_keywords = llm_keywords
            secondary_keywords = bert_keywords
        else:
            primary_keywords = bert_keywords
            secondary_keywords = llm_keywords
        
        # 先添加主要关键词
        for kw in primary_keywords:
            if kw not in combined_keywords:
                combined_keywords.append(kw)
        
        # 再添加次要关键词，直到达到5个
        for kw in secondary_keywords:
            if kw not in combined_keywords:
                combined_keywords.append(kw)
                if len(combined_keywords) >= 5:
                    break
        
        return combined_keywords
        
    def name(self) -> str:
        return f"Hybrid({self.primary.upper()})"


# 策略工厂
class AdAnalysisStrategyFactory:
    """广告分析策略工厂"""
    
    @staticmethod
    def create_strategy(strategy_type: str = "hybrid") -> AdAnalysisStrategy:
        """
        创建指定类型的分析策略
        
        参数:
            strategy_type: 策略类型，可选值为"bert"、"llm"或"hybrid"
            
        返回:
            对应的分析策略实例
        """
        strategy_type = strategy_type.lower()
        
        if strategy_type == "bert":
            return BertAnalysisStrategy()
        elif strategy_type == "llm":
            return LLMAnalysisStrategy()
        elif strategy_type == "hybrid":
            return HybridAnalysisStrategy()
        else:
            logger.warning(f"未知的策略类型: {strategy_type}，使用混合策略")
            return HybridAnalysisStrategy() 