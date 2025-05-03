#!/usr/bin/env python3
"""
魔法视频页面 - 视频自动合成

该页面提供视频分析和魔法视频合成功能
"""

import os
import sys
import json
import logging
import asyncio
import time
import streamlit as st
from pathlib import Path
import pandas as pd
import shutil
from datetime import datetime

# 导入项目组件
from utils.processor import VideoProcessor
from src.core.magic_video_service import MagicVideoService
from src.core.magic_video_fix import video_fix_tools

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Streamlit页面配置
st.set_page_config(
    page_title="魔法视频 - AI视频大师",
    page_icon="🧙‍♂️",
    layout="wide"
)

# 样式
st.markdown("""
<style>
    .stButton button {
        width: 100%;
    }
    .diagnostic-btn {
        font-size: 0.8em;
        color: #888;
    }
    .video-validated {
        color: green;
        font-weight: bold;
    }
    .video-invalid {
        color: red;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def validate_video_files(video_files):
    """验证上传的视频文件是否有效"""
    invalid_files = []
    
    for video_file in video_files:
        temp_path = os.path.join("data", "temp", "videos", video_file.name)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        with open(temp_path, "wb") as f:
            f.write(video_file.getbuffer())
        
        # 验证视频
        valid, error_msg = video_fix_tools.validate_video_file(temp_path)
        if not valid:
            invalid_files.append((video_file.name, error_msg))
            # 尝试修复
            st.warning(f"视频 {video_file.name} 存在问题，正在尝试修复...")
            fixed, result = video_fix_tools.repair_video_file(temp_path)
            if fixed:
                st.success(f"视频 {video_file.name} 已成功修复!")
            else:
                st.error(f"无法修复视频 {video_file.name}: {result}")
                # 删除无效视频文件
                os.remove(temp_path)
                continue
        
        # 复制到目标目录
        target_dir = os.path.join("data", "test_samples", "input", "video")
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, video_file.name)
        shutil.copy2(temp_path, target_path)
    
    return invalid_files

def main():
    """主函数"""
    st.title("🧙‍♂️ 魔法视频")
    st.markdown("上传参考视频和素材视频，自动生成场景完整的魔法视频")
    
    # 初始化会话状态
    if "demo_video_path" not in st.session_state:
        st.session_state.demo_video_path = None
    if "demo_segments" not in st.session_state:
        st.session_state.demo_segments = None
    if "candidate_videos" not in st.session_state:
        st.session_state.candidate_videos = []
    if "match_results" not in st.session_state:
        st.session_state.match_results = None
    if "magic_video_path" not in st.session_state:
        st.session_state.magic_video_path = None
    
    # 创建服务实例
    service = MagicVideoService()
    
    # 分栏布局
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("第1步：上传参考视频")
        demo_video = st.file_uploader("上传参考视频", type=["mp4", "mov", "avi"], key="demo_video")
        
        if demo_video:
            # 保存上传的Demo视频
            demo_dir = os.path.join("data", "test_samples", "input", "video")
            os.makedirs(demo_dir, exist_ok=True)
            
            demo_path = os.path.join(demo_dir, demo_video.name)
            with open(demo_path, "wb") as f:
                f.write(demo_video.getbuffer())
            
            # 检查视频是否有效
            valid, error_msg = video_fix_tools.validate_video_file(demo_path)
            if not valid:
                st.error(f"参考视频无效：{error_msg}")
                st.warning("正在尝试修复视频...")
                fixed, result = video_fix_tools.repair_video_file(demo_path)
                if fixed:
                    st.success("参考视频已修复!")
                else:
                    st.error(f"无法修复参考视频: {result}")
                return
            else:
                st.success("参考视频有效")
            
            st.session_state.demo_video_path = demo_path
            
            # 显示视频预览
            st.video(demo_path)
            
            # 热词表选择（如果需要）
            use_hotwords = st.checkbox("使用热词表", value=False)
            vocabulary_id = None
            if use_hotwords:
                # 这里可以添加热词表选择逻辑
                st.info("热词表功能待实现")
            
            # 分析参考视频按钮
            if st.button("📊 分析参考视频", key="analyze_demo"):
                with st.spinner("正在分析参考视频..."):
                    # 执行异步分析
                    result = asyncio.run(service.process_demo_video(demo_path, vocabulary_id))
                    
                    if "error" in result and result["error"]:
                        st.error(f"分析参考视频失败: {result['error']}")
                    else:
                        st.success(f"分析完成，共识别 {len(result['stages'])} 个语义段落")
                        st.session_state.demo_segments = result["stages"]
        
        st.subheader("第2步：上传素材视频")
            
        # 多个素材视频上传
        candidate_videos = st.file_uploader("上传素材视频（可多选）", 
                                         type=["mp4", "mov", "avi"],
                                         accept_multiple_files=True,
                                         key="candidate_videos")
        
        if candidate_videos:
            # 验证上传的视频文件
            invalid_files = validate_video_files(candidate_videos)
            
            if invalid_files:
                st.warning("以下视频存在问题，但已尝试修复：")
                for name, error in invalid_files:
                    st.write(f"- {name}: {error}")
            
            # 更新会话状态
            valid_videos = [os.path.join("data", "test_samples", "input", "video", v.name) 
                          for v in candidate_videos 
                          if os.path.exists(os.path.join("data", "test_samples", "input", "video", v.name))]
            
            st.session_state.candidate_videos = valid_videos
            
            st.success(f"已上传 {len(valid_videos)} 个有效素材视频")
                        
            # 素材视频处理按钮
            if st.button("🔍 分析素材视频", key="analyze_candidates"):
                if len(st.session_state.candidate_videos) == 0:
                    st.error("请先上传有效的素材视频")
                else:
                    with st.spinner("正在分析素材视频..."):
                        # 使用异步方法处理
                        subtitles = asyncio.run(service.process_candidate_videos(st.session_state.candidate_videos))
                        
                        if subtitles:
                            st.success(f"已完成 {len(subtitles)} 个素材视频的分析")
                    else:
                            st.error("素材视频分析失败")
        
        st.subheader("第3步：设置与合成")
        
        # 魔法视频设置
        output_filename = st.text_input("输出文件名", value=f"magic_video_{datetime.now().strftime('%Y%m%d')}")
        use_demo_audio = st.checkbox("使用参考视频的音频", value=True)
    
        # 魔法视频合成按钮
        if st.button("✨ 合成魔法视频", key="compose_magic"):
            if not st.session_state.demo_segments:
                st.error("请先分析参考视频")
            elif len(st.session_state.candidate_videos) == 0:
                st.error("请先上传并分析素材视频")
            else:
                with st.spinner("正在匹配视频片段..."):
                    # 首先获取所有素材视频的字幕
                    subtitles = asyncio.run(service.process_candidate_videos(st.session_state.candidate_videos))
                    
                    if not subtitles:
                        st.error("素材视频分析失败")
                    else:
                        # 匹配视频片段
                        match_results = asyncio.run(service.match_video_segments(
                            st.session_state.demo_segments,
                            subtitles,
                            similarity_threshold=60
                        ))
                        
                        st.session_state.match_results = match_results
                        
                        if not match_results:
                            st.error("视频片段匹配失败，未找到足够相似的片段")
                        else:
                            # 合成魔法视频
                            with st.spinner("正在合成魔法视频..."):
                                magic_video = asyncio.run(service.compose_magic_video(
                                    st.session_state.demo_video_path,
                                    match_results,
                                    output_filename,
                                    use_demo_audio
                                ))
                                
                                if magic_video and os.path.exists(magic_video):
                                    st.session_state.magic_video_path = magic_video
                                    st.success(f"魔法视频合成成功: {magic_video}")
                                else:
                                    st.error("魔法视频合成失败")
    
    with col2:
        # 诊断工具（折叠面板）
        with st.expander("🔧 诊断工具", expanded=False):
            st.subheader("视频文件检测")
    
            # 诊断按钮
            if st.button("👁️ 检查视频文件", key="check_videos"):
                st.write("#### 检查参考视频:")
                if st.session_state.demo_video_path and os.path.exists(st.session_state.demo_video_path):
                    valid, error = video_fix_tools.validate_video_file(st.session_state.demo_video_path)
                    if valid:
                        st.markdown(f"- **参考视频**: <span class='video-validated'>✅ 有效</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- **参考视频**: <span class='video-invalid'>❌ 无效</span> - {error}", unsafe_allow_html=True)
                else:
                    st.write("- 未找到参考视频")
                
                st.write("#### 检查素材视频:")
                if st.session_state.candidate_videos:
                    for i, video_path in enumerate(st.session_state.candidate_videos):
                        if os.path.exists(video_path):
                            valid, error = video_fix_tools.validate_video_file(video_path)
                            if valid:
                                st.markdown(f"- **素材 {i+1}**: <span class='video-validated'>✅ 有效</span> - {os.path.basename(video_path)}", unsafe_allow_html=True)
                            else:
                                st.markdown(f"- **素材 {i+1}**: <span class='video-invalid'>❌ 无效</span> - {os.path.basename(video_path)} - {error}", unsafe_allow_html=True)
                        else:
                            st.markdown(f"- **素材 {i+1}**: <span class='video-invalid'>❌ 不存在</span> - {os.path.basename(video_path)}", unsafe_allow_html=True)
                else:
                    st.write("- 未找到素材视频")
                
            # 尝试修复按钮
            if st.button("🔄 尝试修复所有视频", key="fix_videos"):
                st.write("#### 修复参考视频:")
                if st.session_state.demo_video_path and os.path.exists(st.session_state.demo_video_path):
                    fixed, result = video_fix_tools.repair_video_file(st.session_state.demo_video_path)
                    if fixed:
                        st.success(f"参考视频修复成功: {os.path.basename(st.session_state.demo_video_path)}")
                    else:
                        st.error(f"参考视频修复失败: {result}")
                
                st.write("#### 修复素材视频:")
                if st.session_state.candidate_videos:
                    for i, video_path in enumerate(st.session_state.candidate_videos):
                        if os.path.exists(video_path):
                            fixed, result = video_fix_tools.repair_video_file(video_path)
                            if fixed:
                                st.success(f"素材 {i+1} 修复成功: {os.path.basename(video_path)}")
                            else:
                                st.error(f"素材 {i+1} 修复失败: {result}")
                        else:
                            st.error(f"素材 {i+1} 不存在: {os.path.basename(video_path)}")
        
        # 结果展示
        st.subheader("结果展示")
        
        # 根据会话状态显示不同内容
        if st.session_state.magic_video_path:
            st.success("魔法视频已生成")
            st.video(st.session_state.magic_video_path)
        elif st.session_state.match_results:
            st.info("视频片段匹配完成，等待合成")
            # 显示匹配结果
            st.write("#### 匹配片段:")
            for stage_id, matches in st.session_state.match_results.items():
                st.write(f"**阶段 {stage_id}:** {len(matches)} 个匹配")
                if matches:
                    best_match = matches[0]
                    st.write(f"- 最佳匹配: {os.path.basename(best_match['video_id'])}, "
                           f"相似度: {best_match['similarity']:.2f}%, "
                           f"时间: {best_match['start_time']:.2f}s - {best_match['end_time']:.2f}s")
        elif st.session_state.demo_segments:
            st.info("参考视频分析完成，等待素材视频处理")
            # 显示分段结果
            st.write("#### 参考视频段落:")
            for segment in st.session_state.demo_segments:
                st.write(f"**{segment['index']}. {segment['label']}** ({segment['start_time']:.2f}s - {segment['end_time']:.2f}s)")
                st.write(f"内容: {segment['text'][:100]}...")
                else:
            st.info("请完成左侧步骤以生成魔法视频")
            
            # 示例或帮助信息
            with st.expander("查看使用指南", expanded=True):
                st.markdown("""
                **魔法视频生成步骤:**
                
                1. **上传参考视频** - 上传一个包含完整场景流程的视频作为参考
                2. **分析参考视频** - 系统将分析视频内容并识别关键场景
                3. **上传素材视频** - 上传包含各种场景的素材视频文件
                4. **分析素材视频** - 系统将分析所有素材视频
                5. **合成魔法视频** - 根据参考视频的场景结构，从素材中匹配最佳片段并合成
                
                **提示:**
                - 参考视频应当包含清晰的场景过渡
                - 素材视频越多，匹配质量越高
                - 如遇到视频处理问题，可使用诊断工具检测和修复
                """)

if __name__ == "__main__":
    main() 