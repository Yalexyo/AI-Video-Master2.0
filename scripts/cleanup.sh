#!/bin/bash

# 设置安全删除选项
set -e
echo "========== 视频内容匹配系统清理脚本 =========="
echo "将删除项目中的临时文件、缓存和不必要的测试文件"
echo ""

# 1. 删除Python缓存文件(不包括.venv中的)
echo "1. 删除Python缓存文件..."
find . -name "__pycache__" -not -path "./.venv*" -type d -exec rm -rf {} +
find . -name "*.pyc" -not -path "./.venv*" -exec rm -f {} +
echo "  完成!"
echo ""

# 2. 删除备份文件
echo "2. 删除备份文件..."
find . -name "*.bak" -type f -exec rm -f {} +
echo "  完成!"
echo ""

# 3. 删除旧日志文件(保留最近3天的)
echo "3. 删除旧日志文件(保留最近3天)..."
find logs -name "*.log" -type f -not -newermt "$(date -v-3d +%Y-%m-%d)" -exec rm -f {} +
echo "  完成!"
echo ""

# 4. 删除临时数据文件
echo "4. 删除临时数据文件..."
rm -rf data/temp/*
echo "  完成!"
echo ""

# 5. 删除旧测试结果文件(保留最近5个)
echo "5. 删除旧测试结果文件..."
cd data/processed/analysis/results && ls -t | tail -n +6 | xargs rm -f 2>/dev/null || true
cd -
cd data/output/segments && ls -t | tail -n +6 | xargs rm -f 2>/dev/null || true
cd -
cd data/output/subtitles && ls -t | tail -n +6 | xargs rm -f 2>/dev/null || true
cd -
echo "  完成!"
echo ""

# 6. 删除系统临时文件
echo "6. 删除系统临时文件..."
find . -name ".DS_Store" -not -path "./.venv*" -exec rm -f {} +
echo "  完成!"
echo ""

echo "========== 清理完成 =========="
echo "所有临时文件和缓存已被删除" 