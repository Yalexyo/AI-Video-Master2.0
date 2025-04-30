# 测试文件结构规范

## 文件放置原则

测试文件应该遵循以下放置原则：

1. **所有测试的文件（包括输入输出）都必须放置在 `data/test_samples` 文件夹下，而不是 `tests/` 文件夹下**。

2. 测试数据应该按照以下结构组织：
   ```
   data/test_samples/
   ├── input/              # 测试输入文件
   │   ├── video/          # 视频测试输入
   │   ├── audio/          # 音频测试输入
   │   └── config/         # 配置文件测试输入
   │
   └── output/             # 测试预期输出
       ├── video/          # 视频测试预期输出
       ├── audio/          # 音频测试预期输出
       └── config/         # 配置文件测试预期输出
   ```

## 迁移指南

当前部分测试文件和数据不符合上述规范，需要进行以下调整：

1. 将 `tests/video/data/` 目录下的所有测试数据移动到 `data/test_samples/input/video/` 目录下
2. 创建对应的 `data/test_samples/output/video/` 目录存放测试输出

## 参考示例

测试脚本应该使用类似以下的路径引用测试数据：

```python
# 引用测试输入
input_file = os.path.join('data', 'test_samples', 'input', 'video', 'sample.mp4')

# 引用测试输出
expected_output = os.path.join('data', 'test_samples', 'output', 'video', 'expected_result.json')
```

## 注意事项

1. 不要在测试代码中使用绝对路径
2. 不要在 `tests/` 目录下存放大型测试文件
3. 测试数据应该尽可能小，以便于版本控制和快速运行测试
4. 对于大型测试文件，考虑使用外部存储或自动下载机制 