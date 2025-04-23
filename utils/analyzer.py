import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

# 配置日志
logger = logging.getLogger(__name__)

class VideoAnalyzer:
    """视频分析器，用于分析视频内容并根据维度或关键词进行匹配"""
    
    def __init__(self, config: Dict = None):
        """
        初始化视频分析器
        
        参数:
            config: 配置字典，包含分析参数
        """
        self.config = config or {}
        logger.info("视频分析器初始化完成")
        
        # 确保输出目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        dirs = [
            os.path.join('data', 'video_analysis', 'results'),
            os.path.join('data', 'cache')
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"创建目录: {dir_path}")
    
    def analyze_dimensions(self, video_data: pd.DataFrame, dimensions: Dict[str, Any], threshold: float = 0.7) -> Dict[str, Any]:
        """
        根据维度分析视频文本数据
        
        参数:
            video_data: 视频文本数据DataFrame，应包含text和timestamp列
            dimensions: 维度结构，格式为 {"title": "标题", "level1": ["一级维度1", "一级维度2"], "level2": {"一级维度1": ["二级维度1", "二级维度2"]}}
            threshold: 匹配阈值
            
        返回:
            分析结果字典
        """
        try:
            # 获取当前时间
            analysis_time = datetime.now()
            timestamp = analysis_time.isoformat()
            
            # 初始化结果结构
            results = {
                "type": "维度分析",
                "timestamp": timestamp,
                "dimensions": dimensions,
                "matches": []
            }
            
            # 处理每条文本记录
            for _, row in video_data.iterrows():
                text = row.get('text', '')
                if not text:
                    continue
                
                # 模拟维度匹配分析
                # 实际项目中，这里应该使用NLP或文本相似度模型进行分析
                matches = self._simulate_dimension_matching(text, dimensions, threshold)
                
                # 如果有匹配，添加到结果中
                if matches:
                    for match in matches:
                        results["matches"].append({
                            "dimension_level1": match["level1"],
                            "dimension_level2": match.get("level2", ""),
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": match["score"]
                        })
            
            logger.info(f"维度分析完成，匹配 {len(results['matches'])} 条记录")
            return results
        
        except Exception as e:
            logger.error(f"维度分析出错: {str(e)}")
            return {"type": "维度分析", "timestamp": datetime.now().isoformat(), "error": str(e), "matches": []}
    
    def analyze_keywords(self, video_data: pd.DataFrame, keywords: List[str], threshold: float = 0.7) -> Dict[str, Any]:
        """
        根据关键词分析视频文本数据
        
        参数:
            video_data: 视频文本数据DataFrame，应包含text和timestamp列
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            分析结果字典
        """
        try:
            # 获取当前时间
            analysis_time = datetime.now()
            timestamp = analysis_time.isoformat()
            
            # 初始化结果结构
            results = {
                "type": "关键词分析",
                "timestamp": timestamp,
                "keywords": keywords,
                "matches": []
            }
            
            # 处理每条文本记录
            for _, row in video_data.iterrows():
                text = row.get('text', '')
                if not text:
                    continue
                
                # 分析关键词匹配
                # 实际项目中，这里应该使用更复杂的语义匹配而不仅仅是简单的包含关系
                for keyword in keywords:
                    if keyword.lower() in text.lower():
                        # 模拟匹配得分
                        score = 0.7 + np.random.random() * 0.3  # 随机生成0.7-1.0之间的分数
                        
                        results["matches"].append({
                            "keyword": keyword,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": float(score)
                        })
            
            logger.info(f"关键词分析完成，匹配 {len(results['matches'])} 条记录")
            return results
        
        except Exception as e:
            logger.error(f"关键词分析出错: {str(e)}")
            return {"type": "关键词分析", "timestamp": datetime.now().isoformat(), "error": str(e), "matches": []}
    
    def _simulate_dimension_matching(self, text: str, dimensions: Dict[str, Any], threshold: float) -> List[Dict[str, Any]]:
        """
        模拟维度匹配逻辑
        
        参数:
            text: 要分析的文本
            dimensions: 维度结构
            threshold: 匹配阈值
            
        返回:
            匹配结果列表
        """
        matches = []
        
        # 获取一级维度
        level1_dims = dimensions.get('level1', [])
        
        for dim1 in level1_dims:
            # 模拟匹配计算，基于简单的字符串包含关系
            # 实际项目中应该使用语义相似度或其他NLP技术
            contains_words = any(word in text for word in dim1.split())
            
            if contains_words:
                # 模拟匹配分数
                score = 0.7 + np.random.random() * 0.3  # 随机生成0.7-1.0之间的分数
                
                # 一级维度匹配
                match = {
                    "level1": dim1,
                    "score": float(score)
                }
                
                # 尝试匹配二级维度
                level2_dims = dimensions.get('level2', {}).get(dim1, [])
                for dim2 in level2_dims:
                    contains_words_l2 = any(word in text for word in dim2.split())
                    
                    if contains_words_l2:
                        # 更新为二级维度匹配
                        score_l2 = 0.7 + np.random.random() * 0.3
                        match["level2"] = dim2
                        match["score"] = float(score_l2)
                        break
                
                matches.append(match)
        
        return matches
    
    def save_analysis_results(self, results: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """
        保存分析结果
        
        参数:
            results: 分析结果字典
            output_file: 输出文件路径，如果为None则生成默认文件名
            
        返回:
            保存的文件路径
        """
        try:
            # 如果未指定输出文件，创建默认文件名
            if output_file is None:
                analysis_type = results.get('type', 'analysis').lower().replace(' ', '_')
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                output_file = os.path.join('data', 'video_analysis', 'results', f"{analysis_type}_{timestamp}.json")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 保存结果
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"分析结果已保存到: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"保存分析结果出错: {str(e)}")
            return "" 