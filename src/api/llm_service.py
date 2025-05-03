import os
import json
import httpx
import logging
import re
from typing import Dict, Any, List, Optional, Literal

logger = logging.getLogger(__name__)

class LLMService:
    """大语言模型服务，支持DeepSeek官方API和OpenRouter API"""
    
    def __init__(self, provider: str = "deepseek"):
        """
        初始化LLM服务
        
        参数:
            provider: API提供商，可选值为 "deepseek" 或 "openrouter"
        """
        self.provider = provider.lower()
        
        # DeepSeek API配置
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.deepseek_model = "deepseek-chat"  # DeepSeek-V3
        self.deepseek_api_url = "https://api.deepseek.com/chat/completions"
        
        # OpenRouter API配置
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3-base:free") 
        self.openrouter_api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.http_referer = os.environ.get("HTTP_REFERER", "") 
        self.x_title = os.environ.get("X_TITLE", "")

        if self.provider == "deepseek" and not self.deepseek_api_key:
            logger.warning("未配置DeepSeek API Key，将无法使用DeepSeek官方API")
        elif self.provider == "openrouter" and not self.openrouter_api_key:
            logger.warning("未配置OpenRouter API Key，将无法使用OpenRouter API")
            
        logger.info(f"LLM服务初始化完成，使用 {self.provider} 提供商")
        if self.provider == "openrouter":
            logger.info(f"OpenRouter模型: {self.openrouter_model}")
        
    async def refine_intent_matching(self, 
                               user_description: str, 
                               subtitles: List[Dict[str, str]],
                               selected_intent: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        使用LLM优化意图匹配或执行自由文本匹配
        
        参数:
            user_description: 用户的具体需求描述
            subtitles: 字幕列表，每个元素包含'timestamp'和'text'
            selected_intent: 可选的用户选择的意图信息字典
        
        返回:
            匹配结果列表，每个元素包含时间戳、上下文、核心文本和分数
        """
        try:
            prompt = self._create_matching_prompt(
                selected_intent=selected_intent, 
                user_description=user_description, 
                subtitles=subtitles
            )
            
            content = None
            if self.provider == "deepseek":
                content = await self._call_deepseek_api(prompt)
            elif self.provider == "openrouter":
                content = await self._call_openrouter_api(prompt)
            else:
                raise ValueError(f"不支持的API提供商: {self.provider}")

            if content:
                return self._parse_matching_result(content)
            else:
                logger.error("LLM API调用失败，未返回任何内容")
                return []
                
        except Exception as e:
            logger.exception(f"LLM处理过程中发生错误: {str(e)}")
            return [{"error": f"LLM处理错误: {str(e)}"}] # 返回包含错误信息的列表

    async def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """调用DeepSeek官方API"""
        if not self.deepseek_api_key:
            logger.error("DeepSeek API Key未配置")
            return None
            
        # 确保prompt中包含"json"一词，以符合response_format=json_object的要求
        if "json" not in prompt.lower():
            prompt += "\n请以JSON格式返回结果。"
            
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "temperature": 0.1, # 设置较低温度以获取更确定的结果
            "max_tokens": 4096, # 根据需要调整
            "response_format": { "type": "json_object" } # 请求JSON格式输出
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client: # 增加超时时间
                logger.info(f"发送请求到DeepSeek模型: {self.deepseek_model}")
                response = await client.post(self.deepseek_api_url, headers=headers, json=data)
                response.raise_for_status() # 检查HTTP错误
                
                result = response.json()
                request_id = response.headers.get("request-id", "未知")
                logger.info(f"DeepSeek API请求ID: {request_id}")
                
                if "choices" in result and result["choices"]:
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"DeepSeek API调用成功，收到响应")
                    logger.debug(f"DeepSeek响应内容片段: {content[:200]}...")
                    return content
                else:
                    logger.error(f"DeepSeek API返回无效响应结构: {result}")
                    return None
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API请求失败，状态码: {e.response.status_code}")
            logger.error(f"DeepSeek API错误响应: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"连接DeepSeek API时出错: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"调用DeepSeek API时发生未知错误: {str(e)}")
            return None

    async def _call_openrouter_api(self, prompt: str) -> Optional[str]:
        """调用OpenRouter API"""
        if not self.openrouter_api_key:
            logger.error("OpenRouter API Key未配置")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        # 添加可选的HTTP头
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title

        data = {
            "model": self.openrouter_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": { "type": "json_object" } # 请求JSON格式输出
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info(f"发送请求到OpenRouter模型: {self.openrouter_model}")
                response = await client.post(self.openrouter_api_url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                request_id = response.headers.get("x-request-id", "未知")
                logger.info(f"OpenRouter API请求ID: {request_id}")
                
                if "choices" in result and result["choices"]:
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"OpenRouter API调用成功，收到响应")
                    logger.debug(f"OpenRouter响应内容片段: {content[:200]}...")
                    return content
                else:
                    logger.error(f"OpenRouter API返回无效响应结构: {result}")
                    return None
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API请求失败，状态码: {e.response.status_code}")
            logger.error(f"OpenRouter API错误响应: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"连接OpenRouter API时出错: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"调用OpenRouter API时发生未知错误: {str(e)}")
            return None

    def _create_matching_prompt(self, 
                               subtitles: List[Dict[str, str]],
                               user_description: str,
                               selected_intent: Optional[Dict[str, Any]] = None) -> str:
        """创建匹配提示词，支持有无预选意图两种模式"""
        
        # 将字幕文本合并（保留时间戳信息）
        subtitles_text = "\\n".join([f"[{s['timestamp']}] {s['text']}" for s in subtitles])
        
        # 构建基础提示词
        prompt_header = "我需要你帮忙从视频字幕中找出与用户需求最相关的内容片段。"
        
        # 根据是否有预选意图添加不同信息
        if selected_intent:
            intent_info = f"""
## 用户选择的意图
- 意图名称: {selected_intent['name']}
- 意图描述: {selected_intent['description']}
- 相关关键词: {', '.join(selected_intent['keywords'])}
"""
        else:
            intent_info = "" # 模式2没有预选意图信息

        user_need_section = f"""
## 用户的具体需求
"{user_description}"
"""
        
        subtitles_section = f"""
## 视频字幕内容
{subtitles_text}
"""

        task_description = f"""
## 你的任务
1. 分析用户需求与视频字幕内容
2. 找出与用户需求最相关的字幕片段
3. 从字幕中提取完整的上下文，确保能理解片段的完整含义
4. 只返回相关性得分高于60分的内容 (分数范围0-100)
5. 结果必须严格按照JSON格式返回
"""

        # 调整返回格式说明，移除旧的70分要求
        return_format = """
## 返回格式
你必须且只能返回一个JSON数组，不要有任何额外的解释文字。格式如下：
[
  {
    "start_timestamp": "00:01:20",  // 片段开始时间
    "end_timestamp": "00:01:35",    // 片段结束时间
    "context": "完整的上下文文本...", // 包含核心内容，并能独立理解的完整上下文
    "core_text": "核心匹配的文本...", // 最能体现用户需求的核心语句
    "score": 95                     // 相关性评分 (0-100)
  }
]
"""

        strict_requirements = """
## 严格要求
1. 你的回复必须是一个有效的JSON数组，前后不能有任何额外文字
2. 数组中的每个对象必须包含所有需要的字段: start_timestamp, end_timestamp, context, core_text, score
3. score必须是一个整数 (0-100)
4. 返回的JSON必须包含在```json```代码块中 (如果API本身不支持JSON模式，请添加)

示例回复:
```json
[
  {
    "start_timestamp": "00:01:20",
    "end_timestamp": "00:01:35",
    "context": "这里是关于HMO如何支持宝宝免疫力的完整段落...",
    "core_text": "HMO有助于建立强大的免疫系统。",
    "score": 95
  }
]
```

如果没有找到相关内容（得分低于60），请返回空数组:
```json
[]
```
"""
        # 组合完整的Prompt
        prompt = (
            prompt_header + 
            intent_info + 
            user_need_section + 
            subtitles_section + 
            task_description + 
            return_format + 
            strict_requirements
        )
        
        # 记录生成的prompt用于调试（只记录部分）
        logger.debug(f"生成的LLM Prompt (部分): {prompt[:300]}...")
        return prompt
        
    def _parse_matching_result(self, content: str) -> List[Dict[str, Any]]:
        """解析LLM返回的匹配结果"""
        try:
            # 完整记录接收到的内容，用于调试
            logger.debug(f"开始解析LLM响应内容: {content[:500]}...")
            
            # 第一步：去除可能的markdown格式，获取纯JSON内容
            json_str = self._extract_json_from_response(content)
            if not json_str:
                logger.error("无法从LLM响应中提取JSON内容")
                logger.error(f"LLM原始返回内容 (片段): {content[:1000]}")
                # 返回错误信息，而不是抛出异常，让上层处理
                return [{"error": "LLM返回的内容中未找到有效的JSON结构"}]
            
            logger.debug(f"提取到的JSON字符串 (片段): {json_str[:500]}...")
            
            # 第二步：解析JSON
            try:
                matched_segments = json.loads(json_str)
                # logger.info(f"JSON解析成功，获取到 {len(matched_segments) if isinstance(matched_segments, list) else '非列表'} 类型数据")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {str(e)}，尝试格式修正")
                json_str = self._fix_json_format(json_str)
                try:
                    matched_segments = json.loads(json_str)
                    logger.info(f"格式修正后JSON解析成功")
                except json.JSONDecodeError as e2:
                    logger.error(f"格式修正后JSON仍解析失败: {str(e2)}")
                    logger.error(f"尝试解析的JSON字符串 (片段): {json_str[:500]}")
                    return [{"error": f"无法解析LLM返回的JSON格式: {str(e2)}"}]
            
            # 第三步：验证结果格式
            if not isinstance(matched_segments, list):
                logger.error(f"LLM返回的不是JSON数组，而是: {type(matched_segments)}")
                return [{"error": "LLM返回的不是JSON数组"}]
                
            # 处理空数组的情况 - 表示未找到匹配
            if not matched_segments:
                logger.info("LLM返回了空数组，表示未找到匹配内容")
                return []
                
            # 第四步：验证和规范化每个片段
            valid_segments = []
            for i, segment in enumerate(matched_segments):
                if not isinstance(segment, dict):
                    logger.warning(f"跳过第 {i+1} 个非字典类型的片段: {str(segment)[:100]}...")
                    continue
                    
                # 检查必要字段
                required_fields = ['start_timestamp', 'end_timestamp', 'context', 'core_text', 'score']
                missing_fields = [field for field in required_fields if field not in segment]
                
                if missing_fields:
                    logger.warning(f"跳过第 {i+1} 个缺少必要字段的片段: 缺少 {', '.join(missing_fields)}. 片段内容: {str(segment)[:100]}...")
                    continue
                
                # 确保score是数字，且在0-100之间
                try:
                    score_value = segment['score']
                    if isinstance(score_value, str):
                        # 尝试从字符串中提取数字
                        score_match = re.search(r'\d+', score_value)
                        if score_match:
                            segment['score'] = int(score_match.group())
                        else:
                            segment['score'] = 0 # 无法提取则认为0分
                    elif not isinstance(score_value, (int, float)):
                         segment['score'] = 0 # 非数字类型认为0分
                    
                    # 转换为整数并确保在范围内
                    segment['score'] = max(0, min(100, int(segment['score'])))

                except Exception as e:
                    logger.warning(f"处理第 {i+1} 个片段分数时出错: {str(e)}，使用默认分数0. 片段内容: {str(segment)[:100]}...")
                    segment['score'] = 0
                
                valid_segments.append(segment)
            
            logger.info(f"原始匹配到 {len(matched_segments)} 个片段，验证后得到 {len(valid_segments)} 个有效片段")
            return valid_segments
            
        except Exception as e:
            # 捕获所有可能的解析错误
            logger.exception(f"解析LLM匹配结果时发生严重错误: {str(e)}")
            # 返回包含错误信息的列表
            return [{"error": f"LLM结果解析错误: {str(e)}"}]
    
    def _extract_json_from_response(self, content: str) -> str:
        """从LLM响应中提取JSON内容"""
        try:
            # 1. 检查API是否直接返回了JSON对象（DeepSeek JSON mode）
            # 尝试直接解析整个内容
            try:
                json.loads(content)
                logger.info("LLM响应本身即为有效JSON，直接返回")
                return content.strip()
            except json.JSONDecodeError:
                # 不是纯JSON，继续查找
                pass 

            # 2. 尝试查找代码块中的JSON
            # 调整模式以匹配可能的前缀和后缀文本
            json_pattern = r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```'
            matches = re.search(json_pattern, content, re.DOTALL)
            
            if matches:
                json_str = matches.group(1)
                logger.info("成功从LLM响应中提取代码块中的JSON内容")
                return json_str.strip()
                
            # 3. 尝试直接查找JSON数组 (更宽松)
            # 寻找从 '[' 开始到最后 ']' 结束的最外层数组
            start_bracket = content.find('[')
            end_bracket = content.rfind(']')
            if start_bracket != -1 and end_bracket > start_bracket:
                 potential_json = content[start_bracket:end_bracket+1]
                 # 做一个简单的验证，看是否像JSON数组
                 if potential_json.strip().startswith('[') and potential_json.strip().endswith(']'):
                     try:
                         # 尝试解析验证一下
                         json.loads(potential_json)
                         logger.info("从LLM响应中直接提取看起来像JSON数组的内容")
                         return potential_json.strip()
                     except json.JSONDecodeError:
                         logger.debug("直接提取的数组内容JSON解析失败，继续尝试其他方法")
                         pass # 解析失败，继续

            # 4. 尝试直接查找JSON对象 (更宽松)
            start_curly = content.find('{')
            end_curly = content.rfind('}')
            if start_curly != -1 and end_curly > start_curly:
                potential_json = content[start_curly:end_curly+1]
                # 做一个简单的验证，看是否像JSON对象
                if potential_json.strip().startswith('{') and potential_json.strip().endswith('}'):
                    try:
                        # 尝试解析验证一下
                        json.loads(potential_json)
                        logger.info("从LLM响应中直接提取看起来像JSON对象的内容")
                        return potential_json.strip()
                    except json.JSONDecodeError:
                        logger.debug("直接提取的对象内容JSON解析失败，继续尝试其他方法")
                        pass # 解析失败，继续
            
            # 如果所有方法都失败
            logger.warning("无法在LLM响应中明确找到JSON代码块或结构化的JSON数组/对象")
            # 作为最后的尝试，返回原始content，让上层解析器处理
            return content.strip() 
            
        except Exception as e:
            logger.exception(f"提取JSON时发生异常: {str(e)}")
            return "" # 提取失败返回空字符串

    def _fix_json_format(self, json_str: str) -> str:
        """尝试修复常见的JSON格式错误"""
        # 移除末尾多余的逗号 (常见于列表或对象末尾)
        fixed_str = re.sub(r",\s*([\]\}])", r"\1", json_str)
        
        # 可以在这里添加更多修复规则，例如处理单引号、缺失引号等
        # ...
        
        if fixed_str != json_str:
            logger.info("尝试修复JSON格式：移除了末尾多余的逗号")
            
        return fixed_str 