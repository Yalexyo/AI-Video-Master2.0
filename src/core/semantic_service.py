#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语义分析服务：提供字幕分段、关键词提取和标题生成等功能
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
import numpy as np

# 引入策略接口
from src.core.semantic_analysis_strategy import AdAnalysisStrategyFactory

# 配置日志
logger = logging.getLogger(__name__)

class SemanticAnalysisService:
    """语义分析服务，提供字幕分段、关键词提取和标题生成等功能"""
    
    def __init__(self, analysis_strategy: str = "hybrid"):
        """
        初始化语义分析服务
        
        参数:
            analysis_strategy: 分析策略类型，可选值为"bert"、"llm"或"hybrid"
        """
        logger.info("初始化语义分析服务")
        
        # 创建分析策略
        self.strategy_factory = AdAnalysisStrategyFactory()
        self.analysis_strategy = self.strategy_factory.create_strategy(analysis_strategy)
        
        logger.info(f"使用分析策略: {self.analysis_strategy.name()}")
        
        # 保留bert_service属性以向后兼容
        self.bert_service = None
        # 懒加载BERT模型，减少资源占用
    
    def _load_bert_model(self):
        """懒加载BERT模型"""
        if self.bert_service is None:
            from src.core.bert_model_service import BertModelService
            logger.info("加载BERT模型服务")
            self.bert_service = BertModelService()
    
    async def analyze_and_segment(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        分析字幕并进行语义分段
        
        参数:
            subtitles: 字幕列表
            
        返回:
            分段后的语义段落列表
        """
        logger.info(f"开始分析和分段，字幕数量: {len(subtitles)}")
        
        # 懒加载BERT模型（为了兼容性）
        self._load_bert_model()
        
        # 使用BERT模型服务进行广告视频分段
        if self.bert_service:
            logger.info("使用BERT模型进行广告视频分段")
            segments = self.bert_service.segment_ad_video(subtitles)
            
            # 使用选择的分析策略进行内容分析
            for segment in segments:
                # 使用策略分析广告阶段
                phase = self.analysis_strategy.analyze_ad_phase(segment["text"])
                if phase != "一般内容":
                    logger.info(f"策略分析结果: 将段落重新分类为 {phase}")
                    segment["phase"] = phase
                
                # 保留原有分析逻辑以增强安全性
                content_analysis = self.bert_service.analyze_ad_content(segment["text"])
                segment.update(content_analysis)
                
                # 使用策略提取关键词
                segment["keywords"] = self.analysis_strategy.extract_keywords(segment["text"])
                segment["title"] = self._generate_title(segment["text"], segment["primary_intent"])
                
            logger.info(f"分段完成，共{len(segments)}个段落")
            return segments
        
        # 如果BERT模型加载失败，回退到简单分段算法
        logger.warning("BERT模型服务不可用，使用简单分段算法")
        return self._simple_segment(subtitles)
    
    def _simple_segment(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """简单的基于规则的分段算法（作为备选）"""
        # 如果字幕太少，直接返回一个段落
        if len(subtitles) <= 5:
            logger.info("字幕数量太少，作为单个段落处理")
            return [{
                "start_time": subtitles[0]["start"],
                "end_time": subtitles[-1]["end"],
                "text": " ".join([s["text"] for s in subtitles]),
                "duration": subtitles[-1]["end"] - subtitles[0]["start"],
                "subtitles": subtitles,
                "keywords": self._extract_keywords(" ".join([s["text"] for s in subtitles])),
                "title": "广告内容",
                "phase": "广告内容",
                "primary_intent": "一般内容"
            }]
        
        # 时长阈值和文字阈值
        min_segment_duration = 10  # 最小段落时长（秒）
        min_segment_text_length = 50  # 最小段落文本长度（字符）
        max_segment_text_length = 300  # 最大段落文本长度（字符）
        
        segments = []
        current_segment = {
            "start_time": subtitles[0]["start"],
            "subtitles": [],
            "text": ""
        }
        
        for i, subtitle in enumerate(subtitles):
            # 添加到当前段落
            current_segment["subtitles"].append(subtitle)
            current_segment["text"] += " " + subtitle["text"]
            current_segment["end_time"] = subtitle["end"]
            
            # 判断是否需要结束当前段落
            # 1. 达到最大文本长度
            # 2. 遇到长停顿（超过2秒）
            # 3. 已经是最后一个字幕
            end_current_segment = False
            
            if len(current_segment["text"]) >= max_segment_text_length:
                end_current_segment = True
            elif i < len(subtitles) - 1 and subtitles[i+1]["start"] - subtitle["end"] > 2.0:
                end_current_segment = True
            elif i == len(subtitles) - 1:
                end_current_segment = True
            
            # 如果需要结束当前段落
            if end_current_segment:
                # 如果段落文本太短，尝试合并到下一个段落
                if len(current_segment["text"]) < min_segment_text_length and i < len(subtitles) - 1:
                    continue
                
                # 计算段落持续时间
                current_segment["duration"] = current_segment["end_time"] - current_segment["start_time"]
                
                # 如果段落太短，尝试合并到下一个段落
                if current_segment["duration"] < min_segment_duration and i < len(subtitles) - 1:
                    continue
                
                # 生成段落标题和关键词
                current_segment["title"] = self._generate_title(current_segment["text"])
                current_segment["keywords"] = self._extract_keywords(current_segment["text"])
                current_segment["phase"] = "广告内容"
                current_segment["primary_intent"] = "一般内容"
                
                # 添加到段落列表
                segments.append(current_segment)
                
                # 如果不是最后一个字幕，创建新段落
                if i < len(subtitles) - 1:
                    current_segment = {
                        "start_time": subtitles[i+1]["start"],
                        "subtitles": [],
                        "text": ""
                    }
        
        logger.info(f"简单分段完成，共{len(segments)}个段落")
        return segments
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词
        
        参数:
            text: 文本内容
            
        返回:
            关键词列表
        """
        # 简单实现：分词后取频率较高的词
        # 在实际项目中，这里应该使用更复杂的算法，如TF-IDF或TextRank
        from jieba import analyse
        
        # 使用TextRank算法提取关键词
        keywords = analyse.textrank(text, topK=5, withWeight=False)
        return list(keywords)
    
    def _generate_title(self, text: str, intent: str = None) -> str:
        """
        生成段落标题
        
        参数:
            text: 段落文本
            intent: 段落的主要意图
            
        返回:
            生成的标题
        """
        # 根据意图生成标题
        if intent and intent != "一般内容":
            # 广告意图映射到标题模板
            title_templates = {
                "吸引注意": "问题引入",
                "问题引入": "问题引入",
                "产品介绍": "产品特性介绍",
                "效果展示": "效果与优势展示",
                "促销信息": "购买信息"
            }
            
            if intent in title_templates:
                # 获取前15个字符作为摘要
                summary = text[:15] + "..." if len(text) > 15 else text
                return f"{title_templates[intent]}: {summary}"
        
        # 默认标题生成：取前20个字符
        if len(text) <= 20:
            return text
        else:
            return text[:20] + "..."
    
    async def generate_title(self, text: str) -> str:
        """
        为文本生成简短标题
        
        参数:
            text: 输入文本
            
        返回:
            生成的标题
        """
        # 简单实现：截取前20个字符作为标题
        if not text:
            return "未知段落"
            
        # 取文本的前20个字符或第一个句号前的内容
        first_sentence_end = text.find("。")
        if 0 < first_sentence_end < 20:
            title = text[:first_sentence_end]
        else:
            title = text[:20] + "..." if len(text) > 20 else text
            
        return title.strip()
    
    async def extract_keywords(self, text: str, limit: int = 5) -> List[str]:
        """
        从文本中提取关键词
        
        参数:
            text: 输入文本
            limit: 最大关键词数量
            
        返回:
            关键词列表
        """
        if not text:
            return []
        
        # 简单实现：基于文本长度，从文本中提取一些词作为关键词
        keywords = []
        
        # 产品相关关键词
        product_keywords = ["启赋", "蕴淳", "HMO", "奶粉", "配方", "品牌"]
        
        # 健康相关关键词
        health_keywords = ["免疫", "自御力", "健康", "成长", "发育", "保护"]
        
        # 分析文本中是否包含特定关键词
        for keyword in product_keywords + health_keywords:
            if keyword in text and keyword not in keywords:
                keywords.append(keyword)
                if len(keywords) >= limit:
                    break
                    
        # 如果关键词不足，根据长度自动生成一些
        words = text.replace("，", "").replace("。", "").replace("！", "").replace("？", "").split()
        
        # 筛选4个字以下的词
        short_words = [w for w in words if 1 < len(w) <= 4]
        
        # 提取一些词作为关键词
        if short_words and len(keywords) < limit:
            # 选择一些较长的词作为关键词
            remaining_count = limit - len(keywords)
            sorted_words = sorted(short_words, key=len, reverse=True)
            
            for word in sorted_words:
                if word not in keywords:
                    keywords.append(word)
                    remaining_count -= 1
                    if remaining_count <= 0:
                        break
                        
        return keywords 