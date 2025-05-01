import torch
import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

class TextEmbeddingModel:
    """文本嵌入模型封装类"""
    
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """
        初始化文本嵌入模型
        
        参数:
            model_name: 模型名称，默认使用多语言模型
        """
        logger.info(f"初始化文本嵌入模型: {model_name}")
        try:
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            logger.info(f"模型 {model_name} 加载成功")
        except Exception as e:
            logger.error(f"加载模型 {model_name} 失败: {str(e)}")
            raise
    
    def encode(self, texts: List[str], batch_size: int = 32, show_progress_bar: bool = False) -> np.ndarray:
        """
        将文本编码为向量表示
        
        参数:
            texts: 要编码的文本列表
            batch_size: 批处理大小
            show_progress_bar: 是否显示进度条
            
        返回:
            文本向量表示的numpy数组
        """
        if not texts:
            logger.warning("传入的文本列表为空")
            return np.array([])
        
        try:
            embeddings = self.model.encode(
                texts, 
                batch_size=batch_size,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True
            )
            logger.debug(f"成功编码 {len(texts)} 个文本段")
            return embeddings
        except Exception as e:
            logger.error(f"文本编码过程出错: {str(e)}")
            raise
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的相似度
        
        参数:
            text1: 第一段文本
            text2: 第二段文本
            
        返回:
            相似度得分 (0-1)
        """
        try:
            embedding1 = self.encode([text1])[0]
            embedding2 = self.encode([text2])[0]
            
            # 计算余弦相似度
            similarity = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
            
            return float(similarity)
        except Exception as e:
            logger.error(f"计算文本相似度出错: {str(e)}")
            return 0.0
    
    def calculate_similarities(self, query: str, texts: List[str]) -> List[float]:
        """
        计算一个查询文本与多个文本的相似度
        
        参数:
            query: 查询文本
            texts: 待比较的文本列表
            
        返回:
            相似度得分列表
        """
        if not texts:
            return []
        
        try:
            query_embedding = self.encode([query])[0]
            texts_embeddings = self.encode(texts)
            
            # 计算余弦相似度
            similarities = []
            for text_embedding in texts_embeddings:
                similarity = np.dot(query_embedding, text_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(text_embedding))
                similarities.append(float(similarity))
            
            return similarities
        except Exception as e:
            logger.error(f"批量计算文本相似度出错: {str(e)}")
            return [0.0] * len(texts)
    
    def match_dimensions(self, text: str, dimensions: Dict[str, Any], threshold: float = 0.7) -> Dict[str, Dict[str, float]]:
        """
        匹配文本与维度
        
        参数:
            text: 要分析的文本
            dimensions: 维度结构，格式为 {"title": "标题", "level1": ["一级维度1", "一级维度2"], "level2": {"一级维度1": ["二级维度1", "二级维度2"]}}
            threshold: 匹配阈值
            
        返回:
            匹配结果，格式为 {"level1": {"维度名": 分数}, "level2": {"维度名": 分数}}
        """
        matches = {
            "level1": {},
            "level2": {}
        }
        
        try:
            # 匹配一级维度
            level1_dims = dimensions.get('level1', [])
            if level1_dims:
                level1_scores = self.calculate_similarities(text, level1_dims)
                
                for dim, score in zip(level1_dims, level1_scores):
                    if score >= threshold:
                        matches["level1"][dim] = float(score)
                
                # 如果一级维度有匹配，进一步匹配二级维度
                for dim1 in matches["level1"]:
                    level2_dims = dimensions.get('level2', {}).get(dim1, [])
                    if level2_dims:
                        level2_scores = self.calculate_similarities(text, level2_dims)
                        
                        for dim2, score in zip(level2_dims, level2_scores):
                            if score >= threshold:
                                if dim1 not in matches["level2"]:
                                    matches["level2"][dim1] = {}
                                matches["level2"][dim1][dim2] = float(score)
            
            return matches
        except Exception as e:
            logger.error(f"维度匹配过程出错: {str(e)}")
            return matches

class VideoAnalysisModel:
    """视频分析模型封装类"""
    
    def __init__(self, text_model: Optional[TextEmbeddingModel] = None):
        """
        初始化视频分析模型
        
        参数:
            text_model: 文本嵌入模型实例，如果为None则创建新实例
        """
        self.text_model = text_model or TextEmbeddingModel()
        logger.info("视频分析模型初始化完成")
    
    def analyze_subtitle_segments(self, segments: List[Dict[str, Any]], dimensions: Dict[str, Any], threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        分析字幕片段，匹配维度
        
        参数:
            segments: 字幕片段列表，每个片段应包含'text'字段
            dimensions: 维度结构
            threshold: 匹配阈值
            
        返回:
            分析结果列表，每个片段添加了维度匹配信息
        """
        if not segments:
            logger.warning("没有字幕片段需要分析")
            return []
        
        try:
            results = []
            for segment in segments:
                text = segment.get('text', '')
                if not text:
                    continue
                
                # 匹配维度
                matches = self.text_model.match_dimensions(text, dimensions, threshold)
                
                # 创建分析结果
                result = segment.copy()
                result['dimension_matches'] = matches
                result['has_matches'] = bool(matches['level1'] or matches['level2'])
                
                results.append(result)
            
            logger.info(f"成功分析 {len(results)} 个字幕片段")
            return results
        except Exception as e:
            logger.error(f"分析字幕片段出错: {str(e)}")
            return segments
    
    def analyze_keywords(self, segments: List[Dict[str, Any]], keywords: List[str], threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        分析字幕片段，匹配关键词
        
        参数:
            segments: 字幕片段列表，每个片段应包含'text'字段
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            分析结果列表，每个片段添加了关键词匹配信息
        """
        if not segments or not keywords:
            logger.warning("没有字幕片段或关键词需要分析")
            return segments
        
        try:
            results = []
            for segment in segments:
                text = segment.get('text', '')
                if not text:
                    continue
                
                # 计算与关键词的相似度
                similarities = self.text_model.calculate_similarities(text, keywords)
                
                # 筛选高于阈值的关键词
                keyword_matches = {}
                for keyword, score in zip(keywords, similarities):
                    if score >= threshold:
                        keyword_matches[keyword] = float(score)
                
                # 创建分析结果
                result = segment.copy()
                result['keyword_matches'] = keyword_matches
                result['has_keyword_matches'] = bool(keyword_matches)
                
                results.append(result)
            
            logger.info(f"成功分析 {len(results)} 个字幕片段的关键词匹配")
            return results
        except Exception as e:
            logger.error(f"分析关键词匹配出错: {str(e)}")
            return segments

@dataclass
class HotWord:
    """热词数据结构"""
    word: str  # 词语
    weight: float = 1.0  # 权重
    category: str = ""  # 分类
    description: str = ""  # 描述
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Dimension:
    """维度数据结构"""
    id: str  # 唯一标识
    name: str  # 维度名称
    weight: float = 1.0  # 权重
    parent_id: Optional[str] = None  # 父级ID，如果是顶级则为None
    description: str = ""  # 描述
    sub_dimensions: List['Dimension'] = field(default_factory=list)  # 子维度列表


@dataclass
class VideoInfo:
    """视频信息数据结构"""
    video_id: str  # 视频唯一标识符
    filename: str  # 文件名
    file_path: str  # 本地文件路径或URL
    file_size: int  # 文件大小(字节)
    duration: float  # 视频时长(秒)
    width: int  # 宽度(像素)
    height: int  # 高度(像素)
    fps: float  # 帧率
    format: str  # 视频格式
    has_audio: bool  # 是否包含音轨
    upload_time: datetime = field(default_factory=datetime.now)  # 上传时间
    oss_key: Optional[str] = None  # 如存储在云端，对应的OSS键值
    is_cloud_stored: bool = False  # 是否存储在云端
    status: str = "pending"  # 视频状态: pending, processing, completed, error
    error_message: Optional[str] = None  # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    
    @property
    def resolution(self) -> str:
        """返回视频分辨率字符串"""
        return f"{self.width}x{self.height}"


@dataclass
class AnalysisResult:
    """视频分析结果数据结构"""
    video_id: str  # 关联的视频ID
    timestamp: float  # 分析时间点(秒)
    frame_num: int  # 帧序号
    content: Dict[str, Any]  # 分析内容
    confidence: float = 0.0  # 分析置信度
    dimension_matches: List[str] = field(default_factory=list)  # 匹配的维度ID列表
    hotword_matches: List[str] = field(default_factory=list)  # 匹配的热词列表


@dataclass
class ProcessingTask:
    """视频处理任务数据结构"""
    task_id: str  # 任务ID
    video_id: str  # 视频ID
    status: str  # 状态: pending, running, completed, error
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0  # 进度百分比
    steps_completed: List[str] = field(default_factory=list)  # 已完成的步骤
    current_step: Optional[str] = None  # 当前进行的步骤
    error_message: Optional[str] = None  # 错误信息
    result: Dict[str, Any] = field(default_factory=dict)  # 处理结果
