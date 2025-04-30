import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime

from utils.analyzer import VideoAnalyzer
from src.api.llm_service import LLMService

logger = logging.getLogger(__name__)

class VideoSegmentService:
    """视频片段处理服务，负责获取和处理视频片段"""
    
    def __init__(self):
        self.analyzer = VideoAnalyzer()
        self.llm_service = LLMService()
        
    async def get_video_segments(self, 
                           video_id: str, 
                           subtitle_df: pd.DataFrame,
                           selected_intent: Dict[str, Any], 
                           user_description: str) -> Dict[str, Any]:
        """
        获取匹配用户意图的视频片段
        
        参数:
            video_id: 视频ID
            subtitle_df: 字幕DataFrame
            selected_intent: 用户选择的意图
            user_description: 用户输入的详细描述
            
        返回:
            包含匹配片段的结果字典
        """
        try:
            # 创建结果结构
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results = {
                "type": "视频片段匹配",
                "timestamp": timestamp,
                "video_id": video_id,
                "intent": selected_intent,
                "user_description": user_description,
                "matches": []
            }
            
            # 检查是否启用LLM精细匹配
            if user_description:
                # 将DataFrame转换为列表，便于传递给LLM服务
                subtitles = []
                for _, row in subtitle_df.iterrows():
                    subtitles.append({
                        "timestamp": row.get('timestamp', '00:00:00'),
                        "text": row.get('text', '')
                    })
                
                # 使用LLM进行精确匹配
                llm_matches = await self.llm_service.refine_intent_matching(
                    selected_intent, user_description, subtitles
                )
                
                if llm_matches:
                    results["matches"] = llm_matches
                    results["analysis_method"] = "LLM精确匹配"
                    return results
            
            # 如果未启用LLM或LLM匹配失败，回退到关键词匹配
            keyword_results = self.analyzer.analyze_keywords(
                subtitle_df, 
                selected_intent.get('keywords', []),
                threshold=0.6
            )
            
            if keyword_results and "matches" in keyword_results:
                results["matches"] = keyword_results["matches"]
                results["analysis_method"] = "关键词匹配"
            
            return results
            
        except Exception as e:
            logger.error(f"获取视频片段时出错: {str(e)}")
            return {
                "type": "视频片段匹配", 
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "error": str(e), 
                "matches": [],
                "analysis_method": "分析失败"
            } 