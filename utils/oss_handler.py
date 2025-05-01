import os
import logging
import uuid
import urllib.parse
import time
from typing import Dict, Optional, Any, Tuple
from pathlib import Path

try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    logging.warning("未安装oss2库，OSS功能将不可用。请执行: pip install oss2")

from utils.config_handler import ConfigHandler

logger = logging.getLogger(__name__)

class OssHandler:
    """
    OSS操作处理类
    
    负责文件上传和URL生成，支持从配置字典、配置文件或环境变量读取配置
    
    使用方法:
    ```python
    # 从环境变量初始化
    oss_handler = OssHandler()
    
    # 从配置文件初始化
    oss_handler = OssHandler(config_path="config/app_config.json")
    
    # 从配置字典初始化
    config = {
        'access_key_id': 'your_id',
        'access_key_secret': 'your_secret',
        'bucket_name': 'your_bucket',
        'endpoint': 'oss-cn-shanghai.aliyuncs.com',
        'upload_dir': 'audio'
    }
    oss_handler = OssHandler(config=config)
    
    # 上传文件并获取URL
    url = oss_handler.create_accessible_url('/path/to/local/file.mp3')
    ```
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化OSS处理器
        
        Args:
            config: OSS配置字典，包含access_key_id, access_key_secret, bucket_name, endpoint, upload_dir
            config_path: OSS配置文件路径，如果config为None则尝试从此文件读取
            
        配置优先级: config参数 > config_path文件 > 环境变量
        """
        self.auth = None
        self.bucket = None
        self.client = None
        self.config = {}
        self.initialized = False
        
        # 按优先级尝试加载配置
        if config is not None:
            # 使用传入的配置字典
            self.config = config.copy()
            if self._validate_config():
                self._init_oss()
        elif config_path is not None:
            # 尝试从配置文件加载
            success, cfg = ConfigHandler.read_oss_config(config_path)
            if success:
                self.config = cfg
                self._init_oss()
        else:
            # 尝试从环境变量加载
            success, cfg = ConfigHandler.read_env_oss_config()
            if success:
                self.config = cfg
                self._init_oss()
                
        if not self.initialized:
            logger.warning("OSS初始化失败，将使用本地文件URL模式")
    
    def _validate_config(self) -> bool:
        """
        验证配置是否合法
        
        Returns:
            bool: 配置是否有效
        """
        return ConfigHandler.validate_oss_config(self.config)
    
    def _init_oss(self) -> bool:
        """
        初始化OSS连接
        
        Returns:
            bool: 初始化是否成功
        """
        if not OSS_AVAILABLE:
            logger.error("缺少oss2库，无法初始化OSS")
            return False
            
        try:
            access_key_id = self.config['access_key_id']
            access_key_secret = self.config['access_key_secret']
            endpoint = self.config['endpoint']
            bucket_name = self.config['bucket_name']
            
            # 创建验证对象
            self.auth = oss2.Auth(access_key_id, access_key_secret)
            
            # 创建存储桶对象
            self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)
            self.client = self.bucket  # 将bucket赋值给client保持一致性
            
            # 轻量检查 - 只检查是否能访问存储桶（而不是获取完整信息）
            # 注意: object_exists虽然会返回False（因为对象不存在），但API调用成功表示我们有权限访问存储桶
            test_obj_name = f"test_init_{int(time.time())}_{str(uuid.uuid4())[:8]}.txt"
            logger.info(f"尝试检查OSS存储桶 {bucket_name} 中的测试对象是否存在: {test_obj_name}")
            
            # 执行API调用测试
            test_exists = self.bucket.object_exists(test_obj_name)
            logger.info(f"OSS连接检查: object_exists测试结果={test_exists} (预期为False)")
            
            # 如果能够成功调用API，即使对象不存在也表示我们有访问权限
            self.initialized = True
            logger.info(f"OSS初始化成功，存储桶: {bucket_name}")
            return True
            
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS初始化错误: {e.code}, {e.message}")
            if e.code == "NoSuchBucket":
                logger.error(f"存储桶 {self.config.get('bucket_name', '未指定')} 不存在")
            elif e.code == "AccessDenied":
                logger.error("访问被拒绝，请检查AccessKey权限")
            elif e.code == "InvalidAccessKeyId":
                logger.error("AccessKey ID无效，请检查配置")
            elif e.code == "SignatureDoesNotMatch":
                logger.error("签名不匹配，可能AccessKey Secret不正确")
            self.auth = None
            self.bucket = None
            self.client = None
            self.initialized = False
            return False
        except Exception as e:
            logger.error(f"OSS初始化失败: {str(e)}")
            self.auth = None
            self.bucket = None
            self.client = None
            self.initialized = False
            return False
            
    def is_available(self) -> bool:
        """
        检查OSS是否可用
        
        Returns:
            bool: OSS是否初始化成功并可用
        """
        if not self.initialized:
            logger.warning("OSS处理器未初始化")
            return False
            
        # 延迟导入oss2，避免依赖问题
        try:
            import oss2
            # 尝试初始化客户端
            if self.client is None:
                logger.info("尝试初始化OSS客户端...")
                try:
                    auth = oss2.Auth(self.config['access_key_id'], self.config['access_key_secret'])
                    self.client = oss2.Bucket(auth, self.config['endpoint'], self.config['bucket_name'])
                    logger.info(f"OSS客户端初始化成功，存储桶名称: {self.config['bucket_name']}")
                except Exception as e:
                    logger.error(f"OSS客户端初始化失败: {str(e)}")
                    return False
            
            # 生成唯一的测试对象名，避免缓存问题
            test_obj_name = f"test_available_{int(time.time())}_{str(uuid.uuid4())[:8]}.txt"
            logger.info(f"测试OSS连接，检查对象存在性: {test_obj_name}")
            
            # 简单的object_exists调用，即使返回False也表示API调用成功
            try:
                self.client.object_exists(test_obj_name)
                logger.info("OSS连接测试成功: object_exists API调用成功")
                return True
            except oss2.exceptions.OssError as e:
                logger.error(f"OSS连接测试失败(object_exists): {e.code}, {e.message}")
                
                # 如果第一种方法失败，尝试另一种轻量级API调用
                try:
                    # 尝试获取存储桶ACL而不是获取完整info
                    logger.info("尝试备选API调用: get_bucket_acl")
                    self.client.get_bucket_acl()
                    logger.info("OSS连接测试成功: get_bucket_acl API调用成功")
                    return True
                except oss2.exceptions.OssError as e2:
                    logger.error(f"OSS连接测试失败(get_bucket_acl): {e2.code}, {e2.message}")
                    
                    # 最后一次尝试：列出少量对象
                    try:
                        logger.info("尝试最终API调用: list_objects(max-keys=1)")
                        self.client.list_objects(max_keys=1)
                        logger.info("OSS连接测试成功: list_objects API调用成功")
                        return True
                    except oss2.exceptions.OssError as e3:
                        logger.error(f"OSS连接测试失败(list_objects): {e3.code}, {e3.message}")
                        
                        if e3.code == "AccessDenied":
                            logger.warning("无法执行list_objects操作，但这不一定表示无法上传文件")
                            # 此时我们可能仍有上传权限，但没有列出对象的权限
                            # 进行一次小型上传测试
                            try:
                                test_content = f"Test content at {time.time()}"
                                self.client.put_object(test_obj_name, test_content)
                                logger.info("OSS上传测试成功！可以上传文件")
                                # 删除刚才创建的测试对象
                                try:
                                    self.client.delete_object(test_obj_name)
                                    logger.info(f"已删除测试对象: {test_obj_name}")
                                except:
                                    logger.warning(f"无法删除测试对象，但上传成功: {test_obj_name}")
                                return True
                            except Exception as e4:
                                logger.error(f"OSS上传测试失败: {str(e4)}")
                                return False
                        return False
            except Exception as e:
                logger.error(f"OSS连接测试失败: {str(e)}")
                return False
        except ImportError:
            logger.error("OSS依赖未安装，请通过pip安装oss2包")
            return False
        except Exception as e:
            logger.error(f"OSS连接测试过程出现异常: {str(e)}")
            return False
    
    def upload_file(self, local_file_path: str, object_name: str = None) -> Tuple[bool, str]:
        """
        上传文件到OSS并返回访问URL
        
        Args:
            local_file_path: 本地文件路径
            object_name: OSS中的对象名，如不指定将使用文件名作为对象名
            
        Returns:
            Tuple[bool, str]: (是否成功, URL或错误信息)
        """
        if not self.is_available():
            logger.error("OSS未初始化或不可用，无法上传文件")
            return False, "OSS未初始化或不可用"
            
        if not object_name:
            # 使用唯一文件名避免冲突
            filename = os.path.basename(local_file_path)
            # 添加时间戳和UUID前缀
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            object_name = f"{self.config['upload_dir']}/{timestamp}_{unique_id}_{filename}"
            
        if not os.path.exists(local_file_path):
            logger.error(f"要上传的文件不存在: {local_file_path}")
            return False, f"文件不存在: {local_file_path}"
            
        logger.info(f"开始上传文件 {local_file_path} 到OSS路径 {object_name}")
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(local_file_path)
            logger.info(f"文件大小: {file_size / 1024:.2f} KB")
            
            # 上传文件
            import oss2
            try:
                start_time = time.time()
                result = self.client.put_object_from_file(object_name, local_file_path)
                end_time = time.time()
                
                if result.status == 200:
                    logger.info(f"文件上传成功! 耗时: {end_time - start_time:.2f}秒")
                    
                    # 构建访问URL (公开读)
                    url = f"https://{self.config['bucket_name']}.{self.config['endpoint']}/{object_name}"
                    logger.info(f"生成的访问URL: {url}")
                    
                    return True, url
                else:
                    logger.error(f"文件上传失败，状态码: {result.status}")
                    logger.error(f"响应头: {result.headers}")
                    return False, f"上传失败，状态码: {result.status}"
            except oss2.exceptions.OssError as e:
                logger.error(f"OSS操作错误: {e.code}, {e.message}")
                return False, f"OSS错误: {e.code} - {e.message}"
        except ImportError:
            logger.error("OSS依赖未安装，请通过pip安装oss2包")
            return False, "OSS依赖未安装"
        except Exception as e:
            logger.error(f"文件上传过程中出现异常: {str(e)}")
            return False, f"上传出错: {str(e)}"
    
    def generate_local_url(self, file_path: str) -> str:
        """
        生成本地文件URL
        
        Args:
            file_path: 本地文件路径
            
        Returns:
            str: 本地文件URL
        """
        # 转换为绝对路径
        abs_path = os.path.abspath(file_path)
        
        # 转换为file://URL格式
        path_parts = urllib.parse.quote(abs_path)
        url = f"file://{path_parts}"
        
        logger.info(f"生成本地URL: {url}")
        return url
    
    def create_accessible_url(self, file_path: str) -> Optional[str]:
        """
        创建文件的可访问URL，通过上传到OSS获取公网访问URL
        
        参数:
            file_path: 本地文件路径
            
        返回:
            成功时返回OSS的公网可访问URL，失败时返回None
        """
        try:
            # 确保文件存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
                
            # 尝试上传到OSS
            if self.is_available():
                logger.info(f"尝试上传文件到OSS: {file_path}")
                
                success, result = self.upload_file(file_path)
                if success:
                    logger.info(f"文件已上传至OSS: {result}")
                    return result
                else:
                    logger.error(f"上传文件到OSS失败: {result}")
                    return None
            else:
                logger.warning("OSS不可用，上传失败")
                return None
                
        except Exception as e:
            logger.error(f"创建可访问URL时出错: {str(e)}")
            return None