import streamlit as st
import os
import time
import requests
import logging
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from itertools import islice

# 添加项目根目录到Python路径
try:
    # 确保能够正确导入项目模块
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    sys.path.insert(0, str(project_root))
    
    # 尝试导入侧边栏导航
    from src.ui_elements.simple_nav import create_sidebar_navigation
except ImportError:
    # 如果导入失败，创建一个简单的替代函数
    def create_sidebar_navigation(active_page=""):
        st.sidebar.title("AI视频大师")
        st.sidebar.markdown("---")
        
        # 简单的导航菜单
        pages = {
            "视频分析": "/video_analysis",
            "热词管理": "/hotwords",
            "维度管理": "/dimensions",
            "API调试": "/api_debug"
        }
        
        for page_name, page_url in pages.items():
            if page_name == active_page:
                st.sidebar.markdown(f"**➡️ {page_name}**")
            else:
                if st.sidebar.button(page_name):
                    st.switch_page(page_url)

# 配置日志
logger = logging.getLogger(__name__)

# 设置页面
st.set_page_config(
    page_title="API调试 - AI视频大师",
    page_icon="🔧",
    layout="wide"
)

# 注入自定义样式
st.markdown("""
<style>
/* 隐藏streamlit自带导航和其他UI元素 */
[data-testid="stSidebarNav"], 
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
#MainMenu,
footer {
    display: none !important;
}

.output-box {
    background-color: #f8f9fa;
    border-radius: 5px;
    padding: 15px;
    border: 1px solid #eee;
    font-family: monospace;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
}

.success {
    color: #28a745;
    font-weight: bold;
}

.error {
    color: #dc3545;
    font-weight: bold;
}

.debug-container {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
}

.api-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    background-color: #f8f9fa;
}

.tab-content {
    padding: 15px 0;
}
</style>
""", unsafe_allow_html=True)

# API配置信息
api_configs = {
    "dashscope": {
        "name": "阿里云DashScope API",
        "env_var": "DASHSCOPE_API_KEY",
        "url": "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/customization",
        "prefix": "sk-",
        "description": "阿里云语音识别和热词服务"
    },
    "openrouter": {
        "name": "OpenRouter API",
        "env_var": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/models",
        "prefix": "sk-or-v1-",
        "description": "OpenRouter AI模型路由服务"
    },
    "deepseek": {
        "name": "DeepSeek API",
        "env_var": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/models",
        "prefix": "sk-",
        "description": "DeepSeek AI大模型服务"
    },
    "oss": {
        "name": "阿里云OSS存储",
        "env_vars": ["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_BUCKET_NAME", "OSS_ENDPOINT"],
        "url": None,  # OSS没有单一测试URL
        "description": "阿里云对象存储服务"
    }
}

# 导入OSS模块（如果可用）
try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False

# 导入DashScope模块（如果可用）
try:
    import dashscope
    from dashscope.audio.asr.transcription import Transcription
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False

def test_oss_connection():
    """测试阿里云OSS连接"""
    try:
        # 获取OSS配置
        access_key_id = os.environ.get("OSS_ACCESS_KEY_ID", "")
        access_key_secret = os.environ.get("OSS_ACCESS_KEY_SECRET", "")
        bucket_name = os.environ.get("OSS_BUCKET_NAME", "")
        endpoint = os.environ.get("OSS_ENDPOINT", "")
        
        test_results = []
        test_results.append(f"开始测试OSS连接 ({time.strftime('%H:%M:%S')})")
        
        # 检查配置
        missing_configs = []
        if not access_key_id:
            missing_configs.append("OSS_ACCESS_KEY_ID")
        if not access_key_secret:
            missing_configs.append("OSS_ACCESS_KEY_SECRET")
        if not bucket_name:
            missing_configs.append("OSS_BUCKET_NAME")
        if not endpoint:
            missing_configs.append("OSS_ENDPOINT")
        
        if missing_configs:
            test_results.append(f"❌ 缺少OSS配置: {', '.join(missing_configs)}")
            return test_results, False
        
        # 测试连接
        try:
            # 创建OSS认证对象
            auth = oss2.Auth(access_key_id, access_key_secret)
            
            # 创建Bucket对象
            bucket = oss2.Bucket(auth, endpoint, bucket_name)
            
            # 测试列举对象
            test_results.append(f"尝试连接到Bucket: {bucket_name}")
            files = list(islice(bucket.list_objects().object_list, 10))
            
            test_results.append(f"✅ OSS连接成功")
            if files:
                test_results.append(f"Bucket中对象数量: {len(files)}")
                test_results.append(f"首个对象: {files[0].key}")
            else:
                test_results.append(f"Bucket为空或没有访问权限")
            
            return test_results, True
        except Exception as e:
            test_results.append(f"❌ OSS连接失败: {str(e)}")
            return test_results, False
    except Exception as e:
        return ["❌ 测试OSS连接时出错: " + str(e)], False

def test_api_connection(api_key, url, method="GET", data=None, headers=None):
    """通用API连接测试函数"""
    test_results = []
    test_results.append(f"开始测试API连接 ({time.strftime('%H:%M:%S')})")
    
    # 确保有默认请求头
    if headers is None:
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            headers = {}
            
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    # 记录请求信息
    test_results.append(f"请求URL: {url}")
    test_results.append(f"请求方法: {method}")
    
    # 屏蔽API密钥
    if api_key:
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        test_results.append(f"API密钥: {masked_key}")
    
    # 发送请求
    try:
        start_time = time.time()
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            test_results.append(f"❌ 不支持的请求方法: {method}")
            return test_results, False
        
        end_time = time.time()
        test_results.append(f"请求耗时: {end_time - start_time:.2f}秒")
        test_results.append(f"状态码: {response.status_code}")
        
        # 检查响应
        if 200 <= response.status_code < 300:
            test_results.append("✅ API连接成功")
            
            # 尝试解析响应
            try:
                json_response = response.json()
                # 限制响应大小，避免输出太多
                response_str = json.dumps(json_response, ensure_ascii=False, indent=2)
                if len(response_str) > 1000:
                    response_str = response_str[:1000] + "...(已截断)"
                test_results.append("响应内容:")
                test_results.append(response_str)
            except Exception:
                # 非JSON响应，直接输出文本
                text = response.text[:500] + ("..." if len(response.text) > 500 else "")
                test_results.append(f"响应内容: {text}")
            
            return test_results, True
        elif response.status_code == 401:
            test_results.append("❌ API密钥无效，认证失败")
            test_results.append(f"响应内容: {response.text[:200]}")
            return test_results, False
        elif response.status_code == 429:
            test_results.append("❌ API调用频率超限")
            test_results.append(f"响应内容: {response.text[:200]}")
            return test_results, False
        else:
            test_results.append(f"❌ API调用失败，状态码: {response.status_code}")
            test_results.append(f"响应内容: {response.text[:200]}")
            return test_results, False
    
    except requests.exceptions.Timeout:
        test_results.append("❌ API请求超时")
        test_results.append("可能的原因:")
        test_results.append("1. 网络连接问题")
        test_results.append("2. 服务器响应慢")
        test_results.append("3. 防火墙或代理设置")
        return test_results, False
    
    except requests.exceptions.ConnectionError:
        test_results.append("❌ 无法连接到API服务器")
        test_results.append("可能的原因:")
        test_results.append("1. 网络连接问题")
        test_results.append("2. DNS解析失败")
        test_results.append("3. 防火墙阻止连接")
        return test_results, False
    
    except Exception as e:
        test_results.append(f"❌ 测试过程中发生错误: {str(e)}")
        return test_results, False

def get_dashscope_test_payload():
    """获取DashScope API测试数据"""
    return {
        "model": "speech-biasing",
        "input": {
            "action": "list_vocabulary",
            "page_index": 0,
            "page_size": 1
        }
    }

def get_openrouter_test_payload():
    """获取OpenRouter API测试数据"""
    return None  # GET请求不需要payload

def get_deepseek_test_payload():
    """获取DeepSeek API测试数据"""
    return None  # GET请求不需要payload

def update_env_file(key, value):
    """更新.env文件中的环境变量"""
    try:
        env_path = '.env'
        env_content = ""
        
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_content = f.read()
        
        # 更新或添加环境变量
        if f"{key}=" in env_content:
            # 替换现有值
            import re
            new_content = re.sub(
                rf'{key}=.*', 
                f'{key}={value}',
                env_content
            )
        else:
            # 添加新值
            new_content = env_content + f"\n{key}={value}\n"
        
        # 写入文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 更新环境变量
        os.environ[key] = value
        
        return True, f"{key}已更新"
    except Exception as e:
        return False, f"更新环境变量失败: {str(e)}"

def check_dashscope_version():
    """检查DashScope包版本"""
    try:
        import dashscope
        import pkg_resources
        
        # 获取包版本
        dashscope_version = pkg_resources.get_distribution("dashscope").version
        
        # 返回版本信息
        return {
            "installed": True,
            "version": dashscope_version,
            "path": dashscope.__file__
        }
    except ImportError:
        return {
            "installed": False,
            "version": None,
            "path": None
        }
    except Exception as e:
        return {
            "installed": True,
            "version": "未知",
            "error": str(e),
            "path": getattr(dashscope, "__file__", "未知")
        }

def test_dashscope_asr():
    """测试DashScope ASR功能"""
    try:
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            return False, "未设置DASHSCOPE_API_KEY环境变量"
        
        # 设置API密钥
        dashscope.api_key = api_key
        
        # 测试列出热词表API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 创建请求体
        data = {
            "model": "speech-biasing",
            "input": {
                "action": "list_vocabulary",
                "page_index": 0,
                "page_size": 10
            }
        }
        
        # 发送请求
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/customization",
            headers=headers,
            json=data,
            timeout=30
        )
        
        # 检查响应
        if response.status_code == 200:
            return True, response.json()
        else:
            error_info = response.json() if response.text else {"error": "无响应内容"}
            return False, error_info
    
    except Exception as e:
        return False, str(e)

def check_dashscope_api():
    """检测DashScope API是否可用"""
    st.write("#### DashScope API 检测")
    
    # 检查版本信息
    version_info = check_dashscope_version()
    if version_info["installed"]:
        st.write(f"✅ DashScope已安装")
        st.write(f"版本: {version_info['version']}")
        st.write(f"路径: {version_info['path']}")
        if "error" in version_info:
            st.error(f"版本检查错误: {version_info['error']}")
    else:
        st.error("❌ DashScope未安装")
        st.info("请安装DashScope: `pip install dashscope`")
        return
    
    # 检查API密钥
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        st.error("未设置DASHSCOPE_API_KEY环境变量")
        st.info("请在.env文件中添加 DASHSCOPE_API_KEY=你的密钥")
        return
    
    # 隐藏中间部分的API密钥
    masked_key = f"{api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else "***"
    st.write(f"检测到API密钥: {masked_key}")
    
    # 测试自定义包装类
    st.subheader("自定义API包装类测试")
    with st.spinner("正在测试自定义包装类..."):
        success, result = test_dashscope_wrapper()
        
        if success:
            st.success("✅ 自定义包装类测试成功!")
            st.write(f"SDK版本: {result.get('version', '未知')}")
            st.write("API端点:")
            st.json(result.get('endpoints', {}))
            st.write("响应结果:")
            st.json(result.get('result', {}))
        else:
            st.error("❌ 自定义包装类测试失败!")
            st.write(f"错误信息: {result}")
    
    # 使用热词API进行测试
    st.subheader("热词API测试")
    with st.spinner("正在测试热词API..."):
        # 使用更新的测试函数
        success, result = test_dashscope_asr()
        
        if success:
            st.success("✅ 热词API连接成功!")
            st.json(result)
        else:
            st.error("❌ 热词API连接失败!")
            st.write(f"错误信息: {result}")
    
    # 测试文本生成API
    st.subheader("文本生成API测试")
    with st.spinner("正在测试文本生成API..."):
        success, result = test_dashscope_generation()
        
        if success:
            st.success("✅ 文本生成API连接成功!")
            st.write(f"使用方法: {result['method']}")
            st.json(result['response'])
        else:
            st.error("❌ 文本生成API连接失败!")
            st.write(f"错误信息: {result}")
            
    # 显示可用的dashscope模块
    st.subheader("DashScope模块探索")
    try:
        import dashscope
        
        # 列出dashscope的所有一级属性和方法
        attributes = [attr for attr in dir(dashscope) if not attr.startswith('_')]
        
        # 显示主要的模块和属性
        st.write("DashScope主要模块:")
        modules = []
        for attr in attributes:
            try:
                value = getattr(dashscope, attr)
                if isinstance(value, type(os)) or callable(value):  # 如果是模块或者可调用对象
                    modules.append({"名称": attr, "类型": str(type(value).__name__)})
            except:
                pass
        
        # 显示模块列表
        st.table(modules)
        
    except Exception as e:
        st.error(f"获取DashScope模块信息失败: {str(e)}")

def check_openrouter_api():
    """检测OpenRouter API是否可用"""
    st.write("#### OpenRouter API 检测")
    
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    
    if not api_key:
        st.error("未设置OPENROUTER_API_KEY环境变量")
        st.info("请在.env文件中添加 OPENROUTER_API_KEY=你的密钥")
        return
    
    # 隐藏中间部分的API密钥
    masked_key = f"{api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else "***"
    st.write(f"检测到API密钥: {masked_key}")
    
    # 测试API连接
    with st.spinner("正在测试OpenRouter API连接..."):
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "openai/gpt-3.5-turbo", 
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Reply with the number 123"}
                ]
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                st.success("✅ OpenRouter API 连接成功!")
                st.write("API响应:")
                st.json(response.json())
            else:
                st.error(f"❌ API响应错误: {response.status_code}")
                st.json(response.json() if response.text else {})
        except Exception as e:
            st.error(f"❌ API连接失败: {str(e)}")

def check_deepseek_api():
    """检测DeepSeek API是否可用"""
    st.write("#### DeepSeek API 检测")
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    
    if not api_key:
        st.error("未设置DEEPSEEK_API_KEY环境变量")
        st.info("请在.env文件中添加 DEEPSEEK_API_KEY=你的密钥")
        return
    
    # 隐藏中间部分的API密钥
    masked_key = f"{api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else "***"
    st.write(f"检测到API密钥: {masked_key}")
    
    # 测试API连接
    with st.spinner("正在测试DeepSeek API连接..."):
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat", 
                "messages": [
                    {"role": "user", "content": "Reply with the number 123"}
                ],
                "stream": False
            }
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                st.success("✅ DeepSeek API 连接成功!")
                st.write("API响应:")
                st.json(response.json())
            else:
                st.error(f"❌ API响应错误: {response.status_code}")
                st.json(response.json() if response.text else {})
        except Exception as e:
            st.error(f"❌ API连接失败: {str(e)}")

def check_oss_connection():
    """检测阿里云OSS是否可用"""
    st.write("#### 阿里云OSS连接检测")
    
    # 获取OSS配置
    access_key_id = os.environ.get("OSS_ACCESS_KEY_ID", "")
    access_key_secret = os.environ.get("OSS_ACCESS_KEY_SECRET", "")
    bucket_name = os.environ.get("OSS_BUCKET_NAME", "")
    endpoint = os.environ.get("OSS_ENDPOINT", "")
    
    # 检查配置是否完整
    if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
        st.error("阿里云OSS配置不完整")
        st.info("请在.env文件中设置以下环境变量:")
        st.code("""
        OSS_ACCESS_KEY_ID=你的AccessKeyID
        OSS_ACCESS_KEY_SECRET=你的AccessKeySecret
        OSS_BUCKET_NAME=你的Bucket名称
        OSS_ENDPOINT=地域节点（如oss-cn-hangzhou.aliyuncs.com）
        """)
        return
    
    # 检查OSS模块是否可用
    if not OSS_AVAILABLE:
        st.error("阿里云OSS模块未安装")
        st.info("请安装OSS模块: `pip install oss2`")
        return
    
    # 测试OSS连接
    with st.spinner("正在测试阿里云OSS连接..."):
        try:
            # 初始化OSS客户端
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, endpoint, bucket_name)
            
            # 检查连接（列出Bucket中的文件）
            files = list(islice(bucket.list_objects().object_list, 10))
            
            st.success("✅ 阿里云OSS连接成功!")
            
            # 显示Bucket信息
            st.write(f"Bucket名称: {bucket_name}")
            st.write(f"Endpoint: {endpoint}")
            
            # 显示文件列表
            if files:
                st.write(f"Bucket中的文件 (前{len(files)}个):")
                for obj in files:
                    st.write(f"- {obj.key}")
            else:
                st.write("Bucket中没有文件")
            
        except oss2.exceptions.ClientError as e:
            st.error(f"❌ OSS客户端错误: {str(e)}")
        except oss2.exceptions.ServerError as e:
            st.error(f"❌ OSS服务器错误: {str(e)}")
        except Exception as e:
            st.error(f"❌ OSS连接失败: {str(e)}")

def test_dashscope_generation():
    """测试DashScope生成API"""
    try:
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            return False, "未设置DASHSCOPE_API_KEY环境变量"
        
        dashscope.api_key = api_key
        
        # 尝试不同的可能API路径
        generation_apis = [
            # 直接使用HTTP请求（最可靠的方法）
            lambda: requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen-turbo",
                    "input": {
                        "prompt": "回复数字123"
                    }
                },
                timeout=30
            ),
            # 尝试最新版本可能的API路径
            lambda: getattr(dashscope, "generation").Generation.call(
                model="qwen-turbo",
                prompt="回复数字123"
            ),
            # 尝试旧版本可能的API路径
            lambda: getattr(dashscope, "aigc").generation.Generation.call(
                model="qwen-turbo",
                prompt="回复数字123"
            ),
            # 尝试另一种可能的API路径
            lambda: dashscope.TextGeneration.call(
                model="qwen-turbo",
                prompt="回复数字123"
            )
        ]
        
        # 依次尝试各种API调用方式
        for i, gen_api in enumerate(generation_apis):
            try:
                response = gen_api()
                
                # 处理返回结果
                if isinstance(response, requests.Response):
                    # HTTP请求响应
                    if response.status_code == 200:
                        return True, {
                            "method": f"方法{i+1} (HTTP请求)",
                            "response": response.json()
                        }
                else:
                    # DashScope SDK响应
                    if hasattr(response, "status_code") and response.status_code == 200:
                        output = response.output if hasattr(response, "output") else "API调用成功但没有输出字段"
                        return True, {
                            "method": f"方法{i+1} (SDK)",
                            "response": output
                        }
            except Exception as e:
                # 记录但继续尝试下一种方法
                if i == len(generation_apis) - 1:
                    # 如果是最后一种方法，则返回错误
                    return False, f"所有生成API调用方法均失败，最后错误: {str(e)}"
                continue
        
        return False, "所有生成API调用方法均失败"
    except Exception as e:
        return False, str(e)

def test_dashscope_wrapper():
    """测试DashScope API包装类"""
    try:
        # 导入包装类
        # from utils.dashscope_wrapper import dashscope_api
        from utils.dashscope_sdk_wrapper import dashscope_sdk
        
        # 获取API密钥
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            return False, "未设置DASHSCOPE_API_KEY环境变量"
        
        # 设置API密钥
        dashscope_sdk.api_key = api_key
        
        # 测试获取热词表列表
        result = dashscope_sdk.get_hot_words_list(page_index=0, page_size=5)
        
        if result.get("status") == "success":
            return True, {
                "version": "SDK版本",
                "result": result
            }
        else:
            return False, result
    except Exception as e:
        return False, str(e)

def main():
    st.title("🔧 API调试工具")
    st.write("使用此工具检测各种API连接是否正常")
    
    # 创建选项卡
    tabs = st.tabs(["DashScope", "OpenRouter", "DeepSeek", "阿里云OSS"])
    
    # DashScope选项卡
    with tabs[0]:
        check_dashscope_api()
    
    # OpenRouter选项卡
    with tabs[1]:
        check_openrouter_api()
    
    # DeepSeek选项卡
    with tabs[2]:
        check_deepseek_api()
    
    # 阿里云OSS选项卡
    with tabs[3]:
        check_oss_connection()

    st.divider()
    st.write("### 环境变量检查")
    
    # 检查关键环境变量
    env_vars = {
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY", ""),
        "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
        "OSS_ACCESS_KEY_ID": os.environ.get("OSS_ACCESS_KEY_ID", ""),
        "OSS_ACCESS_KEY_SECRET": os.environ.get("OSS_ACCESS_KEY_SECRET", ""),
        "OSS_BUCKET_NAME": os.environ.get("OSS_BUCKET_NAME", ""),
        "OSS_ENDPOINT": os.environ.get("OSS_ENDPOINT", "")
    }
    
    # 创建环境变量状态表
    status_data = []
    for key, value in env_vars.items():
        # 隐藏API密钥的具体内容
        if 'KEY' in key and value:
            masked_value = f"{value[:3]}...{value[-3:]}" if len(value) > 6 else "***"
            status = "✅ 已设置" 
        else:
            masked_value = "-"
            status = "❌ 未设置" if not value else "✅ 已设置"
            
        status_data.append({"环境变量": key, "状态": status, "值": masked_value})
    
    # 显示状态表
    st.table(status_data)
    
    # 添加刷新按钮
    if st.button("刷新"):
        st.experimental_rerun()

if __name__ == "__main__":
    main() 