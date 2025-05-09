# 处理结果目录 (Processed Data)

本目录用于存放视频处理流程中生成的**持久化数据**，这些文件是处理结果的最终输出或重要中间结果，需要长期保存。

## 子目录结构

- **subtitles/**：存放从视频中提取和生成的字幕文件
  - SRT格式：`[视频文件名]_[时间戳].srt`，用于视频播放器加载
  - JSON格式：`[视频文件名]_[时间戳]_subtitles.json`，用于系统内部处理
  - 这些文件是语音识别的结果，包含文本内容和时间戳信息
  
- **analysis/**：存放视频分析和处理的结果
  - `results/`：存放匹配结果和分析报告
    - `optimized_matches_[时间戳].json`：视频片段匹配结果
    - 语义分段结果
    - 其他分析指标和数据

## 数据用途

这些处理结果用于：
1. 为视频提供字幕支持
2. 为视频内容分析提供文本数据
3. 作为视频合成的素材来源
4. 作为历史记录，便于追踪和回溯处理过程

## 备份策略

建议定期备份此目录下的内容：
- 每周自动备份到备用存储
- 重要项目完成后手动备份
- 可使用`scripts/backup_processed.py`进行手动备份

## 注意事项

- 请勿随意删除此目录下的文件，除非确定它们不再需要
- 可使用`scripts/cleanup_old_processed.py --days=30`清理较旧的数据
- 这些数据也可能被其他模块或系统引用，删除前请确认 