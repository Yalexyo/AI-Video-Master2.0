#!/usr/bin/env bash
set -e

# Step 1: 检查Python版本
if command -v python3.10 &> /dev/null; then
  PYTHON_CMD=python3.10
else
  echo "[错误] 未找到Python 3.10，请安装Python 3.10.13后再试"
  exit 1
fi

# Step 2: venv
if [ ! -d ".venv" ]; then
  echo "[INFO] 创建虚拟环境 .venv (使用Python 3.10)"
  $PYTHON_CMD -m venv .venv
fi

# Step 3: activate
source .venv/bin/activate

# Step 4: 验证Python版本
PY_VERSION=$(python --version)
if [[ $PY_VERSION != *"3.10"* ]]; then
  echo "[错误] 需要Python 3.10.x，当前版本: $PY_VERSION"
  echo "请运行: rm -rf .venv && python3.10 -m venv .venv"
  exit 1
fi

# Step 5: deps
python - <<'PY'
try:
    import streamlit  # noqa
    print('[INFO] 依赖已满足')
except ImportError:
    import os, subprocess, sys  # noqa
    print('[INFO] 安装依赖...')
    cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-i', 'https://pypi.org/simple']
    subprocess.check_call(cmd)
PY

# Step 6: run
exec streamlit run app.py 