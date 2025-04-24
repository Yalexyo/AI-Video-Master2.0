import streamlit as st
import os
import json
import pandas as pd
import logging
import sys
from datetime import datetime
import time
from src.ui_elements.simple_nav import create_sidebar_navigation
import urllib.parse

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

# 配置日志
logger = logging.getLogger(__name__)

# 文件路径
ANALYSIS_RESULTS_DIR = os.path.join('data', 'video_analysis', 'results')

from src.ui_elements.custom_theme import set_custom_theme

def load_dimensions():
    """加载当前维度结构"""
    if 'dimensions' in st.session_state:
        return st.session_state.dimensions
    else:
        return {'title': "", 'level1': [], 'level2': {}}

def process_video_analysis(file, analysis_type, dimensions=None, keywords=None):
    """处理视频分析"""
    # 确保结果目录存在
    os.makedirs(ANALYSIS_RESULTS_DIR, exist_ok=True)
    
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
    
    # 显示视频信息（如果有）
    if 'video_info' in results:
        video_info = results['video_info']
        st.markdown(f"""
        **视频信息**:  
        - 文件名: {video_info.get('file_name', '未知')}  
        - 对象名: {video_info.get('object', '未知')}
        """)
    
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
    
    # 创建选项卡
    upload_tab, analysis_tab = st.tabs(["上传视频", "分析设置"])
    
    # 上传视频选项卡
    with upload_tab:
        st.header("上传视频")
        
        # 方式一：上传本地视频
        st.subheader("方式一：上传本地视频")
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
        
        # 添加分隔线
        st.markdown("---")
        
        # 方式二：阿里云OSS视频
        st.subheader("方式二：阿里云OSS视频")
        
        # 默认CSV路径
        default_csv_path = os.path.join("data", "input", "export_urls.csv")
        
        # 检查默认CSV文件是否存在
        if os.path.exists(default_csv_path):
            st.info(f"已找到默认URL列表: {default_csv_path}")
            
            # 加载CSV文件
            try:
                df = pd.read_csv(default_csv_path)
                
                # 检查文件格式
                if 'object' in df.columns and 'url' in df.columns:
                    # 过滤出视频文件
                    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.m4v', '.webm', '.flv', '.wmv']
                    video_files = []
                    
                    for _, row in df.iterrows():
                        obj_name = row['object']
                        url = row['url']
                        file_name = os.path.basename(urllib.parse.unquote(obj_name))
                        
                        # 检查是否为视频文件
                        if any(file_name.lower().endswith(ext) for ext in video_extensions):
                            video_files.append({
                                'file_name': file_name,
                                'object': obj_name,
                                'url': url
                            })
                    
                    if video_files:
                        # 显示可选择的视频文件
                        st.write(f"找到 {len(video_files)} 个视频文件:")
                        
                        # 创建选择框
                        selected_index = st.selectbox(
                            "选择要分析的OSS视频", 
                            range(len(video_files)),
                            format_func=lambda i: video_files[i]['file_name']
                        )
                        
                        # 显示选中的视频信息
                        selected_video = video_files[selected_index]
                        st.markdown(f"""
                        **选中的视频**:  
                        - 文件名: {selected_video['file_name']}  
                        - 对象名: {selected_video['object']}
                        """)
                        
                        # 添加单个视频选择按钮和批量分析按钮，保持两列布局
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("使用此OSS视频", key="use_oss_video"):
                                # 保存OSS视频信息到会话状态
                                st.session_state.oss_video = selected_video
                                st.session_state.video_source = "oss"
                                st.session_state.batch_mode = False
                                st.success(f"已选择OSS视频: {selected_video['file_name']}")
                        
                        with col2:
                            if st.button("批量分析所有视频", key="batch_analyze_videos"):
                                # 保存所有视频信息到会话状态
                                st.session_state.all_oss_videos = video_files
                                st.session_state.video_source = "oss_batch"
                                st.session_state.batch_mode = True
                                st.success(f"已选择批量分析 {len(video_files)} 个视频")
                    else:
                        st.warning("在CSV文件中没有找到视频文件。")
                else:
                    st.error("CSV文件格式不正确，必须包含'object'和'url'列。")
            except Exception as e:
                st.error(f"读取CSV文件出错: {str(e)}")
        else:
            st.warning(f"默认OSS URL列表文件不存在: {default_csv_path}")
            st.info("您可以上传一个包含阿里云OSS视频URL的CSV文件")
        
        # 添加自定义CSV上传选项
        custom_csv = st.file_uploader("上传OSS URL列表", type=["csv"], help="必须包含object和url两列")
        if custom_csv:
            # 保存上传的CSV文件
            os.makedirs(os.path.join("data", "input"), exist_ok=True)
            custom_csv_path = os.path.join("data", "input", custom_csv.name)
            with open(custom_csv_path, "wb") as f:
                f.write(custom_csv.getbuffer())
            
            st.success(f"已上传OSS URL列表: {custom_csv.name}")
            st.info("请刷新页面加载新的URL列表")
    
    # 分析设置选项卡
    with analysis_tab:
        st.header("分析设置")
        
        if 'video_path' not in st.session_state and 'oss_video' not in st.session_state and 'all_oss_videos' not in st.session_state:
            st.warning("请先上传视频或选择OSS视频")
        else:
            # 显示当前选中的视频源
            if 'video_source' in st.session_state:
                if st.session_state.video_source == "oss":
                    st.info(f"当前分析OSS视频: {st.session_state.oss_video['file_name']}")
                elif st.session_state.video_source == "oss_batch":
                    st.info(f"批量分析模式: 将分析 {len(st.session_state.all_oss_videos)} 个OSS视频")
                    # 显示批量分析的视频列表
                    with st.expander("查看待分析的视频列表", expanded=False):
                        for i, video in enumerate(st.session_state.all_oss_videos):
                            st.write(f"{i+1}. {video['file_name']}")
            elif 'video_path' in st.session_state:
                st.info(f"当前分析本地视频: {os.path.basename(st.session_state.video_path)}")
            
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
                        # 确定视频来源
                        video_source = st.session_state.get('video_source', 'local')
                        
                        # 批量分析模式
                        if video_source == "oss_batch":
                            all_videos = st.session_state.all_oss_videos
                            st.info(f"开始批量分析 {len(all_videos)} 个OSS视频...")
                            
                            # 创建进度条显示总体进度
                            batch_progress = st.progress(0)
                            batch_status = st.empty()
                            
                            # 创建结果容器
                            all_results = []
                            
                            # 处理每个视频
                            for i, video in enumerate(all_videos):
                                try:
                                    # 更新进度
                                    progress_pct = i / len(all_videos)
                                    batch_progress.progress(progress_pct)
                                    batch_status.info(f"正在处理 ({i+1}/{len(all_videos)}): {video['file_name']}")
                                    
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
                                    
                                    # 处理分析
                                    results, result_file = process_video_analysis(sample_data_path, "维度分析", dimensions)
                                    
                                    if results:
                                        # 添加视频信息到结果
                                        results['video_info'] = {
                                            'file_name': video['file_name'],
                                            'object': video['object'],
                                            'url': video['url']
                                        }
                                        all_results.append((results, result_file))
                                except Exception as e:
                                    st.error(f"处理视频 {video['file_name']} 时出错: {str(e)}")
                            
                            # 更新进度为完成
                            batch_progress.progress(1.0)
                            batch_status.success(f"批量分析完成，成功处理 {len(all_results)}/{len(all_videos)} 个视频")
                            
                            # 显示批量分析结果
                            if all_results:
                                st.subheader(f"批量分析结果 ({len(all_results)} 个视频)")
                                
                                # 为每个视频创建一个展开区域显示结果
                                for i, (results, result_file) in enumerate(all_results):
                                    video_name = results['video_info']['file_name']
                                    with st.expander(f"{i+1}. {video_name}", expanded=i==0):
                                        # 显示单个视频的分析结果
                                        show_analysis_results(results, result_file)
                        else:
                            # 单个视频分析模式
                            with st.spinner("正在处理视频分析..."):
                                if video_source == "oss":
                                    oss_video = st.session_state.oss_video
                                    st.info(f"正在分析OSS视频: {oss_video['file_name']}")
                                    st.write("视频URL: " + oss_video['url'])
                                else:
                                    video_path = st.session_state.get('video_path', '')
                                    if video_path:
                                        st.info(f"正在分析本地视频: {os.path.basename(video_path)}")
                                
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
                                
                                # 处理分析
                                results, result_file = process_video_analysis(sample_data_path, "维度分析", dimensions)
                                
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
                        # 确定视频来源
                        video_source = st.session_state.get('video_source', 'local')
                        
                        # 批量分析模式
                        if video_source == "oss_batch":
                            all_videos = st.session_state.all_oss_videos
                            st.info(f"开始批量关键词分析 {len(all_videos)} 个OSS视频...")
                            
                            # 创建进度条显示总体进度
                            batch_progress = st.progress(0)
                            batch_status = st.empty()
                            
                            # 创建结果容器
                            all_results = []
                            
                            # 处理每个视频
                            for i, video in enumerate(all_videos):
                                try:
                                    # 更新进度
                                    progress_pct = i / len(all_videos)
                                    batch_progress.progress(progress_pct)
                                    batch_status.info(f"正在处理 ({i+1}/{len(all_videos)}): {video['file_name']}")
                                    
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
                                    
                                    # 处理分析
                                    results, result_file = process_video_analysis(sample_data_path, "关键词分析", keywords=keywords)
                                    
                                    if results:
                                        # 添加视频信息到结果
                                        results['video_info'] = {
                                            'file_name': video['file_name'],
                                            'object': video['object'],
                                            'url': video['url']
                                        }
                                        all_results.append((results, result_file))
                                except Exception as e:
                                    st.error(f"处理视频 {video['file_name']} 时出错: {str(e)}")
                            
                            # 更新进度为完成
                            batch_progress.progress(1.0)
                            batch_status.success(f"批量分析完成，成功处理 {len(all_results)}/{len(all_videos)} 个视频")
                            
                            # 显示批量分析结果
                            if all_results:
                                st.subheader(f"批量关键词分析结果 ({len(all_results)} 个视频)")
                                
                                # 为每个视频创建一个展开区域显示结果
                                for i, (results, result_file) in enumerate(all_results):
                                    video_name = results['video_info']['file_name']
                                    with st.expander(f"{i+1}. {video_name}", expanded=i==0):
                                        # 显示单个视频的分析结果
                                        show_analysis_results(results, result_file)
                        else:
                            # 单个视频分析模式
                            with st.spinner("正在处理视频分析..."):
                                if video_source == "oss":
                                    oss_video = st.session_state.oss_video
                                    st.info(f"正在分析OSS视频: {oss_video['file_name']}")
                                    st.write("视频URL: " + oss_video['url'])
                                else:
                                    video_path = st.session_state.get('video_path', '')
                                    if video_path:
                                        st.info(f"正在分析本地视频: {os.path.basename(video_path)}")
                                
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
                                
                                # 处理分析
                                results, result_file = process_video_analysis(sample_data_path, "关键词分析", keywords=keywords)
                                
                                # 显示结果
                                if results:
                                    show_analysis_results(results, result_file)
                else:
                    st.warning("请输入至少一个关键词")

if __name__ == "__main__":
    show() 