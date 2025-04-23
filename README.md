# AI视频大师 2.0

基于AI技术的视频内容分析系统，能够从视频中提取语义信息，进行维度分析和关键词匹配。

## 功能特性

- 分析维度管理：自定义多层次分析维度，用于视频内容归类
- 热词管理：定义和管理关键词列表，用于内容检索
  - 本地热词管理：创建、编辑和删除热词分类和内容
  - 云端热词同步：检查和同步阿里云DashScope API上的热词表
- 视频分析：基于维度和关键词对视频内容进行语义分析
- 多种数据源支持：本地视频文件、YouTube视频、字幕文件(.srt/.vtt)

## 技术栈

- 前端：Streamlit
- 数据处理：Pandas, NumPy
- AI模型：sentence-transformers, PyTorch
- 视频处理：moviepy

## 项目结构

```
AI-Video-Master2.0/
│
├── app.py                 # 主应用入口
├── pages/                 # Streamlit页面
│   ├── dimensions.py      # 分析维度管理页面
│   ├── hotwords.py        # 热词管理页面
│   └── video_analysis.py  # 视频分析页面
│
├── src/                   # 核心源代码
│   ├── core/              # 核心逻辑和模型
│   │   ├── logic.py       # 业务逻辑
│   │   └── model.py       # AI模型
│   │
│   ├── data_access/       # 数据访问层
│   ├── ui_elements/       # UI组件
│   ├── utils/             # 工具函数
│   └── config/            # 配置
│
├── utils/                 # 实用工具类
│   ├── analyzer.py        # 视频分析工具
│   └── processor.py       # 视频处理工具
│
├── data/                  # 数据目录
│   ├── raw/               # 原始数据
│   ├── processed/         # 处理后的数据
│   ├── cache/             # 缓存数据
│   ├── dimensions/        # 维度定义
│   ├── hotwords/          # 热词定义
│   └── video_analysis/    # 分析结果
│
├── logs/                  # 日志文件
├── static/                # 静态资源
├── tests/                 # 测试
└── requirements.txt       # 依赖
```

## 工具模块 (utils)

### VideoAnalyzer

视频内容分析工具，提供基于维度和关键词的视频内容分析功能：

- `analyze_dimensions()`: 根据维度结构分析视频文本内容，找出与各维度匹配的片段
- `analyze_keywords()`: 根据关键词列表分析视频文本内容，找出包含关键词的片段
- `save_analysis_results()`: 保存分析结果到JSON文件

### VideoProcessor

视频处理工具，提供视频文件处理和字幕提取功能：

- `process_video_file()`: 处理视频文件，提取字幕信息并保存为CSV
- `convert_from_youtube()`: 从YouTube视频URL提取字幕
- `convert_to_csv()`: 将字幕文件(.srt/.vtt)转换为CSV格式

## 安装与运行

1. 克隆仓库
```bash
git clone https://github.com/yourusername/AI-Video-Master2.0.git
cd AI-Video-Master2.0
```

2. 创建虚拟环境并安装依赖
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置环境变量（用于热词云端同步功能）
```bash
# 创建.env文件
echo "DASHSCOPE_API_KEY=你的阿里云DashScope API密钥" > .env
```

4. 运行应用
```bash
streamlit run app.py
```

## 使用说明

### 热词管理

热词管理功能分为两个主要部分：

1. **热词管理**：创建和管理本地热词分类和热词列表
   - 添加新分类：输入分类名称并添加
   - 管理热词：在选定分类下添加、批量添加或删除热词
   - 同步到远程：将选定分类的热词同步到阿里云

2. **云端热词检查**：检查和同步阿里云上的热词表
   - 检查云端热词表：查看阿里云上所有可用的热词表及其内容
   - 同步到本地：将云端热词表同步到本地应用
   - 自动处理无名称热词表：系统会为没有名称的热词表自动分配默认名称

## 许可证

MIT
