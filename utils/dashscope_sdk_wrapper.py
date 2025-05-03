#!/usr/bin/env python3
"""
DashScope SDK包装模块

使用官方SDK而不是HTTP API直接调用，以规避API权限问题
"""

import os
import time
import logging
import json
import requests
from typing import Dict, List, Any, Optional, Union

# 导入官方SDK
try:
    import dashscope
    from dashscope.audio.asr.transcription import Transcription
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    
# 设置日志
logger = logging.getLogger(__name__)

class DashScopeSDKWrapper:
    """DashScope SDK包装类"""
    
    def __init__(self, api_key=None):
        """
        初始化DashScope SDK包装类
        
        参数:
            api_key: API密钥，如果为None则尝试从环境变量获取
        """
        if not SDK_AVAILABLE:
            logger.error("DashScope SDK未安装，请使用pip install dashscope安装")
            return
            
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            logger.warning("未设置API密钥，请设置DASHSCOPE_API_KEY环境变量或通过参数传入")
            
        # 配置SDK
        dashscope.api_key = self.api_key
        
        logger.info("DashScope SDK包装器初始化完成")
        
    def _parse_transcription_url(self, url: str) -> List[Dict[str, Any]]:
        """
        下载并解析转写结果URL
        
        参数:
            url: 转写结果URL
            
        返回:
            字幕列表
        """
        if not url:
            logger.error("转写结果URL为空")
            return []
            
        try:
            # 下载转写结果
            logger.info(f"下载转写结果: {url}")
            response = requests.get(url, timeout=30)
            
            # 检查响应
            if response.status_code != 200:
                logger.error(f"下载转写结果失败: {response.status_code}")
                return []
                
            # 解析JSON数据
            try:
                data = response.json()
                logger.info(f"转写结果数据格式: {type(data)}")
                
                # 检查数据格式
                if isinstance(data, dict):
                    # 打印主要字段
                    logger.info(f"转写结果包含字段: {list(data.keys())}")
                    
                    # 提取字幕
                    sentences = []
                    
                    # 常见字段名检查
                    if 'sentences' in data:
                        sentences = data['sentences']
                        logger.info(f"直接从'sentences'字段中提取到 {len(sentences)} 条字幕")
                    elif 'result' in data and isinstance(data['result'], dict) and 'sentences' in data['result']:
                        sentences = data['result']['sentences']
                        logger.info(f"从'result.sentences'字段中提取到 {len(sentences)} 条字幕")
                    elif 'transcripts' in data:
                        # 从transcripts字段提取字幕
                        transcripts = data['transcripts']
                        logger.info(f"从'transcripts'字段中提取到 {len(transcripts)} 条转写结果")
                        
                        # 如果只有一条transcript但文本很长，应该进行分段
                        if len(transcripts) == 1 and len(transcripts[0].get('text', '')) > 30:
                            transcript = transcripts[0]
                            text = transcript.get('text', '')
                            begin_time = transcript.get('begin_time', 0)
                            end_time = transcript.get('end_time', 0)
                            
                            # 按标点符号分割
                            segments = self._split_text_by_punctuation(text)
                            logger.info(f"将长文本分割为 {len(segments)} 个段落")
                            
                            # 计算每个分段的时间比例
                            total_duration = end_time - begin_time
                            total_chars = len(text)
                            
                            current_time = begin_time
                            for segment in segments:
                                if not segment.strip():
                                    continue
                                    
                                # 按文本长度比例计算时间
                                segment_duration = max(1000, (len(segment) / total_chars) * total_duration)  # 至少1秒
                                segment_end_time = current_time + segment_duration
                                
                                sentences.append({
                                    'text': segment.strip(),
                                    'begin_time': current_time,
                                    'end_time': segment_end_time
                                })
                                
                                # 更新开始时间
                                current_time = segment_end_time
                                
                            logger.info(f"将单条转写结果分割为 {len(sentences)} 条字幕")
                        else:
                            # 将transcripts转换为sentences格式
                            for transcript in transcripts:
                                if isinstance(transcript, dict) and 'text' in transcript:
                                    text = transcript.get('text', '')
                                    begin_time = transcript.get('begin_time', 0)
                                    end_time = transcript.get('end_time', 0)
                                    
                                    # 如果文本较长，进行智能分段
                                    if len(text) > 50:
                                        # 按标点符号分割
                                        segments = self._split_text_by_punctuation(text)
                                        
                                        # 计算每个分段的时间比例
                                        total_duration = end_time - begin_time
                                        total_chars = len(text)
                                        
                                        current_time = begin_time
                                        for segment in segments:
                                            if not segment.strip():
                                                continue
                                                
                                            # 按文本长度比例计算时间
                                            segment_duration = max(1000, (len(segment) / total_chars) * total_duration)  # 至少1秒
                                            segment_end_time = current_time + segment_duration
                                            
                                            sentences.append({
                                                'text': segment.strip(),
                                                'begin_time': current_time,
                                                'end_time': segment_end_time
                                            })
                                            
                                            # 更新开始时间
                                            current_time = segment_end_time
                                    else:
                                        sentences.append({
                                            'text': text,
                                            'begin_time': begin_time,
                                            'end_time': end_time
                                        })
                        
                        logger.info(f"从'transcripts'转换为 {len(sentences)} 条字幕")
                    elif 'transcript' in data:
                        # 有些API只返回完整文本，没有时间戳信息
                        text = data['transcript']
                        logger.info(f"从'transcript'字段中提取到文本，长度: {len(text)}")
                        
                        # 将文本分割为句子
                        segments = self._split_text_by_punctuation(text)
                        
                        # 估算总时长 (平均每字0.3秒)
                        total_duration = len(text) * 0.3
                        total_chars = len(text)
                        
                        current_time = 0
                        for i, segment in enumerate(segments):
                            if not segment.strip():
                                continue
                                
                            # 按文本长度比例计算时间
                            segment_duration = (len(segment) / total_chars) * total_duration
                            segment_end_time = current_time + segment_duration
                            
                            sentences.append({
                                'text': segment.strip(),
                                'begin_time': current_time * 1000,  # 转换为毫秒
                                'end_time': segment_end_time * 1000  # 转换为毫秒
                            })
                            
                            # 更新开始时间
                            current_time = segment_end_time
                        
                        logger.info(f"从文本中智能分割生成了 {len(sentences)} 条字幕")
                    
                    # 打印前几条字幕
                    for i, sentence in enumerate(sentences[:3]):
                        logger.info(f"字幕 {i+1}: {json.dumps(sentence, ensure_ascii=False)}")
                        
                    return sentences
                else:
                    logger.warning(f"转写结果数据格式不是字典: {type(data)}")
                    return []
            except ValueError:
                # 不是JSON格式，可能是纯文本
                logger.info("转写结果不是JSON格式，尝试作为纯文本处理")
                text = response.text
                
                # 将文本分割为句子
                segments = self._split_text_by_punctuation(text)
                
                # 估算总时长 (平均每字0.3秒)
                total_duration = len(text) * 0.3
                total_chars = len(text)
                
                sentences = []
                current_time = 0
                for segment in segments:
                    if not segment.strip():
                        continue
                        
                    # 按文本长度比例计算时间
                    segment_duration = (len(segment) / total_chars) * total_duration
                    segment_end_time = current_time + segment_duration
                    
                    sentences.append({
                        'text': segment.strip(),
                        'begin_time': current_time * 1000,  # 转换为毫秒
                        'end_time': segment_end_time * 1000  # 转换为毫秒
                    })
                    
                    # 更新开始时间
                    current_time = segment_end_time
                
                logger.info(f"从纯文本中生成了 {len(sentences)} 条字幕")
                return sentences
                
        except Exception as e:
            logger.exception(f"解析转写结果URL时出错: {str(e)}")
            return []
            
    def _split_text_by_punctuation(self, text: str) -> List[str]:
        """
        根据标点符号智能分割文本
        
        参数:
            text: 待分割的文本
            
        返回:
            分割后的文本片段列表
        """
        # 标点符号列表 (中文和英文)
        punctuations = ['。', '！', '？', '；', '.', '!', '?', ';']
        
        # 第一步：按标点符号分割
        segments = []
        last_pos = 0
        
        for i, char in enumerate(text):
            if char in punctuations:
                segment = text[last_pos:i+1]
                if segment.strip():
                    segments.append(segment)
                last_pos = i + 1
        
        # 处理最后一段文本
        if last_pos < len(text) and text[last_pos:].strip():
            segments.append(text[last_pos:])
        
        # 如果没有找到标点符号，或者分割后的片段过长，进行进一步处理
        if not segments or any(len(s) > 100 for s in segments):
            # 第二步：按逗号分割
            new_segments = []
            for segment in segments or [text]:
                if len(segment) > 50:
                    # 按逗号再分割
                    comma_segments = []
                    last_comma_pos = 0
                    
                    for i, char in enumerate(segment):
                        if char in ['，', ',']:
                            comma_segment = segment[last_comma_pos:i+1]
                            if comma_segment.strip():
                                comma_segments.append(comma_segment)
                            last_comma_pos = i + 1
                    
                    # 处理最后一段
                    if last_comma_pos < len(segment) and segment[last_comma_pos:].strip():
                        comma_segments.append(segment[last_comma_pos:])
                    
                    new_segments.extend(comma_segments if comma_segments else [segment])
                else:
                    new_segments.append(segment)
            
            segments = new_segments
        
        # 如果仍然有过长的片段，进行更小粒度的分割
        if any(len(s) > 50 for s in segments):
            final_segments = []
            for segment in segments:
                if len(segment) > 50:
                    # 按固定长度分割
                    for i in range(0, len(segment), 30):
                        chunk = segment[i:i+30]
                        if i + 30 < len(segment):
                            # 查找最后一个词的边界
                            j = min(i + 30, len(segment) - 1)
                            while j > i and segment[j] not in [' ', '，', ',', '。', '.', '！', '!', '？', '?', '；', ';']:
                                j -= 1
                            chunk = segment[i:j+1] if j > i else segment[i:i+30]
                        final_segments.append(chunk)
                else:
                    final_segments.append(segment)
            segments = final_segments
        
        return segments
        
    def transcribe_audio(self, 
                       file_url: str,
                       model: str = "paraformer-v2", 
                       vocabulary_id: Optional[str] = None,
                       sample_rate: int = 16000,
                       punctuation: bool = True,
                       **kwargs) -> Dict[str, Any]:
        """
        使用DashScope SDK转写音频
        
        参数:
            file_url: 音频文件URL
            model: 模型名称，默认为"paraformer-v2"
            vocabulary_id: 热词表ID
            sample_rate: 采样率，默认16000
            punctuation: 是否添加标点，默认True
            **kwargs: 其他参数
            
        返回:
            转写结果
        """
        if not SDK_AVAILABLE:
            return {
                "status": "error",
                "error": "DashScope SDK未安装，请使用pip install dashscope安装"
            }
            
        try:
            # 配置参数
            params = {}
            
            # 添加热词表ID（如果提供）
            if vocabulary_id:
                params["vocabulary_id"] = vocabulary_id
                
            # 添加采样率和标点符号参数
            params["sample_rate"] = sample_rate
            params["punctuation"] = punctuation
            
            # 添加其他参数
            for key, value in kwargs.items():
                params[key] = value
                
            logger.info(f"转写音频文件: {file_url}, 模型: {model}, 热词ID: {vocabulary_id}")
            
            # 使用SDK调用
            # 使用异步方式（async_call方法）发起转写请求
            start_time = time.time()
            
            # 提交异步转写任务
            response = Transcription.async_call(
                model=model,
                file_urls=[file_url],  # 使用列表形式，正确的参数名是file_urls
                **params
            )
            
            # 从响应中获取任务ID
            task_id = response.output.get('task_id')
            if not task_id:
                logger.error("未获取到有效的任务ID")
                return {
                    "status": "error",
                    "error": "未获取到有效的任务ID"
                }
                
            logger.info(f"转写任务已提交，任务ID: {task_id}")
            
            # 等待任务完成 - 使用SDK内置的wait方法
            try:
                result = Transcription.wait(task_id)
                
                # 计算耗时
                elapsed_time = time.time() - start_time
                logger.info(f"转写任务完成，耗时: {elapsed_time:.2f}秒")
                
                # 打印完整的输出结果（JSON格式）
                logger.info(f"转写结果输出 (status_code={result.status_code}):")
                if hasattr(result, 'output') and result.output:
                    logger.info(f"输出字段: {list(result.output.keys())}")
                    
                    # 检查并打印sentences字段
                    if 'sentences' in result.output:
                        sentences = result.output.get('sentences', [])
                        logger.info(f"字幕数量: {len(sentences)}")
                        
                        # 如果有字幕，打印前3条
                        for i, sentence in enumerate(sentences[:3]):
                            logger.info(f"字幕 {i+1}: {json.dumps(sentence, ensure_ascii=False)}")
                    else:
                        logger.warning("输出中没有sentences字段")
                        
                        # 检查response内容，查找结果
                        for key, value in result.output.items():
                            logger.info(f"字段 {key}: {type(value)}")
                            
                            # 如果值是字典或列表，继续检查
                            if isinstance(value, dict):
                                logger.info(f"字典字段 {key} 包含: {list(value.keys())}")
                                
                                # 检查是否有sentences
                                if 'sentences' in value:
                                    inner_sentences = value.get('sentences', [])
                                    logger.info(f"在子字段 {key} 中发现字幕，数量: {len(inner_sentences)}")
                                    
                                    # 更新结果
                                    sentences = inner_sentences
                            elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                logger.info(f"列表字段 {key} 包含 {len(value)} 个元素")
                                
                                # 检查第一个元素是否包含sentences
                                first_item = value[0]
                                if isinstance(first_item, dict):
                                    logger.info(f"列表字段 {key} 第一个元素包含键: {list(first_item.keys())}")
                                    if 'sentences' in first_item:
                                        inner_sentences = first_item.get('sentences', [])
                                        logger.info(f"在列表字段 {key} 的第一个元素中发现字幕，数量: {len(inner_sentences)}")
                                        
                                        # 更新结果
                                        sentences = inner_sentences
                else:
                    logger.warning("结果没有output字段")
                    
                # 检查任务状态
                if result.status_code == 200:
                    logger.info("转写任务成功完成")
                    
                    # 从输出中提取sentences
                    sentences = []
                    if hasattr(result, 'output') and result.output:
                        # 直接在输出中查找
                        if 'sentences' in result.output:
                            sentences = result.output.get('sentences', [])
                        # 在results字段中查找
                        elif 'results' in result.output:
                            results = result.output.get('results', [])
                            if results and isinstance(results, list) and len(results) > 0:
                                first_result = results[0]
                                if isinstance(first_result, dict):
                                    # 打印first_result的所有键
                                    logger.info(f"results[0]包含键: {list(first_result.keys())}")
                                    if 'sentences' in first_result:
                                        sentences = first_result.get('sentences', [])
                                    elif 'text' in first_result:
                                        # 有些API返回格式可能是text字段而不是sentences
                                        logger.info(f"在text字段中寻找字幕")
                                        text = first_result.get('text', '')
                                        if text:
                                            # 将文本分割为句子，创建sentences格式
                                            segments = self._split_text_by_punctuation(text)
                                            for i, segment in enumerate(segments):
                                                if segment.strip():
                                                    sentences.append({
                                                        'text': segment.strip(),
                                                        'begin_time': i * 1000,  # 估计开始时间
                                                        'end_time': (i + 1) * 1000  # 估计结束时间
                                                    })
                                    # 检查是否有transcription_url
                                    elif 'transcription_url' in first_result:
                                        logger.info("发现转写结果URL，尝试下载字幕数据")
                                        transcription_url = first_result.get('transcription_url')
                                        if transcription_url:
                                            sentences = self._parse_transcription_url(transcription_url)
                        
                    # 打印找到的字幕数量
                    logger.info(f"找到字幕数量: {len(sentences)}")
                    
                    # 如果有字幕，打印前3条
                    for i, sentence in enumerate(sentences[:3]):
                        logger.info(f"字幕 {i+1}: {json.dumps(sentence, ensure_ascii=False)}")
                    
                    # 返回标准格式结果
                    return {
                        "status": "success",
                        "sentences": sentences,
                        "duration": result.output.get('duration', 0),
                        "task_id": task_id
                    }
                else:
                    error_code = result.code
                    error_message = result.message
                    logger.error(f"转写任务失败: {error_code} - {error_message}")
                    
                    return {
                        "status": "error",
                        "error_code": error_code,
                        "error_message": error_message,
                        "task_id": task_id
                    }
            except Exception as e:
                logger.exception(f"等待任务完成时出错: {str(e)}")
                
                # 改用手动轮询方式
                logger.info("使用轮询方式查询任务状态")
                
                max_retry = 60  # 最多轮询60次
                retry_interval = 10  # 每10秒查询一次
                
                for i in range(max_retry):
                    # 查询任务状态
                    logger.info(f"第 {i+1} 次查询任务状态")
                    query_response = Transcription.fetch(task_id)
                    
                    # 获取任务状态
                    task_status = query_response.output.get('task_status')
                    logger.info(f"任务状态: {task_status}")
                    
                    if task_status == "SUCCEEDED":
                        # 任务完成
                        logger.info("转写任务已完成")
                        
                        # 打印完整的输出结果（JSON格式）
                        logger.info(f"转写结果输出 (status_code={query_response.status_code}):")
                        if hasattr(query_response, 'output') and query_response.output:
                            logger.info(f"输出字段: {list(query_response.output.keys())}")
                        
                        # 计算耗时
                        elapsed_time = time.time() - start_time
                        logger.info(f"转写任务完成，耗时: {elapsed_time:.2f}秒")
                        
                        # 返回标准格式结果
                        return {
                            "status": "success",
                            "sentences": query_response.output.get('sentences', []),
                            "duration": query_response.output.get('duration', 0),
                            "task_id": task_id
                        }
                    elif task_status == "FAILED":
                        # 任务失败
                        error_code = query_response.code
                        error_message = query_response.message
                        logger.error(f"转写任务失败: {error_code} - {error_message}")
                        
                        return {
                            "status": "error",
                            "error_code": error_code,
                            "error_message": error_message,
                            "task_id": task_id
                        }
                    else:
                        # 任务仍在进行中，等待一段时间后再查询
                        time.sleep(retry_interval)
                
                # 超过最大重试次数
                logger.error("转写任务超时")
                return {
                    "status": "error",
                    "error": "任务超时",
                    "task_id": task_id
                }
                
        except Exception as e:
            logger.exception(f"转写音频文件时出错: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    def get_hot_words_list(self, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """
        获取热词表列表
        
        参数:
            page_index: 页码，从0开始
            page_size: 每页大小
            
        返回:
            热词表列表
        """
        if not SDK_AVAILABLE:
            return {
                "status": "error",
                "error": "DashScope SDK未安装，请使用pip install dashscope安装"
            }
            
        try:
            from dashscope.audio.asr.vocabulary import VocabularyManager
            
            logger.info(f"获取热词表列表: page_index={page_index}, page_size={page_size}")
            
            # 查询热词表列表
            response = VocabularyManager.list(page_index=page_index, page_size=page_size)
            
            # 检查响应
            if response.status_code == 200:
                vocabularies = response.output.get('vocabularies', [])
                logger.info(f"获取热词表列表成功，共 {len(vocabularies)} 个热词表")
                
                return {
                    "status": "success",
                    "vocabularies": vocabularies
                }
            else:
                error_code = response.code
                error_message = response.message
                logger.error(f"获取热词表列表失败: {error_code} - {error_message}")
                
                return {
                    "status": "error",
                    "error_code": error_code,
                    "error_message": error_message
                }
                
        except Exception as e:
            logger.exception(f"获取热词表列表时出错: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# 创建单例实例
dashscope_sdk = DashScopeSDKWrapper() 