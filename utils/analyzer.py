import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
from sentence_transformers import SentenceTransformer, util
from sklearn.feature_extraction.text import TfidfVectorizer
import jieba
import re
from multiprocessing import Pool, cpu_count

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
        self.model = None
        self.model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
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
    
    def _load_model(self):
        """
        加载语义匹配模型
        
        返回:
            加载的模型实例
        """
        if self.model is None:
            try:
                logger.info(f"加载语义匹配模型: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("模型加载成功")
            except Exception as e:
                logger.error(f"加载模型失败: {str(e)}")
                # 模型加载失败时返回None，后续将使用备用匹配方法
                self.model = None
        return self.model
    
    def analyze_dimensions(self, video_data: pd.DataFrame, dimensions: Dict[str, Any], threshold: float = 0.7) -> Dict[str, Any]:
        """
        根据维度分析视频文本数据，使用语义相似度匹配
        
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
            timestamp = analysis_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 初始化结果结构
            results = {
                "type": "维度分析",
                "timestamp": timestamp,
                "dimensions": dimensions,
                "matches": []
            }
            
            # 尝试加载模型
            model = self._load_model()
            
            # 如果模型加载失败，使用备用方法
            if model is None:
                logger.warning("模型加载失败，使用备用维度匹配方法")
                matches = self._fallback_dimension_matching(video_data, dimensions, threshold)
                results["matches"] = matches
                return results
            
            # 获取一级维度列表
            level1_dims = dimensions.get('level1', [])
            
            # 预处理：一次性编码所有文本
            texts = video_data['text'].tolist()
            try:
                # 对文本进行分词预处理（仅对中文）
                preprocessed_texts = [self._preprocess_text(text) for text in texts]
                
                # 编码所有文本
                logger.info(f"编码 {len(texts)} 条文本")
                text_embeddings = model.encode(preprocessed_texts, show_progress_bar=False)
                
                # 编码所有一级维度
                logger.info(f"编码 {len(level1_dims)} 个一级维度")
                dim1_embeddings = model.encode([self._preprocess_text(dim) for dim in level1_dims], show_progress_bar=False)
                
                # 构建二级维度的编码映射
                dim2_embeddings = {}
                for dim1 in level1_dims:
                    level2_dims = dimensions.get('level2', {}).get(dim1, [])
                    if level2_dims:
                        dim2_embeddings[dim1] = model.encode(
                            [self._preprocess_text(dim2) for dim2 in level2_dims], 
                            show_progress_bar=False
                        )
            except Exception as e:
                logger.error(f"编码文本时出错: {str(e)}")
                matches = self._fallback_dimension_matching(video_data, dimensions, threshold)
                results["matches"] = matches
                return results
            
            # 处理每条文本记录
            for i, row in video_data.iterrows():
                text = row.get('text', '')
                if not text:
                    continue
                
                # 获取当前文本的embedding
                text_embedding = text_embeddings[i]
                
                # 计算与一级维度的相似度
                for dim1_idx, dim1 in enumerate(level1_dims):
                    # 计算相似度
                    similarity = util.cos_sim(text_embedding, dim1_embeddings[dim1_idx])[0][0].item()
                    
                    # 如果相似度高于阈值，添加到匹配结果
                    if similarity >= threshold:
                        # 尝试匹配二级维度
                        matched_dim2 = ""
                        max_dim2_similarity = 0
                        
                        # 如果有二级维度，计算相似度
                        if dim1 in dim2_embeddings:
                            level2_dims = dimensions.get('level2', {}).get(dim1, [])
                            level2_embeddings = dim2_embeddings[dim1]
                            
                            # 计算与所有二级维度的相似度
                            dim2_similarities = util.cos_sim(text_embedding, level2_embeddings)[0]
                            
                            # 获取最大相似度的索引
                            max_dim2_idx = dim2_similarities.argmax().item()
                            max_dim2_similarity = dim2_similarities[max_dim2_idx].item()
                            
                            # 如果二级维度相似度也高于阈值，记录匹配结果
                            if max_dim2_similarity >= threshold:
                                matched_dim2 = level2_dims[max_dim2_idx]
                        
                        # 使用最高的相似度作为分数
                        score = max(similarity, max_dim2_similarity)
                        
                        results["matches"].append({
                            "dimension_level1": dim1,
                            "dimension_level2": matched_dim2,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": float(score)
                        })
            
            logger.info(f"维度分析完成，匹配 {len(results['matches'])} 条记录")
            return results
        
        except Exception as e:
            logger.error(f"维度分析出错: {str(e)}")
            results = {
                "type": "维度分析", 
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "error": str(e), 
                "matches": []
            }
            
            # 尝试使用备用方法
            matches = self._fallback_dimension_matching(video_data, dimensions, threshold)
            results["matches"] = matches
            
            return results
    
    def analyze_keywords(self, video_data: pd.DataFrame, keywords: List[str], threshold: float = 0.7) -> Dict[str, Any]:
        """
        根据关键词分析视频文本数据，使用语义相似度和关键词提取
        
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
            timestamp = analysis_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 初始化结果结构
            results = {
                "type": "关键词分析",
                "timestamp": timestamp,
                "keywords": keywords,
                "matches": []
            }
            
            # 尝试加载模型
            model = self._load_model()
            
            # 如果模型加载失败，使用备用方法
            if model is None:
                logger.warning("模型加载失败，使用备用关键词匹配方法")
                matches = self._fallback_keyword_matching(video_data, keywords, threshold)
                results["matches"] = matches
                return results
            
            # 预处理：一次性编码所有文本和关键词
            texts = video_data['text'].tolist()
            try:
                # 对文本和关键词进行预处理
                preprocessed_texts = [self._preprocess_text(text) for text in texts]
                preprocessed_keywords = [self._preprocess_text(kw) for kw in keywords]
                
                # 编码所有文本
                logger.info(f"编码 {len(texts)} 条文本")
                text_embeddings = model.encode(preprocessed_texts, show_progress_bar=False)
                
                # 编码所有关键词
                logger.info(f"编码 {len(keywords)} 个关键词")
                keyword_embeddings = model.encode(preprocessed_keywords, show_progress_bar=False)
                
                # 提取额外关键词
                extracted_keywords, extracted_embeddings = self._extract_keywords(texts, model)
                logger.info(f"自动提取了 {len(extracted_keywords)} 个额外关键词")
            except Exception as e:
                logger.error(f"编码文本时出错: {str(e)}")
                matches = self._fallback_keyword_matching(video_data, keywords, threshold)
                results["matches"] = matches
                return results
            
            # 处理每条文本记录
            for i, row in video_data.iterrows():
                text = row.get('text', '')
                if not text:
                    continue
                
                # 获取当前文本的embedding
                text_embedding = text_embeddings[i]
                
                # 计算与预定义关键词的相似度
                for kw_idx, keyword in enumerate(keywords):
                    # 计算相似度
                    similarity = util.cos_sim(text_embedding, keyword_embeddings[kw_idx])[0][0].item()
                    
                    # 如果相似度高于阈值或关键词直接包含在文本中，添加到匹配结果
                    if similarity >= threshold or keyword.lower() in text.lower():
                        results["matches"].append({
                            "keyword": keyword,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": float(similarity) if similarity >= threshold else 0.85,  # 如果是直接包含，给一个较高的分数
                            "source": "预定义关键词"
                        })
                
                # 计算与自动提取关键词的相似度
                for ext_idx, ext_keyword in enumerate(extracted_keywords):
                    # 计算相似度
                    similarity = util.cos_sim(text_embedding, extracted_embeddings[ext_idx])[0][0].item()
                    
                    # 如果相似度高于阈值，添加到匹配结果
                    if similarity >= threshold and not any(m.get('keyword') == ext_keyword for m in results["matches"]):
                        results["matches"].append({
                            "keyword": ext_keyword,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": float(similarity),
                            "source": "自动提取关键词"
                        })
            
            logger.info(f"关键词分析完成，匹配 {len(results['matches'])} 条记录")
            return results
        
        except Exception as e:
            logger.error(f"关键词分析出错: {str(e)}")
            results = {
                "type": "关键词分析", 
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "error": str(e), 
                "matches": []
            }
            
            # 尝试使用备用方法
            matches = self._fallback_keyword_matching(video_data, keywords, threshold)
            results["matches"] = matches
            
            return results
    
    def _extract_keywords(self, texts: List[str], model) -> Tuple[List[str], np.ndarray]:
        """
        从文本中提取关键词
        
        参数:
            texts: 文本列表
            model: 语义模型
            
        返回:
            (keywords, embeddings): 提取的关键词列表和对应的嵌入向量
        """
        try:
            # 合并所有文本
            combined_text = " ".join(texts)
            
            # 使用jieba分词
            seg_list = jieba.cut(combined_text)
            seg_text = " ".join(seg_list)
            
            # 使用TF-IDF提取关键词
            vectorizer = TfidfVectorizer(max_features=20, stop_words='english')
            try:
                vectorizer.fit_transform([seg_text])
                feature_names = vectorizer.get_feature_names_out()
            except:
                # 备用方案：简单分词后选择长度大于1的词
                words = [word for word in seg_list if len(word) > 1]
                # 按词频排序，取前20个
                word_counts = {}
                for word in words:
                    word_counts[word] = word_counts.get(word, 0) + 1
                feature_names = sorted(word_counts.keys(), key=lambda x: word_counts[x], reverse=True)[:20]
            
            # 过滤掉数字和标点符号
            keywords = [word for word in feature_names if not re.match(r'^\d+$', word) and len(word) > 1]
            
            # 编码关键词
            embeddings = model.encode(keywords, show_progress_bar=False)
            
            return keywords, embeddings
        except Exception as e:
            logger.error(f"提取关键词时出错: {str(e)}")
            return [], np.array([])
    
    def _preprocess_text(self, text: str) -> str:
        """
        对文本进行预处理，如分词、去除停用词等
        
        参数:
            text: 待处理文本
            
        返回:
            处理后的文本
        """
        if not isinstance(text, str):
            text = str(text)
        
        # 简单清理：去除标点和多余空格
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _fallback_dimension_matching(self, video_data: pd.DataFrame, dimensions: Dict[str, Any], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        维度分析失败时返回错误提示信息
        
        参数:
            video_data: 视频文本数据DataFrame
            dimensions: 维度结构
            threshold: 匹配阈值
            
        返回:
            包含错误信息的匹配结果列表
        """
        logger.error("维度分析失败：无法加载语义模型或处理分析")
        
        # 返回单条错误信息记录
        return [{
            'dimension_level1': '错误',
            'dimension_level2': '',
            'timestamp': '00:00:00',
            'text': '维度分析失败。可能的原因：1) 语义模型加载失败；2) 内存不足；3) 文本编码过程出错。请尝试重新加载页面或联系管理员。',
            'score': 0.0,
            'is_error': True
        }]
    
    def _fallback_keyword_matching(self, video_data: pd.DataFrame, keywords: List[str], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        关键词分析失败时返回错误提示信息
        
        参数:
            video_data: 视频文本数据DataFrame
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            包含错误信息的匹配结果列表
        """
        logger.error("关键词分析失败：无法加载语义模型或处理分析")
        
        # 返回单条错误信息记录
        return [{
            'keyword': '错误',
            'timestamp': '00:00:00',
            'text': '关键词分析失败。可能的原因：1) 语义模型加载失败；2) 内存不足；3) 文本编码过程出错。请尝试重新加载页面或联系管理员。',
            'score': 0.0,
            'is_error': True
        }]
    
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