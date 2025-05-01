import os
import json
import logging
import asyncio
import uuid
import subprocess
import shutil
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import re
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeAudioClip, AudioFileClip

# 导入项目其他组件
from utils.processor import VideoProcessor
from src.api.llm_service import LLMService

# 配置日志
logger = logging.getLogger(__name__)

class MagicVideoService:
    """魔法视频服务，负责视频分析、语义分段、视频匹配和合成"""
    
    def __init__(self, max_concurrent_tasks: int = 3):
        """
        初始化魔法视频服务
        
        参数:
            max_concurrent_tasks: 最大并行任务数
        """
        self.processor = VideoProcessor()
        self.llm_service = LLMService(provider="deepseek")
        self.max_concurrent_tasks = max_concurrent_tasks
        self.embedder = None  # 懒加载Sentence Transformer模型
        
        # 创建必要的目录
        self._ensure_directories()
        
        logger.info("魔法视频服务初始化完成")
    
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        dirs = [
            os.path.join('data', 'processed', 'analysis', 'results'),
            os.path.join('data', 'processed', 'subtitles'),
            os.path.join('data', 'output', 'segments'),
            os.path.join('data', 'output', 'videos'),
            os.path.join('data', 'temp', 'videos'),
            os.path.join('data', 'temp', 'audio')
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"创建目录: {dir_path}")
    
    def _get_sentence_transformer(self):
        """懒加载Sentence Transformer模型"""
        if self.embedder is None:
            # 使用多语言模型，支持中英文
            model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            cache_folder = os.path.join('data', 'models', 'sentence_transformers')
            
            logger.info(f"加载Sentence Transformer模型: {model_name}")
            self.embedder = SentenceTransformer(model_name, cache_folder=cache_folder)
            logger.info("Sentence Transformer模型加载完成")
        
        return self.embedder
    
    async def process_demo_video(self, video_path: str, vocabulary_id: str = None) -> Dict[str, Any]:
        """
        处理Demo视频：提取字幕，进行语义分段，并生成阶段标签
        
        参数:
            video_path: Demo视频文件路径
            vocabulary_id: 热词表ID（可选）
            
        返回:
            包含分段结果的字典
        """
        logger.info(f"开始处理Demo视频: {video_path}")
        result = {
            "video_path": video_path,
            "stages": [],
            "error": None
        }
        
        try:
            # 1. 提取字幕
            audio_file = self.processor._preprocess_video_file(video_path)
            if not audio_file:
                raise ValueError(f"无法提取音频: {video_path}")
                
            subtitles = self.processor._extract_subtitles_from_video(audio_file, vocabulary_id)
            if not subtitles:
                raise ValueError(f"无法提取字幕: {video_path}")
                
            # 将字幕数据转换为DataFrame
            subtitle_df = pd.DataFrame([{
                'timestamp': item.get('start_formatted', '00:00:00'),
                'text': item.get('text', ''),
                'start_time': item.get('start', 0),
                'end_time': item.get('end', 0)
            } for item in subtitles if item.get('text')])
            
            if subtitle_df.empty:
                raise ValueError("提取的字幕为空")
            
            # 保存字幕数据
            subtitles_json_path = os.path.join('data', 'processed', 'subtitles', f"{os.path.basename(video_path)}_subtitles.json")
            subtitle_df.to_json(subtitles_json_path, orient='records', force_ascii=False, indent=2)
            
            # 2. 进行语义分段
            segments = await self._segment_subtitles_semantic(subtitle_df)
            if not segments:
                raise ValueError("语义分段失败，未能识别有效段落")
            
            # 3. 为每个段落生成标签
            labeled_segments = await self._generate_segment_labels(segments)
            
            # 4. 保存分段结果
            result["stages"] = labeled_segments
            segments_json_path = os.path.join('data', 'processed', 'analysis', 'results', f"{os.path.basename(video_path)}_segments.json")
            with open(segments_json_path, 'w', encoding='utf-8') as f:
                json.dump(labeled_segments, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Demo视频处理完成，共识别 {len(labeled_segments)} 个语义段落")
            return result
            
        except Exception as e:
            logger.exception(f"处理Demo视频时出错: {str(e)}")
            result["error"] = str(e)
            return result
    
    async def _segment_subtitles_semantic(self, subtitle_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        使用语义相似度对字幕进行分段
        
        参数:
            subtitle_df: 字幕DataFrame，包含timestamp、text、start_time和end_time列
            
        返回:
            包含分段信息的字典列表
        """
        logger.info("开始进行字幕语义分段")
        
        try:
            # 1. 确保DataFrame非空且包含所需列
            if subtitle_df.empty or not all(col in subtitle_df.columns for col in ['text', 'start_time', 'end_time']):
                logger.error("字幕数据无效或缺少必要字段")
                return []
            
            # 2. 按时序分组为基本句子组（通常基于标点或语义自然分割）
            # 这里我们使用一个简单的方法：将连续的几条字幕合并为一个基本语句
            basic_sentences = []
            current_group = []
            
            for _, row in subtitle_df.iterrows():
                current_group.append(row)
                
                # 如果当前句子以句号、问号或感叹号结束，或者已经累积了5条字幕，则将当前组合并为一个基本句子
                if (row['text'].endswith(('.', '?', '!', '。', '？', '！')) or 
                    len(current_group) >= 5):
                    
                    if current_group:
                        combined_text = ' '.join([r['text'] for r in current_group])
                        start_time = current_group[0]['start_time']
                        end_time = current_group[-1]['end_time']
                        start_timestamp = current_group[0]['timestamp']
                        end_timestamp = subtitle_df.loc[subtitle_df['end_time'] >= end_time, 'timestamp'].iloc[0] if not pd.isna(end_time) else start_timestamp
                        
                        basic_sentences.append({
                            'text': combined_text,
                            'start_time': start_time,
                            'end_time': end_time,
                            'start_timestamp': start_timestamp,
                            'end_timestamp': end_timestamp
                        })
                        current_group = []
            
            # 处理剩余的分组
            if current_group:
                combined_text = ' '.join([r['text'] for r in current_group])
                start_time = current_group[0]['start_time']
                end_time = current_group[-1]['end_time']
                start_timestamp = current_group[0]['timestamp']
                end_timestamp = subtitle_df.loc[subtitle_df['end_time'] >= end_time, 'timestamp'].iloc[0] if not pd.isna(end_time) else start_timestamp
                
                basic_sentences.append({
                    'text': combined_text,
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_timestamp': start_timestamp,
                    'end_timestamp': end_timestamp
                })
            
            logger.info(f"基本句子分组完成，共 {len(basic_sentences)} 个基本句子")
            
            # 3. 对每个基本句子计算嵌入向量
            embedder = self._get_sentence_transformer()
            sentence_texts = [s['text'] for s in basic_sentences]
            embeddings = embedder.encode(sentence_texts, show_progress_bar=True)
            
            # 4. 使用滑动窗口计算语义连贯性，找到分段点
            window_size = 5  # 滑动窗口大小
            similarity_changes = []
            
            for i in range(len(embeddings) - window_size):
                # 计算窗口内所有句子对的平均相似度
                current_window_embeddings = embeddings[i:i+window_size]
                next_window_embeddings = embeddings[i+1:i+window_size+1]
                
                # 计算窗口整体的相似度变化
                current_centroid = np.mean(current_window_embeddings, axis=0)
                next_centroid = np.mean(next_window_embeddings, axis=0)
                
                # 计算余弦相似度
                similarity = np.dot(current_centroid, next_centroid) / (np.linalg.norm(current_centroid) * np.linalg.norm(next_centroid))
                similarity_change = 1 - similarity  # 变化率，值越大表示语义变化越大
                
                similarity_changes.append({
                    'index': i,
                    'change': similarity_change
                })
            
            # 5. 根据相似度变化率找到分段点
            # 排序并取变化率最大的点作为分段点，但分段点之间至少间隔window_size个句子
            if not similarity_changes:
                logger.warning("无法计算相似度变化率，句子数量可能不足")
                # 如果句子数量不足以分段，则整个内容作为一个段落
                segments = [{
                    'start_time': basic_sentences[0]['start_time'],
                    'end_time': basic_sentences[-1]['end_time'],
                    'start_timestamp': basic_sentences[0]['start_timestamp'],
                    'end_timestamp': basic_sentences[-1]['end_timestamp'],
                    'sentences': basic_sentences
                }]
            else:
                # 按变化率排序
                sorted_changes = sorted(similarity_changes, key=lambda x: x['change'], reverse=True)
                
                # 确定分段数，这里使用一个简单的启发式方法
                n_segments = max(2, min(5, len(basic_sentences) // 15))  # 根据句子数量决定段落数，至少2个段落，最多5个
                
                # 获取前n_segments-1个分段点（因为有n段需要n-1个分段点）
                segment_points = [x['index'] for x in sorted_changes[:n_segments-1]]
                segment_points.sort()  # 按索引顺序排序
                
                # 构建段落
                segments = []
                start_idx = 0
                
                for point in segment_points:
                    # 分段点对应的句子索引
                    end_idx = point + window_size // 2  # 在滑动窗口中间位置分段
                    
                    # 确保不越界
                    end_idx = min(end_idx, len(basic_sentences) - 1)
                    
                    # 构建段落
                    segment = {
                        'start_time': basic_sentences[start_idx]['start_time'],
                        'end_time': basic_sentences[end_idx]['end_time'],
                        'start_timestamp': basic_sentences[start_idx]['start_timestamp'],
                        'end_timestamp': basic_sentences[end_idx]['end_timestamp'],
                        'sentences': basic_sentences[start_idx:end_idx+1]
                    }
                    segments.append(segment)
                    
                    # 更新起始索引
                    start_idx = end_idx + 1
                
                # 添加最后一个段落
                if start_idx < len(basic_sentences):
                    segment = {
                        'start_time': basic_sentences[start_idx]['start_time'],
                        'end_time': basic_sentences[-1]['end_time'],
                        'start_timestamp': basic_sentences[start_idx]['start_timestamp'],
                        'end_timestamp': basic_sentences[-1]['end_timestamp'],
                        'sentences': basic_sentences[start_idx:]
                    }
                    segments.append(segment)
            
            logger.info(f"语义分段完成，共 {len(segments)} 个段落")
            
            # 计算每个段落的文本内容
            for segment in segments:
                segment_texts = [s['text'] for s in segment['sentences']]
                segment['text'] = ' '.join(segment_texts)
            
            return segments
            
        except Exception as e:
            logger.exception(f"进行语义分段时出错: {str(e)}")
            return []
    
    async def _generate_segment_labels(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        为每个段落生成标签
        
        参数:
            segments: 分段信息的字典列表
            
        返回:
            添加了标签的分段信息字典列表
        """
        logger.info("开始为段落生成标签")
        
        try:
            labeled_segments = []
            
            for i, segment in enumerate(segments):
                # 构建用于生成标签的提示词
                prompt = f"""
分析以下文本段落，提取其核心主题并生成一个简短的标签。标签应当能够概括该段落的主要内容。

文本段落:
{segment['text']}

请按照以下格式输出:
{{
  "label": "简短的主题标签",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}

标签应控制在5个字以内，关键词应从文本中提取，最多提供3个关键词。
                """
                
                # 调用LLM生成标签
                llm_response = None
                if self.llm_service.provider == "deepseek":
                    llm_response = await self.llm_service._call_deepseek_api(prompt)
                elif self.llm_service.provider == "openrouter":
                    llm_response = await self.llm_service._call_openrouter_api(prompt)
                
                # 解析LLM响应
                label = f"阶段{i+1}"  # 默认标签
                keywords = []
                
                if llm_response:
                    try:
                        # 提取JSON部分
                        json_match = re.search(r'(\{[\s\S]*\})', llm_response)
                        if json_match:
                            json_str = json_match.group(1)
                            label_data = json.loads(json_str)
                            
                            if "label" in label_data:
                                label = label_data["label"]
                            if "keywords" in label_data and isinstance(label_data["keywords"], list):
                                keywords = label_data["keywords"]
                    except Exception as e:
                        logger.warning(f"解析LLM响应时出错: {str(e)}")
                
                # 构建标记后的段落信息
                labeled_segment = {
                    'stage': i + 1,
                    'start': segment['start_time'],
                    'end': segment['end_time'],
                    'start_timestamp': segment['start_timestamp'],
                    'end_timestamp': segment['end_timestamp'],
                    'label': label,
                    'keywords': keywords,
                    'text': segment['text']
                }
                
                labeled_segments.append(labeled_segment)
            
            logger.info(f"段落标签生成完成，共 {len(labeled_segments)} 个标记段落")
            return labeled_segments
            
        except Exception as e:
            logger.exception(f"生成段落标签时出错: {str(e)}")
            # 返回原始段落，添加默认标签
            return [{'stage': i + 1, 'start': s['start_time'], 'end': s['end_time'], 
                     'start_timestamp': s['start_timestamp'], 'end_timestamp': s['end_timestamp'],
                     'label': f"阶段{i+1}", 'keywords': [], 'text': s['text']} 
                    for i, s in enumerate(segments)]

    async def process_candidate_videos(self, video_paths: List[str], vocabulary_id: str = None) -> Dict[str, pd.DataFrame]:
        """
        批量处理候选视频：提取字幕
        
        参数:
            video_paths: 候选视频文件路径列表
            vocabulary_id: 热词表ID（可选）
            
        返回:
            视频ID到字幕DataFrame的映射
        """
        logger.info(f"开始处理 {len(video_paths)} 个候选视频")
        results = {}
        
        # 创建处理任务
        tasks = []
        for video_path in video_paths:
            tasks.append(self._process_single_candidate(video_path, vocabulary_id))
            
        # 使用信号量控制并发数量
        sem = asyncio.Semaphore(self.max_concurrent_tasks)
        
        async def bounded_process(task):
            async with sem:
                return await task
        
        # 并行执行所有任务
        bounded_tasks = [bounded_process(task) for task in tasks]
        processed_results = await asyncio.gather(*bounded_tasks)
        
        # 整理结果
        for video_id, subtitle_df in processed_results:
            if subtitle_df is not None and not subtitle_df.empty:
                results[video_id] = subtitle_df
        
        logger.info(f"候选视频处理完成，成功处理 {len(results)} 个视频")
        return results
    
    async def _process_single_candidate(self, video_path: str, vocabulary_id: str = None) -> Tuple[str, Optional[pd.DataFrame]]:
        """处理单个候选视频"""
        video_id = os.path.basename(video_path)
        logger.info(f"处理候选视频: {video_id}")
        
        try:
            # 提取音频
            audio_file = self.processor._preprocess_video_file(video_path)
            if not audio_file:
                logger.error(f"无法提取音频: {video_path}")
                return video_id, None
                
            # 提取字幕
            subtitles = self.processor._extract_subtitles_from_video(audio_file, vocabulary_id)
            if not subtitles:
                logger.error(f"无法提取字幕: {video_path}")
                return video_id, None
                
            # 将字幕数据转换为DataFrame
            subtitle_df = pd.DataFrame([{
                'timestamp': item.get('start_formatted', '00:00:00'),
                'text': item.get('text', ''),
                'start_time': item.get('start', 0),
                'end_time': item.get('end', 0)
            } for item in subtitles if item.get('text')])
            
            if subtitle_df.empty:
                logger.error(f"提取的字幕为空: {video_path}")
                return video_id, None
            
            # 保存字幕数据
            subtitles_json_path = os.path.join('data', 'processed', 'subtitles', f"{video_id}_subtitles.json")
            subtitle_df.to_json(subtitles_json_path, orient='records', force_ascii=False, indent=2)
            
            logger.info(f"候选视频 {video_id} 处理完成，提取了 {len(subtitle_df)} 条字幕")
            return video_id, subtitle_df
            
        except Exception as e:
            logger.exception(f"处理候选视频 {video_id} 时出错: {str(e)}")
            return video_id, None
    
    async def match_video_segments(self, demo_segments: List[Dict[str, Any]], 
                                    candidate_subtitles: Dict[str, pd.DataFrame],
                                    similarity_threshold: int = 60) -> Dict[str, List[Dict[str, Any]]]:
        """
        为每个Demo段落找到最匹配的候选视频片段
        
        参数:
            demo_segments: Demo视频的分段信息
            candidate_subtitles: 候选视频的字幕数据
            similarity_threshold: 最低相似度阈值
            
        返回:
            每个阶段的匹配结果
        """
        logger.info(f"开始为 {len(demo_segments)} 个Demo段落进行视频匹配")
        match_results = {}
        
        try:
            # 加载嵌入模型
            embedder = self._get_sentence_transformer()
            
            # 为每个Demo段落计算嵌入向量
            demo_texts = [segment['text'] for segment in demo_segments]
            demo_embeddings = embedder.encode(demo_texts, show_progress_bar=True)
            
            # 计算每个候选视频的句子嵌入向量
            candidate_embeddings = {}
            candidate_sentences = {}
            
            for video_id, subtitle_df in candidate_subtitles.items():
                logger.info(f"处理候选视频 {video_id} 的嵌入向量")
                
                # 按时序分组为基本句子组
                basic_sentences = []
                current_group = []
                
                for _, row in subtitle_df.iterrows():
                    current_group.append(row)
                    
                    # 分组逻辑与_segment_subtitles_semantic方法相同
                    if (row['text'].endswith(('.', '?', '!', '。', '？', '！')) or 
                        len(current_group) >= 5):
                        
                        if current_group:
                            combined_text = ' '.join([r['text'] for r in current_group])
                            start_time = current_group[0]['start_time']
                            end_time = current_group[-1]['end_time']
                            start_timestamp = current_group[0]['timestamp']
                            end_timestamp = subtitle_df.loc[subtitle_df['end_time'] >= end_time, 'timestamp'].iloc[0] if not pd.isna(end_time) else start_timestamp
                            
                            basic_sentences.append({
                                'text': combined_text,
                                'start_time': start_time,
                                'end_time': end_time,
                                'start_timestamp': start_timestamp,
                                'end_timestamp': end_timestamp
                            })
                            current_group = []
                
                # 处理剩余的分组
                if current_group:
                    combined_text = ' '.join([r['text'] for r in current_group])
                    start_time = current_group[0]['start_time']
                    end_time = current_group[-1]['end_time']
                    start_timestamp = current_group[0]['timestamp']
                    end_timestamp = subtitle_df.loc[subtitle_df['end_time'] >= end_time, 'timestamp'].iloc[0] if not pd.isna(end_time) else start_timestamp
                    
                    basic_sentences.append({
                        'text': combined_text,
                        'start_time': start_time,
                        'end_time': end_time,
                        'start_timestamp': start_timestamp,
                        'end_timestamp': end_timestamp
                    })
                
                # 计算句子嵌入向量
                if basic_sentences:
                    sentence_texts = [s['text'] for s in basic_sentences]
                    embeddings = embedder.encode(sentence_texts, show_progress_bar=True)
                    
                    candidate_embeddings[video_id] = embeddings
                    candidate_sentences[video_id] = basic_sentences
                
            # 为每个Demo段落找到最匹配的候选视频片段
            for stage_idx, demo_segment in enumerate(demo_segments):
                stage_id = demo_segment['stage']
                demo_embedding = demo_embeddings[stage_idx]
                
                # 为当前阶段创建匹配结果列表
                match_results[stage_id] = []
                
                for video_id, embeddings in candidate_embeddings.items():
                    sentences = candidate_sentences[video_id]
                    
                    # 计算与每个候选句子的相似度
                    similarities = []
                    window_size = 3  # 滑动窗口大小，用于计算连续句子的整体相似度
                    
                    for i in range(len(embeddings) - window_size + 1):
                        # 计算窗口内所有句子的平均嵌入向量
                        window_embedding = np.mean(embeddings[i:i+window_size], axis=0)
                        
                        # 计算与Demo段落的余弦相似度
                        similarity = np.dot(demo_embedding, window_embedding) / (np.linalg.norm(demo_embedding) * np.linalg.norm(window_embedding))
                        similarity = float(similarity)  # 转换为Python原生float
                        
                        # 计算窗口时间范围
                        window_start_time = sentences[i]['start_time']
                        window_end_time = sentences[i+window_size-1]['end_time']
                        window_duration = window_end_time - window_start_time
                        
                        # 计算窗口文本
                        window_text = ' '.join([s['text'] for s in sentences[i:i+window_size]])
                        
                        similarities.append({
                            'video_id': video_id,
                            'start_idx': i,
                            'end_idx': i + window_size - 1,
                            'similarity': similarity,
                            'start_time': window_start_time,
                            'end_time': window_end_time,
                            'duration': window_duration,
                            'text': window_text,
                            'start_timestamp': sentences[i]['start_timestamp'],
                            'end_timestamp': sentences[i+window_size-1]['end_timestamp']
                        })
                    
                    # 按相似度排序
                    similarities.sort(key=lambda x: x['similarity'], reverse=True)
                    
                    # 添加最相似的窗口到匹配结果
                    if similarities and similarities[0]['similarity'] * 100 >= similarity_threshold:
                        # 计算Demo段落的持续时间
                        demo_duration = demo_segment['end'] - demo_segment['start']
                        
                        # 选择持续时间接近的片段
                        close_duration_matches = [m for m in similarities[:10] 
                                              if 0.85 * demo_duration <= m['duration'] <= 1.15 * demo_duration]
                        
                        # 如果没有持续时间接近的，就使用最相似的
                        if close_duration_matches:
                            top_match = close_duration_matches[0]
                        else:
                            top_match = similarities[0]
                        
                        # 将分数转换为百分比
                        score = int(top_match['similarity'] * 100)
                        
                        # 添加到匹配结果
                        match_results[stage_id].append({
                            'stage': stage_id,
                            'video_id': top_match['video_id'],
                            'start_time': top_match['start_time'],
                            'end_time': top_match['end_time'],
                            'start_timestamp': top_match['start_timestamp'],
                            'end_timestamp': top_match['end_timestamp'],
                            'similarity': score,
                            'text': top_match['text']
                        })
                
                # 对该阶段的所有匹配结果按相似度排序
                if stage_id in match_results:
                    match_results[stage_id].sort(key=lambda x: x['similarity'], reverse=True)
                    logger.info(f"阶段 {stage_id} 找到 {len(match_results[stage_id])} 个匹配片段")
            
            # 保存匹配结果
            matches_json_path = os.path.join('data', 'processed', 'analysis', 'results', f"matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(matches_json_path, 'w', encoding='utf-8') as f:
                json.dump(match_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"视频匹配完成，匹配结果已保存到 {matches_json_path}")
            return match_results
            
        except Exception as e:
            logger.exception(f"视频匹配过程出错: {str(e)}")
            return {}
    
    async def compose_magic_video(self, demo_video_path: str, match_results: Dict[str, List[Dict[str, Any]]], 
                                 output_filename: str, use_demo_audio: bool = False) -> str:
        """
        合成魔法视频
        
        参数:
            demo_video_path: Demo视频文件路径
            match_results: 匹配结果
            output_filename: 输出文件名（不含扩展名）
            use_demo_audio: 是否使用Demo视频的音频
            
        返回:
            生成的视频文件路径
        """
        logger.info("开始合成魔法视频")
        
        # 输出文件路径
        output_dir = os.path.join('data', 'output', 'videos')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{output_filename}.mp4")
        temp_dir = os.path.join('data', 'temp', 'videos', str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 1. 提取每个阶段的最佳匹配片段
            clips_to_concat = []
            for stage_id, matches in sorted(match_results.items()):
                if not matches:
                    logger.warning(f"阶段 {stage_id} 没有匹配片段，跳过")
                    continue
                
                # 获取该阶段的最佳匹配
                best_match = matches[0]
                video_id = best_match['video_id']
                start_time = best_match['start_time']
                end_time = best_match['end_time']
                
                # 查找视频文件
                video_path = None
                for root_dir in ['data/test_samples/input/video', 'data/input']:
                    potential_path = os.path.join(root_dir, video_id)
                    if os.path.exists(potential_path):
                        video_path = potential_path
                        break
                
                if not video_path:
                    logger.warning(f"找不到视频文件: {video_id}，跳过阶段 {stage_id}")
                    continue
                
                # 裁剪视频片段
                logger.info(f"裁剪视频 {video_id}，时间范围: {start_time} - {end_time}")
                temp_clip_path = os.path.join(temp_dir, f"stage_{stage_id}_{video_id}_{start_time:.2f}_{end_time:.2f}.mp4")
                
                try:
                    # 使用FFmpeg精确裁剪
                    ffmpeg_cmd = [
                        "ffmpeg", "-y",
                        "-i", video_path,
                        "-ss", str(start_time),
                        "-to", str(end_time),
                        "-c:v", "libx264", "-c:a", "aac",
                        "-preset", "fast", "-crf", "22",
                        temp_clip_path
                    ]
                    
                    process = subprocess.run(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if process.returncode != 0:
                        logger.error(f"裁剪视频失败: {process.stderr}")
                        continue
                        
                    if not os.path.exists(temp_clip_path) or os.path.getsize(temp_clip_path) == 0:
                        logger.error(f"裁剪后的视频文件不存在或为空: {temp_clip_path}")
                        continue
                    
                    # 添加到待合成列表
                    clips_to_concat.append({
                        'stage': stage_id,
                        'path': temp_clip_path,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': end_time - start_time
                    })
                    
                except Exception as e:
                    logger.exception(f"裁剪视频时出错: {str(e)}")
                    continue
            
            if not clips_to_concat:
                raise ValueError("没有有效的视频片段可合成")
            
            # 按阶段排序
            clips_to_concat.sort(key=lambda x: x['stage'])
            
            # 2. 使用MoviePy合成视频
            video_clips = []
            
            for clip_info in clips_to_concat:
                clip_path = clip_info['path']
                video_clip = VideoFileClip(clip_path)
                
                # 如果使用Demo视频的音频，则将片段音量设为0
                if use_demo_audio:
                    video_clip = video_clip.without_audio()
                
                video_clips.append(video_clip)
            
            # 合成视频
            logger.info(f"合成 {len(video_clips)} 个视频片段")
            final_clip = concatenate_videoclips(video_clips, method="compose")
            
            # 如果使用Demo视频的音频，则提取Demo视频的音频并添加到合成视频中
            if use_demo_audio:
                logger.info("使用Demo视频的音频")
                demo_clip = VideoFileClip(demo_video_path)
                demo_audio = demo_clip.audio
                
                # 如果Demo音频比合成视频长，则裁剪音频
                if demo_audio.duration > final_clip.duration:
                    demo_audio = AudioFileClip(demo_video_path).subclip(0, final_clip.duration)
                # 如果Demo音频比合成视频短，则用silence补充
                elif demo_audio.duration < final_clip.duration:
                    logger.warning(f"Demo音频长度 ({demo_audio.duration}s) 短于合成视频 ({final_clip.duration}s)，将使用原视频片段的音频")
                
                final_clip = final_clip.set_audio(demo_audio)
                demo_clip.close()
            
            # 导出合成视频
            logger.info(f"导出魔法视频到: {output_path}")
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"),
                remove_temp=True,
                threads=4,
                preset="fast",
                ffmpeg_params=["-crf", "22"]
            )
            
            # 关闭所有视频片段
            for clip in video_clips:
                clip.close()
            final_clip.close()
            
            logger.info(f"魔法视频合成完成: {output_path}")
            
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"已清理临时目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录时出错: {str(e)}")
            
            return output_path
            
        except Exception as e:
            logger.exception(f"合成魔法视频时出错: {str(e)}")
            
            # 尝试清理临时文件
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass
                
            return "" 