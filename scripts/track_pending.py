#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
待验证项追踪脚本

该脚本扫描debug_history.md文件，收集所有标记为🤔️的待验证项，
并更新文档开头的"待验证清单"部分。

使用方法:
    python scripts/track_pending.py  # 扫描并更新待验证清单
    python scripts/track_pending.py --auto-update  # 自动更新已完成但未修改标记的项
"""

import os
import re
import sys
import argparse
from datetime import datetime

# 配置
DEBUG_HISTORY_FILE = "docs/debug_history.md"
PENDING_EMOJI = "🤔️"
SUCCESS_EMOJI = "✅"
FAILURE_EMOJI = "❌"

def ensure_file_exists(file_path):
    """确保文件存在，如果不存在则创建包含基本结构的文件"""
    if not os.path.exists(file_path):
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# 调试历史记录\n\n")
            f.write("> 本文档记录项目开发中的调试过程和经验，包括问题假设、尝试的解决方案及结果，以便后续参考和学习。\n\n")
            f.write("## 待验证清单\n\n")
            f.write("暂无待验证项\n\n")
            f.write("## 目录结构\n\n")
        print(f"已创建新的调试历史文件: {file_path}")
    return True

def read_file_content(file_path):
    """读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def write_file_content(file_path, content):
    """写入文件内容"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"写入文件失败: {e}")
        return False

def find_pending_items(content):
    """查找所有待验证项"""
    # 查找所有包含🤔️的结果行
    result_pattern = re.compile(r'[-*]\s+\*\*结果\*\*:\s*' + PENDING_EMOJI + r'\s*(.*?)(?:\n|$)', re.MULTILINE)
    results = result_pattern.findall(content)
    
    # 查找所有带有AUTO-UPDATE注释的行
    auto_update_pattern = re.compile(
        r'[-*]\s+\*\*结果\*\*:\s*' + PENDING_EMOJI + r'\s*(.*?)\s*#AUTO-UPDATE:\s*([' + SUCCESS_EMOJI + FAILURE_EMOJI + r'].*?)(?:\n|$)', 
        re.MULTILINE
    )
    auto_updates = auto_update_pattern.findall(content)
    
    # 找到包含这些行的上下文（章节标题等）
    pending_items = []
    
    # 章节标题模式
    heading_pattern = re.compile(r'^(#{1,6})\s+(.*?)$', re.MULTILINE)
    headings = [(m.start(), m.group(1), m.group(2)) for m in heading_pattern.finditer(content)]
    
    # 找到每个待验证项所在的章节
    for match in result_pattern.finditer(content):
        result_pos = match.start()
        result_text = match.group(1).strip()
        
        # 查找这个结果上方最近的章节标题
        current_heading = "未分类"
        current_level = 0
        section_path = []
        
        for pos, hashes, heading in headings:
            if pos > result_pos:
                break
            
            level = len(hashes)
            
            # 处理章节层级
            while current_level >= level:
                if section_path:
                    section_path.pop()
                current_level -= 1
            
            section_path.append(heading)
            current_level = level
            current_heading = heading
        
        # 检查是否有AUTO-UPDATE标记
        auto_update_value = None
        for text, update in auto_updates:
            if text.strip() == result_text.strip():
                auto_update_value = update
                break
        
        # 查找假设编号
        context_lines = content[max(0, result_pos-500):result_pos].split('\n')
        hypothesis_number = "未知"
        for line in reversed(context_lines):
            hyp_match = re.search(r'^\s*\d+\.\s+\*\*假设.*?(\d+)', line)
            if hyp_match:
                hypothesis_number = hyp_match.group(1)
                break
        
        # 构建章节路径
        section_title = " > ".join(section_path)
        
        # 构建链接
        section_link = "#" + "-".join(section_path[-1].lower().replace('(', '').replace(')', '').replace('.', '').split())
        
        pending_items.append({
            'section': section_title,
            'hypothesis': hypothesis_number,
            'text': result_text,
            'link': section_link,
            'auto_update': auto_update_value,
            'position': result_pos
        })
    
    return pending_items

def update_pending_list(content, pending_items):
    """更新文档中的待验证清单"""
    # 查找待验证清单部分
    pending_list_pattern = re.compile(r'^## 待验证清单.*?(?=^#{1,2}[^#]|\Z)', re.MULTILINE | re.DOTALL)
    
    if pending_items:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 生成新的待验证清单
        new_pending_list = "## 待验证清单\n\n"
        for i, item in enumerate(pending_items):
            # 只包含没有自动更新标记的项
            if not item['auto_update']:
                new_pending_list += f"{i+1}. [{today}] 待验证：假设{item['hypothesis']} - {item['text']} - [链接到{item['section']}]({item['link']})\n"
        
        if new_pending_list == "## 待验证清单\n\n":
            new_pending_list += "暂无待验证项\n\n"
        else:
            new_pending_list += "\n"
    else:
        new_pending_list = "## 待验证清单\n\n暂无待验证项\n\n"
    
    # 替换或添加待验证清单
    if pending_list_pattern.search(content):
        updated_content = pending_list_pattern.sub(new_pending_list, content)
    else:
        # 如果没有找到待验证清单部分，在文档开头添加
        header_pattern = re.compile(r'^# 调试历史记录.*?\n\n', re.MULTILINE | re.DOTALL)
        if header_pattern.search(content):
            updated_content = header_pattern.sub(f"# 调试历史记录\n\n{new_pending_list}", content)
        else:
            updated_content = f"# 调试历史记录\n\n{new_pending_list}{content}"
    
    return updated_content

def auto_update_pending_items(content, pending_items):
    """自动更新标记了AUTO-UPDATE的待验证项"""
    updated_content = content
    
    for item in pending_items:
        if item['auto_update']:
            # 构建查找模式
            pattern_str = r'([-*]\s+\*\*结果\*\*:\s*)' + PENDING_EMOJI + r'(\s*' + re.escape(item['text']) + r'\s*#AUTO-UPDATE:\s*[' + SUCCESS_EMOJI + FAILURE_EMOJI + r'].*?)(?:\n|$)'
            pattern = re.compile(pattern_str, re.MULTILINE)
            
            # 提取更新标记中的emoji
            update_emoji = re.search(r'([' + SUCCESS_EMOJI + FAILURE_EMOJI + r'])', item['auto_update']).group(1)
            
            # 替换为自动更新的结果
            replacement = r'\1' + update_emoji + r'\2'
            updated_content = pattern.sub(replacement, updated_content)
    
    return updated_content

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='待验证项追踪工具')
    parser.add_argument('--auto-update', action='store_true', help='自动更新已标记的待验证项')
    args = parser.parse_args()
    
    # 确保文件存在
    if not ensure_file_exists(DEBUG_HISTORY_FILE):
        return
    
    # 读取文件内容
    content = read_file_content(DEBUG_HISTORY_FILE)
    if content is None:
        return
    
    # 查找待验证项
    pending_items = find_pending_items(content)
    
    # 更新待验证清单
    updated_content = update_pending_list(content, pending_items)
    
    # 如果指定了自动更新，则处理带有AUTO-UPDATE标记的项
    if args.auto_update:
        updated_content = auto_update_pending_items(updated_content, pending_items)
    
    # 写入更新后的内容
    if write_file_content(DEBUG_HISTORY_FILE, updated_content):
        # 计算统计信息
        total_pending = len([item for item in pending_items if not item['auto_update']])
        auto_updated = len([item for item in pending_items if item['auto_update']])
        
        print(f"待验证追踪完成:")
        print(f"- 找到 {len(pending_items)} 个待验证项")
        print(f"- 更新了待验证清单，当前有 {total_pending} 个待验证项")
        
        if args.auto_update and auto_updated > 0:
            print(f"- 自动更新了 {auto_updated} 个已标记的待验证项")

if __name__ == "__main__":
    main() 