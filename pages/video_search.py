import streamlit as st
import pandas as pd
import logging
import asyncio
from typing import Dict, Any, Optional
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
    
    # 步骤1：选择视频文件
    with st.expander("第一步：选择视频文件", expanded=True):
        if not video_files:
            st.warning("⚠️ 未找到可用的视频文件，请将视频文件放入data/test_samples/input/video或data/input/video目录")
            return
            
        video_option = st.selectbox(
            "选择需要分析的视频",
            options=video_files,
            format_func=lambda x: f"{x} - {os.path.getsize(os.path.join(video_dir, x)) // (1024*1024)}MB"
        )
        
        video_path = os.path.join(video_dir, video_option) if video_option else None
        
        if video_path and os.path.exists(video_path):
            st.video(video_path)
    
    # 步骤2：内容意图选择（必选）
    with st.expander("第二步：选择内容意图（必选）", expanded=True):
        selected_intent = render_intent_selector()
        
        # 如果没有选择意图，禁用后续步骤
        if not selected_intent:
            st.stop()  # 阻止页面继续执行，直到用户选择了意图
    
    # 步骤3：详细描述（可选，只有选择了意图才能使用）
    with st.expander("第三步：输入详细描述(可选)", expanded=True):
        st.caption("在已选择的意图「{}」基础上，您可以输入更精确的描述".format(
            selected_intent['name'] if selected_intent else ""))
        user_description = render_description_input()
    
    # 步骤4：执行搜索
    col1, col2 = st.columns([1, 1])
    with col1:
        search_button = st.button("🔍 开始搜索", type="primary", use_container_width=True, 
                                disabled=not (video_path and selected_intent))
    
    with col2:
        cancel_button = st.button("❌ 取消", type="secondary", use_container_width=True)
    
    # 处理搜索请求
    if search_button and video_path and selected_intent:
        with st.spinner("正在分析视频内容，请稍候..."):
            try:
                # 创建服务实例
                processor = VideoProcessor()
                segment_service = VideoSegmentService()
                
                # 获取或处理字幕
                subtitles_dir = os.path.join('data', 'output', 'subtitles')
                os.makedirs(subtitles_dir, exist_ok=True)
                
                video_base_name = os.path.basename(video_path).split('.')[0]
                srt_files = [f for f in os.listdir(subtitles_dir) 
                            if f.startswith(video_base_name)]
                
                subtitle_df = None
                
                if srt_files:
                    # 使用最新的字幕文件
                    latest_srt = sorted(srt_files)[-1]
                    srt_path = os.path.join(subtitles_dir, latest_srt)
                    
                    # 从SRT读取字幕
                    subtitles = processor._parse_srt_file(srt_path)
                    subtitle_df = pd.DataFrame([{
                        'timestamp': item.get('start_formatted', '00:00:00'),
                        'text': item.get('text', '')
                    } for item in subtitles if item.get('text')])
                    
                    st.info(f"已读取现有字幕文件，共 {len(subtitle_df)} 条记录")
                else:
                    # 提取新字幕
                    st.info("正在提取视频字幕...")
                    audio_file = processor._preprocess_video_file(video_path)
                    
                    if audio_file:
                        subtitles = processor._extract_subtitles_from_video(audio_file)
                        
                        if subtitles:
                            subtitle_df = pd.DataFrame([{
                                'timestamp': item.get('start_formatted', '00:00:00'),
                                'text': item.get('text', '')
                            } for item in subtitles if item.get('text')])
                            
                            # 保存字幕文件
                            processor._save_subtitles_to_srt(video_path, subtitles)
                            
                            st.success(f"成功提取字幕，共 {len(subtitle_df)} 条记录")
                        else:
                            st.error("字幕提取失败")
                    else:
                        st.error("视频音频提取失败")
                
                # 执行内容搜索
                if subtitle_df is not None and not subtitle_df.empty:
                    st.info("正在执行内容匹配分析...")
                    video_id = video_base_name
                    
                    # 异步调用，获取匹配结果
                    results = await segment_service.get_video_segments(
                        video_id=video_id,
                        subtitle_df=subtitle_df,
                        selected_intent=selected_intent,
                        user_description=user_description
                    )
                    
                    # 显示结果
                    if results and "matches" in results and results["matches"]:
                        matches = results["matches"]
                        st.success(f"✅ 找到 {len(matches)} 个相关片段!")
                        
                        # 保存结果
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        result_dir = os.path.join('data', 'output', 'segments')
                        os.makedirs(result_dir, exist_ok=True)
                        
                        result_file = os.path.join(
                            result_dir, 
                            f'segment_results_{video_id}_{timestamp}.json'
                        )
                        
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=2)
                        
                        # 展示匹配片段
                        for i, match in enumerate(sorted(matches, key=lambda x: -x.get('score', 0)), 1):
                            # 兼容两种不同的结果格式（LLM精确匹配 vs 关键词匹配）
                            if "start_timestamp" in match:  # LLM精确匹配格式
                                score = match.get('score', 0)
                                start_timestamp = match.get('start_timestamp', '00:00:00')
                                end_timestamp = match.get('end_timestamp', '00:00:00')
                                context = match.get('context', '')
                                core_text = match.get('core_text', '')
                                reason = match.get('reason', '')
                                
                                with st.container():
                                    st.markdown(f"""
                                    ### 片段 {i} - 匹配度: {score}%
                                    - **时间段**: {start_timestamp} - {end_timestamp}
                                    - **核心内容**: "{core_text}"
                                    - **完整上下文**: "{context}"
                                    - **匹配原因**: {reason}
                                    """)
                                    
                                    # 提取时间点制作视频片段链接
                                    hh, mm, ss = start_timestamp.split(':')
                                    seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                                    
                                    st.caption(f"[跳转到此片段](#{seconds})")
                                    st.divider()
                            else:  # 关键词匹配格式
                                score = match.get('score', 0) * 100  # 转换为百分比
                                timestamp = match.get('timestamp', '00:00:00')
                                text = match.get('text', '')
                                keyword = match.get('keyword', '')
                                
                                with st.container():
                                    st.markdown(f"""
                                    ### 片段 {i} - 匹配度: {score:.0f}%
                                    - **时间点**: {timestamp}
                                    - **内容**: "{text}"
                                    - **匹配关键词**: {keyword}
                                    """)
                                    
                                    # 提取时间点制作视频片段链接
                                    hh, mm, ss = timestamp.split(':')
                                    seconds = int(hh) * 3600 + int(mm) * 60 + float(ss)
                                    
                                    st.caption(f"[跳转到此片段](#{seconds})")
                                    st.divider()
                    else:
                        st.warning("❗ 未找到与您需求匹配的视频片段，请尝试调整搜索条件")
                
            except Exception as e:
                logger.error(f"搜索过程出错: {str(e)}")
                st.error(f"搜索过程出现错误: {str(e)}")
    
    # 显示页脚
    st.markdown("---")
    st.caption("AI视频智能分析系统 - 版权所有")

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main()) 