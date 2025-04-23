import streamlit as st
import os
import json
import logging
from datetime import datetime
from src.core.hot_words_service import get_service

# 配置日志
logger = logging.getLogger(__name__)

def show():
    """显示热词管理页面"""
    # 设置页面标题和图标
    st.set_page_config(
        page_title="AI视频大师 - 热词管理",
        page_icon="🎬",
        layout="wide"
    )
    
    # 使用CSS隐藏文件浏览器和其他不需要的元素
    hide_streamlit_style = """
        <style>
        /* 隐藏顶部的文件浏览器和其他开发者选项 */
        #MainMenu {visibility: hidden;}
        div[data-testid="stToolbar"] {visibility: hidden !important;}
        div[data-testid="stDecoration"] {visibility: hidden !important;}
        div[data-testid="stStatusWidget"] {visibility: hidden !important;}
        footer {visibility: hidden !important;}
        
        /* 确保边栏导航标题正常显示 */
        #sidebar-content {visibility: visible !important;}
        section[data-testid="stSidebar"] {visibility: visible !important;}
        
        /* 修复侧边栏样式 */
        .css-1d391kg {padding-top: 3.5rem;}
        
        /* 隐藏app导航项 */
        [data-testid="stSidebarNav"] ul li:first-child,
        [data-testid="baseButton-headerNoPadding"],
        .stApp header,
        div[data-testid="stSidebarNavItems"],
        [data-testid="stSidebarNav"],
        header[data-testid="stHeader"] {
            display: none !important;
        }
        
        /* 隐藏streamlit自带导航 */
        div.css-1q1n0ol.egzxvld0,
        div.css-uc1cuc.e1fqkh3o4,
        [data-testid="stSidebarNav"] ul {
            display: none !important;
        }
        
        /* 页面过渡动画 */
        .main .block-container {
            animation: fadein 0.3s;
        }
        
        @keyframes fadein {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        
        /* 统一侧边栏样式 */
        div[data-testid="stSidebar"] {
            background-color: #f8f9fa !important;
            border-right: 1px solid #eee !important;
        }
        
        div[data-testid="stSidebar"] button[kind="secondary"] {
            background-color: transparent !important;
            border: none !important;
            text-align: left !important;
            font-weight: normal !important;
            padding: 0.5rem 1rem !important;
            border-radius: 4px !important;
            margin-bottom: 5px !important;
            transition: background-color 0.2s, color 0.2s !important;
            width: 100% !important;
        }
        
        div[data-testid="stSidebar"] button[kind="secondary"]:hover {
            background-color: #e9ecef !important;
            color: #000 !important;
        }
        
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
            padding-top: 1rem !important;
        }
        
        div[data-testid="stSidebar"] [aria-selected="true"] {
            background-color: #e9ecef !important;
            font-weight: bold !important;
        }
        </style>
    """
    
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # 侧边栏导航
    with st.sidebar:
        st.title("AI视频大师")
        st.markdown("---")
        
        # 导航选项
        selected_page = st.radio(
            "导航",
            ["热词管理", "分析维度管理", "视频分析"],
            index=0,  # 热词管理页面默认选中第一项
            key="nav",
            label_visibility="collapsed"
        )
        
        # 处理页面导航
        if selected_page == "分析维度管理":
            st.switch_page("pages/dimensions.py")
        elif selected_page == "视频分析":
            st.switch_page("pages/video_analysis.py")
    
    # 页面主体内容
    st.title("热词管理")
    st.markdown("管理语音识别的热词表，提高字幕识别准确率")
    
    # 获取热词服务
    hotwords_service = get_service()
    
    # 显示API状态
    api_status = hotwords_service.api.check_api_key()
    if not api_status:
        st.warning("未设置DASHSCOPE_API_KEY，某些功能可能不可用")
        st.info("请在.env文件中设置DASHSCOPE_API_KEY环境变量后重启应用")
    
    # 加载热词数据
    if 'hotwords_data' not in st.session_state:
        st.session_state.hotwords_data = hotwords_service.load_hotwords()
    
    # 页面布局 - 使用两列
    left_col, right_col = st.columns([2, 3])
    
    # 左侧列 - 热词分类管理
    with left_col:
        st.subheader("热词分类管理")
        
        # 云端热词同步区
        with st.expander("阿里云热词同步", expanded=api_status):
            if api_status:
                # 检查云端热词按钮
                if st.button("🔍 检查云端热词表", key="check_cloud_hotwords_btn", use_container_width=True):
                    with st.spinner("正在检查阿里云热词表..."):
                        vocabularies, error_msg = hotwords_service.check_cloud_hotwords()
                        
                        if error_msg:
                            st.error(error_msg)
                        elif not vocabularies:
                            st.info("未在阿里云上找到任何热词表")
                        else:
                            st.success(f"找到 {len(vocabularies)} 个热词表")
                            st.session_state.cloud_vocabularies = vocabularies
                # 显示云端热词信息（如果有）
                if 'cloud_vocabularies' in st.session_state and st.session_state.cloud_vocabularies:
                    st.divider()
                    st.markdown("**云端热词表**")
                    
                    for i, vocab in enumerate(st.session_state.cloud_vocabularies, 1):
                        vocab_id = vocab.get('vocabulary_id', 'N/A')
                        vocab_name = vocab.get('name', '')
                        word_list = vocab.get('word_list', [])
                        word_count = len(word_list) if word_list else 0
                        
                        with st.expander(f"{i}. {vocab_name if vocab_name else '无名称 (将使用默认分类名)'}"):
                            st.markdown(f"**ID**: {vocab_id}")
                            st.markdown(f"**热词数量**: {word_count}")
                            
                            if word_list:
                                words_text = []
                                for word in word_list[:8]:
                                    word_text = word['text'] if isinstance(word, dict) and 'text' in word else word
                                    words_text.append(word_text)
                                
                                st.markdown(f"**热词**: {', '.join(words_text)}" + (f"... 等{word_count}个" if word_count > 8 else ""))
            else:
                st.info("请先设置API密钥以启用云端同步功能")
        
        # 添加新分类的表单
        hotwords_data = st.session_state.hotwords_data
        categories = list(hotwords_data['categories'].keys())
        
        with st.expander("添加新热词分类", expanded=len(categories) == 0):
            new_category = st.text_input("分类名称", key="new_category", placeholder="输入新分类名称")
            if st.button("添加分类", key="add_category_btn", use_container_width=True):
                if new_category:
                    if new_category not in hotwords_data['categories']:
                        if hotwords_service.add_category(new_category):
                            st.success(f"已添加分类: {new_category}")
                            # 刷新数据
                            st.session_state.hotwords_data = hotwords_service.load_hotwords()
                            st.rerun()
                        else:
                            st.error("添加分类失败")
                    else:
                        st.warning(f"分类 '{new_category}' 已存在")
                else:
                    st.warning("请输入分类名称")
        
        # 显示分类列表
        categories = list(hotwords_data['categories'].keys())
        if categories:
            st.markdown("### 热词分类列表")
            
            # 显示分类卡片
            for category in categories:
                vocab_id = hotwords_data.get('vocabulary_ids', {}).get(category, 'N/A')
                hotword_count = len(hotwords_data['categories'][category])
                
                col1, col2, col3 = st.columns([5, 2, 2])
                with col1:
                    if st.button(f"📂 {category}", key=f"select_{category}", use_container_width=True):
                        st.session_state.selected_category = category
                        st.rerun()
                with col2:
                    st.markdown(f"**{hotword_count}** 热词")
                with col3:
                    if st.button("🗑️", key=f"delete_{category}"):
                        if hotwords_service.delete_category(category):
                            st.success(f"已删除分类: {category}")
                            # 如果删除的是当前选中的分类，清除选择
                            if 'selected_category' in st.session_state and st.session_state.selected_category == category:
                                del st.session_state.selected_category
                            # 刷新数据
                            st.session_state.hotwords_data = hotwords_service.load_hotwords()
                            st.rerun()
        else:
            st.info("请先添加热词分类或从阿里云同步")
        
        # 显示最后更新时间
        if hotwords_data.get('last_updated'):
            st.caption(f"最后更新时间: {hotwords_data['last_updated']}")
    
    # 右侧列 - 热词内容管理
    with right_col:
        if 'selected_category' in st.session_state and st.session_state.selected_category in categories:
            selected_category = st.session_state.selected_category
            
            st.subheader(f"{selected_category} - 热词管理")
            
            # 显示热词表ID（如果有）
            if 'vocabulary_ids' in hotwords_data and selected_category in hotwords_data['vocabulary_ids']:
                vocab_id = hotwords_data['vocabulary_ids'][selected_category]
                st.info(f"热词表ID: {vocab_id}")
            
            # 云端同步按钮
            if api_status:
                if st.button("⬆️ 同步到阿里云", key=f"sync_btn_{selected_category}", use_container_width=True):
                    # 刷新数据确保最新
                    hotwords_data = hotwords_service.load_hotwords()
                    
                    # 手动触发同步
                    hotwords_service._sync_category_to_api(hotwords_data, selected_category)
                    
                    # 保存更新的数据
                    if hotwords_service.save_hotwords(hotwords_data):
                        st.success(f"已同步 {selected_category} 分类的热词到阿里云")
                        # 刷新数据
                        st.session_state.hotwords_data = hotwords_service.load_hotwords()
                        st.rerun()
                    else:
                        st.error("同步热词失败")
            
            # 添加热词的表单
            st.markdown("### 添加热词")
            input_col, button_col = st.columns([4, 1])
            with input_col:
                new_hotword = st.text_input("输入热词", key=f"new_hotword_{selected_category}", placeholder="输入新热词")
            with button_col:
                if st.button("添加", key=f"add_hotword_btn_{selected_category}", use_container_width=True):
                    current_hotwords = hotwords_data['categories'].get(selected_category, [])
                    if new_hotword:
                        if new_hotword not in current_hotwords:
                            if hotwords_service.add_hotword(selected_category, new_hotword):
                                st.success(f"已添加热词: {new_hotword}")
                                # 刷新数据
                                st.session_state.hotwords_data = hotwords_service.load_hotwords()
                                st.rerun()
                            else:
                                st.error("添加热词失败")
                        else:
                            st.warning(f"热词 '{new_hotword}' 已存在")
                    else:
                        st.warning("请输入热词")
            
            # 批量添加热词
            with st.expander("批量添加热词"):
                batch_hotwords = st.text_area("每行一个热词", key=f"batch_hotwords_{selected_category}", 
                                          height=100, placeholder="每行输入一个热词，回车分隔")
                if st.button("批量添加", key=f"batch_add_btn_{selected_category}", use_container_width=True):
                    if batch_hotwords:
                        # 分割文本为行
                        new_words = [line.strip() for line in batch_hotwords.split('\n') if line.strip()]
                        
                        if new_words:
                            added_count = hotwords_service.batch_add_hotwords(selected_category, new_words)
                            if added_count > 0:
                                st.success(f"已添加 {added_count} 个热词")
                                # 刷新数据
                                st.session_state.hotwords_data = hotwords_service.load_hotwords()
                                st.rerun()
                            else:
                                st.warning("没有可添加的新热词")
                        else:
                            st.warning("没有可添加的热词")
                    else:
                        st.warning("请输入热词")
            
            # 显示当前热词列表
            current_hotwords = hotwords_data['categories'].get(selected_category, [])
            
            if current_hotwords:
                st.markdown("### 热词列表")
                
                # 搜索框
                search_term = st.text_input("搜索热词", key=f"search_{selected_category}", placeholder="输入关键词过滤热词列表")
                
                # 过滤热词
                if search_term:
                    filtered_hotwords = [word for word in current_hotwords if search_term.lower() in word.lower()]
                else:
                    filtered_hotwords = current_hotwords
                
                # 分页显示
                page_size = 30
                total_pages = (len(filtered_hotwords) - 1) // page_size + 1
                
                if total_pages > 1:
                    col1, col2, col3 = st.columns([1, 3, 1])
                    with col2:
                        page = st.select_slider(
                            "页码",
                            options=list(range(1, total_pages + 1)),
                            key=f"page_{selected_category}"
                        )
                else:
                    page = 1
                
                start_idx = (page - 1) * page_size
                end_idx = min(start_idx + page_size, len(filtered_hotwords))
                
                # 网格显示热词
                if filtered_hotwords:
                    # 使用3列布局
                    cols = st.columns(3)
                    for i, word in enumerate(filtered_hotwords[start_idx:end_idx]):
                        col_idx = i % 3
                        with cols[col_idx]:
                            col1, col2 = st.columns([4, 1])
                            col1.markdown(f"**{start_idx + i + 1}.** {word}")
                            if col2.button("🗑️", key=f"del_btn_{selected_category}_{start_idx + i}"):
                                if hotwords_service.delete_hotword(selected_category, word):
                                    st.success(f"已删除热词: {word}")
                                    # 刷新数据
                                    st.session_state.hotwords_data = hotwords_service.load_hotwords()
                                    st.rerun()
                                else:
                                    st.error("删除热词失败")
                    
                    # 显示分页信息
                    if total_pages > 1:
                        st.caption(f"显示 {start_idx + 1}-{end_idx} / 共 {len(filtered_hotwords)} 个热词")
                else:
                    if search_term:
                        st.info(f"没有找到包含 '{search_term}' 的热词")
                    else:
                        st.info(f"分类 '{selected_category}' 下还没有热词")
        else:
            st.info("👈 请从左侧选择一个热词分类或创建新分类")

if __name__ == "__main__":
    show()