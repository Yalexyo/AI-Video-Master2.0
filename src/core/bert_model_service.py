#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BERT模型服务：提供基于Chinese-BERT-wwm的语义分析服务，特别适用于广告短视频
"""

import os
import logging
import numpy as np
import torch
from typing import List, Dict, Any, Tuple, Optional
from transformers import BertTokenizer, BertModel

# 配置日志
logger = logging.getLogger(__name__)

# 模型缓存目录
MODELS_DIR = os.path.join("data", "models", "bert")

class BertModelService:
    """基于Chinese-BERT-wwm的语义分析服务"""
    
    def __init__(self):
        """初始化BERT模型服务"""
        # 确保模型目录存在
        os.makedirs(MODELS_DIR, exist_ok=True)
        
        self.model_name = "hfl/chinese-bert-wwm-ext"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"使用设备: {self.device}")
        
        # 初始化模型和分词器
        try:
            self._initialize_model()
            self.use_bert = True
        except Exception as e:
            logger.error(f"加载BERT模型失败: {str(e)}")
            logger.info("将使用备用的jieba词向量方案")
            self._initialize_fallback()
            self.use_bert = False
    
    def _initialize_model(self):
        """初始化BERT模型和分词器"""
        try:
            # 使用本地模型路径
            local_model_path = os.path.join(MODELS_DIR, "chinese-bert-wwm-ext")
            logger.info(f"正在从本地加载BERT模型: {local_model_path}")
            
            if not os.path.exists(local_model_path):
                logger.error(f"本地模型路径不存在: {local_model_path}")
                raise FileNotFoundError(f"本地模型路径不存在: {local_model_path}")
                
            self.tokenizer = BertTokenizer.from_pretrained(local_model_path)
            self.model = BertModel.from_pretrained(local_model_path)
            self.model.to(self.device)
            self.model.eval()  # 设置为评估模式
            logger.info("BERT模型加载完成")
        except Exception as e:
            logger.error(f"加载BERT模型失败: {str(e)}")
            raise
    
    def _initialize_fallback(self):
        """初始化备用的jieba词向量方案"""
        import jieba
        import jieba.analyse
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        # 确保jieba数据加载
        jieba.initialize()
        
        # 初始化TF-IDF矢量器
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            tokenizer=lambda x: jieba.cut(x, cut_all=False),
            max_features=100
        )
        
        # 预编译常用词的词向量
        sample_texts = [
            "婴儿奶粉配方", "宝宝成长发育", "新生儿营养", "母乳喂养",
            "免疫力提升", "护理保养", "婴儿辅食", "哺乳期妈妈",
            "优质蛋白", "儿童营养", "宝宝健康", "育儿知识"
        ]
        
        # 拟合向量化器
        self.vectorizer.fit(sample_texts)
        logger.info("备用词向量方案初始化完成")
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        获取文本的嵌入向量
        
        参数:
            texts: 文本列表
            
        返回:
            文本嵌入向量数组
        """
        if self.use_bert:
            return self._get_bert_embeddings(texts)
        else:
            return self._get_fallback_embeddings(texts)
            
    def _get_bert_embeddings(self, texts: List[str]) -> np.ndarray:
        """使用BERT模型获取嵌入向量"""
        embeddings = []
        
        for text in texts:
            try:
                # 对文本进行编码
                inputs = self.tokenizer(
                    text, 
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding="max_length"
                )
                
                # 将输入移到适当的设备
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # 获取BERT输出
                with torch.no_grad():
                    outputs = self.model(**inputs)
                
                # 使用CLS token作为句子嵌入
                sentence_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                embeddings.append(sentence_embedding[0])
                
            except Exception as e:
                logger.error(f"获取文本嵌入失败: {str(e)}")
                # 返回零向量作为后备
                embeddings.append(np.zeros(self.model.config.hidden_size))
        
        return np.array(embeddings)
        
    def _get_fallback_embeddings(self, texts: List[str]) -> np.ndarray:
        """使用jieba+TF-IDF获取词向量"""
        try:
            # 转换成TF-IDF向量
            vectors = self.vectorizer.transform(texts).toarray()
            return vectors
        except Exception as e:
            logger.error(f"获取备用词向量失败: {str(e)}")
            # 生成随机向量作为备选
            return np.random.rand(len(texts), 100)
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的语义相似度
        
        参数:
            text1: 第一段文本
            text2: 第二段文本
            
        返回:
            相似度得分 (0-1之间)
        """
        # 获取嵌入向量
        embeddings = self.get_embeddings([text1, text2])
        
        # 计算余弦相似度
        similarity = self._cosine_similarity(embeddings[0], embeddings[1])
        
        return similarity
    
    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return np.dot(v1, v2) / (norm1 * norm2)
    
    def segment_ad_video(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        根据广告结构对视频字幕进行分段
        
        参数:
            subtitles: 字幕列表，包含时间戳和文本
            
        返回:
            分段后的语义段落列表
        """
        if not subtitles:
            logger.warning("没有字幕数据，无法进行分段")
            return []
            
        # 如果字幕太少，作为单个段落处理
        if len(subtitles) <= 3:
            logger.info("字幕数量太少，作为单个段落处理")
            return self._create_single_segment(subtitles)
            
        # 提取字幕文本
        texts = [item["text"] for item in subtitles]
        all_text = " ".join(texts)
        
        # 获取所有字幕的嵌入向量
        embeddings = self.get_embeddings(texts)
        
        # 段落边界标记
        boundaries = self._detect_ad_phase_boundaries(embeddings, texts)
        
        # 根据检测到的边界创建段落
        segments = self._create_segments_from_boundaries(subtitles, boundaries)
        
        # 输出日志
        logger.info(f"分段完成，共 {len(segments)} 个段落")
        for i, segment in enumerate(segments):
            logger.info(f"段落 {i+1}: {segment.get('phase', '未知')} - [{segment.get('start_time', 0):.2f}s-{segment.get('end_time', 0):.2f}s]")
        
        return segments
    
    def _detect_ad_phase_boundaries(self, embeddings: np.ndarray, texts: List[str]) -> List[int]:
        """
        检测广告视频的语义阶段边界（增强版，结合关键词）
        
        参数:
            embeddings: 字幕文本的嵌入向量
            texts: 字幕文本列表
            
        返回:
            段落边界索引列表
        """
        if len(texts) < 3: # 如果字幕少于3条，很难分成多个阶段
            return []

        # 广告核心意图关键词，用于辅助判断边界
        ad_phase_keywords = {
            "问题引入": ["为什么", "你是否", "有没有", "如何", "问题", "不好带", "勃弱期", "才知道"],
            "产品介绍": ["推出", "研发", "技术", "特点", "产品", "配方", "蕴醇", "低聚糖", "蛋白", "组合"],
            "效果展示": ["帮助", "改善", "提高", "增强", "保护", "效果", "提升", "自愈力", "准没错", "不用操心"],
            "促销信息": ["立即", "马上", "优惠", "限时", "折扣", "抢购", "专享", "福利", "码住", "库存", "零元", "新客", "是核"]
        }
        
        phase_order = ["问题引入", "产品介绍", "效果展示", "促销信息"]

        # 1. 计算相邻字幕的综合变化得分
        potential_boundaries_scores = []
        window_size = min(2, max(1, len(texts) // 4)) # 根据字幕总数调整窗口大小
        
        for i in range(1, len(texts)):
            # a) 语义变化得分
            semantic_change = 1 - self._cosine_similarity(embeddings[i-1], embeddings[i])
            
            # b) 关键词阶段变化得分
            keyword_change_score = 0
            text_before = " ".join(texts[max(0, i-window_size):i])
            text_after = " ".join(texts[i:min(len(texts), i+window_size)])
            
            phase_before = self._get_dominant_phase(text_before, ad_phase_keywords, phase_order)
            phase_after = self._get_dominant_phase(text_after, ad_phase_keywords, phase_order)
            
            # 如果检测到阶段跃迁，给予较高分数
            if phase_before and phase_after and phase_before != phase_after:
                 # 如果是按顺序的阶段变化，得分更高
                 try:
                     if phase_order.index(phase_after) > phase_order.index(phase_before):
                         keyword_change_score = 0.8 # 顺序变化得分高
                     else:
                         keyword_change_score = 0.4 # 非顺序变化得分低
                 except ValueError:
                      keyword_change_score = 0.2 # 出现未知阶段
            
            # c) 综合得分 (语义变化权重0.4, 关键词变化权重0.6)
            # 可以调整权重来侧重不同因素
            combined_score = 0.4 * semantic_change + 0.6 * keyword_change_score
            potential_boundaries_scores.append((i, combined_score))

        # 2. 根据综合得分选择边界
        potential_boundaries_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 3. 选择边界数量 - 根据字幕数量和视频长度调整
        # 短视频强制尝试分成3-4段
        if len(texts) <= 10:
            # 短视频尝试分成更多段落（3段→4个阶段）
            max_boundaries = 3  
        else:
            max_boundaries = min(3, len(texts) // 3)  # 确保每个段落至少有3条字幕
        
        logger.info(f"字幕数量: {len(texts)}, 目标边界数: {max_boundaries}")

        # 4. 过滤边界，确保最小段落长度和边界间距
        # 选择得分最高的 N*2 个候选点进行过滤
        potential_indices = [score[0] for score in potential_boundaries_scores[:max_boundaries * 2]]
        potential_indices.sort()

        final_boundaries = []
        last_boundary_idx = 0 # 从第一个字幕开始
        min_segment_len = max(1, len(texts) // (max_boundaries + 2)) # 动态调整最小段落长度
        
        logger.info(f"最小段落长度: {min_segment_len}, 潜在边界: {potential_indices}")

        for boundary_idx in potential_indices:
            # 检查与上一个边界的距离 和 段落长度
            if boundary_idx - last_boundary_idx >= min_segment_len:
                final_boundaries.append(boundary_idx)
                last_boundary_idx = boundary_idx
                # 如果已找到足够数量的边界，则停止
                if len(final_boundaries) >= max_boundaries:
                    break
        
        # 如果找到的边界数量不足，但字幕数量足够，可以强制添加边界
        if len(final_boundaries) < max_boundaries and len(texts) >= max_boundaries + 1:
            # 确保至少尝试添加一个边界
            remaining_boundaries = max_boundaries - len(final_boundaries)
            logger.info(f"边界数量不足，尝试添加 {remaining_boundaries} 个额外边界")
            
            # 计算等距分布的边界点
            total_segments = max_boundaries + 1  # 段落数 = 边界数 + 1
            segment_size = len(texts) // total_segments
            
            # 生成等距边界
            equidistant_boundaries = [segment_size * (i+1) for i in range(total_segments-1)]
            
            # 过滤掉已经添加过的边界点附近的点
            new_boundaries = []
            for b in equidistant_boundaries:
                # 检查是否与现有边界太近
                if all(abs(b - existing) >= min_segment_len for existing in final_boundaries):
                    new_boundaries.append(b)
                    
                    if len(new_boundaries) + len(final_boundaries) >= max_boundaries:
                        break
            
            # 添加新边界并排序
            final_boundaries.extend(new_boundaries[:remaining_boundaries])
            final_boundaries.sort()
        
        # 确保边界按顺序排列
        final_boundaries.sort()
        
        logger.info(f"检测到 {len(final_boundaries)} 个潜在边界: {final_boundaries}")
        
        return final_boundaries

    def _get_dominant_phase(self, text: str, phase_keywords: Dict[str, List[str]], phase_order: List[str]) -> Optional[str]:
        """判断文本主要属于哪个广告阶段"""
        scores = {phase: 0 for phase in phase_order}
        for phase, keywords in phase_keywords.items():
            for kw in keywords:
                if kw in text:
                    scores[phase] += 1
        
        # 找到得分最高的阶段
        max_score = 0
        dominant_phase = None
        for phase in phase_order: # 按预定顺序优先选择
             if scores[phase] > max_score:
                  max_score = scores[phase]
                  dominant_phase = phase
        
        return dominant_phase if max_score > 0 else None

    def _create_segments_from_boundaries(self, subtitles: List[Dict[str, Any]], boundaries: List[int]) -> List[Dict[str, Any]]:
        """
        根据检测到的边界创建视频段落，并根据内容分析调整阶段
        
        参数:
            subtitles: 字幕列表
            boundaries: 边界索引列表
            
        返回:
            分段后的段落列表
        """
        if not boundaries:
            return self._create_single_segment(subtitles)
            
        segments = []
        start_idx = 0
        
        # 组合成广告阶段
        ad_phases = ["问题引入", "产品介绍", "效果展示", "促销信息"]
        phase_idx = 0
        
        # 遍历边界创建段落
        for end_idx in boundaries:
            phase_name = ad_phases[phase_idx] if phase_idx < len(ad_phases) else f"段落{phase_idx+1}"
            phase_idx += 1
            
            # 创建段落
            segment = self._create_segment_from_subtitles(
                subtitles[start_idx:end_idx],
                phase_name
            )
            segments.append(segment)
            start_idx = end_idx
        
        # 添加最后一个段落
        if start_idx < len(subtitles):
            phase_name = ad_phases[phase_idx] if phase_idx < len(ad_phases) else f"段落{phase_idx+1}"
            segment = self._create_segment_from_subtitles(
                subtitles[start_idx:],
                phase_name
            )
            segments.append(segment)

        # 1. 尝试对长段落进行二次分割
        self._refine_segments(segments, subtitles)
        
        # 2. 分析每个段落内容并校准阶段名称
        for segment in segments:
            # 分析内容
            content_analysis = self.analyze_ad_content(segment["text"])
            segment.update(content_analysis)
            
            # 如果检测到的意图与阶段名称不一致，考虑调整阶段名称
            detected_intent = content_analysis.get("primary_intent")
            if detected_intent in ad_phases and detected_intent != segment["phase"] and detected_intent != "一般内容":
                logger.info(f"调整段落阶段: 从 {segment['phase']} 更改为 {detected_intent}")
                segment["phase"] = detected_intent
        
        return segments
        
    def _refine_segments(self, segments: List[Dict[str, Any]], all_subtitles: List[Dict[str, Any]]) -> None:
        """
        进一步细化分段，特别是针对长段落
        
        参数:
            segments: 初步分段后的段落列表
            all_subtitles: 所有字幕列表
        """
        # 如果已经分成了4段或以上，不做进一步处理
        if len(segments) >= 4:
            logger.info("已有4个或更多段落，不需要进一步分割")
            return
            
        # 分析现有段落覆盖情况
        phases = ["问题引入", "产品介绍", "效果展示", "促销信息"]
        existing_phases = [segment["phase"] for segment in segments]
        
        # 获取缺失的阶段
        missing_phases = [phase for phase in phases if phase not in existing_phases]
        logger.info(f"现有段落: {existing_phases}, 缺失的阶段: {missing_phases}")
        
        # 如果缺少某些阶段，尝试从现有段落中拆分
        if missing_phases:
            # 针对特殊情况的处理
            custom_splits = {
                # 如果有宝宝和保护力薄弱期的内容，属于问题引入
                "问题引入": lambda text: "宝宝" in text and "保护力勃弱期" in text,
                # 如果有低聚糖、组合等词，属于产品介绍
                "产品介绍": lambda text: any(kw in text for kw in ["低聚糖", "蛋白", "组合", "蕴醇里面有"]),
                # 如果有提升自愈力等词，属于效果展示
                "效果展示": lambda text: any(kw in text for kw in ["自愈力", "准没错", "不用操心"]),
                # 如果有限时、专享等词，属于促销信息
                "促销信息": lambda text: any(kw in text for kw in ["限时", "专享", "零元", "福利"])
            }
            
            # 根据内容特征找出可以细分的段落
            for i, segment in enumerate(segments):
                segment_text = segment["text"]
                
                # 检查段落是否可以细分为多个阶段
                possible_phases = []
                for phase in missing_phases:
                    if phase in custom_splits and custom_splits[phase](segment_text):
                        possible_phases.append(phase)
                
                if possible_phases:
                    logger.info(f"在段落{i+1}({segment['phase']})中检测到可能的阶段: {possible_phases}")
                    
                    # 处理特殊情况：拆分长段落
                    subtitles = segment["subtitles"]
                    if len(subtitles) >= 2:
                        # 直接找出包含特征的字幕，作为边界点
                        split_points = []
                        for j, subtitle in enumerate(subtitles[:-1]):  # 排除最后一个字幕
                            subtitle_text = subtitle["text"]
                            # 检查是否包含某个阶段的特征
                            for phase in possible_phases:
                                if phase in custom_splits and custom_splits[phase](subtitle_text):
                                    logger.info(f"在字幕{j+1}中发现{phase}特征: {subtitle_text[:20]}...")
                                    split_points.append((j+1, phase))
                        
                        if split_points:
                            # 按字幕索引排序
                            split_points.sort(key=lambda x: x[0])
                            
                            # 获取分割点
                            split_idx, next_phase = split_points[0]
                            
                            # 获取原始段落在所有字幕中的索引范围
                            segment_start_idx = all_subtitles.index(subtitles[0])
                            
                            # 创建两个新段落
                            first_half = self._create_segment_from_subtitles(
                                subtitles[:split_idx],
                                segment["phase"]  # 保持原始阶段
                            )
                            
                            second_half = self._create_segment_from_subtitles(
                                subtitles[split_idx:],
                                next_phase  # 使用检测到的新阶段
                            )
                            
                            # 分析内容并调整阶段
                            first_content = self.analyze_ad_content(first_half["text"])
                            second_content = self.analyze_ad_content(second_half["text"])
                            
                            first_half.update(first_content)
                            second_half.update(second_content)
                            
                            # 用两个新段落替换原来的长段落
                            segments[i] = first_half
                            segments.insert(i+1, second_half)
                            
                            logger.info(f"成功拆分段落: {segment['phase']}({first_half['primary_intent']}) + {next_phase}({second_half['primary_intent']})")
                            return  # 一次只拆分一个段落，避免复杂化
        
        # 标准的长段落分割处理（如果没有特殊规则触发）
        if len(segments) < 4:
            # 找到最长的段落进行细分
            longest_segment_idx = max(range(len(segments)), key=lambda i: segments[i]["duration"])
            longest_segment = segments[longest_segment_idx]
            
            # 只有当段落超过一定长度且有多个字幕时才分割
            if longest_segment["duration"] < 2.0 or len(longest_segment["subtitles"]) <= 1:
                return
            
            # 分析该段落中的字幕
            subtitles = longest_segment["subtitles"]
            
            # 找到最佳分割点
            best_split_idx = self._find_best_split_point(subtitles)
            if best_split_idx == 0:
                return  # 无法找到合适的分割点
            
            # 获取原始段落在所有字幕中的索引范围
            segment_start_idx = all_subtitles.index(subtitles[0])
            
            # 创建新段落
            first_half = self._create_segment_from_subtitles(
                subtitles[:best_split_idx],
                longest_segment["phase"]
            )
            
            # 为第二部分选择适当的阶段名称（根据广告流程顺序）
            phases = ["问题引入", "产品介绍", "效果展示", "促销信息"]
            current_phase_idx = phases.index(longest_segment["phase"]) if longest_segment["phase"] in phases else 0
            next_phase_idx = min(current_phase_idx + 1, len(phases) - 1)
            next_phase = phases[next_phase_idx]
            
            second_half = self._create_segment_from_subtitles(
                subtitles[best_split_idx:],
                next_phase
            )
            
            # 分析内容
            first_content = self.analyze_ad_content(first_half["text"])
            second_content = self.analyze_ad_content(second_half["text"])
            
            first_half.update(first_content)
            second_half.update(second_content)
            
            # 用两个新段落替换原来的长段落
            segments[longest_segment_idx] = first_half
            segments.insert(longest_segment_idx + 1, second_half)
            
            logger.info(f"细分长段落: {longest_segment['phase']} → {first_half['phase']} + {second_half['phase']}")
    
    def _find_best_split_point(self, subtitles: List[Dict[str, Any]]) -> int:
        """
        在一组字幕中找到最佳分割点
        
        参数:
            subtitles: 字幕列表
            
        返回:
            最佳分割点索引
        """
        if len(subtitles) <= 2:
            return 0  # 字幕太少，不分割
        
        # 提取字幕文本
        texts = [s["text"] for s in subtitles]
        all_text = " ".join(texts)
        
        # 广告意图关键词
        intent_keywords = {
            "问题引入": ["为什么", "你是否", "有没有", "如何", "问题", "不好带", "勃弱期", "才知道"],
            "产品介绍": ["推出", "研发", "技术", "特点", "产品", "配方", "蕴醇", "低聚糖", "蛋白", "组合"],
            "效果展示": ["帮助", "改善", "提高", "增强", "保护", "效果", "提升", "自愈力", "准没错", "不用操心"],
            "促销信息": ["立即", "马上", "优惠", "限时", "折扣", "抢购", "专享", "福利", "码住", "库存"]
        }
        
        # 如果字幕较多，优先考虑中间位置
        if len(subtitles) >= 4:
            mid_point = len(subtitles) // 2
            return mid_point
        
        # 对于3个字幕的情况，分析第2个字幕是否包含明显的阶段转换关键词
        if len(subtitles) == 3:
            middle_text = texts[1]
            for intent, keywords in intent_keywords.items():
                if any(kw in middle_text for kw in keywords):
                    return 1  # 以第1个和第2个字幕之间为分割点
            
            # 默认在第2个和第3个字幕之间分割
            return 2
            
        # 默认不分割
        return 0

    def _create_single_segment(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """创建单个段落"""
        if not subtitles:
            return []
            
        return [self._create_segment_from_subtitles(subtitles, "广告内容")]
    
    def _create_segment_from_subtitles(self, subtitles: List[Dict[str, Any]], phase_name: str) -> Dict[str, Any]:
        """从字幕创建段落"""
        if not subtitles:
            return {}
            
        # 提取时间和文本
        # 兼容不同的字段名称
        if "start" in subtitles[0]:
            start_time = subtitles[0]["start"]
        elif "start_time" in subtitles[0]:
            start_time = subtitles[0]["start_time"]
        elif "begin_time" in subtitles[0]:
            start_time = subtitles[0]["begin_time"]
        else:
            logger.warning(f"字幕没有包含开始时间字段，使用0作为默认值")
            start_time = 0
            
        if "end" in subtitles[-1]:
            end_time = subtitles[-1]["end"]
        elif "end_time" in subtitles[-1]:
            end_time = subtitles[-1]["end_time"]
        else:
            logger.warning(f"字幕没有包含结束时间字段，使用近似值")
            end_time = start_time + 1000  # 默认假设1秒
        
        text = " ".join([s["text"] for s in subtitles])
        
        # 创建段落
        segment = {
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
            "duration": end_time - start_time,
            "phase": phase_name,
            "subtitles": subtitles
        }
        
        return segment
    
    def analyze_ad_content(self, segment_text: str) -> Dict[str, Any]:
        """
        分析广告段落内容，提取关键词和意图
        
        参数:
            segment_text: 段落文本
            
        返回:
            分析结果字典
        """
        # 1. 基于规则的意图分析
        # 广告核心意图模板
        ad_intents = {
            "问题引入": ["为什么", "你是否", "有没有", "如何", "问题", "不好带", "勃弱期", "才知道", "六月龄"],
            "产品介绍": ["推出", "研发", "技术", "特点", "产品", "配方", "蕴醇", "低聚糖", "蛋白", "组合", "里面有"],
            "效果展示": ["帮助", "改善", "提高", "增强", "保护", "效果", "提升", "自愈力", "准没错", "不用操心", "好处"],
            "促销信息": ["立即", "马上", "优惠", "限时", "折扣", "抢购", "专享", "福利", "码住", "库存", "零元", "新客", "是核"]
        }
        
        # 2. 关键词匹配分析
        intent_scores = {}
        for intent, keywords in ad_intents.items():
            score = sum([1 for kw in keywords if kw in segment_text])
            intent_scores[intent] = score
        
        # 基于关键词的初步判断
        initial_intent = "一般内容"
        max_score = 0
        for intent, score in intent_scores.items():
            if score > max_score:
                max_score = score
                initial_intent = intent
        
        # 3. 尝试使用LLM进行更精确的分类 (异步函数中无法同步调用)
        # 但我们可以设置一些明确的模式匹配来改进分类
        
        # 特殊情况处理 - 根据用户提供的专业知识进行调整
        product_patterns = ["蕴醇里面有", "低聚糖", "活性蛋白", "组合"]
        problem_patterns = ["不好带", "问了主任才知道", "保护力勃弱期"]
        effect_patterns = ["提升自愈力", "准没错", "不用操心"]
        promotion_patterns = ["限时", "专享", "零元", "福利", "新客", "是核", "给到新客"]
        
        # 针对性调整
        if any(pattern in segment_text for pattern in problem_patterns) and "勃弱期" in segment_text:
            logger.info(f"应用专家规则：文本'{segment_text[:20]}...'包含问题引入模式")
            refined_intent = "问题引入"
        elif any(pattern in segment_text for pattern in product_patterns) and ("低聚糖" in segment_text or "蛋白" in segment_text):
            logger.info(f"应用专家规则：文本'{segment_text[:20]}...'包含产品介绍模式")
            refined_intent = "产品介绍"
        elif any(pattern in segment_text for pattern in effect_patterns) and ("自愈力" in segment_text or "准没错" in segment_text):
            logger.info(f"应用专家规则：文本'{segment_text[:20]}...'包含效果展示模式")
            refined_intent = "效果展示"
        elif any(pattern in segment_text for pattern in promotion_patterns) and any(kw in segment_text for kw in ["专享", "限时", "零元", "福利"]):
            logger.info(f"应用专家规则：文本'{segment_text[:20]}...'包含促销信息模式")
            refined_intent = "促销信息"
        else:
            # 如果没有匹配到专家规则，使用关键词匹配结果
            refined_intent = initial_intent
        
        # 特殊情况：明确的促销描述
        if "限时给到新客专享零元" in segment_text or ("限时" in segment_text and "专享" in segment_text):
            logger.info(f"明确的促销描述检测：'{segment_text[:30]}...'")
            refined_intent = "促销信息"
        
        # 提取可能的品牌词和产品名
        brand_keywords = self._extract_potential_brands(segment_text)
        
        return {
            "primary_intent": refined_intent,
            "intent_scores": intent_scores,
            "brand_keywords": brand_keywords,
            "is_promotional": "产品" in segment_text or "品牌" in segment_text or len(brand_keywords) > 0
        }
    
    def _extract_potential_brands(self, text: str) -> List[str]:
        """提取文本中可能的品牌词"""
        # 这里简化处理，实际项目中应该使用更复杂的品牌词提取算法
        # 或者与现有的热词列表集成
        brand_words = []
        
        # 简单示例：寻找大写开头单词或特殊符号包围的词
        # 实际使用中，这部分需要更复杂的NER模型或与热词表集成
        
        return brand_words 