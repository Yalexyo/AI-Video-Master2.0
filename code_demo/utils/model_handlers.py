#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AI模型处理工具模块
---------------
提供AI模型相关的函数，包括模型加载、推理等功能，
对接各种AI服务和本地模型。
"""

import os
import json
import logging
import numpy as np
from datetime import datetime
import requests
from pathlib import Path
import tempfile

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("model_handlers")

# 全局模型缓存
_MODEL_CACHE = {}

def get_env_api_key(service='openai'):
    """
    获取环境变量中的API密钥
    
    参数:
        service: 服务名称
    
    返回:
        API密钥，如果未设置则返回None
    """
    # 从项目根目录导入配置模块
    from utils import config
    
    if service.lower() == 'openai':
        return config.get_env('OPENAI_API_KEY')
    elif service.lower() in ['ali', 'aliyun', 'dashscope']:
        return config.get_env('DASHSCOPE_API_KEY')
    elif service.lower() in ['baidu', 'ernie']:
        return config.get_env('BAIDU_API_KEY')
    elif service.lower() in ['deepseek']:
        return config.get_env('DEEPSEEK_API_KEY')
    elif service.lower() in ['qwen', 'qianwen']:
        return config.get_env('QWEN_API_KEY')
    else:
        return None

def get_sentence_encoder(model_name='paraphrase-multilingual-MiniLM-L12-v2'):
    """
    获取句子编码模型
    
    参数:
        model_name: 模型名称
    
    返回:
        句子编码模型
    """
    global _MODEL_CACHE
    
    cache_key = f"sentence_encoder:{model_name}"
    
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    
    try:
        # 导入 SentenceTransformer
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.error("未安装 sentence-transformers 库，无法加载句子编码模型")
            return None
        
        # 加载模型
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[cache_key] = model
        
        logger.info(f"已加载句子编码模型: {model_name}")
        return model
    
    except Exception as e:
        logger.error(f"加载句子编码模型失败: {e}")
        return None

def compute_sentence_similarity(sentence1, sentence2, model_name='paraphrase-multilingual-MiniLM-L12-v2'):
    """
    计算句子相似度
    
    参数:
        sentence1: 第一个句子
        sentence2: 第二个句子
        model_name: 模型名称
    
    返回:
        相似度得分(0-1)
    """
    # 获取句子编码模型
    model = get_sentence_encoder(model_name)
    
    if model is None:
        # 降级为余弦相似度
        from utils import text_analysis
        return text_analysis._compute_cosine_similarity(sentence1, sentence2)
    
    try:
        # 编码句子
        embedding1 = model.encode(sentence1, convert_to_tensor=False)
        embedding2 = model.encode(sentence2, convert_to_tensor=False)
        
        # 计算余弦相似度
        similarity = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        
        return float(similarity)
    
    except Exception as e:
        logger.error(f"计算句子相似度失败: {e}")
        
        # 降级为余弦相似度
        from utils import text_analysis
        return text_analysis._compute_cosine_similarity(sentence1, sentence2)

def batch_compute_sentence_similarity(sentences1, sentences2, method='sentence-bert'):
    """
    批量计算句子相似度
    
    参数:
        sentences1: 第一组句子
        sentences2: 第二组句子
        method: 计算方法
    
    返回:
        相似度矩阵
    """
    if method != 'sentence-bert':
        # 使用其他方法逐对计算
        similarity_matrix = np.zeros((len(sentences1), len(sentences2)))
        
        from utils import text_analysis
        for i, sent1 in enumerate(sentences1):
            for j, sent2 in enumerate(sentences2):
                if method == 'cosine':
                    similarity_matrix[i, j] = text_analysis._compute_cosine_similarity(sent1, sent2)
                elif method == 'jaccard':
                    similarity_matrix[i, j] = text_analysis._compute_jaccard_similarity(sent1, sent2)
                else:
                    similarity_matrix[i, j] = 0
        
        return similarity_matrix
    
    # 使用Sentence-BERT计算
    model = get_sentence_encoder()
    
    if model is None:
        logger.warning("未能加载句子编码模型，降级为余弦相似度")
        return batch_compute_sentence_similarity(sentences1, sentences2, method='cosine')
    
    try:
        # 编码所有句子
        embeddings1 = model.encode(sentences1, convert_to_tensor=False, show_progress_bar=False)
        embeddings2 = model.encode(sentences2, convert_to_tensor=False, show_progress_bar=False)
        
        # 计算相似度矩阵
        similarity_matrix = np.zeros((len(sentences1), len(sentences2)))
        
        for i, emb1 in enumerate(embeddings1):
            for j, emb2 in enumerate(embeddings2):
                similarity_matrix[i, j] = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        return similarity_matrix
    
    except Exception as e:
        logger.error(f"批量计算句子相似度失败: {e}")
        
        # 降级为余弦相似度
        return batch_compute_sentence_similarity(sentences1, sentences2, method='cosine')

def get_bertopic_model(nr_topics=5, language='chinese'):
    """
    获取BERTopic模型
    
    参数:
        nr_topics: 主题数量
        language: 语言
    
    返回:
        BERTopic模型
    """
    global _MODEL_CACHE
    
    cache_key = f"bertopic:{nr_topics}:{language}"
    
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    
    try:
        # 导入 BERTopic
        try:
            from bertopic import BERTopic
            from sklearn.feature_extraction.text import CountVectorizer
        except ImportError:
            logger.error("未安装 bertopic 或 scikit-learn 库，无法加载BERTopic模型")
            return None
        
        # 设置停用词
        stop_words = None
        if language == 'chinese':
            try:
                import jieba
                from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
                
                # 中文停用词
                chinese_stop_words = [
                    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很',
                    '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '这个', '来', '那', 
                    '他', '她'
                ]
                stop_words = list(ENGLISH_STOP_WORDS) + chinese_stop_words
                
                # 设置jieba分词器
                vectorizer = CountVectorizer(tokenizer=lambda x: jieba.lcut(x), stop_words=stop_words)
            except ImportError:
                logger.warning("未安装 jieba 库，使用默认分词")
                vectorizer = CountVectorizer(stop_words=stop_words)
        else:
            vectorizer = CountVectorizer(stop_words=stop_words)
        
        # 获取句子编码模型
        sentence_model = get_sentence_encoder()
        
        if sentence_model is None:
            logger.error("无法加载句子编码模型，BERTopic初始化失败")
            return None
        
        # 创建模型
        model = BERTopic(
            language=language,
            nr_topics=nr_topics,
            vectorizer_model=vectorizer,
            embedding_model=sentence_model,
            verbose=True
        )
        
        _MODEL_CACHE[cache_key] = model
        
        logger.info(f"已创建BERTopic模型: {nr_topics}主题, {language}语言")
        return model
    
    except Exception as e:
        logger.error(f"创建BERTopic模型失败: {e}")
        return None

def extract_topics_from_texts(texts, model=None, language='chinese', n_topics=5, top_n_words=10):
    """
    从文本中提取主题
    
    参数:
        texts: 文本列表
        model: BERTopic模型，如果为None则创建新模型
        language: 语言
        n_topics: 主题数量
        top_n_words: 每个主题的关键词数量
    
    返回:
        主题字典，格式为 {主题ID: {label: 主题标签, keywords: 关键词列表}}
    """
    if not texts:
        logger.error("没有输入文本")
        return {}
    
    # 如果未提供模型，创建新模型
    if model is None:
        model = get_bertopic_model(nr_topics=n_topics, language=language)
    
    if model is None:
        logger.error("BERTopic模型加载失败")
        return {}
    
    try:
        # 训练模型
        topics, probs = model.fit_transform(texts)
        
        # 获取主题信息
        topic_info = model.get_topic_info()
        
        # 提取结果
        result = {}
        
        for topic_id in range(-1, n_topics):
            if topic_id == -1:
                # 跳过异常值主题(-1)
                continue
            
            topic_words = model.get_topic(topic_id)
            if not topic_words:
                continue
            
            # 主题标签
            topic_label = f"主题_{topic_id}"
            
            # 主题关键词
            keywords = [word for word, _ in topic_words[:top_n_words]]
            
            # 包含该主题的文档
            documents = [i for i, t in enumerate(topics) if t == topic_id]
            
            result[topic_id] = {
                'label': topic_label,
                'keywords': keywords,
                'documents': documents
            }
        
        return result
    
    except Exception as e:
        logger.error(f"提取主题失败: {e}")
        return {}

def extract_keywords_from_text(text, top_n=10, model_name='qwen-max'):
    """
    从文本中提取关键词
    
    参数:
        text: 输入文本
        top_n: 返回的关键词数量
        model_name: 使用的模型
    
    返回:
        关键词列表
    """
    if not text:
        return []
    
    # 尝试使用大型语言模型提取关键词
    try:
        prompt = f"""
        请从以下文本中提取{top_n}个最重要的关键词。
        只返回关键词列表，每行一个关键词，不要有编号，不要有解释。

        文本内容:
        {text}
        
        关键词:
        """
        
        response = generate_text(prompt=prompt, model=model_name, temperature=0.3, max_tokens=300)
        
        if response:
            # 解析关键词
            keywords = []
            for line in response.strip().split('\n'):
                word = line.strip()
                if word and len(keywords) < top_n:
                    keywords.append(word)
            
            if keywords:
                return keywords
    
    except Exception as e:
        logger.error(f"使用LLM提取关键词失败: {e}")
    
    # 如果LLM失败，尝试使用jieba提取关键词
    try:
        import jieba.analyse
        
        keywords = jieba.analyse.extract_tags(text, topK=top_n)
        return keywords
    
    except Exception as e:
        logger.error(f"使用jieba提取关键词失败: {e}")
    
    # 如果所有方法都失败，使用简单的词频统计
    from utils import text_analysis
    clean_text = text_analysis.clean_text(text)
    words = clean_text.split()
    
    # 统计词频
    word_counts = {}
    for word in words:
        if len(word) > 1:  # 忽略单个字符
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # 按词频排序
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 提取前top_n个词
    keywords = [word for word, _ in sorted_words[:top_n]]
    
    return keywords

def generate_text(prompt, model='qwen-max', temperature=0.7, max_tokens=1500):
    """
    生成文本
    
    参数:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大生成长度
    
    返回:
        生成的文本
    """
    # 根据模型选择服务
    if model.startswith('qwen'):
        return _generate_text_dashscope(
            prompt=prompt, 
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif model.startswith('deepseek'):
        return _generate_text_deepseek(
            prompt=prompt, 
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    elif model.startswith('gpt'):
        return _generate_text_openai(
            prompt=prompt, 
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        logger.warning(f"未知的模型: {model}，使用qwen-max")
        return _generate_text_dashscope(
            prompt=prompt, 
            model='qwen-max',
            temperature=temperature,
            max_tokens=max_tokens
        )

def _generate_text_dashscope(prompt, model='qwen-max', temperature=0.7, max_tokens=1500):
    """
    使用阿里云DashScope API生成文本
    
    参数:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大生成长度
    
    返回:
        生成的文本
    """
    try:
        # 获取API密钥
        api_key = get_env_api_key('dashscope')
        
        if not api_key:
            logger.error("未设置DASHSCOPE_API_KEY环境变量")
            return ""
        
        try:
            import dashscope
            from dashscope.aigc.generation import Generation
            
            dashscope.api_key = api_key
            
            response = Generation.call(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format='message'
            )
            
            # 检查请求是否成功
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                logger.error(f"请求失败: {response.status_code}, {response.message}")
                return ""
        
        except ImportError:
            logger.warning("未安装dashscope库，使用HTTP请求")
            
            # 使用HTTP请求
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "input": {
                    "prompt": prompt
                },
                "parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('output', {}).get('text', "")
            else:
                logger.error(f"请求失败: {response.status_code}, {response.text}")
                return ""
    
    except Exception as e:
        logger.error(f"使用DashScope生成文本失败: {e}")
        return ""

def _generate_text_openai(prompt, model='gpt-3.5-turbo', temperature=0.7, max_tokens=1500):
    """
    使用OpenAI API生成文本
    
    参数:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大生成长度
    
    返回:
        生成的文本
    """
    try:
        # 获取API密钥
        api_key = get_env_api_key('openai')
        
        if not api_key:
            logger.error("未设置OPENAI_API_KEY环境变量")
            return ""
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
        
        except ImportError:
            logger.warning("未安装openai库，使用HTTP请求")
            
            # 使用HTTP请求
            url = "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', "")
            else:
                logger.error(f"请求失败: {response.status_code}, {response.text}")
                return ""
    
    except Exception as e:
        logger.error(f"使用OpenAI生成文本失败: {e}")
        return ""

def _generate_text_deepseek(prompt, model='deepseek-llm', temperature=0.7, max_tokens=1500):
    """
    使用DeepSeek API生成文本
    
    参数:
        prompt: 提示词
        model: 模型名称
        temperature: 温度
        max_tokens: 最大生成长度
    
    返回:
        生成的文本
    """
    try:
        # 获取API密钥
        api_key = get_env_api_key('deepseek')
        
        if not api_key:
            logger.error("未设置DEEPSEEK_API_KEY环境变量")
            return ""
        
        # 使用HTTP请求
        url = "https://api.deepseek.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('choices', [{}])[0].get('message', {}).get('content', "")
        else:
            logger.error(f"请求失败: {response.status_code}, {response.text}")
            return ""
    
    except Exception as e:
        logger.error(f"使用DeepSeek生成文本失败: {e}")
        return ""

def asr_audio_file(audio_file, model="paraformer-v2", format_type="wav", sample_rate=16000, sentence_level=True, vocabulary_id=None):
    """
    音频文件语音识别
    
    参数:
        audio_file: 音频文件路径
        model: 模型名称
        format_type: 音频格式
        sample_rate: 采样率
        sentence_level: 是否以句子级别返回结果
        vocabulary_id: 热词列表ID，用于提高特定词汇的识别准确率
    
    返回:
        字幕条目列表，每项包含start_time, end_time, text
    """
    try:
        # 获取API密钥
        api_key = get_env_api_key('dashscope')
        
        if not api_key:
            logger.error("未设置DASHSCOPE_API_KEY环境变量")
            return []
        
        # 读取音频文件
        with open(audio_file, 'rb') as f:
            audio_content = f.read()
        
        # 检查文件大小
        if len(audio_content) > 50 * 1024 * 1024:  # 50MB
            logger.error(f"音频文件过大: {len(audio_content) / (1024 * 1024):.2f}MB，超过50MB限制")
            return []
        
        try:
            import dashscope
            dashscope.api_key = api_key
        except ImportError:
            logger.warning("未安装dashscope库，使用HTTP请求")
            
            # 构建参数
            params = {
                'audio': audio_content,
                'model': model,
                'format': format_type,
                'sample_rate': sample_rate,
                'sentence_level': sentence_level
            }
            
            # 添加热词列表ID
            if vocabulary_id:
                logger.info(f"使用热词列表ID: {vocabulary_id}")
                params['vocabulary_id'] = vocabulary_id
            
            # 使用最新API提交任务
            response = dashscope.Audio.async_transcription(
                file_url=None,
                file_path=None,
                file_bytes=audio_content,
                **params
            )
            
            task_id = response.output.task_id
            logger.info(f"ASR任务提交成功，任务ID: {task_id}")
            
            # 等待任务完成
            import time
            while True:
                result = dashscope.Audio.fetch(task_id=task_id)
                if result.output.task_status == 'SUCCEEDED':
                    break
                time.sleep(5)
            
            # 解析结果
            if result.status_code == 200 and result.output:
                sentences = result.output.get('sentences', [])
                
                # 转换为字幕条目格式
                subtitles = []
                
                for sentence in sentences:
                    start_time = sentence.get('begin_time', 0) / 1000  # 毫秒转秒
                    end_time = sentence.get('end_time', 0) / 1000  # 毫秒转秒
                    text = sentence.get('text', '')
                    
                    if text:
                        subtitles.append({
                            'start_time': start_time,
                            'end_time': end_time,
                            'text': text
                        })
                
                return subtitles
            else:
                logger.error(f"ASR任务失败: {result.status_code}, {result.message}")
                return []
        
        except ImportError:
            logger.warning("未安装dashscope库，使用HTTP请求")
            
            # 使用HTTP请求
            url = "https://dashscope.aliyuncs.com/api/v1/services/asr/recognition/submit"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/octet-stream"
            }
            
            params = {
                "model": model,
                "format": format_type,
                "sample_rate": sample_rate,
                "sentence_level": sentence_level
            }
            
            # 提交任务
            response = requests.post(url, headers=headers, params=params, data=audio_content)
            
            if response.status_code == 200:
                result = response.json()
                task_id = result.get('output', {}).get('task_id')
                
                if not task_id:
                    logger.error(f"ASR任务提交失败: {result}")
                    return []
                
                logger.info(f"ASR任务提交成功，任务ID: {task_id}")
                
                # 等待任务完成
                get_url = f"https://dashscope.aliyuncs.com/api/v1/services/asr/recognition/get?task_id={task_id}"
                
                # 轮询结果
                import time
                for _ in range(30):  # 最多等待30次
                    time.sleep(5)  # 等待5秒
                    
                    get_response = requests.get(get_url, headers={"Authorization": f"Bearer {api_key}"})
                    
                    if get_response.status_code == 200:
                        result = get_response.json()
                        status = result.get('output', {}).get('status')
                        
                        if status == 'SUCCEEDED':
                            sentences = result.get('output', {}).get('results', {}).get('sentences', [])
                            
                            # 转换为字幕条目格式
                            subtitles = []
                            
                            for sentence in sentences:
                                start_time = sentence.get('begin_time', 0) / 1000  # 毫秒转秒
                                end_time = sentence.get('end_time', 0) / 1000  # 毫秒转秒
                                text = sentence.get('text', '')
                                
                                if text:
                                    subtitles.append({
                                        'start_time': start_time,
                                        'end_time': end_time,
                                        'text': text
                                    })
                            
                            return subtitles
                        
                        elif status == 'FAILED':
                            logger.error(f"ASR任务失败: {result}")
                            return []
                    
                    else:
                        logger.error(f"获取ASR任务结果失败: {get_response.status_code}, {get_response.text}")
                
                logger.error("ASR任务超时")
                return []
            
            else:
                logger.error(f"ASR任务提交失败: {response.status_code}, {response.text}")
                return []
    
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        return []
