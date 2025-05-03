#!/bin/bash

# 视频生成测试运行器
# 这个脚本用于在离线环境中运行魔法视频生成流水线测试
# 它设置必要的环境变量，避免测试过程中的网络依赖

# 设置所有Hugging Face离线模式环境变量
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_SYMLINKS_WARNING=1

# 输出设置的环境变量
echo "已设置以下离线模式环境变量:"
echo "TRANSFORMERS_OFFLINE=$TRANSFORMERS_OFFLINE"
echo "HF_HUB_OFFLINE=$HF_HUB_OFFLINE"
echo "HF_DATASETS_OFFLINE=$HF_DATASETS_OFFLINE"
echo "DISABLE_TELEMETRY=$DISABLE_TELEMETRY"
echo "HF_HUB_DISABLE_TELEMETRY=$HF_HUB_DISABLE_TELEMETRY"
echo "HF_HUB_DISABLE_SYMLINKS_WARNING=$HF_HUB_DISABLE_SYMLINKS_WARNING"
echo ""

# 显示用法说明
function show_usage {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  test         运行标准视频生成流水线测试"
    echo "  model        测试模型加载"
    echo "  multiple     运行多策略视频生成 (生成多个不同风格的视频)"
    echo "  help         显示帮助信息"
    echo ""
}

# 检查命令行参数，执行相应的测试
if [ "$1" == "test" ]; then
    echo "运行视频生成流水线测试..."
    python tests/video/test_video_generation_pipeline.py
elif [ "$1" == "model" ]; then
    echo "测试模型加载..."
    python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_folder='data/models/sentence_transformers'); print('模型加载成功!')"
elif [ "$1" == "multiple" ]; then
    echo "运行多策略视频生成测试..."
    python tests/video/test_multiple_videos.py
elif [ "$1" == "help" ]; then
    show_usage
else
    echo "错误: 未知的选项 '$1'"
    show_usage
    exit 1
fi 