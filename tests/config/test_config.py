# 测试配置文件
# 包含测试过程中使用的各种配置参数

# 热词表ID列表
TEST_VOCABULARY_IDS = [
    "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b" # 通用热词表
]

# 默认热词表ID
DEFAULT_VOCABULARY_ID = "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b"

# 视频与热词表的映射关系
VIDEO_VOCABULARY_MAPPING = {
    # 默认所有视频都使用通用热词表
    "17.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "18.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "19.m4v": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "20.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "21.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "22.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "23.mov": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "24.mov": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "25.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "26.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "27.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b",
    "28.mp4": "vocab-aivideo-4d73bdb1b5ef496d94f5104a957c012b"
} 