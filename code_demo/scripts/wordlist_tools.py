#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
热词列表工具模块
-------------
提供热词列表管理的命令行工具，支持创建、查询、删除热词列表。
支持交互式和命令行两种操作模式。
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wordlist_tools")

# 添加项目根目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# 导入工具模块
from utils import config, wordlist_manager

def init():
    """初始化配置"""
    config.init()
    return wordlist_manager.get_manager()

def create_wordlist(args):
    """创建热词列表"""
    mgr = init()
    
    if args.file:
        vocabulary_id = mgr.create_vocabulary_from_file(
            file_path=args.file,
            lang=args.lang,
            weight=args.weight,
            prefix=args.prefix,
            target_model=args.model
        )
        logger.info(f"成功从文件创建热词列表，ID: {vocabulary_id}" if vocabulary_id else "从文件创建热词列表失败")
    elif args.words:
        vocabulary = [{
            'text': word,
            'weight': args.weight,
            'lang': 'en' if all(ord(c) < 128 for c in word) else args.lang
        } for word in args.words]
        
        vocabulary_id = mgr.create_vocabulary(
            vocabulary=vocabulary,
            prefix=args.prefix,
            target_model=args.model
        )
        logger.info(f"成功创建热词列表，ID: {vocabulary_id}" if vocabulary_id else "创建热词列表失败")
    else:
        logger.error("必须提供热词列表文件(--file)或热词列表(--words)")

def list_wordlists(args):
    """列出热词列表"""
    mgr = init()
    vocabularies = mgr.list_vocabularies(
        prefix=args.prefix,
        page_index=args.page,
        page_size=args.size
    )
    
    if not vocabularies:
        logger.info("未找到热词列表")
        return
    
    print("\n热词列表:")
    for i, vocab in enumerate(vocabularies, 1):
        print(f"{i}. ID: {vocab.get('vocabulary_id', '未知')}")
        print(f"   前缀: {vocab.get('prefix', '未知')}")
        print(f"   模型: {vocab.get('target_model', '未知')}")
        
        if args.verbose:
            vocabulary_content = mgr.query_vocabulary(vocab.get('vocabulary_id', ''))
            if vocabulary_content and 'vocabulary' in vocabulary_content:
                print("   热词列表内容:")
                for j, item in enumerate(vocabulary_content['vocabulary'], 1):
                    print(f"     {j}. 文本: {item.get('text', '未知')}")
                    print(f"        权重: {item.get('weight', '未知')}")
                    print(f"        语言: {item.get('lang', '未知')}")
            print()

def query_wordlist(args):
    """查询热词列表内容"""
    mgr = init()
    vocabulary_content = mgr.query_vocabulary(args.id)
    
    if not vocabulary_content or 'vocabulary' not in vocabulary_content:
        logger.error(f"查询热词列表失败: {args.id}")
        return
    
    print(f"\n热词列表 {args.id} 内容:")
    for i, item in enumerate(vocabulary_content['vocabulary'], 1):
        print(f"{i}. 文本: {item.get('text', '未知')}")
        print(f"   权重: {item.get('weight', '未知')}")
        print(f"   语言: {item.get('lang', '未知')}")
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(vocabulary_content, f, indent=2, ensure_ascii=False)
            logger.info(f"已保存热词列表内容到文件: {args.output}")
        except Exception as e:
            logger.error(f"保存热词列表内容到文件失败: {e}")

def update_wordlist(args):
    """更新热词列表内容"""
    mgr = init()
    
    # 获取现有热词内容
    current_content = mgr.query_vocabulary(args.id)
    if not current_content or 'vocabulary' not in current_content:
        logger.error(f"无法获取热词列表内容: {args.id}")
        return
    
    # 从文件更新
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                new_content = json.load(f)
            
            if mgr.update_vocabulary(args.id, new_content.get('vocabulary', [])):
                logger.info(f"成功更新热词列表: {args.id}")
            else:
                logger.error(f"更新热词列表失败: {args.id}")
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
    
    # 交互式更新
    elif args.interactive:
        print(f"\n当前热词列表 {args.id} 内容:")
        for i, item in enumerate(current_content['vocabulary'], 1):
            print(f"{i}. 文本: {item.get('text')}")
            print(f"   权重: {item.get('weight')}")
            print(f"   语言: {item.get('lang')}")
        
        print("\n选择操作:")
        print("1. 添加热词")
        print("2. 删除热词")
        print("3. 修改热词")
        choice = input("请输入选项(1-3): ")
        
        if choice == '1':
            text = input("输入新热词: ")
            weight = int(input("输入权重(1-10): "))
            lang = input("输入语言(zh/en): ")
            
            current_content['vocabulary'].append({
                'text': text,
                'weight': weight,
                'lang': lang
            })
            
            if mgr.update_vocabulary(args.id, current_content['vocabulary']):
                logger.info("成功添加热词")
            else:
                logger.error("添加热词失败")
        
        elif choice == '2':
            index = int(input("输入要删除的热词编号: ")) - 1
            if 0 <= index < len(current_content['vocabulary']):
                del current_content['vocabulary'][index]
                if mgr.update_vocabulary(args.id, current_content['vocabulary']):
                    logger.info("成功删除热词")
                else:
                    logger.error("删除热词失败")
            else:
                logger.error("无效的热词编号")
        
        elif choice == '3':
            index = int(input("输入要修改的热词编号: ")) - 1
            if 0 <= index < len(current_content['vocabulary']):
                print(f"\n当前热词: {current_content['vocabulary'][index]['text']}")
                print(f"当前权重: {current_content['vocabulary'][index]['weight']}")
                print(f"当前语言: {current_content['vocabulary'][index]['lang']}")
                
                text = input(f"新文本(回车保持原值): ") or current_content['vocabulary'][index]['text']
                weight = input(f"新权重(回车保持原值): ") or current_content['vocabulary'][index]['weight']
                lang = input(f"新语言(回车保持原值): ") or current_content['vocabulary'][index]['lang']
                
                current_content['vocabulary'][index] = {
                    'text': text,
                    'weight': int(weight),
                    'lang': lang
                }
                
                if mgr.update_vocabulary(args.id, current_content['vocabulary']):
                    logger.info("成功修改热词")
                else:
                    logger.error("修改热词失败")
            else:
                logger.error("无效的热词编号")
    
    else:
        logger.error("必须提供更新文件(--file)或使用交互模式(--interactive)")

def delete_wordlist(args):
    """删除热词列表"""
    mgr = init()
    
    if not args.force and input(f"确定要删除热词列表 {args.id} 吗？(y/n): ").lower() != 'y':
        logger.info("取消删除")
        return
    
    logger.info(f"成功删除热词列表: {args.id}" if mgr.delete_vocabulary(args.id) else f"删除热词列表失败: {args.id}")

def analyze_srt(args):
    """分析SRT文件"""
    mgr = init()
    results = mgr.analyze_srt_with_hotwords(args.srt, args.id)
    
    if not results:
        logger.warning(f"在SRT文件中未找到包含热词的字幕: {args.srt}")
        return
    
    print(f"\n在SRT文件 {args.srt} 中找到 {len(results)} 个包含热词的字幕:")
    for i, result in enumerate(results, 1):
        print(f"{i}. 编号: {result.get('number', '未知')}")
        print(f"   时间: {result.get('start_time', '未知')} --> {result.get('end_time', '未知')}")
        print(f"   热词: {result.get('hotword', '未知')}")
        print(f"   文本: {result.get('text', '未知')}")
        print()
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"已保存分析结果到文件: {args.output}")
        except Exception as e:
            logger.error(f"保存分析结果到文件失败: {e}")

def auto_weight(args):
    """自动调整热词权重"""
    mgr = init()
    vocabularies = mgr.list_vocabularies(prefix=args.prefix)
    
    if not vocabularies:
        logger.info("未找到热词列表")
        return
    
    for vocab in vocabularies:
        vocabulary_id = vocab.get('vocabulary_id')
        vocabulary_content = mgr.query_vocabulary(vocabulary_id)
        
        if not vocabulary_content or 'vocabulary' not in vocabulary_content:
            continue
        
        updated_vocabulary = []
        for item in vocabulary_content['vocabulary']:
            freq = mgr.get_term_frequency(item['text'])
            new_weight = min(4 + freq // 100, 10)
            
            updated_vocabulary.append({
                'text': item['text'],
                'weight': new_weight,
                'lang': item['lang']
            })
        
        if mgr.update_vocabulary(vocabulary_id, updated_vocabulary):
            logger.info(f"成功更新热词列表 {vocabulary_id} 的权重")
        else:
            logger.error(f"更新热词列表 {vocabulary_id} 的权重失败")

def interactive_mode():
    """交互式操作模式"""
    print("\n热词列表管理系统 - 交互模式")
    print("------------------------")
    
    while True:
        print("\n主菜单:")
        print("1. 创建热词列表")
        print("2. 列出热词列表")
        print("3. 查询热词内容")
        print("4. 更新热词列表")
        print("5. 删除热词列表")
        print("6. 分析SRT文件")
        print("7. 自动调整权重")
        print("0. 退出")
        
        choice = input("请选择操作(0-7): ")
        
        if choice == '0':
            break
        
        elif choice == '1':
            file_path = input("热词文件路径(留空手动输入): ")
            words = input("手动输入热词(空格分隔，留空跳过): ").split() if not file_path else None
            lang = input("默认语言(zh/en，默认zh): ") or 'zh'
            weight = int(input("默认权重(1-10，默认4): ") or 4)
            prefix = input("前缀(可选): ")
            model = input("目标模型(可选): ")
            
            args = type('Args', (), {
                'file': file_path if file_path else None,
                'words': words,
                'lang': lang,
                'weight': weight,
                'prefix': prefix,
                'model': model
            })()
            
            create_wordlist(args)
        
        elif choice == '2':
            prefix = input("前缀过滤(可选): ")
            verbose = input("显示详情(y/n): ").lower() == 'y'
            
            args = type('Args', (), {
                'prefix': prefix if prefix else None,
                'page': 0,
                'size': 10,
                'verbose': verbose
            })()
            
            list_wordlists(args)
        
        elif choice == '3':
            vocab_id = input("输入热词列表ID: ")
            output = input("输出文件路径(可选): ")
            
            args = type('Args', (), {
                'id': vocab_id,
                'output': output if output else None
            })()
            
            query_wordlist(args)
        
        elif choice == '4':
            vocab_id = input("输入要更新的热词列表ID: ")
            file_path = input("更新文件路径(留空使用交互模式): ")
            
            args = type('Args', (), {
                'id': vocab_id,
                'file': file_path if file_path else None,
                'interactive': not bool(file_path)
            })()
            
            update_wordlist(args)
        
        elif choice == '5':
            vocab_id = input("输入要删除的热词列表ID: ")
            force = input("强制删除(y/n): ").lower() == 'y'
            
            args = type('Args', (), {
                'id': vocab_id,
                'force': force
            })()
            
            delete_wordlist(args)
        
        elif choice == '6':
            srt_path = input("输入SRT文件路径: ")
            vocab_id = input("热词列表ID(留空使用最新): ")
            output = input("输出文件路径(可选): ")
            
            args = type('Args', (), {
                'srt': srt_path,
                'id': vocab_id if vocab_id else None,
                'output': output if output else None
            })()
            
            analyze_srt(args)
        
        elif choice == '7':
            prefix = input("前缀过滤(可选): ")
            
            args = type('Args', (), {
                'prefix': prefix if prefix else None
            })()
            
            auto_weight(args)
        
        else:
            print("无效选项，请重新输入")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='热词列表管理工具')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # 创建命令
    create_parser = subparsers.add_parser('create', help='创建热词列表')
    create_parser.add_argument('--file', help='热词列表文件路径')
    create_parser.add_argument('--words', nargs='+', help='热词列表')
    create_parser.add_argument('--lang', default='zh', help='默认语言')
    create_parser.add_argument('--weight', type=int, default=4, help='热词权重')
    create_parser.add_argument('--prefix', help='前缀')
    create_parser.add_argument('--model', help='目标模型')
    
    # 列出命令
    list_parser = subparsers.add_parser('list', help='列出热词列表')
    list_parser.add_argument('--prefix', help='前缀过滤')
    list_parser.add_argument('--page', type=int, default=0, help='页码')
    list_parser.add_argument('--size', type=int, default=10, help='每页大小')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='详细模式')
    
    # 查询命令
    query_parser = subparsers.add_parser('query', help='查询热词列表内容')
    query_parser.add_argument('id', help='热词列表ID')
    query_parser.add_argument('--output', '-o', help='输出文件路径')
    
    # 更新命令
    update_parser = subparsers.add_parser('update', help='更新热词列表')
    update_parser.add_argument('id', help='热词列表ID')
    update_group = update_parser.add_mutually_exclusive_group(required=True)
    update_group.add_argument('--file', help='更新文件路径')
    update_group.add_argument('--interactive', action='store_true', help='交互模式')
    
    # 删除命令
    delete_parser = subparsers.add_parser('delete', help='删除热词列表')
    delete_parser.add_argument('id', help='热词列表ID')
    delete_parser.add_argument('--force', '-f', action='store_true', help='强制删除')
    
    # 分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析SRT文件')
    analyze_parser.add_argument('srt', help='SRT文件路径')
    analyze_parser.add_argument('--id', help='热词列表ID')
    analyze_parser.add_argument('--output', '-o', help='输出文件路径')
    
    # 自动权重命令
    weight_parser = subparsers.add_parser('auto-weight', help='自动调整权重')
    weight_parser.add_argument('--prefix', help='前缀过滤')
    
    # 交互模式命令
    interactive_parser = subparsers.add_parser('interactive', help='交互模式')
    interactive_parser.set_defaults(func=lambda _: interactive_mode())

    # 解析参数并执行对应函数
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
