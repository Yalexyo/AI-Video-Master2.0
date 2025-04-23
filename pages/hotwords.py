import streamlit as st
import pandas as pd
import logging
import os

from src.core.hot_words_service import HotWordsService
from src.ui_elements.simple_nav import create_sidebar_navigation
from src.config.settings import HOTWORDS_DIR

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
</style>
""", unsafe_allow_html=True)

# 配置日志
logger = logging.getLogger(__name__)

def show():
    """渲染热词管理页面"""
    # 添加导航栏, 并标记当前页面
    create_sidebar_navigation("热词管理")
    
    # 页面标题
    st.title("热词管理")
    st.markdown("---")
        
    # 确保热词目录存在
    os.makedirs(HOTWORDS_DIR, exist_ok=True)
    
    # 初始化热词服务
    hot_words_service = HotWordsService()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("当前热词列表")
        # 获取当前热词列表并显示
        hot_words = hot_words_service.list_hot_words()
        
        if not hot_words:
            st.info("当前没有热词，请添加新热词")
        else:
            # 将热词列表转换为DataFrame以便展示
            hot_words_df = pd.DataFrame({
                "热词": hot_words,
                "操作": ["删除"] * len(hot_words)
            })
            
            # 使用st.data_editor显示可编辑表格
            edited_df = st.data_editor(
                hot_words_df,
                column_config={
                    "热词": st.column_config.TextColumn("热词"),
                    "操作": st.column_config.SelectboxColumn(
                        "操作",
                        options=["删除", "保留"],
                        default="保留"
                    )
                },
                hide_index=True,
                key="hot_words_editor"
            )
            
            # 处理删除操作
            if st.button("应用更改", type="primary"):
                words_to_delete = edited_df[edited_df["操作"] == "删除"]["热词"].tolist()
                
                for word in words_to_delete:
                    hot_words_service.delete_hot_word(word)
                    logger.info(f"删除热词: {word}")
                
                # 重新加载页面
                st.success(f"成功删除 {len(words_to_delete)} 个热词")
                st.rerun()
    
    with col2:
        st.subheader("添加新热词")
        
        # 添加新热词的表单
        with st.form(key="add_hot_word_form"):
            new_hot_word = st.text_input("输入新热词")
            submit_button = st.form_submit_button(label="添加", type="primary")
            
            if submit_button and new_hot_word:
                if hot_words_service.add_hot_word(new_hot_word):
                    st.success(f"成功添加热词: {new_hot_word}")
                    # 重新加载页面
                    st.rerun()
                else:
                    st.error(f"热词 '{new_hot_word}' 已存在")
            elif submit_button:
                st.warning("请输入热词内容")
        
        # 批量导入热词功能
        st.subheader("批量导入热词")
        with st.form(key="import_hot_words_form"):
            hot_words_text = st.text_area("每行输入一个热词")
            import_button = st.form_submit_button(label="导入", type="primary")
            
            if import_button and hot_words_text:
                # 分割文本并去除空行
                new_hot_words = [word.strip() for word in hot_words_text.split("\n") if word.strip()]
                
                if new_hot_words:
                    # 记录已添加和已存在的热词
                    added = []
                    existed = []
                    
                    for word in new_hot_words:
                        if hot_words_service.add_hot_word(word):
                            added.append(word)
                        else:
                            existed.append(word)
                    
                    # 显示结果信息
                    if added:
                        st.success(f"成功添加 {len(added)} 个热词")
                    
                    if existed:
                        st.warning(f"{len(existed)} 个热词已存在")
                    
                    # 重新加载页面以显示最新数据
                    st.rerun()
                else:
                    st.warning("未找到有效的热词")
            elif import_button:
                st.warning("请输入热词内容")

if __name__ == "__main__":
    show()