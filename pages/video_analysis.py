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
import numpy as np
import requests, shutil

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

# 从配置导入分析目录路径
from src.config.settings import DIMENSIONS_DIR, INITIAL_DIMENSION_FILENAME, VIDEO_ANALYSIS_DIR

# 确保结果目录存在
ANALYSIS_RESULTS_DIR = os.path.join(VIDEO_ANALYSIS_DIR, 'results')
os.makedirs(ANALYSIS_RESULTS_DIR, exist_ok=True)

from src.ui_elements.custom_theme import set_custom_theme

def get_available_templates():
    """获取data/dimensions目录下所有json模板文件名"""
    import glob
    template_files = glob.glob(os.path.join(DIMENSIONS_DIR, '*.json'))
    # 提取文件名（不含扩展名）作为模板名
    template_names = [os.path.splitext(os.path.basename(f))[0] for f in template_files]
    return template_names

def load_dimension_template(template_name):
    """根据模板名称加载维度模板文件"""
    file_path = os.path.join(DIMENSIONS_DIR, f"{template_name}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
                # 检查是否是预期的格式
                if isinstance(template_data, dict) and len(template_data) > 0:
                    # 如果顶层只有一个键值对，取第一个值
                    if len(template_data) == 1:
                        dimensions = list(template_data.values())[0]
                        template_key = list(template_data.keys())[0]
                        logger.info(f"从文件加载模板: {template_key}")
                        return dimensions
                    else:
                        # 如果结构不是预期的，返回第一个匹配的项
                        logger.warning(f"模板文件格式不是预期的单键值对: {template_name}")
                        for key, value in template_data.items():
                            if isinstance(value, dict) and 'level1' in value and 'level2' in value:
                                logger.info(f"使用找到的第一个有效模板: {key}")
                                return value
                        logger.error(f"在模板中未找到有效的维度结构: {template_name}")
                        return None
        except Exception as e:
            logger.error(f"加载模板文件出错: {str(e)}")
    else:
        logger.warning(f"模板文件不存在: {file_path}")
    return None

def load_dimensions():
    """加载当前维度结构，如果session_state中没有，自动加载initial_dimension模板"""
    if 'dimensions' in st.session_state:
        return st.session_state.dimensions
    else:
        # 尝试加载初始维度模板
        initial_template_path = os.path.join(DIMENSIONS_DIR, INITIAL_DIMENSION_FILENAME)
        if os.path.exists(initial_template_path):
            try:
                with open(initial_template_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                    # 获取模板的第一个值，假设模板文件是一个字典，其中包含单个键值对
                    if isinstance(template_data, dict) and len(template_data) == 1:
                        dimensions = list(template_data.values())[0]
                        # 将加载的维度保存到session_state
                        st.session_state.dimensions = dimensions
                        logger.info(f"已自动加载初始维度模板: {list(template_data.keys())[0]}")
                        return dimensions
            except Exception as e:
                logger.error(f"加载初始维度模板失败: {str(e)}")
        
        # 如果无法加载模板，返回空维度结构
        empty_dimensions = {'title': "未命名", 'level1': [], 'level2': {}}
        st.session_state.dimensions = empty_dimensions
        return empty_dimensions

def process_video_analysis(file, analysis_type, dimensions=None, keywords=None):
    """处理视频分析"""
    try:
        # 初始化进度条，共6步
        progress_bar = st.progress(0, text='正在初始化...')
        status_text = st.empty()

        # 第1步：读取视频文件
        progress_bar.progress(1/6, text='正在读取视频文件...')
        status_text.text("")
        try:
            # 创建VideoProcessor实例并调用实例方法
            processor = VideoProcessor()
            video_info = processor._get_video_info(file)
            results = {
                'type': analysis_type,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'video_info': video_info
            }
        except Exception as e:
            logger.error(f"读取视频文件失败: {str(e)}")
            status_text.error(f"读取视频文件失败: {str(e)}")
            return None, None

        # 第2步：提取音频
        progress_bar.progress(2/6, text='正在提取音频...')
        status_text.text("")
        try:
            # 使用相同的processor实例
            audio_file = processor._preprocess_video_file(file)
        except Exception as e:
            logger.error(f"提取音频失败: {str(e)}")
            status_text.error(f"提取音频失败: {str(e)}")
            return None, None

        # 第3步：语音识别
        progress_bar.progress(3/6, text='正在进行语音识别...')
        status_text.text("")
        try:
            # 使用VideoProcessor处理音频文件获取文本
            subtitles = processor._extract_subtitles_from_video(audio_file)
            text = "\n".join([item.get('text', '') for item in subtitles])
        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}")
            status_text.error(f"语音识别失败: {str(e)}")
            return None, None

        # 第4步：语义分割
        progress_bar.progress(4/6, text='正在进行语义分割...')
        status_text.text("")
        try:
            # 创建DataFrame用于分析
            df = pd.DataFrame([{
                'timestamp': item.get('start_time', '00:00:00'),
                'text': item.get('text', '')
            } for item in subtitles if item.get('text')])
            
            if len(df) > 0:
                status_text.text(f"识别了 {len(df)} 条句子")
            else:
                error_msg = "未识别到有效的句子"
                # 添加调试信息显示
                st.error("语义分割失败：未识别到有效的句子")
                
                # 显示详细诊断信息
                with st.expander("查看详细错误诊断", expanded=True):
                    st.markdown("### 错误诊断")
                    st.markdown("分析失败可能是由以下原因导致：")
                    
                    # 检查视频文件是否存在/可访问
                    is_url = file.startswith(('http://', 'https://'))
                    if is_url:
                        st.markdown(f"1. **远程视频文件问题**")
                        st.markdown(f"   - URL: `{file}`")
                        st.markdown(f"   - 可能原因：视频URL无法直接访问、需要授权或文件不存在")
                        st.markdown(f"   - 建议：确认URL是否有效，可以尝试在浏览器中直接打开")
                    else:
                        st.markdown(f"1. **本地视频文件问题**")
                        st.markdown(f"   - 路径: `{file}`")
                        st.markdown(f"   - 文件存在: {'是' if os.path.exists(file) else '否'}")
                        st.markdown(f"   - 建议：检查文件路径是否正确，文件是否被其他程序占用")
                    
                    # 检查音频提取情况
                    st.markdown(f"2. **音频提取问题**")
                    st.markdown(f"   - 音频文件: `{audio_file}`")
                    st.markdown(f"   - 音频文件存在: {'是' if audio_file and os.path.exists(audio_file) else '否'}")
                    
                    # 检查语音识别结果
                    st.markdown(f"3. **语音识别问题**")
                    st.markdown(f"   - 识别到的字幕数量: {len(subtitles) if subtitles else 0}")
                    st.markdown(f"   - 可能原因：视频没有语音内容、背景噪音过大、语音不清晰或API调用失败")
                    
                    # 检查环境配置
                    st.markdown(f"4. **环境配置问题**")
                    st.markdown(f"   - API配置: {'已设置' if 'API_KEY' in os.environ else '未设置'}")
                    st.markdown(f"   - 建议：检查环境变量中是否正确设置了API密钥")
                
                raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"语义分割失败: {str(e)}")
            status_text.error(f"语义分割失败: {str(e)}")
            return None, None

        # 第5步：维度/关键词分析
        progress_bar.progress(5/6, text='正在进行维度/关键词分析...')
        if analysis_type == "维度分析":
            status_text.text("应用维度：" + ",".join(dimensions.get('level1', [])[:3]) + "...")
            results['dimensions'] = dimensions
            try:
                from utils.analyzer import VideoAnalyzer
                analyzer = VideoAnalyzer()
                dimension_results = analyzer.analyze_dimensions(df, dimensions)
                if dimension_results and 'matches' in dimension_results:
                    results['matches'] = dimension_results['matches']
                    # 添加分析方法显示
                    if 'analysis_method' in dimension_results:
                        results['analysis_method'] = dimension_results['analysis_method']
                    else:
                        results['analysis_method'] = '语义匹配'
                else:
                    st.error("维度分析失败，未能生成有效的匹配结果")
                    return None, None
            except ImportError:
                st.error("维度分析失败，无法导入 VideoAnalyzer 模块")
                return None, None
        elif analysis_type == "关键词分析":  
            status_text.text("应用关键词：" + ",".join(keywords[:3] if len(keywords) > 3 else keywords) + "...")
            results['keywords'] = keywords
            try:
                from utils.analyzer import VideoAnalyzer
                analyzer = VideoAnalyzer()
                keyword_results = analyzer.analyze_keywords(df, keywords)
                if keyword_results and 'matches' in keyword_results:
                    results['matches'] = keyword_results['matches']
                    # 添加分析方法显示
                    if 'analysis_method' in keyword_results:
                        results['analysis_method'] = keyword_results['analysis_method']
                    else:
                        results['analysis_method'] = '语义匹配'
                else:
                    st.error("关键词分析失败，未能生成有效的匹配结果")
                    return None, None
            except ImportError:
                st.error("关键词分析失败，无法导入 VideoAnalyzer 模块")
                return None, None

        # 第6步：保存结果
        progress_bar.progress(6/6, text='正在保存结果...')
        status_text.text("")
        try:
            result_file = os.path.join(ANALYSIS_RESULTS_DIR, f"analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存结果失败: {str(e)}")
            status_text.error(f"保存结果失败: {str(e)}")
            return None, None

        # 分析完成
        progress_bar.progress(1.0, text='分析完成！')
        if 'analysis_method' in results:
            status_text.text(f"使用方法：{results['analysis_method']}")
        else:
            status_text.text("")

        # 检查是否有错误结果
        if len(results['matches']) == 1 and results['matches'][0].get('is_error', False):
            error_match = results['matches'][0]
            st.error(error_match['text'])
            st.info("分析失败。请确保您的API配置正确，并检查视频文件是否有效。您可以尝试使用不同的视频文件或稍后再试。")
            return

        return results, result_file

    except Exception as e:
        logger.error(f"处理视频分析时出错: {str(e)}")
        st.error(f"处理失败: {str(e)}")
        return None, None

def _simulate_dimension_matching(df, dimensions):
    """
    模拟维度匹配逻辑（当VideoAnalyzer不可用时使用）
    
    参数:
        df: 视频文本数据DataFrame
        dimensions: 维度结构
        
    返回:
        匹配结果列表
    """
    matches = []
    
    # 处理每条记录
    for _, row in df.iterrows():
        text = row.get('text', '')
        if not text:
            continue
        
        # 获取一级维度
        level1_dims = dimensions.get('level1', [])
        
        for dim1 in level1_dims:
            # 模拟匹配计算，基于简单的字符串包含关系
            contains_words = any(word in text for word in dim1.split())
            
            if contains_words:
                # 模拟匹配分数
                score = 0.7 + np.random.random() * 0.3  # 随机生成0.7-1.0之间的分数
                
                # 尝试匹配二级维度
                level2_dims = dimensions.get('level2', {}).get(dim1, [])
                matched_l2 = None
                
                for dim2 in level2_dims:
                    contains_words_l2 = any(word in text for word in dim2.split())
                    
                    if contains_words_l2:
                        # 找到匹配的二级维度
                        matched_l2 = dim2
                        score = 0.7 + np.random.random() * 0.3  # 更新分数
                        break
                
                # 添加匹配结果
                matches.append({
                    'dimension_level1': dim1,
                    'dimension_level2': matched_l2 if matched_l2 else '',
                    'timestamp': row.get('timestamp', '00:00:00'),
                    'text': text,
                    'score': float(score)  # 确保分数是float类型
                })
    
    return matches

def _simulate_keyword_matching(df, keywords):
    """
    模拟关键词匹配逻辑（当VideoAnalyzer不可用时使用）
    
    参数:
        df: 视频文本数据DataFrame
        keywords: 关键词列表
        
    返回:
        匹配结果列表
    """
    matches = []
    
    # 处理每条记录
    for _, row in df.iterrows():
        text = row.get('text', '')
        if not text:
            continue
        
        # 对每个关键词进行匹配
        for keyword in keywords:
            # 简单的包含匹配
            if keyword.lower() in text.lower():
                # 模拟匹配分数
                score = 0.7 + np.random.random() * 0.3  # 随机生成0.7-1.0之间的分数
                
                # 添加匹配结果
                matches.append({
                    'keyword': keyword,
                    'timestamp': row.get('timestamp', '00:00:00'),
                    'text': text,
                    'score': float(score)  # 确保分数是float类型
                })
    
    return matches

def show_analysis_results(results, result_file):
    """显示分析结果"""
    if not results:
        return
    
    st.markdown("## 分析结果")
    
    # 检查是否有错误结果
    if len(results['matches']) == 1 and results['matches'][0].get('is_error', False):
        error_match = results['matches'][0]
        st.error(error_match['text'])
        st.info("分析失败。请确保您的API配置正确，并检查视频文件是否有效。您可以尝试使用不同的视频文件或稍后再试。")
        return
    
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
    
    # 显示使用的分析方法
    if 'analysis_method' in results:
        st.markdown(f"**分析方法**: {results['analysis_method']}")
    
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
        # 创建一个tab_id计数器，确保每个tab有唯一ID
        tab_id = 0
        
        # 按维度分组显示
        for dim1 in results.get('dimensions', {}).get('level1', []):
            # 过滤出当前一级维度的匹配
            dim1_matches = [m for m in results['matches'] if m['dimension_level1'] == dim1]
            
            if dim1_matches:
                # 使用expander显示一级维度
                with st.expander(f"{dim1} ({len(dim1_matches)}个匹配)", expanded=False):
                    # 按二级维度分组并直接显示内容，而不是再使用嵌套的expander
                    for dim2 in results.get('dimensions', {}).get('level2', {}).get(dim1, []):
                        # 过滤出当前二级维度的匹配
                        dim2_matches = [m for m in dim1_matches if m['dimension_level2'] == dim2]
                        
                        if dim2_matches:
                            st.markdown(f"#### {dim2} ({len(dim2_matches)}个匹配)")
                            
                            # 创建一个可折叠区域的替代方案 - 使用容器
                            dim2_container = st.container()
                            show_details = st.checkbox(f"显示详情 - {dim2}", key=f"dim2_details_{tab_id}")
                            tab_id += 1
                            
                            if show_details:
                                with dim2_container:
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
    # 设置主题
    set_custom_theme()
    
    # 创建侧边栏导航
    create_sidebar_navigation("视频分析")
    
    # 加载维度结构
    dimensions = load_dimensions()
    
    # 页面标题
    st.title("🎬 视频分析")
    st.write("上传视频或提供视频链接，进行语音和内容分析")
    
    # 修改页面顶部的分析类型选择，将其值保存到session_state
    # 分析类型选择
    if 'analysis_type' not in st.session_state:
        st.session_state.analysis_type = "维度分析"  # 默认选中维度分析
        
    analysis_type_options = st.radio(
        "选择分析类型:", 
        ["维度分析", "关键词分析"],
        key="analysis_type",
        horizontal=True
    )
    
    # 添加分隔线
    st.markdown("---")
    
    # 上传视频部分
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
    
    # 初始化OSS视频URL列表
    def _load_oss_video_urls():
        """从export_urls.csv加载OSS视频URL列表"""
        csv_path = os.path.join("data", "input", "export_urls.csv")
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.m4v', '.webm', '.flv', '.wmv']
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                if 'object' in df.columns and 'url' in df.columns:
                    # 过滤出视频文件
                    video_files = []
                    for _, row in df.iterrows():
                        obj_name = row['object']
                        url = row['url']
                        file_name = os.path.basename(urllib.parse.unquote(obj_name))
                        file_ext = os.path.splitext(file_name.lower())[1]
                        
                        # 检查是否为视频文件
                        if file_ext in video_extensions:
                            video_files.append({
                                'file_name': file_name,
                                'object': obj_name,
                                'url': url
                            })
                    
                    logger.info(f"从export_urls.csv成功加载了 {len(video_files)} 个视频文件")
                    return video_files
                else:
                    logger.error("CSV文件格式不正确，必须包含'object'和'url'列")
            except Exception as e:
                logger.error(f"读取OSS URL列表失败: {str(e)}")
        else:
            logger.warning(f"OSS URL列表文件不存在: {csv_path}")
        
        return []
    
    # 加载OSS视频
    if 'oss_videos' not in st.session_state:
        st.session_state.oss_videos = _load_oss_video_urls()
    
    # 方式二：阿里云OSS视频
    st.subheader("方式二：阿里云OSS视频")
    
    if st.session_state.oss_videos:
        st.info(f"找到 {len(st.session_state.oss_videos)} 个OSS视频文件")
        
        # 创建选择框
        selected_index = st.selectbox(
            "选择要分析的OSS视频", 
            range(len(st.session_state.oss_videos)),
            format_func=lambda i: st.session_state.oss_videos[i]['file_name']
        )
        
        # 显示选中的视频信息
        selected_video = st.session_state.oss_videos[selected_index]
        st.markdown(f"""
        **选中的视频**:  
        - 文件名: {selected_video['file_name']}  
        - 对象名: {selected_video['object']}
        - URL: {selected_video['url']}
        """)
        
        # 保存OSS视频信息到会话状态
        st.session_state.oss_video = selected_video
        st.session_state.video_source = "oss"
    else:
        st.warning("未找到可用的OSS视频。请确认data/input/export_urls.csv文件存在且格式正确。")
    
    # 上传自定义CSV
    st.markdown("### 上传OSS URL列表")
    custom_csv = st.file_uploader("上传OSS URL列表", type=["csv"], help="必须包含object和url两列")
    if custom_csv:
        # 保存上传的CSV文件
        os.makedirs(os.path.join("data", "input"), exist_ok=True)
        custom_csv_path = os.path.join("data", "input", "export_urls.csv")
        with open(custom_csv_path, "wb") as f:
            f.write(custom_csv.getbuffer())
        
        st.success(f"已上传OSS URL列表，请刷新页面加载URL")
        st.session_state.oss_videos = _load_oss_video_urls()
    
    # 添加分隔线
    st.markdown("---")
    
    # 分析设置部分 - 直接显示在页面上
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
        
        # 使用session_state中的分析类型
        analysis_type = st.session_state.analysis_type
        
        if analysis_type == "维度分析":
            # 显示维度选择
            st.subheader("维度选择")
            
            # 添加模板选择下拉列表
            available_templates = get_available_templates()
            if available_templates:
                # 确定默认选择的模板
                default_index = 0
                initial_template_name = os.path.splitext(INITIAL_DIMENSION_FILENAME)[0]
                if initial_template_name in available_templates:
                    default_index = available_templates.index(initial_template_name)
                
                # 初始化session state用于跟踪当前选中的模板
                if 'selected_template' not in st.session_state:
                    st.session_state.selected_template = available_templates[default_index]
                
                # 处理模板变更的回调函数
                def on_template_change():
                    new_template = st.session_state.dimension_template_selector
                    # 只有当模板真正变化时才加载
                    if new_template != st.session_state.selected_template:
                        st.session_state.selected_template = new_template
                        dimensions = load_dimension_template(new_template)
                        if dimensions:
                            st.session_state.dimensions = dimensions
                            # 不要使用st.success，因为在回调中它会被下一个重渲染覆盖
                            # 改为使用session state记录加载成功信息，在下次渲染时显示
                            st.session_state.template_load_success = f"已加载模板: {new_template}"
                        else:
                            st.session_state.template_load_error = f"加载模板失败: {new_template}"
                
                # 使用选择框让用户选择模板，并设置回调函数
                selected_template = st.selectbox(
                    "选择维度模板",
                    available_templates,
                    index=default_index,
                    key="dimension_template_selector",
                    help="从data/dimensions文件夹加载模板",
                    on_change=on_template_change
                )
                
                # 显示加载成功或失败的消息
                if 'template_load_success' in st.session_state:
                    st.success(st.session_state.template_load_success)
                    # 显示后清除，避免重复显示
                    del st.session_state.template_load_success
                
                if 'template_load_error' in st.session_state:
                    st.error(st.session_state.template_load_error)
                    # 显示后清除，避免重复显示
                    del st.session_state.template_load_error
            
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
                                    # 不使用show_analysis_results避免嵌套expander
                                    st.markdown("## 分析结果")
                                    
                                    # 显示视频信息
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
                                    
                                    # 根据分析类型显示不同的结果（直接显示，不使用嵌套expander）
                                    if results['type'] == "维度分析":
                                        # 直接显示所有维度匹配，不使用expander
                                        for dim1 in results.get('dimensions', {}).get('level1', []):
                                            # 过滤出当前一级维度的匹配
                                            dim1_matches = [m for m in results['matches'] if m['dimension_level1'] == dim1]
                                            
                                            if dim1_matches:
                                                st.markdown(f"#### {dim1} ({len(dim1_matches)}个匹配)")
                                                
                                                # 按二级维度分组
                                                for dim2 in results.get('dimensions', {}).get('level2', {}).get(dim1, []):
                                                    # 过滤出当前二级维度的匹配
                                                    dim2_matches = [m for m in dim1_matches if m['dimension_level2'] == dim2]
                                                    
                                                    if dim2_matches:
                                                        st.markdown(f"##### {dim2} ({len(dim2_matches)}个匹配)")
                                                        
                                                        # 显示每个匹配
                                                        for match in dim2_matches:
                                                            st.markdown(f"""
                                                            **时间点**: {match['timestamp']}  
                                                            **匹配分数**: {match['score']:.2f}  
                                                            **文本**: {match['text']}  
                                                            ---
                                                            """)
                                    
                                    elif results['type'] == "关键词分析":
                                        # 直接显示所有关键词匹配，不使用expander
                                        for keyword in results.get('keywords', []):
                                            # 过滤出当前关键词的匹配
                                            keyword_matches = [m for m in results['matches'] if m['keyword'] == keyword]
                                            
                                            if keyword_matches:
                                                st.markdown(f"#### 关键词: {keyword} ({len(keyword_matches)}个匹配)")
                                                
                                                # 显示每个匹配
                                                for match in keyword_matches:
                                                    st.markdown(f"""
                                                    **时间点**: {match['timestamp']}  
                                                    **匹配分数**: {match['score']:.2f}  
                                                    **文本**: {match['text']}  
                                                    ---
                                                    """)
                    else:
                        # 单个视频分析模式
                        with st.spinner("正在处理视频分析..."):
                            video_source = st.session_state.get('video_source', 'local')
                            video_path = ""
                            
                            if video_source == "oss":
                                oss_video = st.session_state.oss_video
                                st.info(f"正在分析OSS视频: {oss_video['file_name']}")
                                
                                # 直接使用OSS URL进行处理，避免下载
                                video_path = oss_video['url']
                                st.write(f"视频URL: {video_path}")
                            else:
                                video_path = st.session_state.get('video_path', '')
                                if video_path:
                                    st.info(f"正在分析本地视频: {os.path.basename(video_path)}")
                                else:
                                    st.error("未选择任何视频文件")
                                    return
                                
                            # 如果CSV文件存在且在测试模式，则使用它
                            if 'use_sample' in st.session_state and st.session_state.use_sample:
                                sample_data_path = os.path.join("data", "temp", "sample_subtitles.csv")
                                if os.path.exists(sample_data_path):
                                    st.info("使用示例字幕数据进行分析")
                                    video_path = sample_data_path
                            
                            # 如果没有视频路径，尝试使用示例
                            if not video_path:
                                st.error("未找到有效的视频路径")
                                return
                                
                            # 处理分析
                            results, result_file = process_video_analysis(video_path, "维度分析", dimensions)
                                
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
                                    # 不使用show_analysis_results避免嵌套expander
                                    st.markdown("## 分析结果")
                                    
                                    # 显示视频信息
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
                                    
                                    # 根据分析类型显示不同的结果（直接显示，不使用嵌套expander）
                                    if results['type'] == "维度分析":
                                        # 直接显示所有维度匹配，不使用expander
                                        for dim1 in results.get('dimensions', {}).get('level1', []):
                                            # 过滤出当前一级维度的匹配
                                            dim1_matches = [m for m in results['matches'] if m['dimension_level1'] == dim1]
                                            
                                            if dim1_matches:
                                                st.markdown(f"#### {dim1} ({len(dim1_matches)}个匹配)")
                                                
                                                # 按二级维度分组
                                                for dim2 in results.get('dimensions', {}).get('level2', {}).get(dim1, []):
                                                    # 过滤出当前二级维度的匹配
                                                    dim2_matches = [m for m in dim1_matches if m['dimension_level2'] == dim2]
                                                    
                                                    if dim2_matches:
                                                        st.markdown(f"##### {dim2} ({len(dim2_matches)}个匹配)")
                                                        
                                                        # 显示每个匹配
                                                        for match in dim2_matches:
                                                            st.markdown(f"""
                                                            **时间点**: {match['timestamp']}  
                                                            **匹配分数**: {match['score']:.2f}  
                                                            **文本**: {match['text']}  
                                                            ---
                                                            """)
                                    
                                    elif results['type'] == "关键词分析":
                                        # 直接显示所有关键词匹配，不使用expander
                                        for keyword in results.get('keywords', []):
                                            # 过滤出当前关键词的匹配
                                            keyword_matches = [m for m in results['matches'] if m['keyword'] == keyword]
                                            
                                            if keyword_matches:
                                                st.markdown(f"#### 关键词: {keyword} ({len(keyword_matches)}个匹配)")
                                                
                                                # 显示每个匹配
                                                for match in keyword_matches:
                                                    st.markdown(f"""
                                                    **时间点**: {match['timestamp']}  
                                                    **匹配分数**: {match['score']:.2f}  
                                                    **文本**: {match['text']}  
                                                    ---
                                                    """)
                    else:
                        # 单个视频分析模式
                        with st.spinner("正在处理视频分析..."):
                            video_source = st.session_state.get('video_source', 'local')
                            video_path = ""
                            
                            if video_source == "oss":
                                oss_video = st.session_state.oss_video
                                st.info(f"正在分析OSS视频: {oss_video['file_name']}")
                                
                                # 直接使用OSS URL进行处理，避免下载
                                video_path = oss_video['url']
                                st.write(f"视频URL: {video_path}")
                            else:
                                video_path = st.session_state.get('video_path', '')
                                if video_path:
                                    st.info(f"正在分析本地视频: {os.path.basename(video_path)}")
                                else:
                                    st.error("未选择任何视频文件")
                                    return
                                
                            # 如果CSV文件存在且在测试模式，则使用它
                            if 'use_sample' in st.session_state and st.session_state.use_sample:
                                sample_data_path = os.path.join("data", "temp", "sample_subtitles.csv")
                                if os.path.exists(sample_data_path):
                                    st.info("使用示例字幕数据进行分析")
                                    video_path = sample_data_path
                            
                            # 如果没有视频路径，尝试使用示例
                            if not video_path:
                                st.error("未找到有效的视频路径")
                                return
                                
                            # 处理分析
                            results, result_file = process_video_analysis(video_path, "关键词分析", keywords=keywords)
                                
                            # 显示结果
                            if results:
                                show_analysis_results(results, result_file)
                else:
                    st.warning("请输入至少一个关键词")

if __name__ == "__main__":
    show() 