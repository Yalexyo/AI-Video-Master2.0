import streamlit as st
import os
import sys
import logging
import pandas as pd
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui_elements.simple_nav import create_sidebar_navigation
from utils.processor import VideoProcessor
from src.core.hot_words_service import HotWordsService
from src.core.magic_video_service import MagicVideoService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置页面
st.set_page_config(
    page_title="魔法视频",
    page_icon="🪄",
    layout="wide"
)

async def main():
    """魔法视频页面主函数"""
    # 添加侧边栏导航
    create_sidebar_navigation(active_page="🪄魔法视频")
    
    st.title("🪄 魔法视频")
    st.write("基于AI智能分析，将多个视频语义匹配并合成新视频")
    
    # 初始化服务
    processor = VideoProcessor()
    hot_words_service = HotWordsService()
    magic_video_service = MagicVideoService()
    
    # 获取当前热词ID
    current_hotword_id = hot_words_service.get_current_hotword_id()
    
    # 步骤1：选择Demo视频
    with st.expander("第一步：选择Demo视频", expanded=True):
        # 默认视频目录
        default_video_dir = os.path.join('data', 'input')
        video_files = [f for f in os.listdir(default_video_dir) if f.endswith(('.mp4', '.mov', '.avi', '.MOV'))]
        
        if not video_files:
            st.warning("⚠️ 未找到可用的视频文件，请将视频文件放入data/input目录")
            return
        
        demo_video = st.selectbox(
            "选择Demo视频",
            options=video_files,
            format_func=lambda x: f"{x} - {os.path.getsize(os.path.join(default_video_dir, x)) // (1024*1024)}MB"
        )
        
        if demo_video:
            demo_video_path = os.path.join(default_video_dir, demo_video)
            st.success(f"已选择Demo视频：{demo_video}")
            
            # 显示视频预览
            st.video(demo_video_path)
    
    # 步骤2：选择视频源
    with st.expander("第二步：选择视频源", expanded=True):
        video_source = st.radio(
            "请选择视频源",
            options=["本地视频库", "在线视频URL列表"],
            horizontal=True,
            help="本地视频库: 使用data/test_samples/input/video目录下的视频；在线视频URL列表: 使用data/input目录下的CSV文件中的视频URL列表"
        )
        
        candidate_video_paths = []
        
        if video_source == "本地视频库":
            # 获取本地视频库目录下的视频文件
            local_video_dir = os.path.join('data', 'test_samples', 'input', 'video')
            local_video_files = [f for f in os.listdir(local_video_dir) if f.endswith(('.mp4', '.mov', '.avi', '.MOV'))]
            
            if not local_video_files:
                st.warning("⚠️ 本地视频库中未找到可用的视频文件")
                return
            
            st.success(f"本地视频库中共有 {len(local_video_files)} 个视频文件")
            
            # 显示视频列表
            with st.expander("查看可用的本地视频", expanded=False):
                for i, file in enumerate(local_video_files, 1):
                    file_path = os.path.join(local_video_dir, file)
                    file_size = os.path.getsize(file_path) // (1024*1024)
                    st.text(f"{i}. {file} - {file_size}MB")
            
            # 设置候选视频路径列表
            candidate_video_paths = [os.path.join(local_video_dir, file) for file in local_video_files]
        
        else:  # 在线视频URL列表
            # 获取CSV文件列表
            csv_dir = os.path.join('data', 'input')
            csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
            
            if not csv_files:
                st.warning("⚠️ 未找到可用的CSV文件，请将CSV文件放入data/input目录")
                return
            
            url_csv_file = st.selectbox(
                "选择视频URL列表文件",
                options=csv_files
            )
            
            video_urls = []
            
            if url_csv_file:
                # 加载CSV文件
                csv_path = os.path.join(csv_dir, url_csv_file)
                try:
                    df = pd.read_csv(csv_path)
                    url_col = None
                    
                    # 尝试自动识别URL列
                    for col in df.columns:
                        if 'url' in col.lower():
                            url_col = col
                            break
                    
                    if url_col is None and len(df.columns) > 0:
                        url_col = df.columns[0]  # 使用第一列作为URL列
                    
                    if url_col:
                        video_urls = df[url_col].tolist()
                        st.success(f"已从CSV文件中读取 {len(video_urls)} 个视频URL")
                        
                        # 显示URL列表
                        with st.expander("查看视频URL列表", expanded=False):
                            for i, url in enumerate(video_urls, 1):
                                st.text(f"{i}. {url}")
                    else:
                        st.error("无法识别CSV文件中的URL列")
                except Exception as e:
                    st.error(f"读取CSV文件出错: {str(e)}")
            
            # 在实际处理流程中，需要下载这些URL对应的视频
            # 在此示例中，暂不实现此功能，仅显示读取的URL
            if video_urls:
                st.info("注意：当前版本暂不支持直接从URL下载视频，请先将视频下载到本地视频库")
    
    # 步骤3：视频分析与合成设置
    with st.expander("第三步：分析与合成设置", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            max_concurrent = st.slider(
                "最大并行任务数",
                min_value=1,
                max_value=10,
                value=3,
                help="设置分析时的最大并行任务数，数值越大处理速度越快，但会消耗更多资源"
            )
        
        with col2:
            similarity_threshold = st.slider(
                "最低相似度阈值",
                min_value=0,
                max_value=100,
                value=60,
                help="设置语义匹配的最低相似度阈值，低于此分数的匹配结果将被过滤"
            )
        
        st.markdown("---")
        
        # 输出设置
        output_filename = st.text_input(
            "输出文件名",
            value=f"magic_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            help="设置生成的魔法视频文件名（不含扩展名）"
        )
        
        # 添加音频设置
        audio_source = st.radio(
            "音频来源",
            options=["使用原片段音频", "使用Demo视频音频"],
            horizontal=True,
            help="选择生成视频的音频来源"
        )
    
    # 步骤4：执行分析和合成
    col1, col2 = st.columns([1, 1])
    with col1:
        process_button = st.button("🪄 开始魔法合成", type="primary", use_container_width=True)
    
    with col2:
        cancel_button = st.button("❌ 取消", type="secondary", use_container_width=True)
    
    # 处理请求
    if process_button and demo_video and candidate_video_paths:
        with st.spinner("正在执行魔法视频合成，请稍候..."):
            try:
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 步骤1：提取字幕并进行语义分段
                status_text.info("步骤1/4：提取Demo视频字幕并进行语义分段")
                demo_result = await magic_video_service.process_demo_video(
                    video_path=demo_video_path,
                    vocabulary_id=current_hotword_id
                )
                
                if "error" in demo_result and demo_result["error"]:
                    st.error(f"处理Demo视频时出错: {demo_result['error']}")
                    return
                
                demo_segments = demo_result.get("stages", [])
                if not demo_segments:
                    st.error("未能从Demo视频中提取到有效的语义段落")
                    return
                
                # 显示分段结果
                st.success(f"Demo视频语义分段完成，共识别 {len(demo_segments)} 个语义段落")
                
                with st.expander("查看语义分段结果", expanded=False):
                    for segment in demo_segments:
                        st.markdown(f"**阶段 {segment['stage']}: {segment['label']}**")
                        st.markdown(f"* 时间段: {segment['start_timestamp']} - {segment['end_timestamp']}")
                        st.markdown(f"* 关键词: {', '.join(segment['keywords']) if segment['keywords'] else '无'}")
                        st.markdown(f"* 内容: {segment['text'][:150]}...")
                        st.markdown("---")
                
                progress_bar.progress(25)
                
                # 步骤2：处理候选视频
                status_text.info("步骤2/4：处理候选视频")
                
                # 设置最大处理视频数量(避免处理太多视频)
                max_videos = 10
                if len(candidate_video_paths) > max_videos:
                    st.warning(f"候选视频数量过多，将只处理前 {max_videos} 个视频")
                    candidate_video_paths = candidate_video_paths[:max_videos]
                
                # 批量处理候选视频
                candidate_subtitles = await magic_video_service.process_candidate_videos(
                    video_paths=candidate_video_paths,
                    vocabulary_id=current_hotword_id
                )
                
                if not candidate_subtitles:
                    st.error("未能处理任何候选视频，请检查视频文件")
                    return
                
                st.success(f"候选视频处理完成，成功处理 {len(candidate_subtitles)} 个视频")
                progress_bar.progress(50)
                
                # 步骤3：执行语义匹配
                status_text.info("步骤3/4：执行语义匹配")
                
                # 为每个Demo段落找到最匹配的候选视频片段
                match_results = await magic_video_service.match_video_segments(
                    demo_segments=demo_segments,
                    candidate_subtitles=candidate_subtitles,
                    similarity_threshold=similarity_threshold
                )
                
                if not match_results:
                    st.error("语义匹配未找到有效的匹配结果")
                    return
                
                # 汇总匹配结果
                total_matches = sum(len(matches) for matches in match_results.values())
                st.success(f"语义匹配完成，共找到 {total_matches} 个匹配片段")
                
                # 显示匹配结果
                with st.expander("查看匹配结果", expanded=False):
                    for stage_id, matches in match_results.items():
                        if not matches:
                            st.warning(f"阶段 {stage_id} 未找到匹配片段")
                            continue
                        
                        st.markdown(f"**阶段 {stage_id} 的匹配结果:**")
                        for i, match in enumerate(matches, 1):
                            st.markdown(f"- 匹配 {i}: 视频 {match['video_id']} ({match['similarity']}% 相似度)")
                            st.markdown(f"  时间段: {match['start_timestamp']} - {match['end_timestamp']}")
                            st.markdown(f"  文本: {match['text'][:100]}...")
                
                progress_bar.progress(75)
                
                # 步骤4：合成魔法视频
                status_text.info("步骤4/4：合成魔法视频")
                
                use_demo_audio = (audio_source == "使用Demo视频音频")
                output_path = await magic_video_service.compose_magic_video(
                    demo_video_path=demo_video_path,
                    match_results=match_results,
                    output_filename=output_filename,
                    use_demo_audio=use_demo_audio
                )
                
                if not output_path or not os.path.exists(output_path):
                    st.error("合成魔法视频失败")
                    return
                
                progress_bar.progress(100)
                status_text.success("✅ 魔法视频合成完成！")
                
                # 显示结果
                st.markdown("### 生成的魔法视频")
                st.video(output_path)
                
                # 提供下载链接
                with open(output_path, "rb") as file:
                    st.download_button(
                        label="下载魔法视频",
                        data=file,
                        file_name=f"{output_filename}.mp4",
                        mime="video/mp4"
                    )
                
            except Exception as e:
                logger.exception(f"魔法视频处理过程出错: {str(e)}")
                st.error(f"处理过程出现错误: {str(e)}")
    
    # 显示页脚
    st.markdown("---")
    st.caption("AI视频魔法合成系统 - 版权所有")

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main()) 