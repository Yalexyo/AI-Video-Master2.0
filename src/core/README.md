# 热词管理模块

本模块提供热词管理功能，支持与阿里云DashScope API交互，实现热词的增删改查操作。

## 功能特点

- 支持本地热词管理：创建、删除分类，添加、删除热词
- 支持热词分类管理，便于不同场景使用不同的热词表
- 支持与阿里云DashScope API交互，将本地热词同步到远程API服务
- 支持批量导入热词
- 支持热词表ID管理，便于语音识别时引用
- 支持热词权重和语言自动判断

## 模块结构

- `hot_words_api.py`：API交互层，负责与阿里云DashScope API交互
- `hot_words_service.py`：服务层，连接API和本地存储，提供业务逻辑功能

## 使用方法

### 配置API密钥

在环境变量中设置 `DASHSCOPE_API_KEY`，或在`.env`文件中配置：

```
DASHSCOPE_API_KEY=your_api_key_here
```

### 代码示例

#### 1. 初始化服务

```python
from src.core.hot_words_service import get_service

# 获取热词服务实例
hot_words_service = get_service()
```

#### 2. 创建分类

```python
# 创建新分类
hot_words_service.add_category("技术术语")
```

#### 3. 添加热词

```python
# 添加单个热词
hot_words_service.add_hotword("技术术语", "人工智能")

# 批量添加热词
hot_words = ["机器学习", "深度学习", "神经网络"]
hot_words_service.batch_add_hotwords("技术术语", hot_words)
```

#### 4. 删除热词

```python
# 删除热词
hot_words_service.delete_hotword("技术术语", "人工智能")
```

#### 5. 删除分类

```python
# 删除分类（同时会删除远程热词表）
hot_words_service.delete_category("技术术语")
```

#### 6. 获取热词表ID

```python
# 获取分类对应的热词表ID，用于语音识别时引用
vocabulary_id = hot_words_service.get_vocabulary_id("技术术语")
```

## API参考

### HotWordsAPI类

- `create_vocabulary(vocabulary, prefix=None, target_model=None)`：创建热词表
- `list_vocabularies(prefix=None, page_index=0, page_size=10)`：获取热词表列表
- `query_vocabulary(vocabulary_id)`：查询热词表详情
- `update_vocabulary(vocabulary_id, vocabulary)`：更新热词表内容
- `delete_vocabulary(vocabulary_id)`：删除热词表

### HotWordsService类

- `load_hotwords()`：加载热词数据
- `save_hotwords(hotwords_data)`：保存热词数据
- `add_category(category_name)`：添加分类
- `delete_category(category_name)`：删除分类
- `add_hotword(category_name, hotword)`：添加热词
- `delete_hotword(category_name, hotword)`：删除热词
- `batch_add_hotwords(category_name, hotwords)`：批量添加热词
- `get_vocabulary_id(category_name)`：获取分类对应的热词表ID

## 数据结构

热词数据以JSON格式存储在`data/hotwords/hotwords.json`文件中，结构如下：

```json
{
  "categories": {
    "技术术语": ["人工智能", "机器学习", "深度学习"],
    "品牌名称": ["阿里云", "DashScope", "飞桨"]
  },
  "vocabulary_ids": {
    "技术术语": "vocab-aivideo-123456789",
    "品牌名称": "vocab-aivideo-987654321"
  },
  "last_updated": "2023-06-01 12:00:00"
}
```

## 核心模块文件说明

- `hot_words_service.py`：热词服务，提供热词管理的业务逻辑功能 