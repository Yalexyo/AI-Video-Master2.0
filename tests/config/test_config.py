# 测试配置文件

# 测试用的热词表ID
TEST_VOCABULARY_IDS = {
    "母婴用品": "vocab_maternal_baby",
    "美妆护肤": "vocab_beauty_care",
    "数码产品": "vocab_digital",
    "通用": "vocab_general"
}

# 测试视频与热词表的映射关系
VIDEO_VOCABULARY_MAPPING = {
    "17.mp4": "vocab_maternal_baby",  # 母婴用品相关视频
    "beauty_review.mp4": "vocab_beauty_care",  # 美妆测评视频
    "tech_unboxing.mp4": "vocab_digital"  # 数码开箱视频
}

# 默认热词表ID
DEFAULT_VOCABULARY_ID = "vocab_general" 