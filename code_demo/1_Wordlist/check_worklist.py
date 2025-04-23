import dashscope
from dashscope.audio.asr import VocabularyService

"""
程序功能说明:
    1. 通过 DashScope 的热词服务获取所有热词列表（支持分页），
       并以用户友好的格式输出每个热词列表的详细信息，包括热词列表ID、前缀和目标模型。
    2. 对于每个热词列表，调用 query_vocabulary 方法获取详细的热词内容（每个热词的文本、权重、语言）。
    3. 最后，提取并输出所有热词列表的ID号。

输入:
    - 无直接输入参数，但程序通过 dashscope.audio.asr.VocabularyService 接口与远程 API 交互，
      使用分页参数（page_index、page_size）获取热词列表数据。
      
输出:
    - 在控制台打印：
        • 每个热词列表的基本信息：热词列表ID、前缀、目标模型；
        • 对应的热词列表内容：每个热词的文本、权重和语言；
        • 最后输出所有热词列表的ID号列表。

依赖:
    - dashscope：用于访问 DashScope API。
    - dashscope.audio.asr.VocabularyService：热词服务类，用于获取和查询热词列表。
"""

def get_all_vocabulary_ids(vocabularies):
    """
    返回所有热词列表的ID号。
    
    参数:
        vocabularies (list): 热词列表字典的列表。
    
    返回:
        list: 包含每个热词列表的 'vocabulary_id' 字段，如果缺失则返回 '未知'。
    """
    return [vocab.get('vocabulary_id', '未知') for vocab in vocabularies]

# 创建热词服务实例
service = VocabularyService()

# 使用 list_vocabularies 方法获取所有热词列表，支持分页
page_index = 0
page_size = 10
vocabularies = service.list_vocabularies(prefix=None, page_index=page_index, page_size=page_size)

# 以用户友好的格式输出所有热词列表的内容
print("所有热词列表:")
for vocab in vocabularies:
    print(f"热词列表 ID: {vocab.get('vocabulary_id', '未知')}, 前缀: {vocab.get('prefix', '未知')}, 模型: {vocab.get('target_model', '未知')}")
    
    # 查询每个热词列表的详细内容
    vocabulary_content = service.query_vocabulary(vocab.get('vocabulary_id', ''))
    
    # 从返回的字典中提取 'vocabulary' 列表（包含具体热词信息）
    if 'vocabulary' in vocabulary_content:
        print("热词列表内容:")
        for item in vocabulary_content['vocabulary']:
            print(f"  文本: {item['text']}, 权重: {item['weight']}, 语言: {item['lang']}")
    else:
        print("Unexpected format for vocabulary content.")
    print("-")

# 获取并输出所有热词列表的ID号
vocabulary_ids = get_all_vocabulary_ids(vocabularies)
print("所有热词列表的ID号:", vocabulary_ids)
