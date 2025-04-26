#!/bin/bash
# 清理AI视频大师产生的所有临时文件
# 
# 该脚本可以清理：
# - 临时视频文件 (data/temp/videos/downloaded/*)
# - 临时音频文件 (data/cache/audio/*)
# - 临时字幕文件 (data/processed/subtitles/* 和 data/output/subtitles/*)
# - 其他临时文件 (data/temp/*.csv 和样本文件)
#
# 使用方法: bash scripts/remove_temp.sh

LOG_FILE="logs/cleanup_$(date +%Y%m%d).log"

# 确保日志目录存在
mkdir -p logs

echo "$(date): 开始清理临时文件..." | tee -a "$LOG_FILE"

# 1. 清理临时视频文件
VIDEOS_DIR="data/temp/videos/downloaded"
if [ -d "$VIDEOS_DIR" ]; then
    VIDEO_COUNT=$(find "$VIDEOS_DIR" -type f -name "*.mp4" | wc -l)
    VIDEO_SIZE=$(du -sh "$VIDEOS_DIR" | cut -f1)
    echo "清理临时视频文件: $VIDEO_COUNT 个文件，共 $VIDEO_SIZE" | tee -a "$LOG_FILE"
    find "$VIDEOS_DIR" -type f -name "*.mp4" -exec rm -f {} \;
else
    echo "$(date): 视频目录不存在: $VIDEOS_DIR" | tee -a "$LOG_FILE"
fi

# 2. 清理audio_server目录
AUDIO_SERVER_DIR="data/temp/audio_server"
if [ -d "$AUDIO_SERVER_DIR" ]; then
    DIRS_COUNT=$(find "$AUDIO_SERVER_DIR" -mindepth 1 -type d | wc -l)
    AUDIO_SERVER_SIZE=$(du -sh "$AUDIO_SERVER_DIR" | cut -f1)
    echo "清理audio_server目录: $DIRS_COUNT 个子目录，共 $AUDIO_SERVER_SIZE" | tee -a "$LOG_FILE"
    rm -rf "$AUDIO_SERVER_DIR"/*
    echo "audio_server目录已清空" | tee -a "$LOG_FILE"
else
    echo "$(date): audio_server目录不存在: $AUDIO_SERVER_DIR" | tee -a "$LOG_FILE"
fi

# 3. 清理其他临时音频文件
TEMP_AUDIO_DIR="data/temp/audio"
if [ -d "$TEMP_AUDIO_DIR" ]; then
    AUDIO_COUNT=$(find "$TEMP_AUDIO_DIR" -type f | wc -l)
    AUDIO_SIZE=$(du -sh "$TEMP_AUDIO_DIR" | cut -f1)
    echo "清理临时音频文件: $AUDIO_COUNT 个文件，共 $AUDIO_SIZE" | tee -a "$LOG_FILE"
    rm -rf "$TEMP_AUDIO_DIR"/*
else
    echo "$(date): 音频目录不存在: $TEMP_AUDIO_DIR" | tee -a "$LOG_FILE"
fi

# 4. 清理缓存音频文件
CACHE_AUDIO_DIR="data/cache/audio"
if [ -d "$CACHE_AUDIO_DIR" ]; then
    CACHE_AUDIO_COUNT=$(find "$CACHE_AUDIO_DIR" -type f -name "*.wav" | wc -l)
    CACHE_AUDIO_SIZE=$(du -sh "$CACHE_AUDIO_DIR" | cut -f1)
    echo "清理缓存音频文件: $CACHE_AUDIO_COUNT 个文件，共 $CACHE_AUDIO_SIZE" | tee -a "$LOG_FILE"
    find "$CACHE_AUDIO_DIR" -type f -name "*.wav" -exec rm -f {} \;
    echo "缓存音频文件已清理" | tee -a "$LOG_FILE"
else
    echo "$(date): 缓存音频目录不存在: $CACHE_AUDIO_DIR" | tee -a "$LOG_FILE"
fi

# 5. 清理临时字幕文件
TEMP_SUBTITLES_DIR="data/temp/subtitles"
if [ -d "$TEMP_SUBTITLES_DIR" ]; then
    SUBTITLES_COUNT=$(find "$TEMP_SUBTITLES_DIR" -type f | wc -l)
    SUBTITLES_SIZE=$(du -sh "$TEMP_SUBTITLES_DIR" | cut -f1)
    echo "清理临时字幕文件: $SUBTITLES_COUNT 个文件，共 $SUBTITLES_SIZE" | tee -a "$LOG_FILE"
    rm -rf "$TEMP_SUBTITLES_DIR"/*
else
    echo "$(date): 字幕目录不存在: $TEMP_SUBTITLES_DIR" | tee -a "$LOG_FILE"
    # 尝试其他可能的字幕目录
    ALT_SUBTITLE_DIR="data/output/subtitles"
    if [ -d "$ALT_SUBTITLE_DIR" ]; then
        find "$ALT_SUBTITLE_DIR" -type f -delete
        echo "$(date): 已清理替代字幕目录文件: $ALT_SUBTITLE_DIR" | tee -a "$LOG_FILE"
    fi
fi

# 6. 清理其他临时文件
TEMP_DIR="data/temp"
if [ -d "$TEMP_DIR" ]; then
    # 删除所有临时CSV文件
    find "$TEMP_DIR" -name "*.csv" -type f -delete
    echo "$(date): 已清理临时CSV文件" | tee -a "$LOG_FILE"
    
    # 删除其他临时文件
    find "$TEMP_DIR" -name "sample_*" -type f -delete
    echo "$(date): 已清理其他临时样本文件" | tee -a "$LOG_FILE"
fi

echo "$(date): 临时文件清理完成" | tee -a "$LOG_FILE"
echo "清理日志已保存至: $LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "如果需要重新生成数据，请重新运行应用!" | tee -a "$LOG_FILE" 