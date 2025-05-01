import os
import json
import logging
import re
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class ConfigHandler:
    """
    配置处理类
    
    用于从文件或环境变量读取配置，并验证配置是否有效
    """
    
    @staticmethod
    def read_oss_config(config_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        从配置文件读取OSS配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否成功, 配置字典)
            成功时返回(True, 配置字典)
            失败时返回(False, 空字典)
        """
        try:
            if not os.path.exists(config_path):
                logger.error(f"配置文件不存在: {config_path}")
                return False, {}
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # 检查是否包含OSS配置部分
            if 'oss' not in config_data:
                logger.error(f"配置文件中不包含OSS配置部分: {config_path}")
                return False, {}
                
            oss_config = config_data['oss']
            
            # 验证OSS配置
            if ConfigHandler.validate_oss_config(oss_config):
                return True, oss_config
            else:
                logger.error("无效的OSS配置")
                return False, {}
                
        except json.JSONDecodeError as e:
            logger.error(f"配置文件解析失败: {str(e)}")
            return False, {}
        except Exception as e:
            logger.error(f"读取配置文件时出错: {str(e)}")
            return False, {}
    
    @staticmethod
    def validate_oss_config(config: Dict[str, Any]) -> bool:
        """
        验证OSS配置是否有效
        
        Args:
            config: OSS配置字典
            
        Returns:
            bool: 配置是否有效
        """
        # 检查必需的配置项
        required_keys = ['access_key_id', 'access_key_secret', 'bucket_name', 'endpoint']
        
        for key in required_keys:
            if key not in config or not config[key]:
                logger.error(f"OSS配置缺少必需项: {key}")
                return False
                
        # 检查endpoint格式
        endpoint = config['endpoint']
        if not re.match(r'^[\w\-\.]+\.\w+\.\w+$', endpoint):
            logger.warning(f"OSS endpoint格式可能有误: {endpoint}，建议格式如: oss-cn-shanghai.aliyuncs.com")
            
        # 确保上传目录存在
        if 'upload_dir' not in config or not config['upload_dir']:
            logger.info("OSS配置中未指定上传目录，将使用默认值: audio")
            config['upload_dir'] = 'audio'
            
        return True
    
    @staticmethod
    def read_env_oss_config() -> Tuple[bool, Dict[str, Any]]:
        """
        从环境变量读取OSS配置
        
        从以下环境变量读取:
        - OSS_ACCESS_KEY_ID: 访问密钥ID
        - OSS_ACCESS_KEY_SECRET: 访问密钥密码
        - OSS_BUCKET_NAME: 存储桶名称
        - OSS_ENDPOINT: 访问域名
        - OSS_UPLOAD_DIR: 上传目录（可选，默认为audio）
        - ENABLE_OSS: 是否启用OSS（可选，默认为True）
        
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否成功, 配置字典)
            成功时返回(True, 配置字典)
            失败时返回(False, 空字典)
        """
        # 检查是否启用OSS
        enable_oss = os.environ.get('ENABLE_OSS', 'True').lower()
        if enable_oss not in ('true', '1', 'yes'):
            logger.info("OSS功能已禁用 (ENABLE_OSS != True)")
            return False, {}
            
        # 创建配置字典
        config = {
            'access_key_id': os.environ.get('OSS_ACCESS_KEY_ID', ''),
            'access_key_secret': os.environ.get('OSS_ACCESS_KEY_SECRET', ''),
            'bucket_name': os.environ.get('OSS_BUCKET_NAME', ''),
            'endpoint': os.environ.get('OSS_ENDPOINT', ''),
            'upload_dir': os.environ.get('OSS_UPLOAD_DIR', 'audio')
        }
        
        # 验证配置
        if ConfigHandler.validate_oss_config(config):
            return True, config
        else:
            return False, {} 