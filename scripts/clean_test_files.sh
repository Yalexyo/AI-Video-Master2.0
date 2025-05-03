#!/bin/bash

echo "===== 视频处理测试文件清理脚本 ====="
echo "将清理以下目录中的测试生成文件:"
echo "1. data/processed/subtitles/"
echo "2. data/temp/audio/"
echo "3. data/processed/analysis/results/"
echo "4. data/output/videos/"
echo "5. data/temp/videos/"
echo "6. logs/ (仅pipeline测试日志)"
echo 

# 确认操作
read -p "确定要清理这些文件吗? [y/N] " confirm
if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "操作已取消"
    exit 0
fi

echo "开始清理..."

# 1. 清理字幕文件
echo "正在清理字幕文件..."
find data/processed/subtitles -type f \( -name "*.srt" -o -name "*_subtitles.json" \) -exec rm -v {} \;

# 2. 清理临时音频文件
echo "正在清理临时音频文件..."
find data/temp/audio -type f -name "*.wav" -exec rm -v {} \;

# 3. 清理匹配结果
echo "正在清理匹配结果..."
find data/processed/analysis/results -type f \( -name "optimized_matches_*.json" -o -name "matches_*.json" -o -name "*_segments.json" \) -exec rm -v {} \;

# 4. 清理最终视频
echo "正在清理输出视频..."
find data/output/videos -type f -name "pipeline_test_*.mp4" -exec rm -v {} \;

# 5. 清理临时视频片段
echo "正在清理临时视频片段..."
find data/temp/videos -type f -exec rm -v {} \;

# 6. 清理测试日志
echo "正在清理测试日志..."
find logs -type f -name "video_pipeline_debug_*.log" -exec rm -v {} \;

echo 
echo "清理完成！"
echo "如需保留某些文件，可从回收站恢复（如果使用了rm命令的-v选项，可以查看删除了哪些文件）" 