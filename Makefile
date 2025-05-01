.PHONY: setup install run test lint clean help

# 变量定义
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
APP = app.py
PYTHON_VERSION = python3.10

# 设置环境
setup:
	$(PYTHON_VERSION) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# 安装依赖
install:
	$(PIP) install -r requirements.txt

# 运行应用
run:
	$(PYTHON) -m streamlit run $(APP)

# 运行测试
test:
	$(PYTHON) -m pytest tests/

# 代码质量检查
lint:
	$(PYTHON) -m flake8 src/
	$(PYTHON) -m black src/ tests/ pages/

# 清理项目
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".streamlit" -exec rm -rf {} +

# 帮助信息
help:
	@echo "可用命令:"
	@echo "  make setup   - 创建Python 3.10虚拟环境并安装依赖"
	@echo "  make install - 安装项目依赖"
	@echo "  make run     - 运行Streamlit应用"
	@echo "  make test    - 运行测试"
	@echo "  make lint    - 运行代码质量检查"
	@echo "  make clean   - 清理项目临时文件"
	@echo "  make help    - 显示帮助信息"
