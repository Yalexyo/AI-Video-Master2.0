#!/bin/bash

# 导航到项目根目录
cd "$(dirname "$0")/.."

# 设置PYTHONPATH
export PYTHONPATH=`pwd`

# 检查并创建必要的目录
mkdir -p data/processed/analysis/results
mkdir -p data/processed/subtitles
mkdir -p data/output/videos
mkdir -p data/output/segments
mkdir -p data/temp/videos
mkdir -p data/temp/audio

# 运行魔法视频页面
echo "启动魔法视频功能..."
streamlit run pages/magic_video.py --server.port=8502 