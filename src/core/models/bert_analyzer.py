import os
import json
import torch
import numpy as np
from transformers import BertTokenizer, BertModel, BertForSequenceClassification
from collections import Counter
import jieba
import logging

logger = logging.getLogger(__name__)

class BertIntentAnalyzer:
    """使用BERT模型进行意图分析和关键词提取的封装类"""
    
    # 意图类型映射
    INTENT_TYPES = {
        0: "问题引入",
        1: "产品介绍",
        2: "效果展示",
        3: "促销信息"
    }
    
    def __init__(self, model_path=None):
        """
        初始化BERT意图分析器
        
        Args:
            model_path: BERT模型路径，默认使用项目中的中文BERT模型
        """
        if model_path is None:
            model_path = "data/models/bert/chinese-bert-wwm-ext"
        
        logger.info(f"初始化BERT分析器，模型路径: {model_path}")
        
        try:
            self.tokenizer = BertTokenizer.from_pretrained(model_path)
            # 意图分类模型 - 假设已经在相同路径下微调了意图分类模型
            self.intent_model = BertForSequenceClassification.from_pretrained(
                model_path, 
                num_labels=len(self.INTENT_TYPES)
            )
            # 用于语义表示的基础BERT模型
            self.bert_model = BertModel.from_pretrained(model_path)
            
            # 将模型设置为评估模式
            self.intent_model.eval()
            self.bert_model.eval()
            
            logger.info("BERT模型加载成功")
        except Exception as e:
            logger.error(f"BERT模型加载失败: {str(e)}")
            raise
    
    def analyze_intent(self, text):
        """
        分析文本的意图类型
        
        Args:
            text: 要分析的文本
            
        Returns:
            intent_type: 意图类型字符串
            confidence: 置信度
        """
        try:
            # 对文本进行编码
            inputs = self.tokenizer(
                text, 
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # 获取模型输出
            with torch.no_grad():
                outputs = self.intent_model(**inputs)
            
            # 获取预测结果
            logits = outputs.logits
            predictions = torch.softmax(logits, dim=1)
            intent_id = torch.argmax(predictions, dim=1).item()
            confidence = predictions[0][intent_id].item()
            
            intent_type = self.INTENT_TYPES.get(intent_id, "未知意图")
            return intent_type, confidence
            
        except Exception as e:
            logger.error(f"意图分析失败: {str(e)}")
            return "未知意图", 0.0
    
    def extract_keywords(self, text, top_n=10):
        """
        从文本中提取名词关键词
        
        Args:
            text: 要分析的文本
            top_n: 返回的关键词数量
            
        Returns:
            list: 关键词列表
        """
        # 使用jieba进行分词和词性标注
        import jieba.posseg as pseg
        words = pseg.cut(text)
        
        # 筛选名词 (n开头的词性)
        nouns = [word for word, flag in words if flag.startswith('n')]
        
        # 统计词频
        counter = Counter(nouns)
        
        # 返回出现频率最高的top_n个名词
        return [word for word, _ in counter.most_common(top_n)]
    
    def analyze_transcript(self, transcript_json):
        """
        分析转录文本，提取每个段落的意图和关键词
        
        Args:
            transcript_json: 转录文本JSON对象
            
        Returns:
            list: 分析结果列表，每个元素包含段落文本、意图类型和关键词
        """
        results = []
        
        # 根据转录JSON的具体结构进行处理
        # 这里假设transcript_json有一个segments字段，包含多个文本段落
        segments = transcript_json.get("segments", [])
        
        for segment in segments:
            text = segment.get("text", "")
            if not text.strip():
                continue
                
            # 分析意图
            intent_type, confidence = self.analyze_intent(text)
            
            # 提取关键词
            keywords = self.extract_keywords(text)
            
            # 保存结果
            results.append({
                "text": text,
                "start_time": segment.get("start", 0),
                "end_time": segment.get("end", 0),
                "intent_type": intent_type,
                "confidence": confidence,
                "keywords": keywords
            })
        
        return results
    
    def generate_abstract_script(self, video_analyses):
        """
        生成BERT抽象脚本
        
        Args:
            video_analyses: 多个视频的分析结果列表
            
        Returns:
            dict: 抽象脚本 {意图序列: [{意图类型: str, 关键词: list}, ...]}
        """
        # 统计所有视频中意图序列的出现频率
        all_intent_sequences = []
        
        for video_analysis in video_analyses:
            # 提取当前视频的意图序列
            intent_sequence = [segment["intent_type"] for segment in video_analysis]
            all_intent_sequences.append(tuple(intent_sequence))
        
        # 找出最频繁的意图序列
        counter = Counter(all_intent_sequences)
        most_common_sequence = counter.most_common(1)[0][0]
        
        # 按意图类型合并关键词
        intent_keywords = {intent_type: [] for intent_type in self.INTENT_TYPES.values()}
        
        for video_analysis in video_analyses:
            for segment in video_analysis:
                intent_type = segment["intent_type"]
                keywords = segment["keywords"]
                intent_keywords[intent_type].extend(keywords)
        
        # 去重关键词
        for intent_type in intent_keywords:
            intent_keywords[intent_type] = list(set(intent_keywords[intent_type]))
        
        # 构建抽象脚本
        abstract_script = {
            "intent_sequence": list(most_common_sequence),
            "intent_details": []
        }
        
        for intent_type in most_common_sequence:
            abstract_script["intent_details"].append({
                "intent_type": intent_type,
                "keywords": intent_keywords[intent_type]
            })
        
        return abstract_script
    
    def save_abstract_script(self, abstract_script, output_path):
        """
        保存抽象脚本到文件
        
        Args:
            abstract_script: 抽象脚本对象
            output_path: 输出文件路径
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(abstract_script, f, ensure_ascii=False, indent=2)
            logger.info(f"BERT抽象脚本已保存到 {output_path}")
        except Exception as e:
            logger.error(f"保存BERT抽象脚本失败: {str(e)}") 