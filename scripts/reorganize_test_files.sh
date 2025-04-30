#!/bin/bash

# 设置操作选项
set -e
echo "========== 测试文件结构重组脚本 =========="
echo "将测试产生的文件统一放到data/test_samples目录下"
echo ""

# 确保测试目录结构存在
echo "1. 创建必要的目录结构..."
mkdir -p data/test_samples/output/video
mkdir -p data/test_samples/output/audio
mkdir -p data/test_samples/output/subtitles
mkdir -p data/test_samples/output/segments
mkdir -p data/test_samples/logs
mkdir -p data/test_samples/temp
mkdir -p data/test_samples/cache/audio
mkdir -p data/test_samples/debug_history
echo "  完成!"
echo ""

# 2. 移动测试日志文件
echo "2. 移动测试日志文件..."
find logs -name "test_*.log" -type f -exec cp {} data/test_samples/logs/ \;
echo "  测试日志文件已复制到 data/test_samples/logs/ 目录"
echo ""

# 3. 移动临时文件
echo "3. 移动临时文件..."
if [ -d "data/temp" ]; then
    cp -r data/temp/* data/test_samples/temp/ 2>/dev/null || echo "  临时目录为空"
fi
echo "  临时文件已复制到 data/test_samples/temp/ 目录"
echo ""

# 4. 复制测试调试记录
echo "4. 复制测试调试记录..."
if [ -f "docs/debug_history.md" ]; then
    cp docs/debug_history.md data/test_samples/debug_history/
    echo "  调试记录已复制到 data/test_samples/debug_history/ 目录"
else
    echo "  调试记录文件不存在"
fi

# 移动调试指南
if [ -f "tests/video/debug_guide.md" ]; then
    cp tests/video/debug_guide.md data/test_samples/debug_history/
    echo "  调试指南已复制到 data/test_samples/debug_history/ 目录"
else
    echo "  调试指南文件不存在"
fi
echo ""

# 5. 移动音频缓存文件
echo "5. 移动音频缓存文件..."
if [ -d "data/cache/audio" ]; then
    cp -r data/cache/audio/* data/test_samples/cache/audio/ 2>/dev/null || echo "  音频缓存目录为空"
fi
echo "  音频缓存文件已复制到 data/test_samples/cache/audio/ 目录"
echo ""

# 6. 移动测试结果文件
echo "6. 移动测试结果文件..."
# 移动字幕文件
if [ -d "data/output/subtitles" ]; then
    cp -r data/output/subtitles/* data/test_samples/output/subtitles/ 2>/dev/null || echo "  字幕输出目录为空"
fi

# 移动分析结果文件
if [ -d "data/output/segments" ]; then
    cp -r data/output/segments/* data/test_samples/output/segments/ 2>/dev/null || echo "  分析结果目录为空"
fi

# 移动其他测试输出
if [ -d "data/processed/analysis/results" ]; then
    mkdir -p data/test_samples/output/analysis
    cp -r data/processed/analysis/results/* data/test_samples/output/analysis/ 2>/dev/null || echo "  分析结果处理目录为空"
fi
echo "  测试结果文件已复制到 data/test_samples/output/ 目录"
echo ""

# 7. 更新测试文件路径
echo "7. 更新测试脚本中的文件路径..."
# 创建备份
cp tests/video/end_to_end_tests.py tests/video/end_to_end_tests.py.bak
cp tests/video/unit_tests.py tests/video/unit_tests.py.bak

# 更新文件路径
sed -i '' 's|TEST_INPUT_DIR = os.path.join(.data., .test_samples., .input., .video.)|TEST_INPUT_DIR = os.path.join("data", "test_samples", "input", "video")|g' tests/video/end_to_end_tests.py
sed -i '' 's|TEST_OUTPUT_DIR = os.path.join(.data., .test_samples., .output., .video.)|TEST_OUTPUT_DIR = os.path.join("data", "test_samples", "output", "video")|g' tests/video/end_to_end_tests.py

# 更新日志路径
sed -i '' 's|logging.FileHandler(os.path.join(.logs., f.test_e2e_|logging.FileHandler(os.path.join("data", "test_samples", "logs", f"test_e2e_|g' tests/video/end_to_end_tests.py
sed -i '' 's|logging.FileHandler(os.path.join(.logs., f.test_|logging.FileHandler(os.path.join("data", "test_samples", "logs", f"test_|g' tests/video/unit_tests.py

# 更新debug_history路径
sed -i '' 's|debug_history_file = os.path.join(project_root, .docs., .debug_history.md.)|debug_history_file = os.path.join(project_root, "data", "test_samples", "debug_history", "debug_history.md")|g' tests/video/end_to_end_tests.py

echo "  测试脚本路径已更新"
echo ""

echo "========== 文件结构重组完成 =========="
echo "测试文件现在统一放在 data/test_samples 目录下"
echo "原始文件仍保留在原位置，可以在确认新结构正常后删除"
echo "备份文件: tests/video/end_to_end_tests.py.bak, tests/video/unit_tests.py.bak" 