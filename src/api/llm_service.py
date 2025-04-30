import os
import json
import httpx
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class LLMService:
    """大语言模型服务，负责与OpenRouter API交互调用DeepSeek模型"""
    
    def __init__(self):
        # 从环境变量或配置获取API密钥
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "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")
        self.model = "deepseek/deepseek-v3-base:free"
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
    async def refine_intent_matching(self, 
                               selected_intent: Dict[str, Any], 
                               user_description: str, 
                               subtitles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        使用LLM精确匹配用户意图与字幕内容
        
        参数:
            selected_intent: 用户选择的大意图
            user_description: 用户输入的详细描述
            subtitles: 字幕列表，包含text和timestamp
            
        返回:
            匹配的字幕片段列表
        """
        try:
            # 准备提示词
            prompt = self._create_matching_prompt(selected_intent, user_description, subtitles)
            
            # 调用API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的视频内容分析助手，擅长找出与用户意图相关的视频片段。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # 低温度，保证输出稳定性
                "max_tokens": 1500
            }
            
            logger.info(f"发送请求到DeepSeek模型: {self.model}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                
            if response.status_code != 200:
                logger.error(f"DeepSeek API调用失败: {response.status_code} - {response.text}")
                return []
                
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 解析LLM返回的结果
            matched_segments = self._parse_matching_result(content)
            return matched_segments
            
        except Exception as e:
            logger.error(f"精确匹配过程出错: {str(e)}")
            return []
    
    def _create_matching_prompt(self, 
                               selected_intent: Dict[str, Any], 
                               user_description: str, 
                               subtitles: List[Dict[str, str]]) -> str:
        """创建匹配提示词"""
        
        # 将字幕文本合并（保留时间戳信息）
        subtitles_text = "\n".join([f"[{s['timestamp']}] {s['text']}" for s in subtitles])
        
        prompt = f"""
我需要你帮忙从视频字幕中找出与用户需求最相关的内容片段。

## 用户选择的意图
- 意图名称: {selected_intent['name']}
- 意图描述: {selected_intent['description']}
- 相关关键词: {', '.join(selected_intent['keywords'])}

## 用户的具体需求
"{user_description}"

## 视频字幕内容
{subtitles_text}

## 你的任务
1. 分析用户需求与视频字幕内容
2. 找出与用户需求最相关的核心字幕行
3. 同时提取该核心内容的前后文（至少前后各1-2句话），形成完整的上下文片段
4. 对于每个相关片段，给出相关性得分（0-100分）以及匹配理由
5. 只返回相关性得分高于70分的内容

## 返回格式
返回一个JSON格式的数组，每个元素包含以下字段：
- start_timestamp: 片段开始时间戳
- end_timestamp: 片段结束时间戳
- context: 完整的上下文文本（包含前因后果，3-5句连续对话）
- core_text: 核心匹配的文本
- score: 相关性得分（0-100）
- reason: 匹配理由

例如:
```json
[
  {{
    "start_timestamp": "00:01:20",
    "end_timestamp": "00:01:35",
    "context": "第三步就是看口碑，咱们给宝宝买奶粉主打一个不是错，这个时候呢口碑就特别重要了。启赋是在七年前就在香港推出了添加母乳低聚糖成分的奶粉。当时呢很多的富国妈妈富港生子喝的也都是启赋。",
    "core_text": "启赋是在七年前就在香港推出了添加母乳低聚糖成分的奶粉",
    "score": 95,
    "reason": "直接提到了HMO成分的历史，与用户查询的产品特性高度相关"
  }}
]
```

请确保返回的是有效的JSON格式，不要添加额外的说明。每个片段应包含足够的上下文，让用户理解完整的表达。
"""
        return prompt
        
    def _parse_matching_result(self, content: str) -> List[Dict[str, Any]]:
        """解析LLM返回的匹配结果"""
        try:
            # 提取JSON部分
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("无法从LLM响应中提取JSON格式的结果")
                return []
                
            json_str = content[start_idx:end_idx]
            matched_segments = json.loads(json_str)
            
            # 验证必要字段
            valid_segments = []
            for segment in matched_segments:
                if all(k in segment for k in ['start_timestamp', 'end_timestamp', 'context', 'core_text', 'score', 'reason']):
                    valid_segments.append(segment)
                else:
                    logger.warning(f"跳过不完整的匹配结果: {segment}")
            
            return valid_segments
            
        except Exception as e:
            logger.error(f"解析匹配结果失败: {str(e)}")
            return [] 