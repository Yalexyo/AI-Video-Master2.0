import aiohttp
import json
import re
import os
import logging

logger = logging.getLogger(__name__)

class AnalyzeService:
    async def analyze_with_deepseek(self, prompt, api_key=None):
        """使用DeepSeek API分析内容"""
        try:
            # 使用环境变量中的API密钥，或者使用传入的密钥
            api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "message": "DeepSeek API密钥未设置",
                    "data": None
                }
            
            # 确保提示中包含"json"关键词，满足response_format的要求
            if "json" not in prompt.lower():
                prompt = f"{prompt}\n\n请务必以JSON格式返回结果。"
            
            # 准备请求参数
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            
            # 记录请求开始
            logger.info(f"开始请求DeepSeek API")
            
            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60  # 增加超时时间
                ) as response:
                    response_json = await response.json()
                    
                    # 记录响应
                    logger.info(f"DeepSeek API响应状态码: {response.status}")
                    
                    if response.status == 200:
                        content = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        # 尝试解析JSON内容
                        try:
                            analysis_result = json.loads(content)
                            logger.info(f"成功解析DeepSeek返回的JSON内容")
                            
                            return {
                                "success": True,
                                "message": "分析成功",
                                "data": analysis_result
                            }
                        except json.JSONDecodeError as json_err:
                            logger.error(f"DeepSeek返回内容不是有效的JSON: {str(json_err)}")
                            # 尝试从文本中提取JSON部分
                            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
                            if json_match:
                                try:
                                    json_content = json_match.group(1).strip()
                                    analysis_result = json.loads(json_content)
                                    logger.info("成功从代码块中提取并解析JSON")
                                    
                                    return {
                                        "success": True,
                                        "message": "分析成功（从代码块中提取JSON）",
                                        "data": analysis_result
                                    }
                                except Exception as e:
                                    logger.error(f"从代码块中提取JSON失败: {str(e)}")
                            
                            return {
                                "success": False,
                                "message": f"DeepSeek返回内容不是有效的JSON: {content[:100]}...",
                                "data": content
                            }
                    else:
                        error_message = response_json.get("error", {}).get("message", "未知错误")
                        logger.error(f"DeepSeek API请求失败: {error_message}")
                        
                        return {
                            "success": False,
                            "message": f"DeepSeek API请求失败: {error_message}",
                            "data": None
                        }
                
        except aiohttp.ClientError as e:
            logger.error(f"DeepSeek API请求网络错误: {str(e)}")
            return {
                "success": False,
                "message": f"DeepSeek API请求网络错误: {str(e)}",
                "data": None
            }
        except Exception as e:
            logger.exception(f"DeepSeek API分析异常: {str(e)}")
            return {
                "success": False,
                "message": f"DeepSeek API分析异常: {str(e)}",
                "data": None
            } 