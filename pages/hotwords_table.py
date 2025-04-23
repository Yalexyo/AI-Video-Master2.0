import streamlit as st
import logging
from src.core.hot_words_service import get_service

# 配置日志
logger = logging.getLogger(__name__)

def hotword_input_section():
    """热词表单输入区域，返回准备好的热词列表"""
    # 使用session_state存储热词列表
    if 'hotword_items' not in st.session_state:
        st.session_state.hotword_items = []  # 初始化为空列表
    
    # 替换现有文本输入为表格式输入
    st.markdown("### 热词输入")
    
    # 添加基本选项
    col1, col2 = st.columns([1, 1])
    with col1:
        auto_clean = st.checkbox("自动清理格式", value=True, 
                               help="自动删除空行和重复项")
    with col2:
        simple_mode = st.checkbox("极简模式", value=True,
                               help="使用极简模式可提高成功率，但每次最多只能提交10个热词")
    
    # 使用checkbox控制高级选项区域的显示/隐藏
    show_advanced = st.checkbox("显示高级选项", value=False)
    
    # 设置默认值
    default_weight = 4
    default_lang = "zh"
    
    # 高级选项区域 - 使用条件控制显示/隐藏
    if show_advanced:
        st.markdown("""
        ### 热词默认设置
        以下设置将作为添加热词时的默认值。您也可以在表格中为每个热词单独设置。
        """)
        
        # 热词权重设置 - 符合官方文档规定的范围[1,5]
        default_weight = st.slider("默认热词权重", 
                              min_value=1, max_value=5, value=4, step=1,
                              help="权重取值范围为[1, 5]之间的整数。常用值：4。权重较大时可能会引起负面效果。")
        
        st.markdown("""
        **权重说明**:
        - **1-2**: 轻微偏好，适合常见词
        - **3-4**: 中等偏好，推荐值
        - **5**: 强烈偏好，仅用于极特殊场景
        
        注意：官方文档建议权重通常使用4，如果效果不明显可适当增加，但权重过大可能导致其他词语识别不准确。
        """)
        
        # 语言选项 - 符合官方文档
        default_lang = st.selectbox("默认热词语言", 
                              options=["zh", "en"], 
                              index=0,
                              help="zh: 中文, en: 英文")
        
        st.markdown("""
        **语言选项**:
        - **zh**: 中文热词 (默认)
        - **en**: 英文热词
        
        请确保选择与热词本身语言一致的选项。
        """)
        
        st.info("注意: 根据阿里云官方文档，每个热词最长不超过10个汉字或英文单词，每个热词表最多添加500个词。")
    
    # 添加单个热词的表单
    with st.form(key="add_hotword_form", clear_on_submit=True):
        st.markdown("#### 添加热词")
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            new_hotword = st.text_input("热词文本", placeholder="输入一个热词，不超过10个汉字或英文单词")
        with col2:
            new_weight = st.select_slider("权重", options=[1, 2, 3, 4, 5], value=default_weight)
        with col3:
            new_lang = st.selectbox("语言", options=["zh", "en"], index=0 if default_lang == "zh" else 1)
        
        # 提交按钮
        submitted = st.form_submit_button("添加", use_container_width=True)
        if submitted and new_hotword.strip():
            # 添加新热词到session_state
            st.session_state.hotword_items.append({
                "text": new_hotword.strip(),
                "weight": new_weight,
                "lang": new_lang
            })
    
    # 批量导入功能
    with st.expander("批量导入热词", expanded=False):
        st.markdown("""
        每行输入一个热词，会使用默认的权重和语言设置。格式：`热词文本`
        """)
        batch_hotwords = st.text_area("每行一个热词", height=100, placeholder="每行输入一个热词，回车分隔")
        if st.button("批量导入", use_container_width=True):
            if batch_hotwords.strip():
                lines = batch_hotwords.split('\n')
                added = 0
                for line in lines:
                    text = line.strip()
                    if text:
                        st.session_state.hotword_items.append({
                            "text": text,
                            "weight": default_weight,
                            "lang": default_lang
                        })
                        added += 1
                if added > 0:
                    st.success(f"成功导入 {added} 个热词")
    
    # 显示当前热词列表
    if st.session_state.hotword_items:
        st.markdown("#### 当前热词列表")
        
        # 创建一个可编辑的表格
        with st.container():
            # 表头
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                st.markdown("**热词文本**")
            with col2:
                st.markdown("**权重**")
            with col3:
                st.markdown("**语言**")
            with col4:
                st.markdown("**操作**")
            
            # 限制显示的热词数量
            display_items = st.session_state.hotword_items
            if simple_mode and len(display_items) > 10:
                st.warning(f"极简模式下，仅显示前10个热词（共{len(display_items)}个）")
                display_items = display_items[:10]
            
            # 显示热词列表
            for i, item in enumerate(display_items):
                col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                with col1:
                    st.text(item["text"])
                with col2:
                    st.text(item["weight"])
                with col3:
                    st.text(item["lang"])
                with col4:
                    if st.button("删除", key=f"del_btn_{i}"):
                        st.session_state.hotword_items.pop(i)
                        st.rerun()
        
        # 添加清空按钮
        if st.button("清空热词列表", key="clear_hotwords"):
            st.session_state.hotword_items = []
            st.rerun()
    else:
        st.info("当前热词列表为空，请添加热词")
    
    # 返回热词列表，用于创建热词表
    return st.session_state.hotword_items, simple_mode

def show():
    """主页面入口"""
    # 仅作为测试使用，实际应用时会与完整页面集成
    st.title("热词表格输入测试")
    hotwords, simple_mode = hotword_input_section()
    
    if st.button("打印热词列表", key="print_hotwords"):
        st.write(hotwords)
        if simple_mode and len(hotwords) > 10:
            st.write("极简模式启用，将只使用前10个热词")

if __name__ == "__main__":
    show() 