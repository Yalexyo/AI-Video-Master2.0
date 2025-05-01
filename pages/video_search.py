import streamlit as st
import pandas as pd
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
import os
import json
from datetime import datetime
import sys

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui_elements.intent_selector import render_intent_selector, render_description_input
from src.core.video_segment_service import VideoSegmentService
from utils.processor import VideoProcessor
from src.ui_elements.simple_nav import create_sidebar_navigation
from src.core.hot_words_service import HotWordsService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置页面
st.set_page_config(
    page_title="视频内容智能搜索",
    page_icon="🔍",
    layout="wide"
)

async def main():
    """页面主函数"""
    # 添加侧边栏导航
    create_sidebar_navigation(active_page="视频匹配")
    
    st.title("🔍 视频内容智能搜索")
    st.write("通过意图匹配和语义理解，精准定位视频中的关键内容")
    
    # 加载已有视频列表 (这里需要根据项目实际情况调整)
    video_dir = os.path.join('data', 'test_samples', 'input', 'video')
    if not os.path.exists(video_dir):
        video_dir = os.path.join('data', 'input', 'video')
        if not os.path.exists(video_dir):
            os.makedirs(video_dir, exist_ok=True)
    
    video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
    
    # 步骤1：选择视频
    with st.expander("第一步：选择视频", expanded=True):
        if not video_files:
            st.warning("⚠️ 未找到可用的视频文件，请将视频文件放入data/test_samples/input/video或data/input/video目录")
            return
            
        # 允许选择多个视频进行批量处理
        multi_select = st.checkbox("批量处理多个视频", value=False)
        
        if multi_select:
            video_options = st.multiselect(
                "选择需要分析的视频",
                options=video_files,
                format_func=lambda x: f"{x} - {os.path.getsize(os.path.join(video_dir, x)) // (1024*1024)}MB"
            )
            video_paths = [os.path.join(video_dir, v) for v in video_options if os.path.exists(os.path.join(video_dir, v))]
            
            if video_paths:
                st.info(f"已选择 {len(video_paths)} 个视频文件进行批量处理")
            else:
                st.warning("请选择至少一个视频文件")
        else:
            video_option = st.selectbox(
                "选择需要分析的视频",
                options=video_files,
                format_func=lambda x: f"{x} - {os.path.getsize(os.path.join(video_dir, x)) // (1024*1024)}MB"
            )
            
            video_paths = [os.path.join(video_dir, video_option)] if video_option else []
    
    # 步骤2：上传视频
    with st.expander("第二步：上传视频", expanded=True):
        uploaded_files = st.file_uploader("选择要分析的视频文件", type=["mp4", "mov", "avi"], accept_multiple_files=True)
        
    # 步骤3：选择分析模式
    with st.expander("第三步：选择分析模式", expanded=True):
        search_mode = st.radio(
            "请选择分析模式",
            options=["意图模式", "自由文本模式"],
            horizontal=True,
            help="意图模式: 基于预定义意图分析内容；自由文本模式: 通过自由文本描述来搜索内容"
        )
        
        selected_intents = None
        user_description = ""
        
        if search_mode == "意图模式":
            # 多选意图选择器
            selected_intents = render_intent_selector()
            
            # 如果没有选择意图，禁用后续步骤
            if not selected_intents:
                st.warning("请选择至少一个意图")
                # 但不阻止页面执行，因为用户可能会切换到其他模式
        
        else:  # 自由文本模式
            st.write("请输入您想在视频中搜索的内容描述")
            user_description = st.text_area(
                "内容描述",
                height=100,
                placeholder="例如：查找视频中讨论产品功效或用户评价的部分",
                help="请详细描述您想要查找的内容，越具体越好"
            )
            
            if not user_description:
                st.warning("请输入内容描述")
    
    # 步骤4：执行设置（并行度、分数阈值等）
    with st.expander("第四步：高级设置(可选)", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            max_concurrent = st.slider(
                "最大并行任务数",
                min_value=1,
                max_value=10,
                value=3,
                help="设置批量处理时的最大并行任务数，数值越大处理速度越快，但也会消耗更多资源"
            )
        
        with col2:
            score_threshold = st.slider(
                "最低匹配分数",
                min_value=0,
                max_value=100,
                value=60,
                help="设置匹配结果的最低分数阈值，低于此分数的结果将被过滤"
            )
    
    # 步骤5：执行搜索
    col1, col2 = st.columns([1, 1])
    with col1:
        # 根据不同模式显示不同的按钮文字
        if search_mode == "意图模式":
            button_text = "🔍 开始意图分析"
            disabled = len(video_paths) == 0 or not selected_intents
        else:
            button_text = "🔍 开始自由文本分析"
            disabled = len(video_paths) == 0 or not user_description
            
        search_button = st.button(button_text, type="primary", use_container_width=True, disabled=disabled)
    
    with col2:
        cancel_button = st.button("❌ 取消", type="secondary", use_container_width=True)
    
    # 处理搜索请求
    if search_button and video_paths:
        with st.spinner("正在分析视频内容，请稍候..."):
            try:
                # 创建服务实例
                processor = VideoProcessor()
                segment_service = VideoSegmentService(max_concurrent_tasks=max_concurrent)
                
                # 获取当前热词ID
                hot_words_service = HotWordsService()
                current_hotword_id = hot_words_service.get_current_hotword_id()
                st.info(f"使用热词ID进行转录: {current_hotword_id}")
                
                # 准备所有视频的字幕数据
                all_subtitle_dfs = []
                
                for video_path in video_paths:
                    video_base_name = os.path.basename(video_path).split('.')[0]
                    
                    # 获取或处理字幕
                    subtitles_dir = os.path.join('data', 'output', 'subtitles')
                    os.makedirs(subtitles_dir, exist_ok=True)
                    
                    srt_files = [f for f in os.listdir(subtitles_dir) 
                                if f.startswith(video_base_name)]
                    
                    subtitle_df = None
                    
                    # 默认始终重新生成字幕，不使用缓存的字幕文件
                    # 检查是否有缓存的字幕文件（仅用于显示信息）
                    if srt_files:
                        st.info(f"视频 {video_base_name} 有现有字幕文件，将使用当前热词重新生成")
                    else:
                        st.info(f"视频 {video_base_name} 没有缓存的字幕文件")
                    
                    # 直接提取新字幕，使用当前热词ID
                    st.info(f"正在为视频 {video_base_name} 提取字幕，使用热词ID: {current_hotword_id}")
                    audio_file = processor._preprocess_video_file(video_path)
                    
                    if audio_file:
                        # 使用当前热词ID进行字幕提取
                        subtitles = processor._extract_subtitles_from_video(audio_file, vocabulary_id=current_hotword_id)
                        
                        if subtitles:
                            subtitle_df = pd.DataFrame([{
                                'timestamp': item.get('start_formatted', '00:00:00'),
                                'text': item.get('text', '')
                            } for item in subtitles if item.get('text')])
                            
                            # 保存字幕文件
                            processor._save_subtitles_to_srt(video_path, subtitles)
                            
                            st.success(f"成功提取视频 {video_base_name} 的字幕，共 {len(subtitle_df)} 条记录")
                        else:
                            st.error(f"视频 {video_base_name} 的字幕提取失败")
                    else:
                        st.error(f"视频 {video_base_name} 的音频提取失败")
                    
                    if subtitle_df is not None and not subtitle_df.empty:
                        all_subtitle_dfs.append((video_base_name, subtitle_df))
                
                # 执行内容分析
                if all_subtitle_dfs:
                    st.info(f"开始执行内容分析，共 {len(all_subtitle_dfs)} 个视频...")
                    
                    # 根据不同模式执行不同的分析
                    if search_mode == "意图模式":
                        with st.spinner(f"正在分析选中的 {len(selected_intents)} 个意图..."):
                            batch_results = await segment_service.get_batch_analysis(
                                videos=all_subtitle_dfs,
                                analysis_type='custom',
                                custom_intent_ids=[intent['id'] for intent in selected_intents]
                            )
                    else:
                        # 自由文本模式
                        with st.spinner(f"正在进行自由文本分析：「{user_description[:30]}{'...' if len(user_description) > 30 else ''}」"):
                            batch_results = await segment_service.get_batch_analysis(
                                videos=all_subtitle_dfs,
                                analysis_type='custom',
                                custom_prompt=user_description
                            )
                    
                    # 保存和展示结果
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    result_dir = os.path.join('data', 'output', 'segments')
                    os.makedirs(result_dir, exist_ok=True)
                    
                    # 保存批量结果
                    result_file = os.path.join(
                        result_dir, 
                        f'batch_results_{search_mode.replace(" ", "_")}_{timestamp}.json'
                    )
                    
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(batch_results, f, ensure_ascii=False, indent=2)
                    
                    st.success(f"✅ 分析完成！结果已保存到 {result_file}")
                    
                    # 展示分析结果
                    for video_id, results in batch_results.items():
                        with st.expander(f"视频 {video_id} 的分析结果", expanded=True):
                            if "error" in results:
                                st.error(f"分析出错: {results['error']}")
                                continue
                                
                            # 展示匹配片段
                            if search_mode == "意图模式":
                                matches_data = results.get("matches", {})
                                total_matches = 0
                                
                                for intent_id, intent_data in matches_data.items():
                                    intent_name = intent_data.get("intent_name", "未知意图")
                                    matches = intent_data.get("matches", [])
                                    
                                    if matches:
                                        total_matches += len(matches)
                                        st.subheader(f"意图「{intent_name}」- 找到 {len(matches)} 个匹配")
                                        
                                        for i, match in enumerate(sorted(matches, key=lambda x: -x.get('score', 0)), 1):
                                            score = match.get('score', 0)
                                            start_timestamp = match.get('start_timestamp', '00:00:00')
                                            end_timestamp = match.get('end_timestamp', '00:00:00')
                                            context = match.get('context', '')
                                            core_text = match.get('core_text', '')
                                            
                                            with st.container():
                                                # 使用HTML替代Markdown，避免特殊字符导致格式问题
                                                st.markdown(f"""
                                                <h4>片段 {i} - 匹配度: {score}%</h4>
                                                <ul>
                                                  <li><strong>时间段</strong>: {start_timestamp} - {end_timestamp}</li>
                                                  <li><strong>核心内容</strong>: {core_text.replace('"', '&quot;')}</li>
                                                  <li><strong>完整上下文</strong>: {context.replace('"', '&quot;')}</li>
                                                </ul>
                                                """, unsafe_allow_html=True)
                                                
                                                st.divider()
                                
                                if total_matches == 0:
                                    st.warning("❗ 未找到匹配的视频片段")
                            else:
                                # 自由文本模式
                                matches = results.get("matches", [])
                                
                                if matches:
                                    st.subheader(f"找到 {len(matches)} 个匹配")
                                    
                                    for i, match in enumerate(sorted(matches, key=lambda x: -x.get('score', 0)), 1):
                                        score = match.get('score', 0)
                                        start_timestamp = match.get('start_timestamp', '00:00:00')
                                        end_timestamp = match.get('end_timestamp', '00:00:00')
                                        context = match.get('context', '')
                                        core_text = match.get('core_text', '')
                                        
                                        with st.container():
                                            # 使用HTML替代Markdown，避免特殊字符导致格式问题
                                            st.markdown(f"""
                                            <h4>片段 {i} - 匹配度: {score}%</h4>
                                            <ul>
                                              <li><strong>时间段</strong>: {start_timestamp} - {end_timestamp}</li>
                                              <li><strong>核心内容</strong>: {core_text.replace('"', '&quot;')}</li>
                                              <li><strong>完整上下文</strong>: {context.replace('"', '&quot;')}</li>
                                            </ul>
                                            """, unsafe_allow_html=True)
                                            
                                            st.divider()
                                else:
                                    st.warning("❗ 未找到与您描述匹配的视频片段")
                else:
                    st.error("没有可用的字幕数据，无法进行内容分析")
                
            except Exception as e:
                logger.error(f"分析过程出错: {str(e)}")
                st.error(f"分析过程出现错误: {str(e)}")
    
    # 显示页脚
    st.markdown("---")
    st.caption("AI视频智能分析系统 - 版权所有")

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main()) 