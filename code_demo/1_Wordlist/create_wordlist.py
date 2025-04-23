import dashscope
from dashscope.audio.asr import VocabularyService

# 定义热词列表前缀，用于标识您的热词列表
prefix = 'qifuKey1'  # 确保前缀不超过10个字符

target_model = 'paraformer-v2'

# 用户自定义输入的热词列表
my_vocabulary = [
    {"text": "启赋", "weight": 4, "lang": "zh"},  # 添加品牌热词
    {"text": "蕴淳", "weight": 4, "lang": "zh"},  # 添加品牌热词
    {"text": "A2奶源", "weight": 4, "lang": "zh"},  # 添加品牌热词
    {"text": "HMO", "weight": 4, "lang": "en"},  # 添加品牌热词
    {"text": "奶粉", "weight": 4, "lang": "zh"},  # 添加品牌热词
]

# 创建热词服务实例
service = VocabularyService()

# 创建热词列表，并获取热词列表的 ID
vocabulary_id = service.create_vocabulary(
    prefix=prefix,
    target_model=target_model,
    vocabulary=my_vocabulary
)

print(f"您的热词列表 ID 是：{vocabulary_id}") 