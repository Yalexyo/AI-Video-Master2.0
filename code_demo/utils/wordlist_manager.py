#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
热词列表管理模块
--------------
提供热词列表管理功能，包括创建、查询、删除热词列表，
以及将热词应用于语音识别，提高特定词汇的识别准确率。

参考:
- 3_audio2srt_opt.py: 使用热词列表ID优化语音识别
- 1_Wordlist/create_wordlist.py: 创建热词列表
- 1_Wordlist/check_worklist.py: 查询热词列表
- 1_Wordlist/delete_wordlist.py: 删除热词列表
"""

import os
import sys
import json
import logging
import csv
import re
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wordlist_manager")

# 导入工具模块
from utils import config

class WordlistManager:
    """
    热词列表管理器类
    """
    def __init__(self):
        """
        初始化热词列表管理器
        """
        # 设置热词列表存储目录
        self.wordlist_dir = os.path.join(config.get_path('root_input_dir'), 'Wordlists')
        os.makedirs(self.wordlist_dir, exist_ok=True)
        
        # 默认热词列表前缀 (确保不超过10个字符)
        self.default_prefix = 'aivideo'
        
        # 默认目标模型
        self.default_model = 'paraformer-v3'
        
        # 已保存的热词ID
        self.saved_vocab_id_file = os.path.join(self.wordlist_dir, 'saved_vocabulary_ids.json')
        
        # 初始化dashscope相关类
        self._init_dashscope()
    
    def _init_dashscope(self):
        """
        初始化DashScope热词服务
        """
        self.api_key = None
        try:
            # 获取API密钥
            self.api_key = config.get_env('DASHSCOPE_API_KEY')
            if not self.api_key:
                logger.warning("未设置DASHSCOPE_API_KEY环境变量，热词功能将不可用")
                self.dashscope = None
                self.vocab_service = None
                return
                
            # 导入并初始化DashScope
            import dashscope
            from dashscope.audio.asr import VocabularyService
            
            dashscope.api_key = self.api_key
            self.dashscope = dashscope
            self.vocab_service = VocabularyService()
            logger.info("DashScope热词服务初始化成功")
        
        except ImportError:
            logger.warning("未安装dashscope库，热词功能将不可用")
            self.dashscope = None
            self.vocab_service = None
        except Exception as e:
            logger.error(f"初始化DashScope热词服务失败: {e}")
            self.dashscope = None
            self.vocab_service = None
    
    def check_service_available(self):
        """
        检查热词服务是否可用
        
        返回:
            成功返回True，否则返回False
        """
        if self.vocab_service is None:
            logger.error("热词服务不可用，请确保已安装dashscope库并设置API密钥")
            return False
        return True
    
    def list_vocabularies(self, prefix=None, page_index=0, page_size=10):
        """
        获取热词列表
        
        参数:
            prefix: 热词列表前缀
            page_index: 页码
            page_size: 每页大小
        
        返回:
            热词列表，如果服务不可用则返回空列表
        """
        if not self.check_service_available():
            return []
        
        try:
            # 直接使用VocabularyService的list_vocabularies方法
            vocabularies = self.vocab_service.list_vocabularies(
                prefix=prefix,  # 如果为None，则获取所有前缀的热词列表
                page_index=page_index,
                page_size=page_size
            )
            
            logger.info(f"成功获取热词列表，共 {len(vocabularies)} 个")
            return vocabularies
        
        except Exception as e:
            logger.error(f"获取热词列表失败: {e}")
            return []
    
    def query_vocabulary(self, vocabulary_id):
        """
        查询热词列表内容
        
        参数:
            vocabulary_id: 热词列表ID
        
        返回:
            热词列表内容，如果查询失败则返回None
        """
        if not self.check_service_available():
            return None
        
        try:
            # 直接使用VocabularyService的query_vocabulary方法
            vocabulary_content = self.vocab_service.query_vocabulary(vocabulary_id)
            
            # 检查返回内容
            if 'vocabulary' in vocabulary_content:
                logger.info(f"成功查询热词列表 {vocabulary_id}，共 {len(vocabulary_content['vocabulary'])} 个热词")
                return vocabulary_content
            else:
                logger.error(f"查询热词列表 {vocabulary_id} 返回格式异常")
                return None
        
        except Exception as e:
            logger.error(f"查询热词列表 {vocabulary_id} 失败: {e}")
            return None
    
    def determine_word_weight(self, word, dimension_level=None, word_type=None):
        """
        根据词语类型和维度级别确定权重
        
        参数:
            word: 词语文本
            dimension_level: 维度级别(1-3)
                1: 一级维度(对应权重4-5)
                2: 二级维度(对应权重3-4)
                3: 三级维度(对应权重1-2)
                None: 根据word_type或自动判断
            word_type: 词语类型
                'regular': 普通词/常规术语(轻度增强,权重1-2)
                'core': 重点词/产品功能(中度增强,权重3-4)
                'brand': 品牌词/专属命名(强度增强,权重4-5)
                'sensitive': 禁止词/敏感词(特殊处理)
                None: 自动判断
        
        返回:
            推荐的权重值(1-5)
        """
        # 如果指定了维度级别，优先使用维度级别确定权重范围
        if dimension_level is not None:
            if dimension_level == 1:  # 一级维度
                return 5  # 使用最高权重5
            elif dimension_level == 2:  # 二级维度
                return 4  # 中高权重4
            elif dimension_level == 3:  # 三级维度
                return 2  # 低权重2
        
        # 如果没有指定类型和级别，尝试自动判断词语类型
        if word_type is None:
            # 品牌词/专有名词特征: 大写字母开头英文、包含TM/®符号等，或长度为1的中文（可能是品牌单字）
            if (word[0].isupper() and all(c.isalpha() or c.isspace() for c in word)) or \
               any(mark in word for mark in ['®', '™', '©']) or \
               (len(word) == 1 and not all(ord(c) < 128 for c in word)):
                word_type = 'brand'
            # 敏感词特征: 包含特殊标记
            elif any(mark in word for mark in ['[敏感]', '[禁止]', '[纠错]']):
                word_type = 'sensitive'
            # 核心词特征: 含有特定关键词的组合
            elif any(key in word for key in ['功能', '特性', '核心', '技术', '专利']):
                word_type = 'core'
            # 普通词语特征: 较短的常见词语
            elif len(word) <= 2 and all(ord(c) < 128 for c in word):
                word_type = 'regular'
            # 默认为核心词
            else:
                word_type = 'core'
        
        # 根据词语类型确定权重
        if word_type == 'regular':  # 普通词/常规术语(轻度增强)
            return 2  # 权重范围1-2，取中值
        elif word_type == 'core':   # 重点词/产品功能(中度增强)
            return 4  # 权重范围3-4，取较高值
        elif word_type == 'brand':  # 品牌词/专属命名(强度增强)
            return 5  # 权重范围4-5，取最高值
        elif word_type == 'sensitive': # 禁止词/敏感词(特殊处理)
            return 5  # 敏感词使用最高权重
        else:
            return 4  # 默认使用中高权重
    
    def create_vocabulary(self, vocabulary, prefix=None, target_model=None):
        """
        创建热词列表
        
        参数:
            vocabulary: 热词列表内容，如[{"text": "热词", "weight": 4, "lang": "zh"}]
            prefix: 热词列表前缀 (不超过10个字符)
            target_model: 目标模型，如"paraformer-v3"
        
        返回:
            热词列表ID，如果创建失败则返回None
        """
        if not self.check_service_available():
            return None
        
        try:
            prefix = prefix or self.default_prefix
            target_model = target_model or self.default_model
            
            # 直接使用VocabularyService的create_vocabulary方法
            vocabulary_id = self.vocab_service.create_vocabulary(
                prefix=prefix,
                target_model=target_model,
                vocabulary=vocabulary
            )
            
            logger.info(f"成功创建热词列表，ID: {vocabulary_id}")
            
            # 保存热词ID
            self._save_vocabulary_id(vocabulary_id, prefix, target_model)
            
            return vocabulary_id
        
        except Exception as e:
            logger.error(f"创建热词列表失败: {e}")
            return None
    
    def delete_vocabulary(self, vocabulary_id):
        """
        删除热词列表
        
        参数:
            vocabulary_id: 热词列表ID
        
        返回:
            成功返回True，否则返回False
        """
        if not self.check_service_available():
            return False
        
        try:
            # 直接使用VocabularyService的delete_vocabulary方法
            self.vocab_service.delete_vocabulary(vocabulary_id)
            
            logger.info(f"成功删除热词列表 {vocabulary_id}")
            
            # 从保存的ID列表中移除
            self._remove_vocabulary_id(vocabulary_id)
            
            return True
        
        except Exception as e:
            logger.error(f"删除热词列表 {vocabulary_id} 失败: {e}")
            return False
    
    def _save_vocabulary_id(self, vocabulary_id, prefix, target_model):
        """
        保存热词列表ID到本地文件
        
        参数:
            vocabulary_id: 热词列表ID
            prefix: 热词列表前缀
            target_model: 目标模型
        """
        # 读取现有ID列表
        saved_ids = self._load_vocabulary_ids()
        
        # 添加新ID
        saved_ids.append({
            'vocabulary_id': vocabulary_id,
            'prefix': prefix,
            'target_model': target_model,
            'create_time': config.get_current_time_str()
        })
        
        # 保存更新后的ID列表
        try:
            with open(self.saved_vocab_id_file, 'w', encoding='utf-8') as f:
                json.dump(saved_ids, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存热词列表ID: {vocabulary_id}")
        
        except Exception as e:
            logger.error(f"保存热词列表ID失败: {e}")
    
    def _remove_vocabulary_id(self, vocabulary_id):
        """
        从保存的ID列表中移除热词列表ID
        
        参数:
            vocabulary_id: 热词列表ID
        """
        # 读取现有ID列表
        saved_ids = self._load_vocabulary_ids()
        
        # 移除指定ID
        saved_ids = [item for item in saved_ids if item.get('vocabulary_id') != vocabulary_id]
        
        # 保存更新后的ID列表
        try:
            with open(self.saved_vocab_id_file, 'w', encoding='utf-8') as f:
                json.dump(saved_ids, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已从保存列表中移除热词列表ID: {vocabulary_id}")
        
        except Exception as e:
            logger.error(f"移除热词列表ID失败: {e}")
    
    def _load_vocabulary_ids(self):
        """
        加载保存的热词列表ID
        
        返回:
            热词列表ID列表
        """
        if not os.path.exists(self.saved_vocab_id_file):
            return []
        
        try:
            with open(self.saved_vocab_id_file, 'r', encoding='utf-8') as f:
                saved_ids = json.load(f)
            
            return saved_ids
        
        except Exception as e:
            logger.error(f"加载热词列表ID失败: {e}")
            return []
    
    def get_latest_vocabulary_id(self, prefix=None, target_model=None):
        """
        获取最新的热词列表ID
        
        参数:
            prefix: 热词列表前缀
            target_model: 目标模型
        
        返回:
            最新的热词列表ID，如果没有则返回None
        """
        # 方法1: 从本地文件获取
        saved_ids = self._load_vocabulary_ids()
        
        if saved_ids:
            # 按前缀和模型筛选
            filtered_ids = saved_ids
            
            if prefix:
                filtered_ids = [item for item in filtered_ids if item.get('prefix') == prefix]
            
            if target_model:
                filtered_ids = [item for item in filtered_ids if item.get('target_model') == target_model]
            
            if filtered_ids:
                # 返回最后一个ID（最新的）
                return filtered_ids[-1].get('vocabulary_id')
        
        # 方法2: 从API获取
        if self.check_service_available():
            try:
                vocabularies = self.list_vocabularies(prefix=prefix)
                
                if vocabularies:
                    # 如果指定了目标模型，筛选匹配的模型
                    if target_model:
                        vocabularies = [item for item in vocabularies if item.get('target_model') == target_model]
                    
                    if vocabularies:
                        # 返回第一个ID
                        return vocabularies[0].get('vocabulary_id')
            
            except Exception as e:
                logger.error(f"获取最新热词列表ID失败: {e}")
        
        return None
    
    def create_vocabulary_from_file(self, file_path, lang='zh', weight=3, prefix=None, target_model=None):
        """
        从文件创建热词列表
        
        参数:
            file_path: 文件路径，支持txt或csv格式
            lang: 语言，zh或en
            weight: 权重
            prefix: 热词列表前缀
            target_model: 目标模型
        
        返回:
            热词列表ID，如果创建失败则返回None
        """
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
        
        vocabulary = []
        
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.txt':
                # 从文本文件读取，每行一个热词
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        text = line.strip()
                        if text:
                            # 简单判断语言
                            word_lang = 'en' if all(ord(c) < 128 for c in text) else lang
                            # 使用determine_word_weight方法确定权重
                            word_weight = self.determine_word_weight(text)
                            vocabulary.append({
                                'text': text,
                                'weight': word_weight,
                                'lang': word_lang
                            })
            
            elif file_ext == '.csv':
                # 从CSV文件读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    
                    # 查找列索引
                    text_idx = 0  # 默认第一列为文本
                    lang_idx = None
                    weight_idx = None
                    type_idx = None  # 词语类型列
                    
                    if header:
                        header_lower = [col.lower() for col in header]
                        
                        # 查找text/word/keyword列
                        for idx, col in enumerate(header_lower):
                            if col in ['text', 'word', 'keyword', '文本', '词语', '关键词']:
                                text_idx = idx
                                break
                        
                        # 查找lang/language列
                        for idx, col in enumerate(header_lower):
                            if col in ['lang', 'language', '语言']:
                                lang_idx = idx
                                break
                        
                        # 查找weight/权重列
                        for idx, col in enumerate(header_lower):
                            if col in ['weight', '权重']:
                                weight_idx = idx
                                break
                        
                        # 查找type/类型列
                        for idx, col in enumerate(header_lower):
                            if col in ['type', 'word_type', '类型', '词语类型']:
                                type_idx = idx
                                break
                    
                    # 读取数据行
                    for row in reader:
                        if not row or len(row) <= text_idx:
                            continue
                        
                        text = row[text_idx].strip()
                        if not text:
                            continue
                        
                        # 获取语言
                        word_lang = row[lang_idx] if lang_idx is not None and len(row) > lang_idx else None
                        if not word_lang:
                            # 简单判断语言
                            word_lang = 'en' if all(ord(c) < 128 for c in text) else lang
                        
                        # 获取类型
                        word_type = None
                        if type_idx is not None and len(row) > type_idx:
                            type_value = row[type_idx].lower().strip()
                            if type_value in ['regular', '普通', '常规']:
                                word_type = 'regular'
                            elif type_value in ['core', '核心', '重点']:
                                word_type = 'core'
                            elif type_value in ['brand', '品牌', '专属']:
                                word_type = 'brand'
                            elif type_value in ['sensitive', '敏感', '禁止']:
                                word_type = 'sensitive'
                        
                        # 获取权重
                        word_weight = None
                        if weight_idx is not None and len(row) > weight_idx:
                            try:
                                word_weight = float(row[weight_idx])
                            except:
                                pass
                        
                        # 如果没有指定权重，根据词语类型确定
                        if word_weight is None:
                            word_weight = self.determine_word_weight(text, word_type=word_type)
                        
                        vocabulary.append({
                            'text': text,
                            'weight': word_weight,
                            'lang': word_lang
                        })
            
            else:
                logger.error(f"不支持的文件格式: {file_ext}")
                return None
            
            # 创建热词列表
            if vocabulary:
                return self.create_vocabulary(vocabulary, prefix, target_model)
            else:
                logger.warning("没有从文件中提取到有效热词")
                return None
        
        except Exception as e:
            logger.error(f"从文件创建热词列表失败: {e}")
            return None
    
    def analyze_srt_with_hotwords(self, srt_file, vocabulary_id=None):
        """
        使用热词列表分析SRT文件，找出包含热词的字幕
        
        参数:
            srt_file: SRT文件路径
            vocabulary_id: 热词列表ID，如果为None则使用最新的
        
        返回:
            包含热词的字幕列表，每项包含编号、开始时间、结束时间和文本
        """
        if not os.path.exists(srt_file):
            logger.error(f"SRT文件不存在: {srt_file}")
            return []
        
        # 获取热词列表
        if vocabulary_id is None:
            vocabulary_id = self.get_latest_vocabulary_id()
        
        if vocabulary_id is None:
            logger.error("未找到可用的热词列表ID")
            return []
        
        # 查询热词列表内容
        vocabulary_content = self.query_vocabulary(vocabulary_id)
        
        if not vocabulary_content or 'vocabulary' not in vocabulary_content:
            logger.error(f"无法获取热词列表内容: {vocabulary_id}")
            return []
        
        # 提取热词文本
        hotwords = [item['text'] for item in vocabulary_content['vocabulary']]
        
        # 分析SRT文件
        results = []
        
        try:
            # 正则表达式匹配时间戳
            timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})')
            
            with open(srt_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 解析SRT文件
            i = 0
            while i < len(lines):
                # 匹配字幕编号
                if lines[i].strip().isdigit():
                    subtitle_number = int(lines[i].strip())
                    i += 1
                    
                    # 匹配时间戳
                    if i < len(lines):
                        match = timestamp_pattern.match(lines[i])
                        if match:
                            start_time, end_time = match.groups()
                            i += 1
                            
                            # 获取字幕文本
                            if i < len(lines):
                                subtitle_text = lines[i].strip()
                                i += 1
                                
                                # 检查每个热词是否在字幕文本中
                                for hotword in hotwords:
                                    if hotword in subtitle_text:
                                        result_entry = {
                                            "number": subtitle_number,
                                            "start_time": start_time,
                                            "end_time": end_time,
                                            "text": subtitle_text,
                                            "hotword": hotword
                                        }
                                        results.append(result_entry)
                                        break  # 一个字幕只记录一次，即使包含多个热词
                
                i += 1
            
            return results
        
        except Exception as e:
            logger.error(f"分析SRT文件失败: {e}")
            return []
    
    def save_hotword_matches_to_json(self, srt_file, output_file=None, vocabulary_id=None):
        """
        保存包含热词的字幕到JSON文件
        
        参数:
            srt_file: SRT文件路径
            output_file: 输出JSON文件路径，如果为None则使用与SRT同名的JSON文件
            vocabulary_id: 热词列表ID，如果为None则使用最新的
        
        返回:
            成功返回True，否则返回False
        """
        # 分析SRT文件
        results = self.analyze_srt_with_hotwords(srt_file, vocabulary_id)
        
        if not results:
            logger.warning(f"在SRT文件中未找到包含热词的字幕: {srt_file}")
            return False
        
        # 确定输出文件路径
        if output_file is None:
            output_file = os.path.splitext(srt_file)[0] + '_hotwords.json'
        
        try:
            # 保存到JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            
            logger.info(f"已保存热词匹配结果到: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"保存热词匹配结果失败: {e}")
            return False

    def get_term_frequency(self, text):
        """
        获取词语的使用频率，用于自动权重调整
        
        参数:
            text: 词语文本
        
        返回:
            使用频率值（模拟值，实际应从语料库统计）
        """
        # 在实际系统中，这里应该查询语料库或统计数据
        # 这里仅为示例，根据词长返回一个模拟频率
        return min(100, len(text) * 20)

    def update_vocabulary(self, vocabulary_id, new_vocabulary):
        """
        更新热词列表内容
        
        参数:
            vocabulary_id: 热词列表ID
            new_vocabulary: 新的热词列表内容
        
        返回:
            成功返回True，否则返回False
        """
        if not self.check_service_available():
            return False
            
        try:
            # 删除旧的热词列表
            if not self.delete_vocabulary(vocabulary_id):
                logger.error(f"删除旧热词列表失败: {vocabulary_id}")
                return False
                
            # 获取原有的前缀和模型
            saved_ids = self._load_vocabulary_ids()
            prefix = self.default_prefix
            target_model = self.default_model
            
            for item in saved_ids:
                if item.get('vocabulary_id') == vocabulary_id:
                    prefix = item.get('prefix', prefix)
                    target_model = item.get('target_model', target_model)
                    break
            
            # 创建新的热词列表
            new_id = self.create_vocabulary(new_vocabulary, prefix, target_model)
            
            if new_id:
                logger.info(f"成功更新热词列表: {vocabulary_id} -> {new_id}")
                return True
            else:
                logger.error(f"创建新热词列表失败")
                return False
                
        except Exception as e:
            logger.error(f"更新热词列表失败: {e}")
            return False

    def check_api_key(self):
        """
        检查 API Key 是否已配置并打印
        
        优先从环境变量 'DASHSCOPE_API_KEY' 读取，否则使用 dashscope.api_key 的值
        """
        api_key = self.api_key
        if api_key:
            logger.info(f"API Key 已配置: {api_key[:4]}...{api_key[-4:]}")
            return True
        else:
            logger.warning("API Key 未配置")
            return False


# 全局实例
_wordlist_manager = None

def get_manager():
    """
    获取热词列表管理器实例
    
    返回:
        WordlistManager实例
    """
    global _wordlist_manager
    
    if _wordlist_manager is None:
        _wordlist_manager = WordlistManager()
    
    return _wordlist_manager
