import streamlit as st
import logging

# 配置日志
logger = logging.getLogger(__name__)

def inject_sidebar_style():
    """注入侧边栏CSS样式，每次页面加载时都注入，确保在页面切换后样式仍然存在"""
    custom_nav_style = """
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
    
    /* 侧边栏宽度最小化 */
    section[data-testid="stSidebar"] {
        width: 200px !important;
        min-width: 200px !important;
        max-width: 200px !important;
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
        padding: 1rem 0.5rem 0 0.5rem !important;
    }
    
    /* 侧边栏内部容器宽度设置 */
    section[data-testid="stSidebar"] > div {
        width: 100% !important;
    }
    
    /* 导航标题样式 */
    .sidebar-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1.2rem;
        margin-top: 0.5rem;
        text-align: center;
    }
    
    /* 导航分隔线 */
    .nav-divider {
        border-top: 1px solid #eee;
        margin: 0.5rem 0 1rem 0;
    }

    /* 统一导航容器样式 */
    .navigation-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 1rem;
    }
    
    /* 导航按钮样式 - 统一高度和间距 */
    .stButton>button {
        width: 100% !important;
        height: 40px !important;
        border-radius: 4px !important;
        transition: all 0.2s ease;
        padding: 0.5rem 0.5rem !important;
        font-size: 0.9rem !important;
        margin: 0 !important;
        box-sizing: border-box !important;
    }
    
    /* 激活状态显示 */
    .nav-button-active {
        background-color: #D22B2B !important;
        color: white !important;
        font-weight: bold !important;
        text-align: center;
        height: 40px;
        line-height: 40px;
        padding: 0 0.5rem;
        border-radius: 4px;
        width: 100%;
        display: block;
        cursor: default;
        font-size: 0.9rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin: 0 0 10px 0;
        box-sizing: border-box;
    }

    /* 普通按钮样式 - 针对Streamlit按钮 */
    .stButton>button {
        background-color: #f8f9fa !important;
        color: #333 !important;
        border: 1px solid #ddd !important;
    }

    /* 修复按钮之间的间距问题 */
    .element-container {
        margin-bottom: 10px !important;
    }
    
    /* 悬停效果 */
    .stButton>button:hover {
        background-color: #f0f0f0 !important;
        border-color: #ccc !important;
    }
    
    /* 调整页面过渡动画 */
    .main .block-container {
        animation: fadein 0.2s;
    }
    
    @keyframes fadein {
        from { opacity: 0; transform: translateY(5px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    </style>
    """
    # 总是注入，避免在页面切换后样式丢失
    st.markdown(custom_nav_style, unsafe_allow_html=True)

def create_sidebar_navigation(active_page="热词管理"):
    """
    在侧边栏创建导航菜单，只显示三个选项
    使用自定义HTML显示当前活动页面，使用Streamlit按钮实现导航
    
    参数:
    active_page - 当前活动页面名称
    """
    # 注入样式
    inject_sidebar_style()
    
    # 添加侧边栏标题
    st.sidebar.markdown('<div class="sidebar-title">AI视频大师</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="nav-divider"></div>', unsafe_allow_html=True)
    
    # 开始导航容器
    st.sidebar.markdown('<div class="navigation-container">', unsafe_allow_html=True)
    
    # 定义导航选项和对应页面
    nav_options = ["热词管理", "分析维度管理", "视频分析"]
    nav_pages = {
        "热词管理": "pages/hotwords.py",
        "分析维度管理": "pages/dimensions.py",
        "视频分析": "pages/video_analysis.py"
    }
    
    # 使用混合方式实现导航 - 活动页面使用HTML，其他使用Streamlit按钮
    for option in nav_options:
        is_current = option == active_page
        if is_current:
            # 当前页面显示为激活状态按钮 - 使用HTML
            st.sidebar.markdown(f'<div class="nav-button-active">{option}</div>', unsafe_allow_html=True)
        else:
            # 非活动页面使用标准Streamlit按钮
            if st.sidebar.button(option, key=f"btn_{option}", use_container_width=True):
                logger.info(f"导航: 从 {active_page} 切换到 {option}")
                st.switch_page(nav_pages[option])
    
    # 结束导航容器
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    return active_page 