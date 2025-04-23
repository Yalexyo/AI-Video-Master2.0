#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文本分析工具模块
---------------
提供文本处理和分析相关的函数，包括字幕解析、关键词提取、
文本相似度计算等功能。
"""

import os
import re
import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_analysis")

# 字幕时间格式正则表达式
SRT_TIME_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})')

def parse_srt_file(srt_file_path):
    """
    解析SRT字幕文件
    
    参数:
        srt_file_path: SRT文件路径
    
    返回:
        字幕条目列表，每项包含编号、开始时间、结束时间和文本
    """
    if not os.path.exists(srt_file_path):
        logger.error(f"SRT文件不存在: {srt_file_path}")
        return []
    
    subtitles = []
    
    try:
        with open(srt_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 按空行分割字幕条目
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # 解析编号
            try:
                subtitle_id = int(lines[0])
            except ValueError:
                continue
            
            # 解析时间
            time_match = SRT_TIME_PATTERN.match(lines[1])
            if not time_match:
                continue
            
            start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = map(int, time_match.groups())
            
            start_time = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d}"
            end_time = f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
            
            start_seconds = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
            end_seconds = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000
            
            # 解析文本
            text = ' '.join(lines[2:])
            
            subtitles.append({
                'id': subtitle_id,
                'start_time': start_time,
                'end_time': end_time,
                'start_seconds': start_seconds,
                'end_seconds': end_seconds,
                'text': text
            })
        
        return subtitles
    
    except Exception as e:
        logger.error(f"解析SRT文件失败 {srt_file_path}: {e}")
        return []

def extract_text_from_srt(srt_file_path):
    """
    从SRT文件中提取所有文本
    
    参数:
        srt_file_path: SRT文件路径
    
    返回:
        字幕文本
    """
    subtitles = parse_srt_file(srt_file_path)
    if not subtitles:
        return ""
    
    texts = [subtitle['text'] for subtitle in subtitles]
    return ' '.join(texts)

def clean_text(text):
    """
    清理文本，去除特殊字符和多余空格
    
    参数:
        text: 输入文本
    
    返回:
        清理后的文本
    """
    if not text:
        return ""
    
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 去除特殊字符
    text = re.sub(r'[^\w\s.,?!;:()，。？！；：（）""\']', ' ', text)
    
    # 替换多个空格为一个空格
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def time_to_seconds(time_str):
    """
    将时间字符串转换为秒
    
    参数:
        time_str: 时间字符串(HH:MM:SS,mmm)
    
    返回:
        秒数
    """
    try:
        h, m, rest = time_str.split(':')
        s, ms = rest.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    except (ValueError, AttributeError):
        return 0

def seconds_to_time(seconds):
    """
    将秒转换为时间字符串
    
    参数:
        seconds: 秒数
    
    返回:
        时间字符串(HH:MM:SS,mmm)
    """
    try:
        seconds = float(seconds)
    except (ValueError, TypeError):
        return "00:00:00,000"
    
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def compute_text_similarity(text1, text2, method='sentence-bert'):
    """
    计算文本相似度
    
    参数:
        text1: 第一个文本
        text2: 第二个文本
        method: 计算方法，可选值: sentence-bert, cosine, jaccard
    
    返回:
        相似度得分(0-1)
    """
    if not text1 or not text2:
        return 0
    
    # 清理文本
    text1 = clean_text(text1)
    text2 = clean_text(text2)
    
    if not text1 or not text2:
        return 0
    
    try:
        if method == 'sentence-bert':
            # 使用Sentence-BERT计算相似度
            from utils import model_handlers
            return model_handlers.compute_sentence_similarity(text1, text2)
        
        elif method == 'cosine':
            # 使用余弦相似度
            return _compute_cosine_similarity(text1, text2)
        
        elif method == 'jaccard':
            # 使用Jaccard相似度
            return _compute_jaccard_similarity(text1, text2)
        
        else:
            logger.warning(f"未知的相似度计算方法: {method}，使用余弦相似度")
            return _compute_cosine_similarity(text1, text2)
    
    except Exception as e:
        logger.error(f"计算文本相似度失败: {e}")
        return 0

def _compute_cosine_similarity(text1, text2):
    """
    计算余弦相似度
    
    参数:
        text1: 第一个文本
        text2: 第二个文本
    
    返回:
        相似度得分(0-1)
    """
    # 分词
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # 创建词汇表
    all_words = list(words1.union(words2))
    
    # 创建词频向量
    vector1 = [1 if word in words1 else 0 for word in all_words]
    vector2 = [1 if word in words2 else 0 for word in all_words]
    
    # 计算余弦相似度
    dot_product = sum(a * b for a, b in zip(vector1, vector2))
    norm1 = sum(a * a for a in vector1) ** 0.5
    norm2 = sum(b * b for b in vector2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0
    
    return dot_product / (norm1 * norm2)

def _compute_jaccard_similarity(text1, text2):
    """
    计算Jaccard相似度
    
    参数:
        text1: 第一个文本
        text2: 第二个文本
    
    返回:
        相似度得分(0-1)
    """
    # 分词
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # 计算Jaccard相似度
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0
    
    return intersection / union

def extract_keywords(text, top_n=10, method='tf-idf'):
    """
    提取文本关键词
    
    参数:
        text: 输入文本
        top_n: 返回的关键词数量
        method: 提取方法，可选值: tf-idf, textrank
    
    返回:
        关键词列表
    """
    if not text:
        return []
    
    try:
        from utils import model_handlers
        
        # 使用模型处理器提取关键词
        return model_handlers.extract_keywords_from_text(
            text=text,
            top_n=top_n,
            method=method
        )
    
    except Exception as e:
        logger.error(f"提取关键词失败: {e}")
        return []

def batch_compute_similarity(texts1, texts2, method='sentence-bert'):
    """
    批量计算文本相似度
    
    参数:
        texts1: 第一组文本列表
        texts2: 第二组文本列表
        method: 计算方法
    
    返回:
        相似度矩阵
    """
    if not texts1 or not texts2:
        return np.zeros((0, 0))
    
    try:
        # 使用模型处理器计算相似度矩阵
        from utils import model_handlers
        return model_handlers.batch_compute_sentence_similarity(texts1, texts2, method)
    
    except Exception as e:
        logger.error(f"批量计算文本相似度失败: {e}")
        
        # 回退到逐个计算
        similarity_matrix = np.zeros((len(texts1), len(texts2)))
        
        for i, text1 in enumerate(texts1):
            for j, text2 in enumerate(texts2):
                similarity_matrix[i, j] = compute_text_similarity(text1, text2, method)
        
        return similarity_matrix

def segment_text(text, max_length=1000, overlap=100):
    """
    将长文本分割成短文本段落
    
    参数:
        text: 输入文本
        max_length: 最大段落长度
        overlap: 段落间重叠的字符数
    
    返回:
        段落列表
    """
    if not text:
        return []
    
    text = clean_text(text)
    
    if len(text) <= max_length:
        return [text]
    
    segments = []
    start = 0
    
    while start < len(text):
        # 确定段落结束位置
        end = start + max_length
        
        if end >= len(text):
            segments.append(text[start:])
            break
        
        # 在自然断句处切分
        punctuations = ['.', '!', '?', '。', '！', '？']
        cut_pos = end
        
        # 向后找最近的句子结束标点
        for i in range(end, min(end + 100, len(text))):
            if text[i] in punctuations:
                cut_pos = i + 1
                break
        
        # 如果没找到合适的断句点，向前找最近的句子结束标点
        if cut_pos == end:
            for i in range(end, max(end - 200, start), -1):
                if text[i] in punctuations:
                    cut_pos = i + 1
                    break
        
        # 如果仍未找到合适的断句点，直接在单词边界切分
        if cut_pos == end:
            for i in range(end, max(end - 50, start), -1):
                if text[i].isspace():
                    cut_pos = i
                    break
        
        # 添加段落
        segments.append(text[start:cut_pos])
        
        # 更新起始位置
        start = cut_pos - overlap
        if start < 0:
            start = 0
    
    return segments

def calculate_readability(text):
    """
    计算文本的可读性指标
    
    参数:
        text: 输入文本
    
    返回:
        可读性得分(0-100)，越高越易读
    """
    if not text:
        return 0
    
    text = clean_text(text)
    
    # 分句
    sentences = re.split(r'[.!?。！？]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return 0
    
    # 分词
    words = text.split()
    
    # 计算统计数据
    num_sentences = len(sentences)
    num_words = len(words)
    num_characters = len(text.replace(" ", ""))
    
    if num_sentences == 0 or num_words == 0:
        return 0
    
    # 计算平均句子长度
    avg_sentence_length = num_words / num_sentences
    
    # 计算平均单词长度
    avg_word_length = num_characters / num_words
    
    # 简化的可读性计算
    readability = 100 - (0.39 * avg_sentence_length + 11.8 * avg_word_length - 15.59)
    
    # 限制得分范围
    readability = max(0, min(100, readability))
    
    return readability

def detect_language(text):
    """
    检测文本语言
    
    参数:
        text: 输入文本
    
    返回:
        语言代码(如'zh'、'en'等)
    """
    if not text:
        return "unknown"
    
    try:
        # 使用langdetect库检测语言
        from langdetect import detect
        return detect(text)
    except:
        # 简单的中英文检测
        chinese_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_count = len(re.findall(r'[a-zA-Z]', text))
        
        if chinese_count > english_count:
            return "zh"
        else:
            return "en"
