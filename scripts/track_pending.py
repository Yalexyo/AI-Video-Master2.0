#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
待验证项自动追踪脚本

用于扫描debug_history.md文件，自动更新待验证清单
"""

import os
import re
import argparse
from datetime import datetime
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='追踪debug_history.md中的待验证项')
    parser.add_argument('--auto-update', action='store_true', help='自动更新已完成但未修改标记的项')
    parser.add_argument('--file', type=str, default='docs/debug_history.md', help='调试历史记录文件路径')
    
    args = parser.parse_args()
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    debug_history_file = os.path.join(project_root, args.file)
    
    if not os.path.exists(debug_history_file):
        logger.error(f"调试历史记录文件不存在: {debug_history_file}")
        return
    
    # 读取文件内容
    with open(debug_history_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 定位待验证清单位置
    checklist_section = re.search(r'## 待验证清单\n(.*?)(?=\n## |$)', content, re.DOTALL)
    if not checklist_section:
        logger.error("找不到待验证清单部分")
        return
    
    # 查找所有待验证项（带有🤔️标记的记录）
    pending_items = []
    auto_updates = []
    
    for match in re.finditer(r'### ([^\n]+?)\s*\(([^\n]+?)\)\n\n.*?(?:\n\n)?(?:.*?\n\n)*?(?:\n\n)?(?:.*?\n\n)?(?:\n\n)?.*?\*\*结果\*\*:\s*(🤔️[^\n]*?)(?:\s*#AUTO-UPDATE:([^\n]*))?', content, re.DOTALL):
        item_title = match.group(1).strip()
        item_date = match.group(2).strip()
        item_result = match.group(3).strip()
        auto_update = match.group(4).strip() if match.group(4) else None
        
        if "🤔️" in item_result:
            # 将日期转换为datetime对象，用于排序
            try:
                date_obj = datetime.strptime(item_date, "%Y-%m-%d %H:%M:%S")
                formatted_date = date_obj.strftime("%Y-%m-%d")
            except:
                formatted_date = datetime.now().strftime("%Y-%m-%d")
            
            # 生成锚点链接
            anchor = item_title.replace(' ', '-').lower()
            
            # 添加到待验证列表
            pending_items.append({
                'title': item_title,
                'date': formatted_date,
                'anchor': anchor,
                'position': match.start(),
                'full_match': match.group(0),
                'auto_update': auto_update
            })
        
            # 如果有自动更新标记，记录下来
            if auto_update and args.auto_update:
                auto_updates.append({
                    'title': item_title,
                    'position': match.start(),
                    'full_match': match.group(0),
                    'old_result': item_result,
                    'new_result': auto_update
                })
    
    # 按日期排序
    pending_items.sort(key=lambda x: x['date'])
    
    # 生成新的待验证清单
    new_checklist = "## 待验证清单\n"
    if pending_items:
        for i, item in enumerate(pending_items):
            new_checklist += f"\n{i+1}. [{item['date']}] 待验证：{item['title']} - [链接到章节](#{item['anchor']})\n"
    else:
        new_checklist += "\n目前没有待验证项\n"
    
    # 用新的待验证清单替换旧的
    old_checklist = checklist_section.group(0)
    updated_content = content.replace(old_checklist, new_checklist)
    
    # 处理自动更新项
    if auto_updates and args.auto_update:
        logger.info(f"发现 {len(auto_updates)} 个待自动更新项")
        
        # 从后向前处理，避免位置偏移
        auto_updates.sort(key=lambda x: x['position'], reverse=True)
        
        for update in auto_updates:
            old_text = update['full_match']
            new_text = old_text.replace(
                f"**结果**: {update['old_result']}",
                f"**结果**: {update['new_result']}"
            ).replace(f"#AUTO-UPDATE:{update['new_result']}", "")
            
            updated_content = updated_content.replace(old_text, new_text)
            logger.info(f"已更新: {update['title']}")
    
    # 保存更新后的文件
    with open(debug_history_file, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    logger.info(f"共找到 {len(pending_items)} 个待验证项，已更新待验证清单")
    if args.auto_update:
        logger.info(f"自动更新了 {len(auto_updates)} 个标记项")

if __name__ == '__main__':
    main() 