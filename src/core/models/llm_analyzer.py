import os
import json
import logging
import requests
from dashscope import Generation

logger = logging.getLogger(__name__)

class LLMScriptAnalyzer:
    """使用大语言模型进行脚本分析和生成的封装类"""
    
    def __init__(self, api_key=None, model_name="deepseek-v3"):
        """
        初始化LLM分析器
        
        Args:
            api_key: API密钥，默认从环境变量中获取
            model_name: 模型名称，默认使用DeepSeek-V3
        """
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        
        if not self.api_key:
            logger.warning("未提供API密钥，请设置DASHSCOPE_API_KEY环境变量")
        else:
            logger.info(f"初始化LLM分析器，使用模型: {model_name}")
    
    def _build_prompt(self, transcripts):
        """
        构建LLM提示词
        
        Args:
            transcripts: 所有视频的转录文本列表
            
        Returns:
            str: 格式化的提示词
        """
        prompt = """你是一位专业的视频内容分析专家，精通广告脚本结构分析。
任务：分析以下水奶产品广告视频文本，提炼出一个理想的脚本结构。

请识别这些视频中最常见的意图序列模式，并提取每种意图部分中最具代表性的名词关键词。

分析以下视频转录文本：

"""
        # 添加所有转录文本作为参考
        for i, transcript in enumerate(transcripts, 1):
            prompt += f"\n--- 视频 {i} 转录 ---\n{transcript}\n"
        
        prompt += """
基于上述视频转录内容，请提供：
1. 一个最优的意图序列（例如：问题引入→产品介绍→效果展示→促销信息）
2. 每种意图类型的代表性名词关键词列表

输出格式：
{
  "intent_sequence": ["意图1", "意图2", "意图3", ...],
  "intent_details": [
    {
      "intent_type": "意图1",
      "keywords": ["关键词1", "关键词2", ...]
    },
    {
      "intent_type": "意图2",
      "keywords": ["关键词1", "关键词2", ...]
    },
    ...
  ]
}

请直接以JSON格式输出，不要有额外的说明文字。"""
        
        return prompt
    
    def analyze_transcripts(self, transcripts):
        """
        分析多个视频转录文本，生成LLM抽象脚本
        
        Args:
            transcripts: 视频转录文本列表
            
        Returns:
            dict: LLM抽象脚本
        """
        if not self.api_key:
            logger.error("未提供API密钥，无法调用LLM服务")
            return None
        
        # 构建提示词
        prompt = self._build_prompt(transcripts)
        
        try:
            # 调用DashScope API
            response = Generation.call(
                model=self.model_name,
                prompt=prompt,
                api_key=self.api_key,
                result_format='message',  # 返回格式
                max_tokens=4096  # 最大输出token数
            )
            
            # 解析返回结果
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                logger.info("LLM分析完成")
                
                # 尝试解析JSON
                try:
                    result = json.loads(content)
                    return result
                except json.JSONDecodeError:
                    # 如果不是纯JSON格式，尝试提取JSON部分
                    import re
                    json_match = re.search(r'({[\s\S]*})', content)
                    if json_match:
                        try:
                            result = json.loads(json_match.group(1))
                            return result
                        except:
                            logger.error("无法解析LLM输出中的JSON部分")
                    else:
                        logger.error("LLM输出不包含有效的JSON格式")
            else:
                logger.error(f"LLM API调用失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"LLM分析过程出错: {str(e)}")
        
        return None
    
    def save_abstract_script(self, abstract_script, output_path):
        """
        保存LLM抽象脚本到文件
        
        Args:
            abstract_script: 抽象脚本对象
            output_path: 输出文件路径
        """
        if not abstract_script:
            logger.error("抽象脚本为空，无法保存")
            return
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(abstract_script, f, ensure_ascii=False, indent=2)
            logger.info(f"LLM抽象脚本已保存到 {output_path}")
        except Exception as e:
            logger.error(f"保存LLM抽象脚本失败: {str(e)}")
    
    def compare_scripts(self, bert_script, llm_script):
        """
        比较BERT和LLM生成的抽象脚本
        
        Args:
            bert_script: BERT生成的抽象脚本
            llm_script: LLM生成的抽象脚本
            
        Returns:
            dict: 比较结果
        """
        if not bert_script or not llm_script:
            logger.error("无法比较脚本，至少有一个脚本为空")
            return None
            
        # 比较意图序列
        bert_sequence = bert_script.get("intent_sequence", [])
        llm_sequence = llm_script.get("intent_sequence", [])
        
        sequence_match = len(bert_sequence) == len(llm_sequence)
        if sequence_match:
            for i, intent in enumerate(bert_sequence):
                if intent != llm_sequence[i]:
                    sequence_match = False
                    break
        
        # 比较关键词覆盖度
        keyword_overlap = {}
        
        bert_details = bert_script.get("intent_details", [])
        llm_details = llm_script.get("intent_details", [])
        
        bert_keywords_by_intent = {}
        for detail in bert_details:
            intent_type = detail.get("intent_type")
            keywords = set(detail.get("keywords", []))
            bert_keywords_by_intent[intent_type] = keywords
        
        llm_keywords_by_intent = {}
        for detail in llm_details:
            intent_type = detail.get("intent_type")
            keywords = set(detail.get("keywords", []))
            llm_keywords_by_intent[intent_type] = keywords
        
        # 计算每种意图类型的关键词重叠度
        all_intent_types = set(bert_keywords_by_intent.keys()) | set(llm_keywords_by_intent.keys())
        
        for intent_type in all_intent_types:
            bert_keywords = bert_keywords_by_intent.get(intent_type, set())
            llm_keywords = llm_keywords_by_intent.get(intent_type, set())
            
            if bert_keywords and llm_keywords:
                overlap = len(bert_keywords & llm_keywords)
                union = len(bert_keywords | llm_keywords)
                overlap_ratio = overlap / union if union > 0 else 0
                keyword_overlap[intent_type] = {
                    "overlap_ratio": overlap_ratio,
                    "common_keywords": list(bert_keywords & llm_keywords),
                    "bert_only": list(bert_keywords - llm_keywords),
                    "llm_only": list(llm_keywords - bert_keywords)
                }
        
        # 构建比较结果
        comparison = {
            "sequence_match": sequence_match,
            "bert_sequence": bert_sequence,
            "llm_sequence": llm_sequence,
            "keyword_overlap": keyword_overlap,
            "recommendation": "bert" if not sequence_match and len(bert_sequence) > len(llm_sequence) else "llm"
        }
        
        return comparison 