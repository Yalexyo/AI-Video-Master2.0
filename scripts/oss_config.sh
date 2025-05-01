#!/bin/bash
# OSS配置与验证脚本
# 用途：帮助用户配置Alibaba Cloud OSS并验证连接是否正常
# 使用方法：bash scripts/oss_config.sh

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 检查是否存在.env文件
ENV_FILE=".env"
ENV_EXAMPLE_FILE=".env.example"

echo -e "${BLUE}========== Alibaba Cloud OSS 配置助手 ==========${NC}"
echo "该脚本将帮助您配置Alibaba Cloud对象存储服务(OSS)，便于视频分析功能使用。"
echo

# 检查python环境
if ! command -v python &> /dev/null; then
    echo -e "${RED}错误: 未找到python命令。请确保已安装Python。${NC}"
    exit 1
fi

# 确保已激活虚拟环境
if [ -d ".venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}提示: 检测到.venv虚拟环境但未激活。尝试激活...${NC}"
    source .venv/bin/activate
fi

# 检查oss2库
if ! python -c "import oss2" &> /dev/null; then
    echo -e "${YELLOW}未检测到oss2库，正在安装...${NC}"
    pip install oss2
    if [ $? -ne 0 ]; then
        echo -e "${RED}oss2安装失败。请手动运行: pip install oss2${NC}"
        exit 1
    fi
fi

# 判断是创建还是验证配置
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}检测到已存在.env文件，是否需要验证配置？[y/n]${NC}"
    read -r verify_choice
    if [[ "$verify_choice" =~ ^[Yy]$ ]]; then
        # 验证配置
        echo -e "${BLUE}正在验证OSS配置...${NC}"
        python - <<EOF
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# 检查OSS配置是否存在
oss_keys = ['OSS_ACCESS_KEY_ID', 'OSS_ACCESS_KEY_SECRET', 'OSS_BUCKET_NAME', 
           'OSS_ENDPOINT', 'OSS_UPLOAD_DIR', 'ENABLE_OSS']

missing_keys = []
for key in oss_keys:
    if not os.environ.get(key):
        missing_keys.append(key)

if missing_keys:
    print(f"\033[0;31m错误: 以下环境变量未在.env中设置: {', '.join(missing_keys)}\033[0m")
    sys.exit(1)

# 验证OSS连接
try:
    if os.environ.get('ENABLE_OSS', 'False').lower() != 'true':
        print("\033[0;33m警告: OSS功能当前已禁用(ENABLE_OSS=False)。若要启用，请在.env设置ENABLE_OSS=True\033[0m")
        sys.exit(0)
        
    import oss2
    
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    bucket_name = os.environ.get('OSS_BUCKET_NAME')
    endpoint = os.environ.get('OSS_ENDPOINT')
    
    # 创建OSS连接
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    # 尝试列出文件
    list(bucket.list_objects(max_keys=1))
    print("\033[0;32m连接成功! OSS配置有效\033[0m")
    
    # 验证上传目录
    upload_dir = os.environ.get('OSS_UPLOAD_DIR', 'audio')
    test_key = f"{upload_dir}/test_connection.txt"
    bucket.put_object(test_key, "测试连接")
    bucket.delete_object(test_key)  # 清理测试文件
    print(f"\033[0;32m上传目录 '{upload_dir}' 验证成功!\033[0m")
    
except Exception as e:
    print(f"\033[0;31m连接失败: {str(e)}\033[0m")
    if "InvalidAccessKeyId" in str(e):
        print("\033[0;31m提示: AccessKey ID或Secret可能不正确\033[0m")
    elif "NoSuchBucket" in str(e):
        print(f"\033[0;31m提示: Bucket '{bucket_name}'不存在。请在OSS控制台创建此Bucket.\033[0m")
    sys.exit(1)
EOF

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}验证完毕！您的OSS配置可正常工作。${NC}"
        else
            echo -e "${RED}验证失败，请检查错误信息并修改配置。${NC}"
        fi
        exit 0
    fi
fi

# 创建新配置
echo -e "${BLUE}正在创建新的OSS配置...${NC}"

# 如果未找到示例文件，则创建一个
if [ ! -f "$ENV_EXAMPLE_FILE" ]; then
    echo "OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_UPLOAD_DIR=audio
ENABLE_OSS=True" > "$ENV_EXAMPLE_FILE"
    echo -e "${GREEN}已创建示例配置文件 $ENV_EXAMPLE_FILE${NC}"
fi

# 询问用户输入
echo -e "${BLUE}请输入Alibaba Cloud OSS配置信息:${NC}"
echo "（提示: 可以从阿里云控制台获取这些信息）"

read -p "AccessKey ID: " access_key_id
read -p "AccessKey Secret: " access_key_secret
read -p "Bucket 名称: " bucket_name
read -p "Endpoint (默认: oss-cn-shanghai.aliyuncs.com): " endpoint
endpoint=${endpoint:-oss-cn-shanghai.aliyuncs.com}
read -p "上传目录 (默认: audio): " upload_dir
upload_dir=${upload_dir:-audio}
read -p "启用OSS? [True/False] (默认: True): " enable_oss
enable_oss=${enable_oss:-True}

# 备份现有.env文件
if [ -f "$ENV_FILE" ]; then
    mv "$ENV_FILE" "${ENV_FILE}.bak"
    echo -e "${YELLOW}已备份现有.env文件到 ${ENV_FILE}.bak${NC}"
fi

# 生成新的.env文件
{
    cat "${ENV_FILE}.bak" 2>/dev/null | grep -v "OSS_" || true
    echo "# OSS配置 - $(date)"
    echo "OSS_ACCESS_KEY_ID=$access_key_id"
    echo "OSS_ACCESS_KEY_SECRET=$access_key_secret"
    echo "OSS_BUCKET_NAME=$bucket_name"
    echo "OSS_ENDPOINT=$endpoint"
    echo "OSS_UPLOAD_DIR=$upload_dir"
    echo "ENABLE_OSS=$enable_oss"
} > "$ENV_FILE"

echo -e "${GREEN}OSS配置已保存到 $ENV_FILE${NC}"

# 询问用户是否验证配置
echo -e "${BLUE}是否立即验证配置？[y/n]${NC}"
read -r verify_now

if [[ "$verify_now" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}正在验证OSS配置...${NC}"
    python - <<EOF
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 重新加载环境变量以确保获取最新配置
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# 验证OSS连接
try:
    if os.environ.get('ENABLE_OSS', 'False').lower() != 'true':
        print("\033[0;33m警告: OSS功能当前已禁用(ENABLE_OSS=False)。配置已保存，但未验证连接。\033[0m")
        sys.exit(0)
        
    import oss2
    
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    bucket_name = os.environ.get('OSS_BUCKET_NAME')
    endpoint = os.environ.get('OSS_ENDPOINT')
    
    # 创建OSS连接
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    # 尝试列出文件
    list(bucket.list_objects(max_keys=1))
    print("\033[0;32m连接成功! OSS配置有效\033[0m")
    
    # 验证上传目录
    upload_dir = os.environ.get('OSS_UPLOAD_DIR', 'audio')
    test_key = f"{upload_dir}/test_connection.txt"
    bucket.put_object(test_key, "测试连接")
    bucket.delete_object(test_key)  # 清理测试文件
    print(f"\033[0;32m上传目录 '{upload_dir}' 验证成功!\033[0m")
    
except Exception as e:
    print(f"\033[0;31m连接失败: {str(e)}\033[0m")
    if "InvalidAccessKeyId" in str(e):
        print("\033[0;31m提示: AccessKey ID或Secret可能不正确\033[0m")
    elif "NoSuchBucket" in str(e):
        print(f"\033[0;31m提示: Bucket '{bucket_name}'不存在。请在OSS控制台创建此Bucket.\033[0m")
    sys.exit(1)
EOF

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}验证完毕！您的OSS配置可正常工作。${NC}"
    else
        echo -e "${RED}验证失败，请检查错误信息并修改配置。${NC}"
        echo -e "${YELLOW}您可以稍后运行 'bash scripts/oss_config.sh' 重新验证或更新配置。${NC}"
    fi
else
    echo -e "${YELLOW}配置已保存。您可以稍后运行 'bash scripts/oss_config.sh' 验证配置。${NC}"
fi

echo
echo -e "${BLUE}========== 配置完成 ==========${NC}"
echo "OSS配置将用于视频处理功能中，提供文件存储与访问服务。"
echo "如需禁用OSS，请将.env中的ENABLE_OSS设置为False。" 