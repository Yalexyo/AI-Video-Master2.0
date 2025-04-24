import streamlit as st
import os
import json
import pandas as pd
import logging
import sys
from datetime import datetime
import time
from src.ui_elements.simple_nav import create_sidebar_navigation

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 设置页面标题和图标
st.set_page_config(
    page_title="AI视频大师 - 视频分析",
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

# 直接导入工具类
try:
    from utils.analyzer import VideoAnalyzer
    from utils.processor import VideoProcessor
except ImportError as e:
    st.error(f"导入工具模块失败: {e}")
    # 备用导入方式
    import importlib.util
    
    def import_from_file(module_name, file_path):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    try:
        analyzer_path = os.path.join(project_root, "utils", "analyzer.py")
        processor_path = os.path.join(project_root, "utils", "processor.py")
        
        analyzer_module = import_from_file("analyzer", analyzer_path)
        processor_module = import_from_file("processor", processor_path)
        
        VideoAnalyzer = analyzer_module.VideoAnalyzer
        VideoProcessor = processor_module.VideoProcessor
    except Exception as e:
        st.error(f"备用导入方式也失败: {e}")

# 导入热词服务
from src.core.hot_words_service import HotWordsService

# 配置日志
logger = logging.getLogger(__name__)

# 文件路径
ANALYSIS_RESULTS_DIR = os.path.join('data', 'video_analysis', 'results')

# 默认热词表ID
DEFAULT_VOCABULARY_ID = "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b"

# 初始化热词服务
hot_words_service = HotWordsService()

from src.ui_elements.custom_theme import set_custom_theme

def load_dimensions():
    """加载当前维度结构"""
    if 'dimensions' in st.session_state:
        return st.session_state.dimensions
    else:
        return {'title': "", 'level1': [], 'level2': {}}

def process_video_analysis(file, analysis_type, dimensions=None, keywords=None, vocabulary_id=None):
    """处理视频分析"""
    # 确保结果目录存在
    os.makedirs(ANALYSIS_RESULTS_DIR, exist_ok=True)
    
    # 记录使用的热词表ID
    if vocabulary_id:
        logger.info(f"使用热词表ID进行视频分析: {vocabulary_id}")
    
    try:
        # 读取CSV文件
        df = pd.read_csv(file)
        
        # 模拟处理过程
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 分析结果
        results = {
            'type': analysis_type,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'matches': []
        }
        
        if analysis_type == "维度分析":
            results['dimensions'] = dimensions
            
            # 处理每个维度
            total_steps = len(dimensions.get('level1', []))
            for i, dim1 in enumerate(dimensions.get('level1', [])):
                status_text.text(f"正在分析维度: {dim1}")
                
                # 模拟处理时间
                time.sleep(0.5)
                
                # 对于每个二级维度
                for dim2 in dimensions.get('level2', {}).get(dim1, []):
                    # 模拟匹配
                    # 实际情况下，这里应该有基于NLP或其他算法的匹配逻辑
                    # 这里我们只是随机选择几条记录作为示例
                    matches = df.sample(min(3, len(df))).to_dict('records')
                    
                    for match in matches:
                        results['matches'].append({
                            'dimension_level1': dim1,
                            'dimension_level2': dim2,
                            'timestamp': match.get('timestamp', '00:00:00'),
                            'text': match.get('text', ''),
                            'score': 0.75  # 模拟匹配分数
                        })
                
                # 更新进度
                progress_bar.progress((i + 1) / total_steps)
        
        elif analysis_type == "关键词分析":
            results['keywords'] = keywords
            
            # 处理每个关键词
            total_steps = len(keywords)
            for i, keyword in enumerate(keywords):
                status_text.text(f"正在分析关键词: {keyword}")
                
                # 模拟处理时间
                time.sleep(0.5)
                
                # 模拟匹配
                matches = df[df['text'].str.contains(keyword, case=False, na=False)].to_dict('records')
                
                for match in matches:
                    results['matches'].append({
                        'keyword': keyword,
                        'timestamp': match.get('timestamp', '00:00:00'),
                        'text': match.get('text', ''),
                        'score': 0.85  # 模拟匹配分数
                    })
                
                # 更新进度
                progress_bar.progress((i + 1) / total_steps)
        
        # 完成处理
        progress_bar.progress(100)
        status_text.text("分析完成！")
        
        # 保存结果
        result_file = os.path.join(ANALYSIS_RESULTS_DIR, f"analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results, result_file
    
    except Exception as e:
        logger.error(f"处理视频分析时出错: {str(e)}")
        st.error(f"处理失败: {str(e)}")
        return None, None

def show_analysis_results(results, result_file):
    """显示分析结果"""
    if not results:
        return
    
    st.markdown("## 分析结果")
    
    # 显示基本信息
    st.markdown(f"**分析类型**: {results['type']}")
    st.markdown(f"**分析时间**: {results['timestamp']}")
    st.markdown(f"**匹配数量**: {len(results['matches'])}")
    
    # 下载按钮
    with open(result_file, 'r', encoding='utf-8') as f:
        json_data = f.read()
        st.download_button(
            label="下载分析结果 (JSON)",
            data=json_data,
            file_name=os.path.basename(result_file),
            mime="application/json"
        )
    
    # 显示匹配结果
    st.markdown("### 匹配详情")
    
    if results['type'] == "维度分析":
        # 按维度分组显示
        for dim1 in results.get('dimensions', {}).get('level1', []):
            # 过滤出当前一级维度的匹配
            dim1_matches = [m for m in results['matches'] if m['dimension_level1'] == dim1]
            
            if dim1_matches:
                with st.expander(f"{dim1} ({len(dim1_matches)}个匹配)", expanded=False):
                    # 按二级维度分组
                    for dim2 in results.get('dimensions', {}).get('level2', {}).get(dim1, []):
                        # 过滤出当前二级维度的匹配
                        dim2_matches = [m for m in dim1_matches if m['dimension_level2'] == dim2]
                        
                        if dim2_matches:
                            st.markdown(f"#### {dim2} ({len(dim2_matches)}个匹配)")
                            
                            # 显示每个匹配
                            for match in dim2_matches:
                                st.markdown(f"""
                                **时间点**: {match['timestamp']}  
                                **匹配分数**: {match['score']:.2f}  
                                **文本**: {match['text']}  
                                ---
                                """)
    
    elif results['type'] == "关键词分析":
        # 按关键词分组显示
        for keyword in results.get('keywords', []):
            # 过滤出当前关键词的匹配
            keyword_matches = [m for m in results['matches'] if m['keyword'] == keyword]
            
            if keyword_matches:
                with st.expander(f"关键词: {keyword} ({len(keyword_matches)}个匹配)", expanded=False):
                    # 显示每个匹配
                    for match in keyword_matches:
                        st.markdown(f"""
                        **时间点**: {match['timestamp']}  
                        **匹配分数**: {match['score']:.2f}  
                        **文本**: {match['text']}  
                        ---
                        """)

def show():
    """显示视频分析页面"""
    # 设置自定义主题
    set_custom_theme()
    
    # 使用通用导航组件
    create_sidebar_navigation("视频分析")
    
    # 页面主体内容
    st.title("视频分析")
    
    # 加载默认热词表ID
    if "selected_vocabulary_id" not in st.session_state:
        # 尝试从配置中获取默认热词表ID
        try:
            default_id = hot_words_service.get_default_vocabulary_id()
            st.session_state.selected_vocabulary_id = default_id if default_id else DEFAULT_VOCABULARY_ID
            logger.info(f"已设置默认热词表ID: {st.session_state.selected_vocabulary_id}")
        except Exception as e:
            logger.error(f"加载默认热词表出错: {str(e)}")
            st.session_state.selected_vocabulary_id = DEFAULT_VOCABULARY_ID
    
    # 创建选项卡
    upload_tab, analysis_tab = st.tabs(["上传视频", "分析设置"])
    
    # 上传视频选项卡
    with upload_tab:
        st.header("上传视频")
        
        # 添加热词表选择
        st.subheader("转录设置")
        
        # 加载所有可用的热词表
        with st.spinner("加载热词表..."):
            vocabularies, error_msg = hot_words_service.check_cloud_hotwords()
        
        if vocabularies:
            # 创建热词表选择下拉框
            vocab_options = []
            vocab_display_names = []
            
            for vocab in vocabularies:
                vocab_id = vocab.get('vocabulary_id', '')
                vocab_name = vocab.get('name', vocab_id)
                vocab_options.append(vocab_id)
                vocab_display_names.append(f"{vocab_name} ({vocab_id})")
            
            # 找到当前选中ID在列表中的索引
            selected_index = 0
            if st.session_state.selected_vocabulary_id in vocab_options:
                selected_index = vocab_options.index(st.session_state.selected_vocabulary_id)
            
            # 显示热词表选择下拉框
            selected_display = st.selectbox(
                "选择用于视频转录的热词表",
                options=vocab_display_names,
                index=selected_index,
                help="热词表将用于提高特定词汇的识别准确率"
            )
            
            # 更新选中的热词表ID
            selected_index = vocab_display_names.index(selected_display)
            st.session_state.selected_vocabulary_id = vocab_options[selected_index]
            
            # 显示当前选中的热词表ID以及热词管理提示
            current_hotword_name = selected_display.split(' (')[0]
            current_hotword_id = st.session_state.selected_vocabulary_id
            st.info(f"当前选中的热词表: {current_hotword_id}，要添加或修改热词表，请前往【热词管理页面】")
        else:
            if error_msg:
                st.warning(f"加载热词表失败: {error_msg}")
            else:
                st.warning("未找到可用的热词表，将使用默认设置进行转录")
            
            # 使用默认热词表ID
            st.session_state.selected_vocabulary_id = DEFAULT_VOCABULARY_ID
        
        uploaded_file = st.file_uploader("选择要分析的视频文件", type=["mp4", "mov", "avi", "mkv"], help="支持常见视频格式")
        
        if uploaded_file:
            # 显示上传的视频信息
            st.video(uploaded_file)
            st.info(f"文件名: {uploaded_file.name}, 大小: {uploaded_file.size} 字节")
            
            # 将上传的视频保存到临时目录
            temp_video_path = os.path.join("data", "temp", uploaded_file.name)
            with open(temp_video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"视频已保存到: {temp_video_path}")
            
            # 保存视频路径到会话状态
            st.session_state.video_path = temp_video_path
    
    # 分析设置选项卡
    with analysis_tab:
        st.header("分析设置")
        
        if 'video_path' not in st.session_state:
            st.warning("请先上传视频")
        else:
            # 分析类型选择
            analysis_type = st.radio("选择分析类型", ["维度分析", "关键词分析"])
            
            if analysis_type == "维度分析":
                # 显示维度选择
                st.subheader("维度选择")
                
                # 加载当前维度结构
                dimensions = load_dimensions()
                
                if not dimensions or not dimensions.get('level1'):
                    st.warning("未找到有效的分析维度。请前往维度管理页面创建或加载维度模板。")
                else:
                    st.markdown(f"**当前加载的维度模板**: {dimensions.get('title', '未命名')}")
                    
                    # 显示维度列表
                    for dim1 in dimensions.get('level1', []):
                        with st.expander(f"{dim1}", expanded=False):
                            # 显示二级维度
                            dim2_list = dimensions.get('level2', {}).get(dim1, [])
                            if dim2_list:
                                st.markdown(", ".join(dim2_list))
                            else:
                                st.markdown("*无二级维度*")
                    
                    # 点击分析按钮
                    if st.button("开始维度分析", key="dim_analysis_btn"):
                        # 模拟文件处理并生成结果
                        with st.spinner("正在处理视频分析..."):
                            # 这里应该有实际的视频处理逻辑
                            # 现在我们只是模拟一个CSV文件作为输入
                            sample_data_path = os.path.join("data", "temp", "sample_subtitles.csv")
                            
                            # 检查是否存在样本数据，如果不存在则创建
                            if not os.path.exists(sample_data_path):
                                # 创建目录
                                os.makedirs(os.path.dirname(sample_data_path), exist_ok=True)
                                
                                # 创建样本数据
                                sample_data = pd.DataFrame({
                                    'timestamp': ['00:00:10', '00:00:20', '00:00:30', '00:00:40', '00:00:50'],
                                    'text': [
                                        '品牌的影响力正在不断增长',
                                        '我们需要提高用户的品牌认知度',
                                        '用户体验是我们产品的核心竞争力',
                                        '创新是推动品牌向前发展的关键',
                                        '我们的产品质量得到了用户的高度认可'
                                    ]
                                })
                                sample_data.to_csv(sample_data_path, index=False)
                            
                            # 处理分析 - 传入当前选中的热词表ID
                            results, result_file = process_video_analysis(
                                sample_data_path, 
                                "维度分析", 
                                dimensions,
                                vocabulary_id=st.session_state.selected_vocabulary_id
                            )
                            
                            # 显示结果
                            if results:
                                show_analysis_results(results, result_file)
            
            elif analysis_type == "关键词分析":
                # 显示关键词输入
                st.subheader("关键词设置")
                keywords_input = st.text_area("输入关键词（每行一个）", height=150)
                
                if keywords_input.strip():
                    # 处理关键词
                    keywords = [kw.strip() for kw in keywords_input.split('\n') if kw.strip()]
                    st.markdown(f"已输入 {len(keywords)} 个关键词")
                    
                    # 点击分析按钮
                    if st.button("开始关键词分析", key="kw_analysis_btn"):
                        # 模拟文件处理并生成结果
                        with st.spinner("正在处理视频分析..."):
                            # 这里应该有实际的视频处理逻辑
                            # 现在我们只是模拟一个CSV文件作为输入
                            sample_data_path = os.path.join("data", "temp", "sample_subtitles.csv")
                            
                            # 检查是否存在样本数据，如果不存在则创建
                            if not os.path.exists(sample_data_path):
                                # 创建目录
                                os.makedirs(os.path.dirname(sample_data_path), exist_ok=True)
                                
                                # 创建样本数据
                                sample_data = pd.DataFrame({
                                    'timestamp': ['00:00:10', '00:00:20', '00:00:30', '00:00:40', '00:00:50'],
                                    'text': [
                                        '品牌的影响力正在不断增长',
                                        '我们需要提高用户的品牌认知度',
                                        '用户体验是我们产品的核心竞争力',
                                        '创新是推动品牌向前发展的关键',
                                        '我们的产品质量得到了用户的高度认可'
                                    ]
                                })
                                sample_data.to_csv(sample_data_path, index=False)
                            
                            # 处理分析 - 传入当前选中的热词表ID
                            results, result_file = process_video_analysis(
                                sample_data_path, 
                                "关键词分析", 
                                keywords=keywords,
                                vocabulary_id=st.session_state.selected_vocabulary_id
                            )
                            
                            # 显示结果
                            if results:
                                show_analysis_results(results, result_file)
                else:
                    st.warning("请输入至少一个关键词")

if __name__ == "__main__":
    show() 