import os
import json
import logging
from datetime import datetime
import requests
import time
import re

# 配置日志
logger = logging.getLogger(__name__)

# 全局API实例
_api_instance = None

class HotWordsAPI:
    """
    热词API交互管理类
    提供热词列表的增删改查功能，与阿里云DashScope API交互
    """
    def __init__(self):
        """初始化热词API管理类"""
        # 从环境变量获取API密钥
        self.api_key = os.environ.get('DASHSCOPE_API_KEY', '')
        
        # 打印API密钥前后几位用于调试
        if self.api_key:
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "***"
            logger.info(f"API密钥已加载: {masked_key}")
        else:
            logger.warning("未找到DASHSCOPE_API_KEY环境变量")
        
        # 设置API基础URL
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/customization"
        
        # 设置默认参数
        self.default_prefix = 'aivideo'  # 热词列表前缀
        self.default_model = 'paraformer-v2'  # 默认目标模型
        
        # API调用限制相关设置
        self.last_api_call = 0  # 上次API调用时间戳
        self.min_api_interval = 0.5  # API调用最小间隔时间(秒)
        self.api_call_count = 0  # API调用计数
        self.api_call_reset_time = time.time()  # API调用计数重置时间
        self.max_api_calls_per_minute = 50  # 每分钟最大API调用次数
        
        # 检查API密钥
        if not self.api_key:
            logger.warning("未设置DASHSCOPE_API_KEY环境变量，热词功能将不可用")
    
    def _rate_limit(self):
        """
        实现API请求速率限制
        在每次API调用前调用此方法，必要时会自动等待
        """
        current_time = time.time()
        
        # 计算距离上次API调用的时间
        time_since_last_call = current_time - self.last_api_call
        
        # 如果时间间隔太短，等待补足
        if time_since_last_call < self.min_api_interval:
            sleep_time = self.min_api_interval - time_since_last_call
            logger.debug(f"API调用过于频繁，等待 {sleep_time:.2f} 秒")
            time.sleep(sleep_time)
        
        # 检查每分钟API调用次数限制
        if current_time - self.api_call_reset_time > 60:
            # 重置计数器
            self.api_call_count = 0
            self.api_call_reset_time = current_time
        
        # 增加API调用计数
        self.api_call_count += 1
        
        # 如果超过每分钟限制，等待
        if self.api_call_count > self.max_api_calls_per_minute:
            wait_time = 60 - (current_time - self.api_call_reset_time) + 1
            if wait_time > 0:
                logger.warning(f"API调用频率超过限制，等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
                # 重置计数器
                self.api_call_count = 1
                self.api_call_reset_time = time.time()
        
        # 更新上次调用时间
        self.last_api_call = time.time()
    
    def _make_api_request(self, data, action="API请求", max_retries=3, retry_delay=2):
        """
        通用API请求方法，包含重试逻辑和错误处理
        
        参数:
            data: API请求数据
            action: 操作名称，用于日志
            max_retries: 最大重试次数
            retry_delay: 重试间隔(秒)
            
        返回:
            (success, result, error_message): 是否成功、结果数据、错误信息
        """
        if not self.check_api_key():
            return False, None, "API密钥无效"
        
        # 应用速率限制
        self._rate_limit()
        
        # 准备请求头
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 记录API请求内容（脱敏）
        safe_data = json.loads(json.dumps(data))
        if 'vocabulary' in safe_data.get('input', {}):
            vocab_length = len(safe_data['input']['vocabulary'])
            # 只保留前2个热词项用于日志记录
            if vocab_length > 2:
                safe_data['input']['vocabulary'] = safe_data['input']['vocabulary'][:2] + [{"note": f"... 省略了 {vocab_length-2} 个热词 ..."}]
        
        try:
            logger.info(f"API请求数据: {json.dumps(safe_data, ensure_ascii=False)}")
        except:
            logger.info(f"API请求数据无法序列化记录")
        
        # 重试逻辑
        for retry in range(max_retries + 1):
            try:
                # 如果是重试，则等待
                if retry > 0:
                    wait_time = retry_delay * retry
                    logger.warning(f"{action}失败，第{retry}次重试，等待{wait_time}秒")
                    time.sleep(wait_time)
                
                # 发送请求
                response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
                
                # 处理常见错误状态码
                if response.status_code == 429:
                    # 请求频率限制错误，使用指数退避策略
                    wait_time = retry_delay * (2 ** retry)
                    logger.warning(f"API请求频率超限 (429)，等待{wait_time}秒后重试")
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code == 500:
                    # 服务器内部错误，记录详细信息
                    try:
                        error_detail = response.json()
                        error_msg = f"服务器内部错误 (500)，详情: {error_detail}"
                    except:
                        error_msg = f"服务器内部错误 (500)，响应内容: {response.text[:200]}"
                    
                    logger.warning(f"{error_msg}，等待{retry_delay * (2 ** retry)}秒后重试")
                    
                    # 对特定错误进行处理
                    if retry == max_retries:
                        return False, None, error_msg
                    
                    # 使用指数退避策略
                    wait_time = retry_delay * (2 ** retry)
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code == 401:
                    # 授权错误
                    return False, None, "API授权失败，请检查API密钥"
                    
                elif response.status_code == 400:
                    # 请求参数错误
                    try:
                        error_detail = response.json()
                        error_message = f"请求参数错误 (400)，详情: {error_detail}"
                    except:
                        error_message = f"请求参数错误 (400)，响应内容: {response.text[:200]}"
                    
                    logger.error(error_message)
                    return False, None, error_message
                
                # 检查其他HTTP错误
                try:
                    response.raise_for_status()
                except Exception as e:
                    if retry < max_retries:
                        logger.warning(f"HTTP错误 ({response.status_code}): {str(e)}，将重试")
                        continue
                    return False, None, f"HTTP错误 ({response.status_code}): {str(e)}"
                
                # 解析响应
                try:
                    result = response.json()
                    return True, result, None
                except Exception as e:
                    error_message = f"解析API响应失败: {str(e)}"
                    logger.error(error_message)
                    return False, None, error_message
                    
            except requests.exceptions.RequestException as e:
                if retry < max_retries:
                    logger.warning(f"请求异常: {str(e)}，将重试")
                    continue
                return False, None, f"网络请求异常: {str(e)}"
            
            except Exception as e:
                if retry < max_retries:
                    logger.warning(f"未知异常: {str(e)}，将重试")
                    continue
                return False, None, f"未知异常: {str(e)}"
        
        # 如果所有重试都失败
        return False, None, f"{action}失败，已达到最大重试次数{max_retries}"
    
    def check_api_key(self):
        """检查API密钥是否可用"""
        if not self.api_key:
            logger.error("未设置DASHSCOPE_API_KEY环境变量，请在.env文件中配置")
            return False
        
        if len(self.api_key.strip()) < 10 or not self.api_key.startswith("sk-"):
            logger.error(f"API密钥格式不正确，应以'sk-'开头且长度足够: {self.api_key[:4]}...")
            return False
        
        # 测试简单的API调用，验证API密钥是否有效
        try:
            # 发送列表请求测试连接
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "speech-biasing",
                "input": {
                    "action": "list_vocabulary",
                    "page_index": 0,
                    "page_size": 1
                }
            }
            
            # 添加超时，避免长时间等待
            response = requests.post(self.base_url, headers=headers, json=data, timeout=10)
            
            # 检查响应
            if response.status_code == 200:
                logger.info("API密钥有效，成功连接到阿里云")
                return True
            elif response.status_code == 401:
                logger.error(f"API密钥无效，认证失败 (401)，请检查密钥是否正确: {self.api_key[:4]}...")
                return False
            elif response.status_code == 429:
                logger.error(f"API调用频率超限 (429)，请稍后再试")
                return False
            else:
                try:
                    error_detail = response.json()
                    logger.error(f"API调用失败，状态码: {response.status_code}, 错误详情: {error_detail}")
                except:
                    logger.error(f"API调用失败，状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
        except requests.exceptions.Timeout:
            logger.error("API连接超时，请检查网络连接或稍后再试")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到API服务器，请检查网络连接")
            return False
        except Exception as e:
            logger.error(f"API连接测试出错: {str(e)}")
            return False
    
    def create_vocabulary(self, vocabulary, prefix=None, target_model=None, name=None):
        """
        创建热词表
        
        参数:
            vocabulary: 热词列表内容，例如：[{"text": "热词", "weight": 4, "lang": "zh"}]
            prefix: 热词表前缀，不超过10个字符，仅支持小写字母和数字
            target_model: 目标模型，例如 "paraformer-v2"
            name: 热词表名称，用于在UI中显示，可选参数
        
        返回:
            创建成功返回热词表ID，失败返回None
        """
        # 先尝试使用直接创建方法
        vocab_id = self.direct_create_vocabulary(vocabulary, prefix, target_model, name)
        if vocab_id:
            return vocab_id
            
        # 如果直接创建失败，回退到原始方法
        logger.warning("直接创建热词表失败，尝试使用原始方法")
        
        # 使用默认值
        prefix = prefix or self.default_prefix
        target_model = target_model or self.default_model
        
        # 确保前缀合法 - 只能包含小写字母和数字，且长度<=10
        if not re.match(r'^[a-z0-9]+$', prefix):
            logger.warning(f"前缀不合法: {prefix}，已替换为默认前缀")
            prefix = self.default_prefix
        
        if len(prefix) > 10:
            prefix = prefix[:10]
            logger.info(f"前缀超长，已截断为: {prefix}")
        
        # 确保vocabulary是列表 - 允许直接传入预格式化的热词
        if not isinstance(vocabulary, list):
            try:
                vocabulary = list(vocabulary)
            except:
                logger.error(f"热词参数无法转换为列表: {type(vocabulary)}")
                return None
                
        # 验证每个热词项格式
        valid_vocabulary = []
        for item in vocabulary:
            try:
                # 如果是字典并且包含text字段
                if isinstance(item, dict) and "text" in item:
                    text = item["text"]
                    if text and isinstance(text, str):
                        valid_item = {
                            "text": text.strip(),
                            "weight": item.get("weight", 4),
                            "lang": item.get("lang", "zh")
                        }
                        valid_vocabulary.append(valid_item)
                # 如果是字符串，直接转为标准格式
                elif isinstance(item, str) and item.strip():
                    valid_vocabulary.append({
                        "text": item.strip(),
                        "weight": 4,
                        "lang": "zh"
                    })
            except Exception as e:
                logger.warning(f"处理热词项错误: {str(e)}, item={item}")
                continue
        
        if not valid_vocabulary:
            logger.error("没有有效的热词")
            return None
            
        logger.info(f"最终准备热词数量: {len(valid_vocabulary)}")
        
        # 打印前几个热词用于调试
        sample = valid_vocabulary[:3]
        logger.info(f"热词示例: {json.dumps(sample, ensure_ascii=False)}")
        
        # 构建请求数据
        data = {
            "model": "speech-biasing",
            "input": {
                "action": "create_vocabulary",
                "target_model": target_model,
                "prefix": prefix,
                "vocabulary": valid_vocabulary
            }
        }
        
        # 如果提供了名称，添加到请求中
        if name:
            data["input"]["name"] = name
        
        # 尝试简化请求 - 如果词表太大可能导致服务器错误
        if len(valid_vocabulary) > 50:
            logger.warning(f"热词数量较多({len(valid_vocabulary)}个)，可能导致服务器负载过高")
            
            # 限制热词数量
            limited_vocabulary = valid_vocabulary[:50]
            data["input"]["vocabulary"] = limited_vocabulary
            logger.info(f"已将热词数量限制为50个以避免服务器错误")
        
        # 确保热词权重是整数而非浮点数
        for item in data["input"]["vocabulary"]:
            if "weight" in item and not isinstance(item["weight"], int):
                item["weight"] = int(item["weight"])
        
        # 记录完整请求，方便调试
        debug_data = json.loads(json.dumps(data))
        logger.info(f"创建热词表请求: {json.dumps(debug_data, ensure_ascii=False)}")
        
        # 发起请求，含基本重试
        success, result, error_msg = self._make_api_request(
            data=data, 
            action="创建热词表", 
            max_retries=2, 
            retry_delay=2
        )
        
        if not success:
            logger.error(f"创建热词表失败: {error_msg}")
            return None
        
        # 输出完整响应调试
        logger.info(f"创建热词表响应: {json.dumps(result, ensure_ascii=False)}")
        
        # 检查是否直接返回vocabulary_id
        if 'output' in result and 'vocabulary_id' in result['output']:
            vocab_id = result['output']['vocabulary_id']
            logger.info(f"热词表创建成功，ID: {vocab_id}")
            return vocab_id
        else:
            logger.error(f"响应格式异常，未找到vocabulary_id: {json.dumps(result, ensure_ascii=False)}")
            return None
    
    def direct_create_vocabulary(self, vocabulary, prefix=None, target_model=None, name=None):
        """
        使用直接API调用创建热词表，参考测试脚本的实现方式
        
        参数:
            vocabulary: 热词列表内容
            prefix: 热词表前缀
            target_model: 目标模型
            name: 热词表名称
            
        返回:
            创建成功返回热词表ID，失败返回None
        """
        if not self.check_api_key():
            logger.error("API密钥验证失败")
            return None
            
        # 使用默认值
        prefix = prefix or self.default_prefix
        target_model = target_model or self.default_model
        
        # 确保前缀合法
        if not re.match(r'^[a-z0-9]+$', prefix):
            logger.warning(f"前缀不合法: {prefix}，已替换为默认前缀")
            prefix = self.default_prefix
            
        if len(prefix) > 10:
            prefix = prefix[:10]
            logger.info(f"前缀超长，已截断为: {prefix}")
            
        # 确保vocabulary是有效列表
        valid_vocabulary = []
        
        # 处理列表
        if isinstance(vocabulary, list):
            for item in vocabulary:
                if isinstance(item, dict) and "text" in item and item["text"].strip():
                    # 确保weight是1-5之间的整数
                    weight = item.get("weight", 4)
                    if isinstance(weight, (int, float)):
                        weight = max(1, min(5, int(weight)))  # 限制在1-5范围内
                    else:
                        weight = 4  # 默认权重
                        
                    valid_item = {
                        "text": item["text"].strip(),
                        "weight": weight,
                        "lang": item.get("lang", "zh")
                    }
                    valid_vocabulary.append(valid_item)
                elif isinstance(item, str) and item.strip():
                    valid_vocabulary.append({
                        "text": item.strip(),
                        "weight": 4,
                        "lang": "zh"
                    })
        
        # 如果没有有效热词，返回失败
        if not valid_vocabulary:
            logger.error("没有有效的热词")
            return None
            
        # 取前50个词避免太多
        if len(valid_vocabulary) > 50:
            logger.warning(f"热词数量过多 ({len(valid_vocabulary)}个)，将只使用前50个")
            valid_vocabulary = valid_vocabulary[:50]
            
        logger.info(f"准备创建热词表: 前缀={prefix}, 模型={target_model}, 热词数量={len(valid_vocabulary)}")
        if len(valid_vocabulary) > 0:
            logger.info(f"热词示例: {json.dumps(valid_vocabulary[:3], ensure_ascii=False)}")
            
        # 构建请求
        payload = {
            "model": "speech-biasing",
            "input": {
                "action": "create_vocabulary",
                "target_model": target_model,
                "prefix": prefix,
                "vocabulary": valid_vocabulary
            }
        }
        
        # 添加名称如果有
        if name:
            payload["input"]["name"] = name
            
        # 发送请求
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"发送热词表创建请求: {json.dumps(payload, ensure_ascii=False)}")
            
            response = requests.post(
                self.base_url, 
                headers=headers, 
                json=payload,
                timeout=30  # 30秒超时
            )
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"创建热词表API请求失败: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    logger.error(f"响应内容: {response.text[:200]}")
                return None
                
            # 解析响应
            try:
                result = response.json()
                logger.info(f"创建热词表API响应: {json.dumps(result, ensure_ascii=False)}")
                
                # 提取vocabulary_id
                vocabulary_id = result.get("output", {}).get("vocabulary_id")
                if vocabulary_id:
                    logger.info(f"热词表创建成功，ID: {vocabulary_id}")
                    return vocabulary_id
                else:
                    logger.error("响应中未找到vocabulary_id")
                    return None
            except json.JSONDecodeError:
                logger.error(f"无法解析API响应为JSON: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"创建热词表过程中出错: {str(e)}")
            return None
    
    def list_vocabularies(self, prefix=None, page_index=0, page_size=10):
        """
        获取热词表列表
        
        参数:
            prefix: 热词表前缀过滤
            page_index: 页码，从0开始
            page_size: 每页数量，最大10
            
        返回:
            热词表列表，失败返回空列表
        """
        # 准备请求数据
        data = {
            "model": "speech-biasing",
            "input": {
                "action": "list_vocabulary",
                "prefix": prefix,
                "page_index": page_index,
                "page_size": page_size
            }
        }
        
        # 发送API请求
        action_desc = f"获取热词表列表(页码:{page_index})"
        success, result, error_msg = self._make_api_request(data, action=action_desc)
        
        if not success:
            logger.error(f"获取热词表列表失败: {error_msg}")
            return []
        
        # 检查响应
        if 'output' in result and 'vocabulary_list' in result['output']:
            vocabularies = result['output']['vocabulary_list']
            logger.info(f"成功获取热词表列表，共 {len(vocabularies)} 个")
            return vocabularies
        else:
            logger.error(f"获取热词表列表响应格式错误: {result}")
            return []
    
    def list_all_vocabularies(self, prefix=None):
        """
        获取所有热词表列表（自动分页）
        
        参数:
            prefix: 热词表前缀过滤
            
        返回:
            所有热词表列表，失败返回空列表
        """
        if not self.check_api_key():
            return []
            
        try:
            all_vocabularies = []
            page_index = 0
            page_size = 10
            
            while True:
                # 获取当前页热词表
                vocabularies = self.list_vocabularies(prefix, page_index, page_size)
                
                # 如果返回为空或出错，终止循环
                if not vocabularies:
                    break
                    
                # 添加到结果列表
                all_vocabularies.extend(vocabularies)
                
                # 如果当前页条数小于page_size，说明已经是最后一页
                if len(vocabularies) < page_size:
                    break
                    
                # 继续获取下一页
                page_index += 1
            
            logger.info(f"成功获取所有热词表，共 {len(all_vocabularies)} 个")
            
            # 获取每个热词表的详细信息
            detailed_vocabularies = []
            for vocab in all_vocabularies:
                vocab_id = vocab.get('vocabulary_id')
                if vocab_id:
                    # 获取热词表详情
                    vocab_detail = self.query_vocabulary(vocab_id)
                    if vocab_detail and 'vocabulary' in vocab_detail:
                        # 合并基本信息和词表内容
                        vocab['word_list'] = vocab_detail.get('vocabulary', [])
                        detailed_vocabularies.append(vocab)
            
            return detailed_vocabularies
                
        except Exception as e:
            logger.error(f"获取所有热词表出错: {str(e)}")
            return []
    
    def query_vocabulary(self, vocabulary_id):
        """
        查询热词表详情
        
        参数:
            vocabulary_id: 热词表ID
            
        返回:
            热词表详情，失败返回None
        """
        if not self.check_api_key():
            return None
            
        try:
            # 准备请求数据
            data = {
                "model": "speech-biasing",
                "input": {
                    "action": "query_vocabulary",
                    "vocabulary_id": vocabulary_id
                }
            }
            
            # 发送请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # 检查响应
            if 'output' in result and 'vocabulary' in result['output']:
                vocabulary = result['output']
                logger.info(f"成功查询热词表详情，ID: {vocabulary_id}")
                return vocabulary
            else:
                logger.error(f"查询热词表详情失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"查询热词表详情出错: {str(e)}")
            return None
    
    def update_vocabulary(self, vocabulary_id, vocabulary):
        """
        更新热词表内容
        
        参数:
            vocabulary_id: 热词表ID
            vocabulary: 新的热词列表内容
            
        返回:
            更新成功返回True，失败返回False
        """
        if not self.check_api_key():
            return False
            
        try:
            # 准备请求数据
            data = {
                "model": "speech-biasing",
                "input": {
                    "action": "update_vocabulary",
                    "vocabulary_id": vocabulary_id,
                    "vocabulary": vocabulary
                }
            }
            
            # 发送请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # 检查响应
            if 'output' in result:
                logger.info(f"热词表更新成功，ID: {vocabulary_id}")
                return True
            else:
                logger.error(f"热词表更新失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"更新热词表出错: {str(e)}")
            return False
    
    def delete_vocabulary(self, vocabulary_id):
        """
        删除热词表
        
        参数:
            vocabulary_id: 热词表ID
            
        返回:
            删除成功返回True，失败返回False
        """
        # 准备请求数据
        data = {
            "model": "speech-biasing",
            "input": {
                "action": "delete_vocabulary",
                "vocabulary_id": vocabulary_id
            }
        }
        
        # 发送API请求
        action_desc = f"删除热词表 {vocabulary_id}"
        success, result, error_msg = self._make_api_request(data, action=action_desc)
        
        if not success:
            logger.error(f"删除热词表失败: {error_msg}")
            return False
        
        # 检查响应
        if 'output' in result:
            logger.info(f"热词表删除成功，ID: {vocabulary_id}")
            return True
        else:
            logger.error(f"热词表删除响应格式错误: {result}")
            return False

def get_api():
    """获取API实例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = HotWordsAPI()
    return _api_instance

def create_env_file(api_key=None):
    """
    创建或更新.env文件
    
    参数:
        api_key: API密钥，如果为None则创建模板
    
    返回:
        (success, message): 是否成功和消息
    """
    try:
        # 检查是否有现有内容
        env_content = ""
        env_path = '.env'
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_content = f.read()
        
        # 如果没有提供API密钥，创建示例模板
        if not api_key:
            # 检查是否已有配置
            if "DASHSCOPE_API_KEY" in env_content and "sk-" in env_content:
                return True, "API密钥已配置，无需创建模板"
            
            # 创建示例模板
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("""# 阿里云DashScope API配置
# 请填入您的真实API密钥
# 格式为: sk-xxxxxxxxxxxx
DASHSCOPE_API_KEY=sk-填入您的实际密钥

# 其他配置（可选）
# DEBUG=True
""")
            return True, "已创建.env模板文件，请编辑填入实际API密钥"
        
        # 提供了API密钥，直接设置
        if not api_key.startswith("sk-"):
            return False, "API密钥格式不正确，应以'sk-'开头"
        
        # 更新现有内容或创建新文件
        if "DASHSCOPE_API_KEY=" in env_content:
            # 替换现有密钥
            new_content = re.sub(
                r'DASHSCOPE_API_KEY=.*', 
                f'DASHSCOPE_API_KEY={api_key}',
                env_content
            )
        else:
            # 添加新密钥
            new_content = env_content + f"\nDASHSCOPE_API_KEY={api_key}\n"
        
        # 写入文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True, "API密钥已成功保存到.env文件"
    
    except Exception as e:
        logger.error(f"创建.env文件出错: {str(e)}")
        return False, f"创建.env文件出错: {str(e)}" 