# 视频处理与内容匹配测试指南

本目录包含用于测试视频处理和内容匹配功能的脚本和数据。

## 测试脚本

### 基础视频处理测试
- `unit_tests.py`: 单元测试，测试视频处理基础组件（视频信息提取、音频提取、字幕生成等）
- `end_to_end_tests.py`: 端到端测试，测试完整视频处理流程

### 视频内容匹配测试
- `test_intent_matching.py`: 测试意图匹配功能
- `test_llm_service.py`: 测试LLM服务功能
- `test_ui_components.py`: 测试UI组件功能

## 使用方法

### 基础视频处理测试

```bash
# 运行单元测试
python -m tests.video.unit_tests

# 运行端到端测试
python -m tests.video.end_to_end_tests

# 测试特定环节（如仅测试字幕提取）
python -m tests.video.end_to_end_tests --video <视频文件路径> --type subtitle
```

### 视频内容匹配测试

```bash
# 测试意图匹配功能
python -m tests.video.test_intent_matching

# 测试LLM服务功能
python -m tests.video.test_llm_service

# 测试UI组件功能
python -m tests.video.test_ui_components
```

## 测试文件结构

所有测试相关文件都统一放在 `data/test_samples` 目录下:

### 输入数据
- `data/test_samples/input/video/`: 测试视频文件
- `data/test_samples/input/audio/`: 测试音频文件
- `data/test_samples/input/config/`: 测试配置文件

### 输出数据
- `data/test_samples/output/video/`: 视频处理结果
- `data/test_samples/output/audio/`: 音频处理结果
- `data/test_samples/output/subtitles/`: 提取的字幕文件
- `data/test_samples/output/segments/`: 视频片段匹配结果
- `data/test_samples/output/analysis/`: 其他分析结果

### 其他测试资源
- `data/test_samples/logs/`: 测试日志文件
- `data/test_samples/temp/`: 测试临时文件
- `data/test_samples/cache/audio/`: 测试音频缓存
- `data/test_samples/debug_history/`: 测试调试记录

## 测试要点

### 基础视频处理
1. **视频提取**: 验证视频信息读取（分辨率、时长等）
2. **音频提取**: 验证从视频中分离音频
3. **字幕提取**: 验证语音转文字功能
4. **数据处理**: 验证数据预处理和格式转换

### 视频内容匹配
1. **意图识别**: 验证系统能否正确识别用户选择的内容意图
2. **关键词匹配**: 验证基础关键词匹配功能的准确性
3. **LLM精确匹配**: 验证使用大语言模型进行精确匹配的效果
4. **用户体验**: 验证UI组件的易用性和交互反馈
5. **错误处理**: 验证系统在各种错误情况下的恢复和反馈能力

## 调试指南

如果遇到测试失败，请检查以下几点:

1. API密钥配置：
   - 语音识别API: `.env` 文件中的 `DASHSCOPE_API_KEY`
   - LLM服务API: `.env` 文件中的 `OPENROUTER_API_KEY`

2. 数据文件:
   - 意图配置文件: `data/intents/intents_keywords.json`
   - 测试视频文件是否存在且可访问

3. 环境问题:
   - 网络连接是否正常，API是否可访问
   - 依赖库是否正确安装

详细的调试步骤请参考 `data/test_samples/debug_history/debug_guide.md` 文件。 