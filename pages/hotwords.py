import streamlit as st
import pandas as pd
import logging
import os
import json
import time
import random
import string
from dotenv import load_dotenv

from src.core.hot_words_service import HotWordsService
from src.core.hot_words_api import create_env_file
from src.ui_elements.simple_nav import create_sidebar_navigation
from src.config.settings import HOTWORDS_DIR

# 重新加载环境变量，确保最新值可用
load_dotenv(override=True)
if os.environ.get('DASHSCOPE_API_KEY'):
    # 记录API密钥前后几位用于调试
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    logging.getLogger(__name__).info(f"热词管理页面加载，API密钥: {masked_key}")
else:
    logging.getLogger(__name__).warning("热词管理页面加载，但未找到API密钥环境变量")

# 页面配置必须是第一个st命令
st.set_page_config(
    page_title="热词管理 - AI视频大师",
    page_icon="📊",
    layout="wide"
)

# 强制注入隐藏顶栏样式
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

/* 添加云端热词表样式 */
.cloud-hotword-item {
    background-color: #f8f9fa;
    border-radius: 4px;
    padding: 12px;
    margin-bottom: 10px;
    border: 1px solid #eee;
}
.hotword-id {
    color: #888;
    font-size: 0.75rem;
    margin-bottom: 5px;
    font-weight: normal;
}
.hotword-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 5px;
}
.hotword-date {
    color: #888;
    font-size: 0.8rem;
}
.hotword-actions {
    margin-top: 10px;
    text-align: right;
}
/* 热词表卡片样式 */
.hotwords-card {
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 20px;
    background-color: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.hotwords-card-header {
    border-bottom: 1px solid #f0f0f0;
    padding-bottom: 10px;
    margin-bottom: 10px;
}
.hotwords-card-content {
    padding: 10px 0;
}
.hotwords-list {
    background-color: #f9f9f9;
    padding: 10px;
    border-radius: 5px;
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.6;
    font-size: 1rem;
}
.hotword-item {
    background-color: #eef2f7;
    border-radius: 4px;
    padding: 3px 8px;
    margin: 3px;
    display: inline-block;
    border: 1px solid #e0e0e0;
}
.hotword-weight {
    color: #ff6b6b;
    font-size: 0.75rem;
    margin-left: 4px;
}
.hotword-lang {
    color: #228be6;
    font-size: 0.75rem;
    margin-left: 4px;
}
/* 自定义删除按钮样式 */
.stButton > button.delete-btn {
    background-color: #e74c3c;
    color: white;
    border: none;
}
.stButton > button.delete-btn:hover {
    background-color: #c0392b;
    color: white;
    border: none;
}
</style>
""", unsafe_allow_html=True)

# 配置日志
logger = logging.getLogger(__name__)

# 初始化热词服务
hot_words_service = HotWordsService()

def show():
    """渲染热词管理页面"""
    # 创建侧边栏，注意active_page修改为"热词管理"
    create_sidebar_navigation(active_page="热词管理")
    
    # 初始化session_state变量
    if "new_vocab_id" not in st.session_state:
        st.session_state.new_vocab_id = None
    if "show_apply_button" not in st.session_state:
        st.session_state.show_apply_button = False
    
    # 页面标题
    st.title("💬 热词管理")
    
    # 显示当前使用的热词ID
    current_hotword_id = hot_words_service.get_current_hotword_id()
    is_default = current_hotword_id == "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b"
    default_tag = ' <span style="background-color: #f8d7da; color: #721c24; padding: 2px 5px; border-radius: 3px; font-size: 12px;">系统默认(不可删除)</span>' if is_default else ''
    
    st.markdown(f"""
    <div style="border: 2px solid #FF4B4B; border-radius: 5px; padding: 10px; margin-bottom: 20px;">
      <p style="margin: 0; font-size: 16px;">当前程序分析运行所调用的热词ID: <span style="font-weight: bold; font-family: monospace;">{current_hotword_id}</span>{default_tag}</p>
      <p style="margin-top: 5px; font-size: 12px; color: #666;">注意：ID为 <code>vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b</code> 的热词表是系统默认热词表，不能删除。</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 注入自定义样式
    st.markdown("""
    <style>
    /* 自定义删除按钮样式 */
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: #e74c3c;
        color: white;
        border: none;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #c0392b;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 确保热词目录存在
    os.makedirs(HOTWORDS_DIR, exist_ok=True)
    
    if "hotword_entries" not in st.session_state:
        # 初始化为一个空热词条目
        st.session_state.hotword_entries = [{"text": "", "weight": 4, "lang": "zh"}]
    
    # 左右分栏: 左侧放热词编辑，右侧放云端热词表
    left_col, right_col = st.columns([5, 5])
    
    with left_col:
        st.header("本地热词编辑")
        
        # 步骤1: 编辑热词
        st.write("第1步: 添加和编辑热词")
        
        # 添加一行的按钮
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write("添加多个热词，每行一个")
        with col2:
            add_empty_btn = st.button("➕ 添加行")
        
        # 添加热词说明
        with st.expander("ℹ️ 热词设置说明", expanded=False):
            st.markdown("""
            ### 热词配置指南
            
            - **热词文本**：每个词语最长10个汉字或英文单词
            - **权重**：取值范围为1-5的整数，默认值为4。较大权重可能会引起负面效果，导致其他词语识别不准确
            - **语言**：指定热词的语言
                - `zh`：中文
                - `en`：英文
            
            > 根据[阿里云文档](https://help.aliyun.com/zh/model-studio/custom-hot-words)，每个热词列表最多添加500个词
            """)
        
        # 处理添加新行
        if add_empty_btn:
            st.session_state.hotword_entries.append({"text": "", "weight": 4, "lang": "zh"})
            st.rerun()
        
        # 添加表头
        header_cols = st.columns([5, 2, 2, 1])
        with header_cols[0]:
            st.write("**热词文本**")
        with header_cols[1]:
            st.write("**权重(1-5)**")
        with header_cols[2]:
            st.write("**语言**")
        with header_cols[3]:
            st.write("**操作**")
        
        # 使用带有侧边操作按钮的表格式布局
        for i, entry in enumerate(st.session_state.hotword_entries):
            # 每行用四列: 文本输入、权重选择器、语言选择器、删除按钮
            cols = st.columns([5, 2, 2, 1])
            
            with cols[0]:
                # 热词文本输入
                st.session_state.hotword_entries[i]["text"] = st.text_input(
                    "词条",
                    value=entry["text"],
                    key=f"text_{i}",
                    label_visibility="collapsed",
                    placeholder="输入热词"
                )
            
            with cols[1]:
                # 权重选择器 (1-5)，根据官方文档，取值范围为[1, 5]之间的整数
                st.session_state.hotword_entries[i]["weight"] = st.select_slider(
                    "权重",
                    options=list(range(1, 6)),  # 1-5
                    value=min(entry["weight"], 5) if entry["weight"] else 4,  # 确保值在有效范围内
                    key=f"weight_{i}",
                    label_visibility="collapsed"
                )
            
            with cols[2]:
                # 语言选择器
                st.session_state.hotword_entries[i]["lang"] = st.selectbox(
                    "语言",
                    options=["zh", "en"],
                    index=0 if entry.get("lang", "zh") == "zh" else 1,
                    key=f"lang_{i}",
                    label_visibility="collapsed",
                    help="zh:中文, en:英文"
                )
            
            with cols[3]:
                # 删除按钮 - 移到表单外部
                if st.button("✕", key=f"delete_{i}"):
                    st.session_state.hotword_entries.pop(i)
                    st.rerun()
        
        # 步骤2: 创建热词表 (在表单内)
        st.write("---")
        st.write("第2步: 创建热词表")
        
        # 生成随机名称，格式: aivideo_{时间戳}_{随机字符}
        timestamp = time.strftime("%y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        default_name = f"aivideo_{timestamp}_{random_suffix}"
        
        # 用于存储创建结果的容器
        create_result_container = st.container()
        
        with st.form(key="create_hotwords_form"):
            # 显示自动生成的热词表名称
            st.write(f"热词表名称: **{default_name}**")
            
            # 隐藏模型选择，直接使用固定模型
            target_model = "paraformer-v2"
            
            # 过滤有效的热词条目 (非空文本)
            valid_entries = [entry for entry in st.session_state.hotword_entries if entry["text"].strip()]
            
            # 显示热词数量信息
            st.info(f"将使用当前编辑的 {len(valid_entries)} 个有效热词创建热词表")
            
            # 表单提交按钮
            submit_button = st.form_submit_button(label="创建热词表", type="primary")
            
            if submit_button:
                if not valid_entries:
                    st.warning("请添加至少一个热词")
                else:
                    with st.spinner("正在创建热词表..."):
                        # 记录创建前的请求参数
                        logger.info(f"准备创建热词表: 名称={default_name}, 模型={target_model}, 热词数量={len(valid_entries)}")
                        logger.info(f"热词内容: {json.dumps(valid_entries[:5], ensure_ascii=False)}" + 
                                  ("..." if len(valid_entries) > 5 else ""))
                        
                        try:
                            success, vocab_id, msg = hot_words_service.create_cloud_vocabulary(
                                vocabulary=valid_entries,  # 直接传递完整格式的热词列表
                                prefix="aivideo",
                                name=default_name,  # 使用自动生成的名称
                                target_model=target_model
                            )
                            
                            if success:
                                # 将新创建的热词ID存储在session_state中，而不是在表单中显示结果
                                st.session_state.new_vocab_id = vocab_id
                                st.session_state.show_apply_button = True
                            else:
                                st.error(f"创建失败: {msg}")
                                
                        except Exception as e:
                            st.error(f"创建过程中出现错误: {str(e)}")
                            logger.exception("热词表创建过程中出现异常")
        
        # 表单外部显示创建结果和应用按钮
        with create_result_container:
            if st.session_state.get("new_vocab_id"):
                vocab_id = st.session_state.new_vocab_id
                
                # 显示成功消息
                st.success(f"成功创建云端热词表，ID: {vocab_id}")
                
                # 添加应用按钮
                if st.session_state.get("show_apply_button", False):
                    if st.button("将新创建的热词表设为当前使用", key="apply_new_vocab"):
                        if hot_words_service.set_current_hotword_id(vocab_id):
                            st.success(f"已成功设置热词ID: {vocab_id}")
                            # 清除缓存并刷新页面
                            if "cloud_vocabularies" in st.session_state:
                                del st.session_state.cloud_vocabularies
                            if "vocabulary_details" in st.session_state:
                                del st.session_state.vocabulary_details
                            # 清除创建状态
                            st.session_state.new_vocab_id = None
                            st.session_state.show_apply_button = False
                            # 重新加载页面
                            st.rerun()
                        else:
                            st.error("设置热词ID失败")
                
                # 显示热词详情
                with st.expander("热词详情", expanded=False):
                    st.json(valid_entries[:10])
                    if len(valid_entries) > 10:
                        st.info(f"... 仅显示前10个，共有 {len(valid_entries)} 个热词")
    
    # 第二列：云端热词管理
    with right_col:
        st.subheader("☁️ 阿里云热词表")
        
        # 刷新按钮
        col_refresh = st.empty()
        if col_refresh.button("刷新热词表", key="refresh_cloud_btn", type="primary"):
            # 清除缓存强制刷新
            if "cloud_vocabularies" in st.session_state:
                del st.session_state.cloud_vocabularies
            if "vocabulary_details" in st.session_state:
                del st.session_state.vocabulary_details
            # 清除删除状态
            if "delete_status" in st.session_state:
                del st.session_state.delete_status
            st.session_state.refresh_cloud = True
            st.rerun()
        
        # 自动加载云端热词列表
        # 如果是首次加载页面或请求了刷新，则加载最新数据
        auto_refresh = False
        error_msg = None  # 初始化error_msg变量
        
        if "cloud_vocabularies" not in st.session_state or st.session_state.get("refresh_cloud", False):
            auto_refresh = True
            st.session_state.refresh_cloud = False
            
        if auto_refresh:
            with st.spinner("正在从阿里云加载最新热词表..."):
                vocabularies, error_msg = hot_words_service.check_cloud_hotwords()
                if error_msg:
                    st.error(error_msg)
                    vocabularies = None
                else:
                    st.success("成功加载最新热词表")
                st.session_state.cloud_vocabularies = vocabularies
                
                # 为每个热词表加载详细信息
                if vocabularies:
                    st.session_state.vocabulary_details = {}
                    with st.spinner("正在加载热词表详情..."):
                        for vocab in vocabularies:
                            vocab_id = vocab.get('vocabulary_id', '')
                            if vocab_id:
                                success, vocab_details = hot_words_service.query_vocabulary(vocab_id)
                                if success and vocab_details:
                                    st.session_state.vocabulary_details[vocab_id] = vocab_details
        else:
            vocabularies = st.session_state.cloud_vocabularies
        
        # 显示云端热词表列表
        if not vocabularies:
            error_message = st.empty()
            if error_msg and "API密钥" in error_msg:
                # API密钥相关错误，提供详细指导
                error_message.error(error_msg)
                
                # 添加API密钥配置指南
                with st.expander("💡 如何配置API密钥", expanded=True):
                    st.markdown("""
                    ### 配置阿里云API密钥指南
                    
                    要使用热词功能，您需要正确配置阿里云DashScope API密钥：
                    
                    1. **创建.env文件**：
                       - 在项目根目录创建一个名为`.env`的文件
                    
                    2. **添加API密钥**：
                       - 在.env文件中添加以下内容：
                       ```
                       DASHSCOPE_API_KEY=sk-您的阿里云API密钥
                       ```
                       - 请确保密钥以`sk-`开头
                    
                    3. **获取阿里云API密钥**：
                       - 登录[阿里云DashScope控制台](https://dashscope.console.aliyun.com/)
                       - 在右上角的「密钥管理」中获取API密钥
                    
                    4. **重启应用**：
                       - 配置完成后重启应用生效
                    """)
                    
                    # 添加API密钥配置表单
                    with st.form("api_key_config_form"):
                        st.write("### 快速配置API密钥")
                        api_key = st.text_input("输入您的API密钥", placeholder="sk-xxxxxxxxxxxx", type="password")
                        submit_api_key = st.form_submit_button("保存API密钥")
                        
                        if submit_api_key:
                            if not api_key or not api_key.startswith("sk-"):
                                st.error("API密钥格式不正确，应以'sk-'开头")
                            else:
                                # 保存API密钥到.env文件
                                success, message = create_env_file(api_key)
                                if success:
                                    st.success(f"{message} 请重启应用使配置生效。")
                                else:
                                    st.error(message)
                    
                    # 自动生成.env模板
                    if st.button("生成.env模板文件"):
                        success, message = create_env_file()
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                # 其他一般错误
                st.info("未找到云端热词表，或者API连接失败")
        else:
            st.info(f"共找到 {len(vocabularies)} 个热词表，可用于提高视频字幕识别准确率")
            
            # 初始化删除状态
            if "delete_status" not in st.session_state:
                st.session_state.delete_status = {}
            
            # 为每个热词表创建卡片视图
            for vocab in vocabularies:
                vocab_id = vocab.get('vocabulary_id', '未命名热词表')
                vocab_name = vocab.get('name', vocab_id)
                create_time = vocab.get('gmt_create', '未知时间')
                status = vocab.get('status', '未知状态')
                
                # 创建卡片容器
                card = st.container()
                
                with card:
                    # 创建卡片样式的热词表展示
                    st.markdown(f"""
                    <div class="hotwords-card">
                        <div class="hotwords-card-header">
                            <h3>{vocab_name} <span class="hotword-id">ID: {vocab_id}</span></h3>
                            <div class="hotword-info">
                                <span class="hotword-date">创建时间: {create_time}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 获取热词表详情
                    vocab_details = st.session_state.get("vocabulary_details", {}).get(vocab_id)
                    if vocab_details:
                        # 提取热词列表
                        vocab_items = []
                        if "vocabulary" in vocab_details:
                            for item in vocab_details["vocabulary"]:
                                if "text" in item:
                                    # 提取权重和语言设置
                                    text = item.get("text", "")
                                    weight = item.get("weight", 4)
                                    lang = item.get("lang", "zh")
                                    vocab_items.append((text, weight, lang))
                        
                        if vocab_items:
                            # 使用HTML构建更丰富的热词展示，包括权重和语言设置
                            hotwords_html = []
                            for text, weight, lang in vocab_items:
                                hotwords_html.append(
                                    f'<span class="hotword-item">{text}'
                                    f'<span class="hotword-weight">权重:{weight}</span>'
                                    f'<span class="hotword-lang">语言:{lang}</span>'
                                    f'</span>'
                                )
                            
                            # 直接显示热词列表，不显示标题
                            st.markdown(
                                f'<div class="hotwords-list">{"".join(hotwords_html)}</div>', 
                                unsafe_allow_html=True
                            )
                        
                            # 添加操作按钮区域
                            col1, col2 = st.columns([1, 1])
                            
                            # 应用该热词列表按钮
                            with col1:
                                if vocab_id == current_hotword_id:
                                    st.success("✓ 当前使用中")
                                else:
                                    if st.button("应用该列表", key=f"apply_{vocab_id}"):
                                        success = hot_words_service.set_current_hotword_id(vocab_id)
                                        if success:
                                            st.success(f"已成功设置热词ID: {vocab_id}")
                                            # 重新加载页面以更新显示
                                            st.rerun()
                                        else:
                                            st.error("设置热词ID失败")
                        
                            # 删除按钮放在第二列
                            with col2:
                                # 对默认热词ID进行特殊处理，不允许删除
                                if vocab_id == "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b":
                                    st.info("默认热词表，不能删除")
                                else:
                                    # 删除按钮 - 避免嵌套列
                                    if vocab_id not in st.session_state.delete_status:
                                        # 初始未删除状态
                                        if st.button("删除此热词表", key=f"delete_{vocab_id}", type="secondary", help="删除此热词表"):
                                            # 标记为准备删除状态
                                            st.session_state.delete_status[vocab_id] = "confirm"
                                            st.rerun()
                                    elif st.session_state.delete_status[vocab_id] == "confirm":
                                        # 显示确认信息
                                        st.warning(f"确定要删除热词表 {vocab_id} 吗？此操作不可恢复!")
                                        
                                        # 使用两个并排按钮，但不嵌套列
                                        if st.button("✓ 确认删除", key=f"confirm_{vocab_id}", type="primary"):
                                            with st.spinner("正在删除热词表..."):
                                                success = hot_words_service.delete_cloud_vocabulary(vocab_id)
                                                if success:
                                                    st.success(f"已成功删除热词表 {vocab_id}")
                                                    # 清除缓存并刷新页面
                                                    if "cloud_vocabularies" in st.session_state:
                                                        del st.session_state.cloud_vocabularies
                                                    if "vocabulary_details" in st.session_state:
                                                        del st.session_state.vocabulary_details
                                                    del st.session_state.delete_status[vocab_id]
                                        
                                        if st.button("✗ 取消", key=f"cancel_{vocab_id}"):
                                            del st.session_state.delete_status[vocab_id]
                                            st.rerun()
                    
                    # 关闭卡片标签
                    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    show()