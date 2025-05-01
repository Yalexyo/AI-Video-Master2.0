import os
import json
import logging
from datetime import datetime
from src.core.hot_words_api import get_api

# 配置日志
logger = logging.getLogger(__name__)

# 热词文件路径
HOTWORDS_FILE = os.path.join('data', 'hotwords', 'hotwords.json')

class HotWordsService:
    """
    热词服务类
    连接API和本地存储，提供业务逻辑功能
    """
    def __init__(self):
        """初始化热词服务"""
        # 获取API实例
        self.api = get_api()
        
        # 确保热词目录存在
        os.makedirs(os.path.dirname(HOTWORDS_FILE), exist_ok=True)
    
    def load_hotwords(self):
        """
        加载热词列表
        
        返回:
            热词数据字典
        """
        if os.path.exists(HOTWORDS_FILE):
            try:
                with open(HOTWORDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载热词文件出错: {str(e)}")
                return self._get_empty_hotwords_data()
        else:
            return self._get_empty_hotwords_data()
    
    def _get_empty_hotwords_data(self):
        """返回空的热词数据结构"""
        return {
            'categories': {},  # 分类对应的热词列表
            'vocabulary_ids': {},  # 分类对应的热词表ID
            'last_updated': ''
        }
    
    def save_hotwords(self, hotwords_data):
        """
        保存热词列表
        
        参数:
            hotwords_data: 热词数据字典
            
        返回:
            保存成功返回True，失败返回False
        """
        try:
            # 更新最后修改时间
            hotwords_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 保存到文件
            with open(HOTWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(hotwords_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存热词文件出错: {str(e)}")
            return False
    
    def add_category(self, category_name):
        """
        添加热词分类
        
        参数:
            category_name: 分类名称
            
        返回:
            添加成功返回True，失败返回False
        """
        # 加载当前热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查分类是否已存在
        if category_name in hotwords_data['categories']:
            logger.warning(f"分类已存在: {category_name}")
            return False
        
        # 添加新分类
        hotwords_data['categories'][category_name] = []
        
        # 保存更新后的数据
        return self.save_hotwords(hotwords_data)
    
    def delete_category(self, category_name):
        """
        删除热词分类
        
        参数:
            category_name: 分类名称
            
        返回:
            删除成功返回True，失败返回False
        """
        # 加载当前热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查分类是否存在
        if category_name not in hotwords_data['categories']:
            logger.warning(f"分类不存在: {category_name}")
            return False
        
        # 删除分类
        del hotwords_data['categories'][category_name]
        
        # 删除对应的热词表ID
        if category_name in hotwords_data.get('vocabulary_ids', {}):
            del hotwords_data['vocabulary_ids'][category_name]
        
        # 保存更新后的数据
        return self.save_hotwords(hotwords_data)
    
    def add_hotword(self, category_name, hotword):
        """
        添加热词
        
        参数:
            category_name: 分类名称
            hotword: 热词文本
            
        返回:
            添加成功返回True，失败返回False
        """
        # 加载当前热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查分类是否存在
        if category_name not in hotwords_data['categories']:
            logger.error(f"分类不存在: {category_name}")
            return False
        
        # 检查热词是否已存在
        if hotword in hotwords_data['categories'][category_name]:
            logger.warning(f"热词已存在: {hotword}")
            return False
        
        # 添加热词
        hotwords_data['categories'][category_name].append(hotword)
        
        # 保存更新后的数据
        return self.save_hotwords(hotwords_data)
    
    def delete_hotword(self, category_name, hotword):
        """
        删除热词
        
        参数:
            category_name: 分类名称
            hotword: 热词文本
            
        返回:
            删除成功返回True，失败返回False
        """
        # 加载当前热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查分类是否存在
        if category_name not in hotwords_data['categories']:
            logger.error(f"分类不存在: {category_name}")
            return False
        
        # 检查热词是否存在
        if hotword not in hotwords_data['categories'][category_name]:
            logger.warning(f"热词不存在: {hotword}")
            return False
        
        # 删除热词
        hotwords_data['categories'][category_name].remove(hotword)
        
        # 保存更新后的数据
        return self.save_hotwords(hotwords_data)
    
    def batch_add_hotwords(self, category_name, hotwords):
        """
        批量添加热词
        
        参数:
            category_name: 分类名称
            hotwords: 热词列表
            
        返回:
            成功添加的热词数量
        """
        # 加载当前热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查分类是否存在
        if category_name not in hotwords_data['categories']:
            logger.error(f"分类不存在: {category_name}")
            return 0
        
        # 获取当前热词列表
        current_hotwords = set(hotwords_data['categories'][category_name])
        
        # 过滤出新热词
        new_hotwords = [hw for hw in hotwords if hw not in current_hotwords]
        
        if not new_hotwords:
            logger.info("没有新热词需要添加")
            return 0
        
        # 添加新热词
        hotwords_data['categories'][category_name].extend(new_hotwords)
        
        # 保存更新后的数据
        if self.save_hotwords(hotwords_data):
            return len(new_hotwords)
        else:
            return 0
    
    def check_cloud_hotwords(self):
        """
        检查阿里云上的热词表状态
        
        返回:
            (vocabularies, error_msg): 词表列表和错误信息(如果有)
        """
        # 检查API密钥
        if not self.api.check_api_key():
            # 检查.env文件是否存在
            env_path = '.env'
            if not os.path.exists(env_path):
                return None, "缺少.env文件，请在项目根目录创建.env文件并配置DASHSCOPE_API_KEY"
            
            # 检查.env文件内容
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    env_content = f.read()
                    if "DASHSCOPE_API_KEY" not in env_content:
                        return None, "API密钥未配置，请在.env文件中添加DASHSCOPE_API_KEY=sk-您的密钥"
                    if "DASHSCOPE_API_KEY=" in env_content and "sk-" not in env_content:
                        return None, "API密钥格式不正确，应以'sk-'开头，请检查.env文件"
            except Exception as e:
                logger.error(f"读取.env文件出错: {str(e)}")
                return None, "读取.env文件出错，请确保文件存在且有正确权限"
            
            return None, "API密钥验证失败，请检查.env文件中的DASHSCOPE_API_KEY设置"
        
        # 获取所有热词表
        try:
            vocabularies = self.api.list_all_vocabularies()
            
            if not vocabularies:
                return None, "未在阿里云上找到任何热词表"
                
            return vocabularies, None
        except Exception as e:
            logger.error(f"获取云端热词表失败: {str(e)}")
            return None, f"获取云端热词表失败: {str(e)}"
    
    def query_vocabulary(self, vocabulary_id):
        """
        查询云端热词表详情
        
        参数:
            vocabulary_id: 热词表ID
            
        返回:
            (success, vocab_details): 是否成功及热词表详情数据
        """
        # 检查API密钥
        if not self.api.check_api_key():
            return False, None
            
        try:
            # 调用API查询热词表详情
            vocab_details = self.api.query_vocabulary(vocabulary_id)
            
            if vocab_details:
                logger.info(f"成功获取热词表详情，ID: {vocabulary_id}")
                return True, vocab_details
            else:
                logger.error(f"无法获取热词表详情，ID: {vocabulary_id}")
                return False, None
                
        except Exception as e:
            error_msg = f"查询热词表详情时出错: {str(e)}"
            logger.error(error_msg)
            return False, None
        
    def delete_cloud_vocabulary(self, vocabulary_id):
        """
        直接删除云端热词表
        
        参数:
            vocabulary_id: 热词表ID
            
        返回:
            (success, message): 是否成功及相关消息
        """
        # 检查API密钥
        if not self.api.check_api_key():
            return False, "API密钥验证失败，请检查.env文件中的DASHSCOPE_API_KEY设置"
        
        try:
            # 调用API删除热词表
            if self.api.delete_vocabulary(vocabulary_id):
                # 删除成功后，检查本地是否有引用此ID的分类
                hotwords_data = self.load_hotwords()
                category_to_remove = None
                
                for category, vocab_id in hotwords_data.get('vocabulary_ids', {}).items():
                    if vocab_id == vocabulary_id:
                        category_to_remove = category
                        break
                
                if category_to_remove:
                    # 移除本地记录的ID
                    del hotwords_data['vocabulary_ids'][category_to_remove]
                    self.save_hotwords(hotwords_data)
                    logger.info(f"从本地记录中移除了热词表ID {vocabulary_id}，关联的分类为 {category_to_remove}")
                
                return True, f"成功删除云端热词表 {vocabulary_id}"
            else:
                return False, f"删除云端热词表 {vocabulary_id} 失败"
        except Exception as e:
            error_msg = f"删除云端热词表时出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
    def create_cloud_vocabulary(self, vocabulary, prefix=None, name=None, target_model=None):
        """
        创建云端热词表
        
        参数:
            vocabulary: 热词列表或热词表名称
            prefix: 自定义前缀（可选），不超过10个字符，仅支持小写字母和数字
            name: 热词表名称（可选）
            target_model: 目标模型，例如 "paraformer-v2"
            
        返回:
            (success, vocabulary_id, message): 成功状态、热词表ID和消息
        """
        # 默认目标模型
        if not target_model:
            target_model = 'paraformer-v2'
        logger.info(f"开始创建云端热词表，目标模型: {target_model}, 名称: {name}")
        
        # 处理参数顺序混淆的情况
        # 如果vocabulary是字符串且name是列表，则交换参数
        if isinstance(vocabulary, str) and isinstance(name, list):
            logger.info("检测到参数顺序混淆，自动调整参数")
            name, vocabulary = vocabulary, name
        # 如果vocabulary是字符串但未提供name，则将其作为name
        elif isinstance(vocabulary, str) and not name:
            logger.info("将第一个参数作为热词表名称")
            name, vocabulary = vocabulary, []
        
        # 处理前缀
        if not prefix:
            # 使用默认前缀
            prefix = 'aivideo'
        
        # 确保vocabulary是列表类型
        if vocabulary is None:
            vocabulary = []
        elif isinstance(vocabulary, str):
            # 如果传入的是单个字符串，转换为列表
            vocabulary = [vocabulary]
        elif not isinstance(vocabulary, list):
            try:
                # 尝试转换为列表
                vocabulary = list(vocabulary)
            except:
                logger.warning(f"无法将输入转换为列表: {type(vocabulary)}")
                vocabulary = []
        
        # 确保热词表格式正确并过滤无效项
        formatted_vocabulary = []
        for item in vocabulary:
            # 跳过None和空字符串
            if item is None or (isinstance(item, str) and not item.strip()):
                continue
            
            # 检查是否已经是格式化的热词项
            if isinstance(item, dict) and "text" in item:
                # 验证text字段
                text = item.get("text", "")
                if isinstance(text, str) and text.strip():
                    # 已经是正确格式，直接添加
                    formatted_vocabulary.append({
                        "text": text.strip(),
                        "weight": item.get("weight", 4),
                        "lang": item.get("lang", "zh")
                    })
                    continue
                    
            # 处理字符串类型
            if isinstance(item, str):
                clean_text = item.strip()
                if clean_text:  # 确保不是空字符串
                    formatted_vocabulary.append({
                        "text": clean_text,
                        "weight": 4,
                        "lang": "zh"
                    })
            else:
                # 尝试转换其他类型
                try:
                    text = str(item).strip()
                    if text:
                        formatted_vocabulary.append({
                            "text": text,
                            "weight": 4,
                            "lang": "zh"
                        })
                except:
                    logger.warning(f"无法转换热词项: {item}")
        
        # 记录处理前后的热词数量
        original_count = len(vocabulary) if isinstance(vocabulary, list) else 0
        formatted_count = len(formatted_vocabulary)
        logger.info(f"热词处理：原始数量 {original_count}，有效数量 {formatted_count}")
        
        # 输出热词详情便于调试
        if formatted_count > 0:
            logger.info(f"热词详情(前5个): {json.dumps(formatted_vocabulary[:5], ensure_ascii=False)}")
        
        if not formatted_vocabulary:
            error_msg = "没有有效的热词，请确保输入至少一个非空的热词"
            logger.error(error_msg)
            return False, None, error_msg
        
        # 检查API密钥
        if not self.api.check_api_key():
            error_msg = "API密钥验证失败，请检查环境变量DASHSCOPE_API_KEY设置"
            logger.error(error_msg)
            return False, None, error_msg
        
        # 调用API创建热词表
        try:
            logger.info(f"准备创建热词表: 名称={name}, 前缀={prefix}, 模型={target_model}, 热词数量={len(formatted_vocabulary)}")
            
            # 创建热词表
            vocab_id = self.api.create_vocabulary(
                vocabulary=formatted_vocabulary,
                prefix=prefix,
                target_model=target_model
            )
            
            if vocab_id:
                logger.info(f"云端热词表创建成功，ID: {vocab_id}")
                # 保存创建记录到本地
                self._add_vocabulary_to_local_record(name or "未命名热词表", vocab_id)
                return True, vocab_id, f"云端热词表创建成功，ID: {vocab_id}"
            else:
                error_msg = "创建云端热词表失败，API返回空ID"
                logger.error(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"创建云端热词表时发生错误: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def _add_vocabulary_to_local_record(self, category_name, vocabulary_id):
        """
        将创建的词汇表ID添加到本地记录
        
        参数:
            category_name: 分类名称
            vocabulary_id: 热词表ID
        """
        try:
            # 加载当前热词数据
            hotwords_data = self.load_hotwords()
            
            # 如果词汇表ID字典不存在，创建它
            if 'vocabulary_ids' not in hotwords_data:
                hotwords_data['vocabulary_ids'] = {}
            
            # 添加或更新词汇表ID记录
            hotwords_data['vocabulary_ids'][category_name] = vocabulary_id
            
            # 保存更新后的数据
            self.save_hotwords(hotwords_data)
            logger.info(f"已将热词表ID {vocabulary_id} 添加到本地记录，关联的分类为 {category_name}")
        except Exception as e:
            logger.error(f"将热词表ID添加到本地记录时出错: {str(e)}")

    def _ensure_default_category(self):
        """确保存在一个名为'default'的默认分类"""
        hotwords_data = self.load_hotwords()
        if 'default' not in hotwords_data['categories']:
            hotwords_data['categories']['default'] = []
            self.save_hotwords(hotwords_data)

    # ================================
    # 兼容简易热词接口（无分类）
    # ================================
    def list_hot_words(self):
        """返回所有热词的平铺列表，供旧版页面使用"""
        hotwords_data = self.load_hotwords()
        all_words = []
        for words in hotwords_data.get('categories', {}).values():
            all_words.extend(words)
        # 去重保持顺序
        return list(dict.fromkeys(all_words))

    def add_hot_word(self, word):
        """向默认分类添加热词，若不存在则创建默认分类"""
        self._ensure_default_category()
        return self.add_hotword('default', word)

    def delete_hot_word(self, word):
        """从任意分类中删除指定热词，找到第一个匹配即删除"""
        hotwords_data = self.load_hotwords()
        for category, words in hotwords_data.get('categories', {}).items():
            if word in words:
                # 使用现有方法删除
                return self.delete_hotword(category, word)
        logger.warning(f"热词不存在: {word}")
        return False

    def upload_hotwords_to_cloud(self, category_name):
        """
        将热词表上传到阿里云，获取vocabulary_id
        
        参数:
            category_name: 热词分类名称
            
        返回:
            成功返回vocabulary_id，失败返回None
        """
        try:
            # 加载热词数据
            hotwords_data = self.load_hotwords()
            
            # 检查分类是否存在
            if category_name not in hotwords_data['categories']:
                logger.error(f"上传热词表失败：分类不存在: {category_name}")
                return None
            
            # 获取分类下的热词列表
            hotwords = hotwords_data['categories'][category_name]
            
            # 如果热词列表为空，返回失败
            if not hotwords:
                logger.warning(f"上传热词表失败：分类 {category_name} 下没有热词")
                return None
            
            # 检查是否已经有vocabulary_id
            existing_id = hotwords_data.get('vocabulary_ids', {}).get(category_name)
            if existing_id:
                # 检查云端是否存在该vocabulary_id
                if self.check_vocabulary_exists(existing_id):
                    logger.info(f"热词表已存在于云端: {existing_id}")
                    return existing_id
            
            # 准备热词表数据，每行一个热词
            vocabulary = "\n".join(hotwords)
            
            # 生成名称
            name = f"{category_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 上传热词表到阿里云
            vocabulary_id = self.create_cloud_vocabulary(
                vocabulary=vocabulary,
                name=name,
                target_model='paraformer-v2'  # 指定目标模型
            )
            
            if vocabulary_id:
                # 保存vocabulary_id到本地记录
                self._add_vocabulary_to_local_record(category_name, vocabulary_id)
                logger.info(f"成功上传热词表到云端: {category_name} -> {vocabulary_id}")
                return vocabulary_id
            else:
                logger.error(f"上传热词表失败: {category_name}")
                return None
                
        except Exception as e:
            logger.error(f"上传热词表出错: {str(e)}")
            return None
    
    def check_vocabulary_exists(self, vocabulary_id):
        """
        检查热词表是否存在于云端
        
        参数:
            vocabulary_id: 热词表ID
            
        返回:
            存在返回True，不存在返回False
        """
        try:
            vocabulary_info = self.query_vocabulary(vocabulary_id)
            return vocabulary_info is not None
        except Exception as e:
            logger.error(f"检查热词表存在性出错: {str(e)}")
            return False
    
    def get_vocabulary_id(self, category_name):
        """
        获取分类对应的热词表ID，如果没有则上传创建
        
        参数:
            category_name: 分类名称
            
        返回:
            热词表ID，如果获取失败返回None
        """
        # 加载热词数据
        hotwords_data = self.load_hotwords()
        
        # 检查是否有记录的vocabulary_id
        vocabulary_id = hotwords_data.get('vocabulary_ids', {}).get(category_name)
        
        # 如果有记录的ID且在云端存在，直接返回
        if vocabulary_id and self.check_vocabulary_exists(vocabulary_id):
            return vocabulary_id
        
        # 否则上传创建新的热词表
        return self.upload_hotwords_to_cloud(category_name)
    
    def get_all_category_vocabulary_ids(self):
        """
        获取所有分类的热词表ID
        
        返回:
            分类名称到vocabulary_id的映射字典
        """
        # 加载热词数据
        hotwords_data = self.load_hotwords()
        
        # 获取所有分类
        categories = list(hotwords_data.get('categories', {}).keys())
        result = {}
        
        # 确保每个分类都有vocabulary_id
        for category in categories:
            vocabulary_id = self.get_vocabulary_id(category)
            if vocabulary_id:
                result[category] = vocabulary_id
        
        return result

# 单例模式
_service_instance = None

def get_service():
    """获取服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = HotWordsService()
    return _service_instance 