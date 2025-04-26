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
from src.config.settings import VIDEO_ANALYSIS_DIR

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
            os.path.join('data', 'raw'),
            os.path.join('data', 'processed'),
            os.path.join('data', 'cache'),
            os.path.join(VIDEO_ANALYSIS_DIR, 'results'),
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
                logger.info(f"准备加载语义匹配模型: {self.model_name}")
                # 添加详细的设备信息
                import torch
                logger.info(f"PyTorch版本: {torch.__version__}")
                logger.info(f"CUDA是否可用: {torch.cuda.is_available()}")
                if torch.cuda.is_available():
                    logger.info(f"CUDA设备: {torch.cuda.get_device_name(0)}")
                
                logger.info("开始加载模型...")
                self.model = SentenceTransformer(self.model_name)
                logger.info("模型加载成功")
                
                # 测试模型是否工作正常
                logger.info("测试模型...")
                test_sentences = ["测试句子1", "测试句子2"]
                try:
                    embeddings = self.model.encode(test_sentences)
                    logger.info(f"模型测试成功，生成了embeddings，shape: {embeddings.shape}")
                except Exception as test_err:
                    logger.error(f"模型测试失败: {str(test_err)}")
                
            except Exception as e:
                logger.error(f"加载模型失败: {str(e)}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
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
                results["analysis_method"] = "备用TF-IDF匹配"
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
                results["analysis_method"] = "备用TF-IDF匹配"
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
            results["analysis_method"] = "语义相似度匹配"
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
            results["analysis_method"] = "备用TF-IDF匹配"
            
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
                results["analysis_method"] = "备用字符串匹配"
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
                results["analysis_method"] = "备用字符串匹配"
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
            results["analysis_method"] = "语义相似度匹配"
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
            results["analysis_method"] = "备用字符串匹配"
            
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
        备用维度匹配逻辑，当语义模型不可用时使用
        使用基于TF-IDF的文本相似度计算
        
        参数:
            video_data: 视频文本数据DataFrame
            dimensions: 维度结构
            threshold: 匹配阈值
            
        返回:
            匹配结果列表
        """
        logger.info("使用备用维度匹配方法(TF-IDF)...")
        
        try:
            level1_dims = dimensions.get('level1', [])
            if not level1_dims:
                logger.warning("维度列表为空，无法进行匹配")
                return []
            
            # 提取文本数据
            texts = video_data['text'].tolist()
            if not texts:
                logger.warning("文本数据为空，无法进行匹配")
                return []
            
            logger.info(f"处理 {len(texts)} 条文本和 {len(level1_dims)} 个维度")
            
            # 使用jieba分词预处理文本（对中文数据）
            processed_texts = []
            for text in texts:
                if isinstance(text, str):
                    # 使用jieba分词，并保留词语间的空格用于TF-IDF处理
                    words = jieba.cut(text)
                    processed_text = ' '.join(words)
                    processed_texts.append(processed_text)
                else:
                    processed_texts.append("")  # 对于非字符串文本，添加空字符串
            
            # 处理维度文本
            processed_dims = []
            for dim in level1_dims:
                words = jieba.cut(dim)
                processed_dim = ' '.join(words)
                processed_dims.append(processed_dim)
            
            # 创建TF-IDF向量化器并转换文本
            try:
                vectorizer = TfidfVectorizer(
                    min_df=1, 
                    max_features=5000, 
                    analyzer='word',
                    token_pattern=r'\S+',  # 匹配任何非空白字符，适合中文分词后的文本
                    max_df=0.95
                )
                
                # 合并所有文本进行向量化
                all_texts = processed_texts + processed_dims
                vectorizer.fit(all_texts)
                
                # 转换文本和维度为TF-IDF向量
                text_vectors = vectorizer.transform(processed_texts)
                dim_vectors = vectorizer.transform(processed_dims)
                
                logger.info(f"TF-IDF向量生成成功: 文本({text_vectors.shape})，维度({dim_vectors.shape})")
            except Exception as ve:
                logger.error(f"TF-IDF向量化失败: {str(ve)}")
                # 回退到简单的字符串匹配
                return self._simplest_fallback_matching(video_data, dimensions, threshold)
            
            # 计算相似度并生成匹配
            matches = []
            for i, row in video_data.iterrows():
                if i >= len(processed_texts) or not processed_texts[i]:
                    continue  # 跳过无效文本
                
                text = row.get('text', '')
                
                # 获取当前文本的TF-IDF向量
                text_vector = text_vectors[i]
                
                # 计算与一级维度的相似度
                for dim_idx, dim1 in enumerate(level1_dims):
                    # 获取维度向量
                    dim_vector = dim_vectors[dim_idx]
                    
                    # 计算余弦相似度
                    similarity = float((text_vector * dim_vector.T).toarray()[0][0]) if text_vector.nnz > 0 and dim_vector.nnz > 0 else 0.0
                    
                    # 如果相似度高于阈值，添加到匹配结果
                    if similarity >= threshold:
                        # 尝试匹配二级维度（简单实现，仅基于字符串匹配）
                        matched_dim2 = ""
                        max_dim2_similarity = 0.0
                        
                        level2_dims = dimensions.get('level2', {}).get(dim1, [])
                        if level2_dims:
                            for dim2 in level2_dims:
                                # 简单检查二级维度是否包含在文本中
                                if dim2 in text:
                                    matched_dim2 = dim2
                                    max_dim2_similarity = 0.8  # 固定值
                                    break
                        
                        # 使用最高的相似度作为分数
                        score = max(similarity, max_dim2_similarity)
                        
                        matches.append({
                            "dimension_level1": dim1,
                            "dimension_level2": matched_dim2,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": float(score)
                        })
            
            logger.info(f"备用匹配方法生成了 {len(matches)} 个匹配结果")
            return matches
            
        except Exception as e:
            logger.error(f"备用维度匹配出错: {str(e)}")
            logger.error(f"将使用最简单的回退方法")
            # 最后的回退方案 - 通常不应该到达这里
            return self._simplest_fallback_matching(video_data, dimensions, threshold)
        
    def _simplest_fallback_matching(self, video_data: pd.DataFrame, dimensions: Dict[str, Any], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        最简单的回退匹配方法，基于纯字符串包含关系
        仅在其他所有方法都失败时使用
        """
        logger.info("使用最简单的字符串匹配作为最终回退方法")
        matches = []
        level1_dims = dimensions.get('level1', [])
        
        for _, row in video_data.iterrows():
            text = row.get('text', '')
            if not isinstance(text, str) or not text:
                continue
            
            for dim1 in level1_dims:
                # 仅检查维度字符串是否在文本中
                if dim1 in text:
                    matched_dim2 = ""
                    
                    # 简单检查二级维度
                    level2_dims = dimensions.get('level2', {}).get(dim1, [])
                    for dim2 in level2_dims:
                        if dim2 in text:
                            matched_dim2 = dim2
                            break
                    
                    matches.append({
                        "dimension_level1": dim1,
                        "dimension_level2": matched_dim2,
                        "timestamp": row.get('timestamp', '00:00:00'),
                        "text": text,
                        "score": 0.75  # 固定分数
                    })
        
        logger.info(f"最简单的回退匹配方法生成了 {len(matches)} 个匹配")
        return matches
    
    def _fallback_keyword_matching(self, video_data: pd.DataFrame, keywords: List[str], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        关键词分析失败时的备用匹配方法，使用简单的字符串匹配
        
        参数:
            video_data: 视频文本数据DataFrame
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            匹配结果列表
        """
        logger.info("使用备用关键词匹配方法...")
        
        try:
            if not keywords:
                logger.warning("关键词列表为空，无法进行匹配")
                return []
            
            # 提取文本数据
            texts = []
            timestamps = []
            for _, row in video_data.iterrows():
                text = row.get('text', '')
                if isinstance(text, str) and text:
                    texts.append(text)
                    timestamps.append(row.get('timestamp', '00:00:00'))
            
            if not texts:
                logger.warning("文本数据为空，无法进行匹配")
                return []
            
            logger.info(f"处理 {len(texts)} 条文本和 {len(keywords)} 个关键词")
            
            # 简单的关键词匹配
            matches = []
            for i, text in enumerate(texts):
                timestamp = timestamps[i]
                
                for keyword in keywords:
                    # 检查关键词是否在文本中
                    if keyword in text:
                        # 计算简单的相似度分数 - 基于关键词在文本中的位置
                        # 越靠前分数越高
                        position = text.find(keyword) / max(1, len(text))
                        score = max(0.5, 1.0 - position)  # 确保分数至少是0.5
                        
                        matches.append({
                            "keyword": keyword,
                            "timestamp": timestamp,
                            "text": text,
                            "score": float(score)
                        })
            
            logger.info(f"备用关键词匹配方法生成了 {len(matches)} 个匹配结果")
            return matches
            
        except Exception as e:
            logger.error(f"备用关键词匹配出错: {str(e)}")
            
            # 最简单的回退方案，返回一些结果而不是错误信息
            simple_matches = []
            for _, row in video_data.iterrows():
                text = row.get('text', '')
                if not isinstance(text, str) or not text:
                    continue
                    
                for keyword in keywords:
                    if keyword in text:
                        simple_matches.append({
                            "keyword": keyword,
                            "timestamp": row.get('timestamp', '00:00:00'),
                            "text": text,
                            "score": 0.75  # 固定分数
                        })
                        
            logger.info(f"最简单的关键词匹配方法生成了 {len(simple_matches)} 个匹配")
            return simple_matches
    
    def save_analysis_results(self, results: Dict, output_file: Optional[str] = None) -> str:
        """
        保存分析结果到文件
        
        参数:
            results: 分析结果字典
            output_file: 输出文件路径，如果为None则自动生成
            
        返回:
            保存的文件路径
        """
        try:
            # 确定保存路径
            if output_file is None:
                # 获取分析类型和时间戳
                analysis_type = results.get('type', 'unknown')
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                
                # 确保目录存在
                output_dir = os.path.join(VIDEO_ANALYSIS_DIR, 'results')
                os.makedirs(output_dir, exist_ok=True)
                
                # 生成输出文件名
                output_file = os.path.join(output_dir, f"{analysis_type}_{timestamp}.json")
            
            # 保存结果
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"分析结果已保存到: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"保存分析结果失败: {str(e)}")
            return "" 