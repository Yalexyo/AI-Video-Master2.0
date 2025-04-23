import streamlit as st
import logging
import os
from datetime import datetime
import sys
from dotenv import load_dotenv
from src.ui_elements.simple_nav import create_sidebar_navigation

# 确保所有必要的目录结构存在
os.makedirs('logs', exist_ok=True)
os.makedirs(os.path.join('data', 'raw'), exist_ok=True)
os.makedirs(os.path.join('data', 'processed'), exist_ok=True)
os.makedirs(os.path.join('data', 'cache'), exist_ok=True)
os.makedirs(os.path.join('data', 'dimensions'), exist_ok=True)
os.makedirs(os.path.join('data', 'hotwords'), exist_ok=True)
os.makedirs(os.path.join('data', 'video_analysis', 'results'), exist_ok=True)
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
    简化的主应用入口函数，只负责初始化和重定向
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
        
        # 使用通用导航组件
        create_sidebar_navigation("视频分析")
        
        # 页面主体内容
        st.title("视频分析")
        st.markdown("使用视频分析功能处理您的视频")

        # 显示视频分析功能说明
        st.info("请使用左侧导航栏中的'视频分析'功能来分析您的视频内容。")
        
        # 提供跳转按钮
        if st.button("前往视频分析", type="primary"):
            st.switch_page("pages/video_analysis.py")
    
    except Exception as e:
        logger.error(f"加载页面出错: {str(e)}")
        st.error(f"启动应用时出错: {str(e)}")
        st.info("请尝试刷新页面，或点击[这里](/video_analysis)进入视频分析页面")

if __name__ == "__main__":
    main()

