import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 处理流程配置
    PROCESS_STEPS = [
        'subtitles',
        'analysis', 
        'matching',
        'compilation'
    ]
    
    # 视频参数
    TRANSITION_TYPES = {
        'fade': {'duration': 1.0},
        'slide': {'direction': 'right', 'duration': 0.8},
        'zoom': {'factor': 1.2, 'duration': 1.2}
    }
    
    # 默认维度结构 - 调整为只有两个层级的结构
    DEFAULT_DIMENSIONS = {
        'title': '品牌认知',  # 之前的level1变成标题
        'level1': ['产品特性', '用户需求'],  # 之前的level2变成level1
        'level2': {  # 之前的level3变成level2
            '产品特性': ['功能', '外观', '性能'],
            '用户需求': ['场景', '痛点', '期望']
        }
    }
    
    # API配置
    @property
    def DASHSCOPE_API_KEY(self):
        return os.getenv('DASHSCOPE_API_KEY', '')
    
    # 路径配置
    INPUT_DIR = 'data/raw'
    OUTPUT_DIR = 'data/processed'
    CACHE_DIR = 'data/cache'
    DIMENSIONS_DIR = os.path.join('data', 'dimensions')
    HOTWORDS_DIR = os.path.join('data', 'hotwords')
    INITIAL_DIMENSION_FILENAME = 'initial_dimension.json'

config = Config()

# 导出常用配置项供直接导入
DIMENSIONS_DIR = config.DIMENSIONS_DIR
HOTWORDS_DIR = config.HOTWORDS_DIR
INITIAL_DIMENSION_FILENAME = config.INITIAL_DIMENSION_FILENAME
