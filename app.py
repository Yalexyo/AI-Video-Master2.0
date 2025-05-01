import streamlit as st
import logging
import os
from datetime import datetime
import sys
from dotenv import load_dotenv
from src.ui_elements.simple_nav import create_sidebar_navigation
from pathlib import Path

# 从settings.py导入所需配置
from src.config.settings import VIDEO_ANALYSIS_DIR

# 确保所有必要的目录结构存在
os.makedirs('logs', exist_ok=True)
os.makedirs(os.path.join('data', 'raw'), exist_ok=True)
os.makedirs(os.path.join('data', 'processed'), exist_ok=True)
os.makedirs(os.path.join('data', 'cache'), exist_ok=True)
os.makedirs(os.path.join('data', 'dimensions'), exist_ok=True)
os.makedirs(os.path.join('data', 'hotwords'), exist_ok=True)
os.makedirs(os.path.join(VIDEO_ANALYSIS_DIR, 'results'), exist_ok=True)
os.makedirs(os.path.join('data', 'temp'), exist_ok=True)

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', f'app_{datetime.now().strftime("%Y%m%d")}.log'), 'a', 'utf-8')
    ]
)

# 主页面
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 加载环境变量
load_dotenv(verbose=True)
api_key = os.environ.get('DASHSCOPE_API_KEY')
if api_key:
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    logger.info(f"从.env文件加载API密钥: {masked_key}")
else:
    logger.warning("无法从.env文件加载DASHSCOPE_API_KEY")

def main():
    """
    简化的主应用入口函数，通过自动跳转到视频内容智能搜索页面
    """
    try:
        logger.info("启动应用")
        
        # 设置页面标题和图标
        st.set_page_config(
            page_title="AI视频大师",
            page_icon="🎬",
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
        
        # 初始化session_state
        if 'first_run' not in st.session_state:
            st.session_state.first_run = True
            # 初始化其他可能需要的session变量
            if 'templates' not in st.session_state:
                st.session_state.templates = {}
            if 'dimensions' not in st.session_state:
                st.session_state.dimensions = {'title': '品牌认知', 'level1': [], 'level2': {}}
        
        # 自动跳转到视频内容智能搜索页面
        st.markdown("""
        <meta http-equiv="refresh" content="0;url=/video_search" />
        <script>
            window.location.href = "/video_search"
        </script>
        """, unsafe_allow_html=True)

        # 显示备用链接，以防自动跳转失败
        st.info("正在跳转到视频内容智能搜索页面，如果没有自动跳转，请点击下方按钮")
        
        if st.button("前往视频内容智能搜索页面", type="primary"):
            st.switch_page("pages/video_search.py")
    
    except Exception as e:
        logger.error(f"加载页面出错: {str(e)}")
        st.error(f"启动应用时出错: {str(e)}")
        st.info("请尝试刷新页面，或点击[这里](/video_search)进入视频内容智能搜索页面")

if __name__ == "__main__":
    main()

