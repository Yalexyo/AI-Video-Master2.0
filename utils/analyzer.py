import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

# 设置所有离线模式环境变量，彻底阻止任何外部连接
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from sentence_transformers import SentenceTransformer, util
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
        self.model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
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
    
    def _check_model_cache(self, cache_dir):
        """
        检查本地模型缓存是否存在
        
        参数:
            cache_dir: 缓存目录
            
        返回:
            布尔值，表示模型文件是否存在
        """
        # 检查目录是否存在
        if not os.path.exists(cache_dir):
            logger.warning(f"模型缓存目录不存在: {cache_dir}")
            return False
            
        # HuggingFace缓存目录结构
        # 模型名称格式化：用--替换/
        formatted_model_name = self.model_name.replace('/', '--')
        # 缓存目录路径
        cache_path = os.path.join(cache_dir, f"models--{formatted_model_name}")
        
        if not os.path.exists(cache_path):
            logger.warning(f"模型缓存目录不存在: {cache_path}")
            return False
            
        # 检查snapshots目录
        snapshots_dir = os.path.join(cache_path, "snapshots")
        if not os.path.exists(snapshots_dir):
            logger.warning(f"模型快照目录不存在: {snapshots_dir}")
            return False
            
        # 查找快照目录中的第一个子目录
        snapshot_dirs = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
        if not snapshot_dirs:
            logger.warning(f"模型快照子目录不存在")
            return False
            
        # 使用第一个快照目录
        snapshot_dir = os.path.join(snapshots_dir, snapshot_dirs[0])
        logger.info(f"找到模型快照目录: {snapshot_dir}")
        
        # 检查关键文件是否存在
        required_files = ["modules.json", "config.json"]
        for file in required_files:
            if not os.path.exists(os.path.join(snapshot_dir, file)):
                logger.warning(f"关键模型文件不存在: {file}")
                return False
                
        # 检查是否有model.safetensors或model.bin文件
        if not (os.path.exists(os.path.join(snapshot_dir, "model.safetensors")) or 
                os.path.exists(os.path.join(snapshot_dir, "pytorch_model.bin"))):
            logger.warning("模型权重文件不存在")
            return False
                
        logger.info(f"本地模型缓存校验成功")
        return True
    
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
                
                # 设置模型缓存目录
                cache_dir = os.path.join('data', 'models', 'sentence_transformers')
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"使用模型缓存目录: {cache_dir}")
                
                # 检查本地模型缓存
                cache_valid = self._check_model_cache(cache_dir)
                if not cache_valid:
                    logger.error(f"本地模型文件不存在或不完整，请先运行脚本下载模型: python scripts/download_models.py")
                    logger.error(f"如果网络环境不佳，请手动下载模型文件并放置在正确的目录结构中")
                    return None
                
                # 设置离线模式 (已在文件顶部设置)
                logger.info(f"使用离线模式加载模型: TRANSFORMERS_OFFLINE={os.environ.get('TRANSFORMERS_OFFLINE', '未设置')}")
                
                logger.info("开始加载模型...")
                self.model = SentenceTransformer(self.model_name, cache_folder=cache_dir)
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
                logger.error("\n解决方案:")
                logger.error("1. 运行脚本下载模型: python scripts/download_models.py")
                logger.error("2. 如果网络环境不佳，手动下载模型并放置在正确的目录")
                logger.error("3. 检查Python环境是否正确安装了sentence-transformers库")
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
            
            # 如果模型加载失败，直接返回空结果
            if model is None:
                logger.error("模型加载失败，无法执行维度分析")
                results["error"] = "模型加载失败，请确保已正确安装sentence-transformers库并下载模型"
                results["analysis_method"] = "未执行分析"
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
                results["error"] = f"编码文本时出错: {str(e)}"
                results["analysis_method"] = "未执行分析"
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
                "matches": [],
                "analysis_method": "分析失败"
            }
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
            
            # 如果模型加载失败，直接返回空结果
            if model is None:
                logger.error("模型加载失败，无法执行关键词分析")
                results["error"] = "模型加载失败，请确保已正确安装sentence-transformers库并下载模型"
                results["analysis_method"] = "未执行分析"
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
                
            except Exception as e:
                logger.error(f"编码文本时出错: {str(e)}")
                results["error"] = f"编码文本时出错: {str(e)}"
                results["analysis_method"] = "未执行分析"
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
                
            
            logger.info(f"关键词分析完成，匹配 {len(results['matches'])} 条记录")
            results["analysis_method"] = "语义相似度匹配"
            return results
        
        except Exception as e:
            logger.error(f"关键词分析出错: {str(e)}")
            results = {
                "type": "关键词分析", 
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "error": str(e), 
                "matches": [],
                "analysis_method": "分析失败"
            }
            return results
    
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