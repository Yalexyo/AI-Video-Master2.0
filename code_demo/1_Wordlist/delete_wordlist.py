import dashscope
from dashscope.audio.asr import VocabularyService

# 创建热词服务实例
service = VocabularyService()

# 定义删除热词列表的函数
def delete_vocabulary(vocabulary_id):
    """
    删除指定的热词表。
    :param vocabulary_id: 需要删除的热词表标识符
    """
    service.delete_vocabulary(vocabulary_id)
    print(f"热词列表 {vocabulary_id} 已被删除。")

# 定义要删除的热词列表ID数组
vocabulary_ids_to_delete = [
    'vocab-qifuKey1-60ee7d7891254324b07b1ee73acccec7'
]

# 删除数组中的所有热词列表
for vocab_id in vocabulary_ids_to_delete:
    delete_vocabulary(vocab_id)