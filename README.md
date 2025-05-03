# AI 视频大师 (AI Video Master) 3.0

AI 视频大师是一款基于人工智能的视频分析与处理工具，可以对视频内容进行智能分析、维度划分和热词提取，帮助用户快速理解视频内容并生成关键信息概览。

## 主要功能

### 视频处理与分析
- **视频上传与分析**: 支持多种格式视频文件的上传与自动分析
- **语音转文字**: 自动提取视频音频并转换为文字内容
- **维度分析**: 根据预设维度对视频内容进行多角度分析
- **意图识别**: 智能识别视频内容中的关键意图

### 魔法视频
- **视频语义分段**: 自动对Demo视频进行语义分析和分段
- **跨视频匹配**: 基于语义相似度在多个视频中查找匹配片段
- **智能视频合成**: 将匹配片段智能剪辑拼接为新视频
- **音频控制**: 支持使用原片段音频或Demo视频音频

### 热词管理
- **热词提取**: 从视频内容中自动识别关键词与热词
- **热词权重调整**: 支持对热词重要性进行手动调整
- **热词分类**: 按照不同维度对热词进行智能分类

### 数据导出与分享
- **分析结果导出**: 支持将分析结果导出为多种格式
- **云端存储**: 可将处理后的数据存储到阿里云OSS
- **结果分享**: 便捷地分享分析结果

## 技术栈

- **前端**: Streamlit
- **后端**: Python
- **AI模型**: Sentence Transformers, OpenAI API, 深度语义匹配
- **存储**: 阿里云OSS
- **音视频处理**: ffmpeg, MoviePy

## 安装与配置

### 环境要求
- Python 3.8+
- ffmpeg

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/Yalexyo/AI-Video-Master3.0.git
cd AI-Video-Master3.0
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
# 复制示例配置文件
cp .env.example .env
cp src/config/oss_config.ini.example src/config/oss_config.ini

# 编辑配置文件，填入您的API密钥和OSS配置
```

4. 下载模型
```bash
python scripts/download_models.py
```

## 使用方法

启动应用：
```bash
streamlit run app.py
```

或启动魔法视频功能：
```bash
./scripts/run_magic_video.sh
```

## 项目结构

```
AI-Video-Master3.0/
├── app.py                    # 应用主入口
│
├── pages/                    # 页面目录
│   ├── hotwords.py           # 热词管理页面
│   ├── video_search.py       # 视频搜索页面
│   ├── magic_video.py        # 魔法视频页面
│   └── legacy/               # 历史页面
│
├── src/                      # 核心源码
│   ├── api/                  # API接口
│   │   └── llm_service.py    # LLM服务调用封装
│   │
│   ├── config/               # 配置文件
│   │   ├── settings.py       # 全局设置
│   │   └── oss_config.ini.example  # OSS配置模板
│   │
│   ├── core/                 # 核心业务逻辑
│   │   ├── hot_words_service.py  # 热词服务
│   │   ├── intent_service.py # 意图识别服务
│   │   ├── magic_video_service.py # 魔法视频服务
│   │   ├── model.py          # 数据模型
│   │   └── video_segment_service.py  # 视频片段处理服务
│   │
│   ├── data_access/          # 数据访问层
│   └── ui_elements/          # UI组件
│       ├── intent_selector.py  # 意图选择器
│       ├── simple_nav.py     # 简易导航
│       └── video_upload.py   # 视频上传组件
│
├── utils/                    # 工具函数
│   ├── analyzer.py           # 分析工具
│   ├── config_handler.py     # 配置处理
│   ├── oss_handler.py        # OSS存储处理
│   ├── processor.py          # 数据处理
│   └── video_utils.py        # 视频工具
│
├── scripts/                  # 脚本工具
│   ├── cleanup.sh            # 清理脚本
│   ├── download_models.py    # 模型下载
│   ├── oss_config.sh         # OSS配置脚本
│   ├── run.sh                # 运行脚本
│   ├── run_magic_video.sh    # 魔法视频启动脚本
│   └── track_pending.py      # 待处理任务跟踪
│
├── data/                     # 数据目录
│   ├── cache/                # 缓存数据
│   ├── intents/              # 意图数据
│   ├── processed/            # 处理过程数据
│   │   ├── analysis/         # 分析结果
│   │   └── subtitles/        # 提取的字幕
│   ├── output/               # 输出结果
│   │   ├── segments/         # 视频片段
│   │   ├── videos/           # 合成视频
│   │   └── subtitles/        # 字幕文件
│   ├── temp/                 # 临时文件
│   │   ├── audio/            # 临时音频
│   │   └── videos/           # 临时视频
│   ├── test_samples/         # 测试样本
│   └── uploads/              # 上传文件
│
├── tests/                    # 测试
│   ├── config/               # 配置测试
│   ├── oss/                  # OSS测试
│   └── video/                # 视频处理测试
│
├── docs/                     # 文档
│   └── debug_history.md      # 调试历史记录
│
├── .env.example              # 环境变量示例
├── .gitignore                # Git忽略配置
├── README.md                 # 项目说明
└── requirements.txt          # 依赖列表
```

## 调试指南

项目遵循规范的调试流程，详情请参考 `docs/debug_history.md`。

## 开发规范

- 代码风格遵循PEP8规范
- 遵循项目分支管理规范，详情参考 `.cursor/rules/branch-management.mdc`
- 遵循最小化改动原则，详情参考 `.cursor/rules/debug-minimal-change.mdc`

## 许可证

[MIT License](LICENSE)
