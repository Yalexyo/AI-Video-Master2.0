# 视频处理流程调试指南

本指南介绍如何系统化地测试和调试视频处理流程中的问题，确保视频分析功能正常工作。

## 1. 调试流程概述

视频处理流程调试采用分层测试策略，从单个组件到完整流程逐步验证：

1. **单元测试**：验证各个处理步骤的正确性
2. **集成测试**：验证不同组件之间的协作
3. **端到端测试**：验证完整的视频处理流程
4. **性能测试**：验证处理大型或多个视频的效率

## 2. 准备工作

### 2.1 测试环境准备

```bash
# 1. 确保Python环境正确配置
python --version  # 应为 Python 3.10+

# 2. 安装必要依赖
pip install -r requirements.txt

# 3. 准备测试视频文件
# - 存放到 data/samples/ 目录下
# - 准备不同类型视频（有声音/无声音，不同分辨率等）
```

### 2.2 了解视频处理流程

视频处理流程主要包括以下步骤：

1. **获取视频**：本地上传或远程URL下载
2. **视频信息读取**：提取视频基本信息（分辨率、时长等）
3. **音频提取**：从视频中分离音频轨道
4. **语音识别**：将音频转换为文本字幕
5. **内容匹配**：基于用户意图和关键词匹配相关内容
6. **结果输出**：生成匹配结果

## 3. 调试工具

项目提供了以下调试工具：

### 3.1 单元测试

```bash
# 运行单元测试
python -m tests.video.unit_tests
```

### 3.2 端到端测试

```bash
# 使用实际视频文件测试完整流程
python tests/video/end_to_end_tests.py --video <视频文件路径>

# 仅测试特定步骤
python tests/video/end_to_end_tests.py --video <视频文件路径> --type info
python tests/video/end_to_end_tests.py --video <视频文件路径> --type audio
python tests/video/end_to_end_tests.py --video <视频文件路径> --type subtitle
```

### 3.3 意图匹配测试

```bash
# 测试意图服务
python -m tests.video.test_intent_matching

# 测试LLM服务
python -m tests.video.test_llm_service

# 测试UI组件
python -m tests.video.test_ui_components
```

### 3.4 调试记录自动化

```bash
# 更新待验证清单
python scripts/track_pending.py

# 自动更新已验证项
python scripts/track_pending.py --auto-update
```

## 4. 步骤化调试流程

### 4.1 视频信息获取测试

问题特征：视频元数据获取失败，如分辨率、时长等信息缺失。

```bash
# 1. 检查视频文件是否可读取
python -c "import cv2; cap = cv2.VideoCapture('<视频文件路径>'); print(cap.isOpened())"

# 2. 检查视频基本信息
python -c "import cv2; cap = cv2.VideoCapture('<视频文件路径>'); print('宽度:', cap.get(cv2.CAP_PROP_FRAME_WIDTH), '高度:', cap.get(cv2.CAP_PROP_FRAME_HEIGHT), 'FPS:', cap.get(cv2.CAP_PROP_FPS), '总帧数:', cap.get(cv2.CAP_PROP_FRAME_COUNT))"

# 3. 测试视频信息提取步骤
python tests/video/end_to_end_tests.py --video <视频文件路径> --type info
```

常见问题：
- 视频编码格式不兼容
- 文件权限问题
- OpenCV库依赖问题

### 4.2 音频提取测试

问题特征：无法从视频中提取音频，或提取的音频文件为空/损坏。

```bash
# 1. 检查ffmpeg是否正确安装
ffmpeg -version

# 2. 手动提取音频测试
ffmpeg -i <视频文件路径> -vn -ar 16000 -ac 1 -c:a pcm_s16le -f wav test_audio.wav

# 3. 测试音频提取步骤
python tests/video/end_to_end_tests.py --video <视频文件路径> --type audio
```

常见问题：
- ffmpeg未正确安装
- 视频文件不包含音频轨道
- 音频格式不受支持

### 4.3 字幕提取测试

问题特征：语音识别失败，无法生成字幕文本。

```bash
# 1. 检查DashScope API密钥配置
echo $DASHSCOPE_API_KEY | wc -c

# 2. 测试API联通性
curl -H "Authorization: Bearer $DASHSCOPE_API_KEY" https://dashscope.aliyuncs.com/api/v1/services

# 3. 测试字幕提取步骤
python tests/video/end_to_end_tests.py --video <视频文件路径> --type subtitle
```

常见问题：
- API密钥未设置或已过期
- 网络连接问题
- 音频质量问题（噪音过大、语音不清晰）
- API调用参数错误

### 4.4 意图服务测试

问题特征：意图加载失败，无法正确匹配用户意图。

```bash
# 1. 检查意图定义文件
cat data/intents/intents_keywords.json

# 2. 测试意图服务
python -c "from src.core.intent_service import IntentService; service = IntentService(); print(f'已加载 {len(service.get_all_intents())} 个意图')"

# 3. 测试意图匹配功能
python -m tests.video.test_intent_matching
```

常见问题：
- 意图定义文件不存在或格式错误
- 意图定义不合理或不全面
- 意图服务加载逻辑错误

### 4.5 LLM服务测试

问题特征：LLM服务调用失败，无法进行精确匹配。

```bash
# 1. 检查LLM API密钥配置
echo $OPENROUTER_API_KEY | wc -c

# 2. 测试LLM服务
python -m tests.video.test_llm_service

# 3. 测试单个LLM功能
python -c "import asyncio; from src.api.llm_service import LLMService; service = LLMService(); prompt = 'Hello, world!'; print('API密钥:', service.api_key[:5]+'...'+service.api_key[-5:], '模型:', service.model)"
```

常见问题：
- API密钥未设置或已过期
- 网络连接问题
- LLM响应格式解析错误
- API调用参数错误

## 5. 问题排查指南

### 5.1 日志分析

```bash
# 查看最新日志
tail -n 50 logs/app_$(date +%Y%m%d).log

# 查找错误信息
grep -i "error\|exception\|failed" logs/app_$(date +%Y%m%d).log
```

### 5.2 环境排查

```bash
# 检查依赖版本
pip freeze | grep -E "dashscope|opencv|numpy|pandas|httpx"

# 检查系统资源
python -c "import psutil; print(f'CPU使用率: {psutil.cpu_percent()}%, 可用内存: {psutil.virtual_memory().available / (1024 ** 3):.2f}GB')"
```

### 5.3 调试记录模板

在调试过程中，请使用以下模板记录问题和解决方案，写入到`docs/debug_history.md`文件中：

```markdown
### 问题名称 (YYYY-MM-DD HH:MM:SS)

**假设**: 可能导致问题的原因

**操作**: 采取的调试或修复操作

**结果**: ✅ 问题已解决，修复后的效果
```

## 6. 完整流程测试

执行完整的端到端测试验证所有步骤：

```bash
# 1. 测试基础视频处理
python tests/video/end_to_end_tests.py --video <视频文件路径> --type all

# 2. 测试意图匹配
python -m tests.video.test_intent_matching

# 3. 测试LLM服务
python -m tests.video.test_llm_service

# 4. 测试UI组件
python -m tests.video.test_ui_components

# 5. 启动应用进行手动测试
streamlit run app.py
```

## 7. 性能优化

如果需要优化处理速度：

1. 使用缓存机制避免重复处理
2. 优化音频提取参数
3. 调整LLM服务参数
4. 使用多线程/多进程处理多个视频

## 注意事项

- 确保已配置好API密钥和环境变量
- 处理大型视频时注意系统资源消耗
- 定期清理临时文件和缓存 