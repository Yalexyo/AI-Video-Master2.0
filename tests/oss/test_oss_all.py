#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
阿里云OSS综合测试模块

本文件整合了OSS相关的所有测试功能：
1. 连接测试：测试OSS服务连接、权限和基本操作
2. 存储桶测试：测试存储桶的创建、删除和基本操作
3. OssHandler测试：测试OssHandler类的文件上传和URL生成功能

使用方法:
- 测试全部功能: `python tests/oss/test_oss_all.py`
- 测试指定功能: `python tests/oss/test_oss_all.py [handler|connection|bucket]`

依赖:
- oss2: 阿里云OSS SDK
- python-dotenv: 环境变量加载
- aliyunsdkcore: (可选) 用于RAM权限测试

配置:
需要在项目根目录的.env文件中配置以下环境变量:
- OSS_ACCESS_KEY_ID: 阿里云访问密钥ID
- OSS_ACCESS_KEY_SECRET: 阿里云访问密钥Secret
- OSS_BUCKET_NAME: OSS存储桶名称
- OSS_ENDPOINT: OSS服务端点，如oss-cn-shanghai.aliyuncs.com
- OSS_UPLOAD_DIR: 文件上传目录，如"audio"
- ENABLE_OSS: 是否启用OSS功能(True/False)
"""

import os
import sys
import logging
import time
import json
import uuid
import traceback
import argparse
from urllib.parse import quote, urlencode
from typing import Dict, Any, List, Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    print("警告: python-dotenv未安装，无法从.env加载环境变量")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("oss_test")

# 检查OSS SDK是否可用
try:
    import oss2
    from itertools import islice
    HAS_OSS2 = True
except ImportError:
    HAS_OSS2 = False
    logger.warning("oss2库未安装，部分测试将无法运行。请执行: pip install oss2")

# 检查阿里云Core SDK是否可用(可选)
try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
    HAS_ALIYUNSDK = True
except ImportError:
    HAS_ALIYUNSDK = False
    logger.warning("aliyunsdkcore库未安装，RAM权限检查将被跳过")

# ============================================================================
# 辅助函数
# ============================================================================

def load_oss_config() -> Tuple[bool, Dict[str, str]]:
    """
    从环境变量加载OSS配置
    
    Returns:
        Tuple[bool, Dict[str, str]]: (是否成功, 配置字典)
    """
    required_keys = [
        "OSS_ACCESS_KEY_ID", 
        "OSS_ACCESS_KEY_SECRET", 
        "OSS_BUCKET_NAME", 
        "OSS_ENDPOINT"
    ]
    
    config = {
        "access_key_id": os.environ.get("OSS_ACCESS_KEY_ID", ""),
        "access_key_secret": os.environ.get("OSS_ACCESS_KEY_SECRET", ""),
        "bucket_name": os.environ.get("OSS_BUCKET_NAME", ""),
        "endpoint": os.environ.get("OSS_ENDPOINT", ""),
        "upload_dir": os.environ.get("OSS_UPLOAD_DIR", "tests")
    }
    
    # 检查必需的配置是否存在
    missing_keys = []
    for key in required_keys:
        env_key = key
        config_key = env_key.lower().replace("oss_", "")
        if not os.environ.get(env_key):
            missing_keys.append(env_key)
            
    if missing_keys:
        logger.error(f"缺少必要的OSS配置: {', '.join(missing_keys)}")
        return False, {}
        
    return True, config

def create_test_file(file_path: str, content: str = None) -> bool:
    """
    创建测试文件
    
    Args:
        file_path: 文件路径
        content: 文件内容，默认为时间戳
        
    Returns:
        bool: 是否成功创建
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if content is None:
            content = f"Test content created at {time.time()}"
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"创建测试文件: {file_path}")
        return True
    except Exception as e:
        logger.error(f"创建测试文件失败: {str(e)}")
        return False

def cleanup_file(file_path: str) -> bool:
    """
    清理文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 是否成功清理
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"已删除文件: {file_path}")
        return True
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        return False

def check_ram_permissions(config: Dict[str, str]) -> Dict[str, bool]:
    """
    检查RAM权限
    
    Args:
        config: OSS配置
        
    Returns:
        Dict[str, bool]: 权限检查结果
    """
    if not HAS_ALIYUNSDK:
        logger.warning("缺少aliyunsdkcore库，RAM权限检查被跳过")
        return {"error": "未安装aliyunsdkcore库"}
        
    try:
        client = AcsClient(
            config["access_key_id"],
            config["access_key_secret"],
            "cn-hangzhou"
        )
        
        # TODO: 实现RAM权限检查
        # 这需要调用相关RAM API，当前简化返回
        
        return {
            "oss:ListBuckets": None,
            "oss:GetBucketInfo": None,
            "oss:PutObject": None,
            "oss:GetObject": None,
            "oss:DeleteObject": None
        }
    except Exception as e:
        logger.error(f"RAM权限检查出错: {str(e)}")
        return {"error": str(e)}

# ============================================================================
# 主要测试函数
# ============================================================================

def test_oss_connection() -> bool:
    """
    测试OSS连接、权限和基本操作
    
    Returns:
        bool: 测试是否整体成功
    """
    if not HAS_OSS2:
        logger.error("缺少oss2库，无法进行OSS连接测试")
        return False
        
    logger.info("=== 开始测试OSS连接 ===")
    
    # 加载OSS配置
    config_success, config = load_oss_config()
    if not config_success:
        logger.error("加载OSS配置失败")
        return False
    
    # 获取配置参数
    access_key_id = config['access_key_id']
    access_key_secret = config['access_key_secret']
    bucket_name = config['bucket_name']
    endpoint = config['endpoint']
    
    # 测试OSS连接
    overall_success = True
    
    # 步骤1: 列出所有Bucket
    logger.info("1. 测试列出所有Bucket")
    try:
        auth = oss2.Auth(access_key_id, access_key_secret)
        service = oss2.Service(auth, endpoint)
        
        # 列出所有存储桶
        bucket_list = []
        for bucket_info in oss2.BucketIterator(service):
            bucket_list.append(bucket_info.name)
            
        if bucket_list:
            logger.info(f"✅ 成功列出所有Bucket，共 {len(bucket_list)} 个")
            for i, name in enumerate(bucket_list[:5], 1):
                logger.info(f"   {i}. {name}")
            if len(bucket_list) > 5:
                logger.info(f"   ... 等 {len(bucket_list)} 个")
        else:
            logger.warning("⚠️ 没有找到任何Bucket")
            
    except oss2.exceptions.ServerError as e:
        logger.error(f"❌ 列出所有Bucket失败 (ServerError): {e.code}, {e.message}")
        overall_success = False
    except oss2.exceptions.ClientError as e:
        if "SignatureDoesNotMatch" in str(e):
            logger.error("❌ 签名不匹配，可能AccessKey Secret不正确")
        elif "InvalidAccessKeyId" in str(e):
            logger.error("❌ 无效的AccessKeyId")
        else:
            logger.error(f"❌ 列出所有Bucket失败 (ClientError): {str(e)}")
        overall_success = False
    except Exception as e:
        logger.error(f"❌ 列出所有Bucket失败: {str(e)}")
        overall_success = False
    
    # 步骤2: 测试指定Bucket操作
    logger.info(f"2. 测试访问Bucket: {bucket_name}")
    try:
        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        
        # 获取存储桶信息
        bucket_info = bucket.get_bucket_info()
        logger.info(f"✅ 成功获取Bucket信息: {bucket_name}")
        logger.info(f"   创建时间: {bucket_info.creation_date}")
        logger.info(f"   存储类型: {bucket_info.storage_class}")
        logger.info(f"   区域: {bucket_info.location}")
        
        # 测试上传文件
        test_key = f"tests/test_connection_{int(time.time())}.txt"
        test_content = f"Test content at {time.time()}"
        logger.info(f"3. 测试上传文件: {test_key}")
        
        # 上传字符串内容
        result = bucket.put_object(test_key, test_content)
        if result.status == 200:
            logger.info(f"✅ 文件上传成功: {test_key}")
            
            # 生成文件URL
            url = f"https://{bucket_name}.{endpoint}/{test_key}"
            logger.info(f"   文件URL: {url}")
            
            # 下载并验证内容
            logger.info(f"4. 测试下载文件: {test_key}")
            download_obj = bucket.get_object(test_key)
            downloaded_content = download_obj.read().decode('utf-8')
            
            if downloaded_content == test_content:
                logger.info("✅ 文件内容验证成功")
            else:
                logger.error("❌ 文件内容不匹配")
                overall_success = False
            
            # 删除测试文件
            logger.info(f"5. 测试删除文件: {test_key}")
            bucket.delete_object(test_key)
            logger.info("✅ 文件删除成功")
            
        else:
            logger.error(f"❌ 文件上传失败，状态码: {result.status}")
            overall_success = False
            
    except oss2.exceptions.NoSuchBucket:
        logger.error(f"❌ 存储桶不存在: {bucket_name}")
        overall_success = False
    except oss2.exceptions.AccessDenied:
        logger.error(f"❌ 访问被拒绝: 当前AccessKey无权限访问存储桶 {bucket_name}")
        logger.info("可能原因:")
        logger.info("1. 存储桶属于其他账号")
        logger.info("2. 当前AccessKey没有该存储桶的权限")
        logger.info("3. RAM策略限制了当前用户的访问权限")
        overall_success = False
    except Exception as e:
        logger.error(f"❌ 访问存储桶出错: {str(e)}")
        overall_success = False
    
    # 输出最终结果
    if overall_success:
        logger.info("✅ OSS连接测试全部通过!")
    else:
        logger.error("❌ OSS连接测试部分失败!")
        logger.info("建议检查:")
        logger.info("1. AccessKey是否正确")
        logger.info("2. 存储桶名称是否正确")
        logger.info("3. RAM权限是否配置正确")
        logger.info("4. 网络是否正常")
    
    return overall_success

def test_create_bucket() -> bool:
    """
    测试创建新的OSS存储桶
    
    Returns:
        bool: 测试是否成功
    """
    if not HAS_OSS2:
        logger.error("缺少oss2库，无法进行OSS创建存储桶测试")
        return False
        
    logger.info("=== 开始测试创建OSS存储桶 ===")
    
    # 加载OSS配置
    config_success, config = load_oss_config()
    if not config_success:
        logger.error("加载OSS配置失败")
        return False
    
    # 准备参数
    access_key_id = config['access_key_id']
    access_key_secret = config['access_key_secret']
    endpoint = config['endpoint']
    
    # 生成唯一存储桶名
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    new_bucket_name = f"test-{timestamp}-{unique_id}"
    
    logger.info(f"尝试创建新存储桶: {new_bucket_name}")
    auth = oss2.Auth(access_key_id, access_key_secret)
    
    try:
        # 创建新存储桶
        bucket = oss2.Bucket(auth, endpoint, new_bucket_name)
        bucket.create_bucket()
        
        logger.info(f"✅ 成功创建存储桶: {new_bucket_name}")
        
        # 上传测试文件
        test_key = "test_file.txt"
        test_content = f"Test content created at {time.time()}"
        
        result = bucket.put_object(test_key, test_content)
        
        if result.status == 200:
            logger.info("✅ 成功上传测试文件")
            
            # 获取文件URL
            url = f"https://{new_bucket_name}.{endpoint}/{test_key}"
            logger.info(f"文件URL: {url}")
            
            # 删除文件
            bucket.delete_object(test_key)
            logger.info("✅ 成功删除测试文件")
        else:
            logger.error(f"❌ 上传测试文件失败: {result.status}")
        
        # 删除测试存储桶
        try:
            bucket.delete_bucket()
            logger.info(f"✅ 成功删除测试存储桶: {new_bucket_name}")
            return True
        except oss2.exceptions.BucketNotEmpty:
            logger.warning(f"⚠️ 存储桶非空，无法删除: {new_bucket_name}")
            # 列出并删除所有对象
            for obj in oss2.ObjectIterator(bucket):
                bucket.delete_object(obj.key)
                logger.info(f"删除对象: {obj.key}")
            # 再次尝试删除存储桶
            bucket.delete_bucket()
            logger.info(f"✅ 成功删除测试存储桶: {new_bucket_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除存储桶失败: {str(e)}")
            return False
    except oss2.exceptions.ServerError as e:
        logger.error(f"❌ 创建存储桶失败 (ServerError): {e.code}, {e.message}")
        if "RequestTimeTooSkewed" in e.code:
            logger.info("原因: 请求时间与服务器时间不同步，请检查本地时间")
        return False
    except oss2.exceptions.ClientError as e:
        logger.error(f"❌ 创建存储桶失败 (ClientError): {str(e)}")
        if "SignatureDoesNotMatch" in str(e):
            logger.info("原因: 签名不匹配，可能AccessKey Secret不正确")
        elif "InvalidAccessKeyId" in str(e):
            logger.info("原因: 无效的AccessKeyId")
        elif "TooManyBuckets" in str(e):
            logger.info("原因: 存储桶数量超出限制")
        return False
    except Exception as e:
        logger.error(f"❌ 创建存储桶失败: {str(e)}")
        return False

def test_oss_handler() -> bool:
    """
    测试OssHandler类的功能
    
    Returns:
        bool: 测试是否成功
    """
    logger.info("=== 开始测试OssHandler ===")
    
    # 导入OssHandler类
    try:
        from utils.oss_handler import OssHandler
    except ImportError as e:
        logger.error(f"导入OssHandler失败: {str(e)}")
        return False
    
    # 初始化OssHandler
    handler = OssHandler()
    
    # 检查是否可用
    is_available = handler.is_available()
    logger.info(f"OSS是否可用: {is_available}")
    
    if not is_available:
        logger.error("OssHandler不可用，测试结束")
        return False
    
    # 创建测试文件
    test_file_path = os.path.join(os.path.dirname(__file__), "../../test_handler_upload.txt")
    if not create_test_file(test_file_path):
        return False
    
    success = False
    try:
        # 上传文件
        logger.info("开始测试文件上传...")
        upload_success, result = handler.upload_file(test_file_path)
        
        if upload_success:
            logger.info(f"文件上传成功！URL: {result}")
            
            # 测试创建可访问URL
            url = handler.create_accessible_url(test_file_path)
            if url:
                logger.info(f"create_accessible_url测试成功，URL: {url}")
                success = True
            else:
                logger.error("create_accessible_url测试失败，返回了None")
        else:
            logger.error(f"文件上传失败: {result}")
    except Exception as e:
        logger.error(f"测试过程中出现异常: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        # 清理测试文件
        cleanup_file(test_file_path)
    
    # 输出测试结果
    if success:
        logger.info("✅ OssHandler测试通过!")
    else:
        logger.error("❌ OssHandler测试失败!")
    
    return success

# ============================================================================
# 命令行界面
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="阿里云OSS测试工具")
    parser.add_argument('test_type', nargs='?', choices=['connection', 'bucket', 'handler', 'all'],
                    default='all', help='测试类型 (默认: all)')
    
    args = parser.parse_args()
    
    if args.test_type == 'all' or args.test_type == 'connection':
        print("\n" + "="*50)
        print("测试OSS连接与基本操作")
        print("="*50)
        test_oss_connection()
    
    if args.test_type == 'all' or args.test_type == 'bucket':
        print("\n" + "="*50)
        print("测试创建OSS存储桶")
        print("="*50)
        test_create_bucket()
    
    if args.test_type == 'all' or args.test_type == 'handler':
        print("\n" + "="*50)
        print("测试OssHandler类")
        print("="*50)
        test_oss_handler()
    
    print("\n测试完成!")

if __name__ == "__main__":
    main() 