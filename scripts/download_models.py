#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
预先下载和缓存模型
用法：python scripts/download_models.py
"""

import os
import logging
import argparse
import glob
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def list_model_files(cache_dir, model_name):
    """列出模型文件"""
    model_name_parts = model_name.split('/')
    model_path = os.path.join(cache_dir, *model_name_parts)
    
    if not os.path.exists(model_path):
        logger.warning(f"模型目录不存在: {model_path}")
        return
    
    logger.info(f"模型目录: {model_path}")
    
    # 列出模型目录下的文件
    files = os.listdir(model_path)
    logger.info(f"模型目录下的文件: {', '.join(files)}")
    
    # 检查特定文件
    for file in ["config.json", "modules.json", "tokenizer_config.json"]:
        file_path = os.path.join(model_path, file)
        if os.path.exists(file_path):
            logger.info(f"找到文件: {file}")
        else:
            logger.warning(f"未找到文件: {file}")
    
    # 查找子目录和权重文件
    for subdir in glob.glob(os.path.join(model_path, "*/")):
        subdir_name = os.path.basename(os.path.dirname(subdir))
        logger.info(f"子目录: {subdir_name}")
        
        # 查找权重文件
        weight_files = glob.glob(os.path.join(subdir, "*.bin")) + glob.glob(os.path.join(subdir, "*.safetensors"))
        if weight_files:
            logger.info(f"  权重文件: {', '.join(os.path.basename(f) for f in weight_files)}")
        else:
            logger.warning(f"  未在 {subdir_name} 中找到权重文件")

def main():
    parser = argparse.ArgumentParser(description='下载和缓存模型')
    parser.add_argument('--model_name', type=str, 
                        default='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
                        help='要下载的模型名称')
    parser.add_argument('--cache_dir', type=str, 
                        default=os.path.join('data', 'models', 'sentence_transformers'),
                        help='模型缓存目录')
    args = parser.parse_args()
    
    try:
        # 创建缓存目录
        os.makedirs(args.cache_dir, exist_ok=True)
        logger.info(f"使用缓存目录: {args.cache_dir}")
        
        # 尝试导入sentence_transformers
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("成功导入sentence_transformers库")
        except ImportError:
            logger.error("未安装sentence_transformers库，请先安装: pip install sentence-transformers")
            return
        
        logger.info(f"开始下载模型: {args.model_name}")
        
        # 下载并缓存模型
        model = SentenceTransformer(args.model_name, cache_folder=args.cache_dir)
        
        # 简单测试模型
        test_sentences = ["这是一个测试句子", "这是另一个测试句子"]
        embeddings = model.encode(test_sentences)
        
        logger.info(f"模型下载并测试成功，生成了embeddings，shape: {embeddings.shape}")
        logger.info(f"模型文件已缓存到: {args.cache_dir}")
        
        # 列出模型文件
        list_model_files(args.cache_dir, args.model_name)
        
        # 使用离线模式的提示
        logger.info("\n离线使用方法:")
        logger.info("1. 设置环境变量 TRANSFORMERS_OFFLINE=1")
        logger.info("2. 确保使用相同的缓存目录")
        logger.info("3. 可以通过在analyzer.py中添加以下代码启用离线模式:")
        logger.info("   import os")
        logger.info("   os.environ['TRANSFORMERS_OFFLINE'] = '1'")
        
    except Exception as e:
        logger.error(f"下载模型时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 