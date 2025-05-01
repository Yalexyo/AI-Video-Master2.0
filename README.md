# AI视频大师 2.0

基于AI技术的视频内容分析系统，能够从视频中提取语义信息，进行维度分析和关键词匹配。

## 功能特性

- 分析维度管理：自定义多层次分析维度，用于视频内容归类
- 热词管理：定义和管理关键词列表，用于内容检索
  - 本地热词管理：创建、编辑和删除热词分类和内容
  - 云端热词同步：检查和同步阿里云DashScope API上的热词表
- 视频分析：基于维度和关键词对视频内容进行语义分析
- 多种数据源支持：本地视频文件、YouTube视频、字幕文件(.srt/.vtt)

## 核心处理流程

视频分析的完整流程包括以下步骤：

1. **视频输入**：系统支持多种来源的视频输入
   - 本地视频文件上传
   - 阿里云OSS存储中的视频URL
   - YouTube视频链接（实验性功能）
   - 已有字幕文件（SRT/VTT格式）

2. **预处理**：对视频进行基础处理
   - 视频信息读取：获取分辨率、帧率、时长等基本信息
   - 音频提取：使用ffmpeg从视频中提取音频文件（WAV格式）

3. **语音识别**：将音频转换为文本
   - 使用阿里云DashScope的Paraformer模型进行语音识别
   - 支持热词表配置，提高特定领域词汇的识别准确率
   - 包含语音识别失败时的备用处理机制

4. **语义分割**：对识别出的文本进行处理
   - 按时间戳分段整理文本内容
   - 形成带有时间信息的文本数据集

5. **语义分析**：根据选择的分析类型，执行不同的分析
   - **维度分析**：使用语义模型将内容与预设维度进行匹配
     - 一级维度匹配：确定内容所属的主要类别
     - 二级维度匹配：进一步细分内容的具体属性
   - **关键词分析**：检测内容中是否包含预设的关键词
     - 使用语义相似度匹配，支持非精确匹配
     - 计算并记录匹配分数和位置信息

6. **结果生成**：整理分析结果
   - 生成包含匹配信息的JSON结构化数据
   - 记录每个匹配项的时间戳、文本内容和匹配分数
   - 保存到分析结果文件中

7. **结果展示**：以用户友好的方式呈现分析结果
   - 按维度/关键词分类展示匹配结果
   - 提供时间轴视图，显示各匹配项在视频中的时间分布
   - 支持结果导出和分享

整个流程采用模块化设计，每个步骤都有明确的错误处理和备用方案，确保分析过程的稳定性和可靠性。

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
