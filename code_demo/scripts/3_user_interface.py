#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户交互模块
-----------
提供命令行交互界面，允许用户:
1. 查看和编辑关键词维度结构
2. 输入广告宣传语
3. 选择片尾风格模板
"""

import os
import sys
import json
import logging
import time
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("user_interface")

# 导入工具模块
from utils import config, io_handlers

class UserInterface:
    """
    用户交互界面类
    """
    def __init__(self, batch_mode=False):
        """
        初始化用户交互界面
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 获取路径配置
        self.input_dir = config.get_path('root_input_dir')
        self.analysis_dir = os.path.join(config.get_path('root_output_dir'), 'Analysis')
        
        # 确保目录存在
        io_handlers.ensure_directory(self.analysis_dir)
        
        # 文件路径
        self.initial_dimensions_file = os.path.join(self.analysis_dir, 'initial_key_dimensions.json')
        self.modified_dimensions_file = os.path.join(self.analysis_dir, 'modified_key_dimensions.json')
        self.slogan_file = os.path.join(self.input_dir, 'slogan.txt')
        
        # 默认广告语
        self.default_slogan = "发现生活的美好，做最好的自己。"
        
        # ANSI颜色代码
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bg_red': '\033[41m',
            'bg_green': '\033[42m',
            'bg_yellow': '\033[43m',
            'bg_blue': '\033[44m'
        }

    def load_dimensions(self):
        """
        加载关键词维度结构
        
        返回:
            维度结构字典
        """
        # 检查维度文件是否存在
        if not os.path.exists(self.initial_dimensions_file):
            logger.warning(f"初始维度文件不存在: {self.initial_dimensions_file}")
            
            # 创建默认维度结构
            # 导入时必须使用标准模块名，而不能以数字开头
            import importlib
            dimension_analyzer_module = importlib.import_module("scripts.2_dimension_analyzer")
            DimensionAnalyzer = dimension_analyzer_module.DimensionAnalyzer
            analyzer = DimensionAnalyzer(batch_mode=True)
            dimensions = analyzer.create_example_dimensions()
            
            # 保存默认维度结构
            with open(self.initial_dimensions_file, 'w', encoding='utf-8') as f:
                json.dump(dimensions, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已创建默认维度结构: {self.initial_dimensions_file}")
        
        try:
            # 加载维度文件
            with open(self.initial_dimensions_file, 'r', encoding='utf-8') as f:
                dimensions = json.load(f)
            
            logger.info(f"已加载维度结构: {self.initial_dimensions_file}")
            return dimensions
        
        except Exception as e:
            logger.error(f"加载维度结构失败: {e}")
            return {}

    def load_slogan(self):
        """
        加载广告宣传语
        
        返回:
            广告宣传语文本
        """
        # 检查广告语文件是否存在
        if not os.path.exists(self.slogan_file):
            try:
                # 创建默认广告语文件
                io_handlers.ensure_directory(os.path.dirname(self.slogan_file))
                with open(self.slogan_file, 'w', encoding='utf-8') as f:
                    f.write(self.default_slogan)
                
                logger.info(f"已创建默认广告语文件: {self.slogan_file}")
                return self.default_slogan
            
            except Exception as e:
                logger.error(f"创建默认广告语文件失败: {e}")
                return self.default_slogan
        
        try:
            # 加载广告语文件
            with open(self.slogan_file, 'r', encoding='utf-8') as f:
                slogan = f.read().strip()
            
            logger.info(f"已加载广告语: {slogan}")
            return slogan
        
        except Exception as e:
            logger.error(f"加载广告语失败: {e}")
            return self.default_slogan

    def save_dimensions(self, dimensions):
        """
        保存修改后的维度结构
        
        参数:
            dimensions: 维度结构字典
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 确保目录存在
            io_handlers.ensure_directory(os.path.dirname(self.modified_dimensions_file))
            
            # 保存修改后的维度结构
            with open(self.modified_dimensions_file, 'w', encoding='utf-8') as f:
                json.dump(dimensions, f, ensure_ascii=False, indent=2)
            
            logger.info(f"维度结构已保存: {self.modified_dimensions_file}")
            return True
        
        except Exception as e:
            logger.error(f"保存维度结构失败: {e}")
            return False

    def save_slogan(self, slogan):
        """
        保存广告宣传语
        
        参数:
            slogan: 广告宣传语文本
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 确保目录存在
            io_handlers.ensure_directory(os.path.dirname(self.slogan_file))
            
            # 保存广告语
            with open(self.slogan_file, 'w', encoding='utf-8') as f:
                f.write(slogan)
            
            logger.info(f"广告语已保存: {self.slogan_file}")
            return True
        
        except Exception as e:
            logger.error(f"保存广告语失败: {e}")
            return False

    def print_welcome(self):
        """
        打印欢迎信息
        """
        c = self.colors
        print("\n" + "=" * 80)
        print(f"{c['bold']}{c['blue']}AI视频分析与合成系统 - 用户配置界面{c['reset']}")
        print("=" * 80)
        print(f"{c['cyan']}在这个界面中，您可以:{c['reset']}")
        print(f"  {c['bold']}1. 查看和编辑视频主题的关键词维度结构{c['reset']}")
        print(f"  {c['bold']}2. 输入广告宣传语{c['reset']}")
        print(f"  {c['bold']}3. 选择片尾风格模板{c['reset']}")
        print("-" * 80)

    def print_dimensions(self, dimensions, max_depth=3, indent=0):
        """
        打印维度结构
        
        参数:
            dimensions: 维度结构字典
            max_depth: 最大打印深度
            indent: 缩进级别
        """
        c = self.colors
        if max_depth <= 0:
            return
        
        # 按照ID排序维度
        sorted_dimensions = sorted(dimensions.items())
        
        for dim_id, dim_info in sorted_dimensions:
            # 确定维度级别(用于颜色)
            level = 3 - max_depth
            
            # 选择颜色
            if level == 0:
                color = f"{c['bold']}{c['magenta']}"
            elif level == 1:
                color = f"{c['bold']}{c['blue']}"
            else:
                color = f"{c['bold']}{c['cyan']}"
            
            # 打印维度信息
            print(f"{' ' * indent}{color}{dim_id}: {dim_info['name']} ({dim_info['weight']}){c['reset']}")
            
            # 打印关键词
            keywords = dim_info.get('keywords', [])
            if keywords:
                print(f"{' ' * (indent+2)}{c['green']}关键词: {', '.join(keywords)}{c['reset']}")
            
            # 递归打印子维度
            sub_dimensions = dim_info.get('sub_dimensions', {})
            if sub_dimensions and max_depth > 1:
                self.print_dimensions(sub_dimensions, max_depth-1, indent+4)

    def edit_dimension(self, dimensions, dim_path):
        """
        编辑特定维度
        
        参数:
            dimensions: 维度结构字典
            dim_path: 维度路径列表，如 ['dimension_1_1', 'subtopic_1']
        
        返回:
            修改后的维度结构
        """
        c = self.colors
        if not dim_path:
            return dimensions
        
        # 查找目标维度
        target = dimensions
        parent = None
        for i, dim_id in enumerate(dim_path):
            if i == len(dim_path) - 1:
                parent = target
            
            if dim_id in target:
                target = target[dim_id]
            else:
                print(f"{c['red']}错误: 找不到维度 {dim_id}{c['reset']}")
                return dimensions
        
        # 显示当前维度信息
        print(f"\n{c['bold']}当前维度信息:{c['reset']}")
        print(f"  {c['cyan']}名称: {c['reset']}{target['name']}")
        print(f"  {c['cyan']}权重: {c['reset']}{target['weight']}")
        print(f"  {c['cyan']}关键词: {c['reset']}{', '.join(target['keywords'])}")
        
        # 询问用户要编辑的属性
        print(f"\n{c['bold']}请选择要编辑的属性:{c['reset']}")
        print(f"  {c['bold']}1. 名称{c['reset']}")
        print(f"  {c['bold']}2. 权重{c['reset']}")
        print(f"  {c['bold']}3. 关键词{c['reset']}")
        print(f"  {c['bold']}0. 返回{c['reset']}")
        
        choice = input(f"{c['yellow']}请输入选项(0-3): {c['reset']}")
        
        if choice == '1':
            # 编辑名称
            new_name = input(f"{c['yellow']}请输入新名称: {c['reset']}")
            if new_name:
                target['name'] = new_name
                print(f"{c['green']}名称已更新为: {new_name}{c['reset']}")
        
        elif choice == '2':
            # 编辑权重
            while True:
                try:
                    new_weight = float(input(f"{c['yellow']}请输入新权重(0.1-1.0): {c['reset']}"))
                    if 0.1 <= new_weight <= 1.0:
                        target['weight'] = new_weight
                        print(f"{c['green']}权重已更新为: {new_weight}{c['reset']}")
                        break
                    else:
                        print(f"{c['red']}权重必须在0.1和1.0之间{c['reset']}")
                except ValueError:
                    print(f"{c['red']}请输入有效的数字{c['reset']}")
        
        elif choice == '3':
            # 编辑关键词
            current_keywords = ', '.join(target['keywords'])
            print(f"{c['cyan']}当前关键词: {current_keywords}{c['reset']}")
            new_keywords = input(f"{c['yellow']}请输入新关键词(用逗号分隔): {c['reset']}")
            
            if new_keywords:
                # 分割并清理关键词
                keyword_list = [k.strip() for k in new_keywords.split(',') if k.strip()]
                
                if keyword_list:
                    target['keywords'] = keyword_list
                    print(f"{c['green']}关键词已更新{c['reset']}")
                else:
                    print(f"{c['red']}未提供有效关键词，保持不变{c['reset']}")
        
        return dimensions

    def edit_dimensions_menu(self, dimensions):
        """
        维度编辑菜单
        
        参数:
            dimensions: 维度结构字典
        
        返回:
            修改后的维度结构
        """
        c = self.colors
        edited_dimensions = dimensions.copy()
        
        while True:
            print("\n" + "=" * 80)
            print(f"{c['bold']}{c['blue']}维度编辑菜单{c['reset']}")
            print("=" * 80)
            
            # 显示当前维度结构
            print(f"{c['bold']}当前维度结构:{c['reset']}")
            self.print_dimensions(edited_dimensions)
            
            print("\n" + "-" * 80)
            print(f"{c['bold']}请选择操作:{c['reset']}")
            print(f"  {c['bold']}1. 编辑一级维度{c['reset']}")
            print(f"  {c['bold']}2. 编辑二级维度{c['reset']}")
            print(f"  {c['bold']}3. 编辑三级维度{c['reset']}")
            print(f"  {c['bold']}0. 保存并返回{c['reset']}")
            
            choice = input(f"{c['yellow']}请输入选项(0-3): {c['reset']}")
            
            if choice == '0':
                break
            
            elif choice == '1':
                # 编辑一级维度
                print(f"\n{c['bold']}可用的一级维度:{c['reset']}")
                for dim_id in edited_dimensions.keys():
                    print(f"  {c['magenta']}{dim_id}: {edited_dimensions[dim_id]['name']}{c['reset']}")
                
                dim_id = input(f"{c['yellow']}请输入要编辑的维度ID(如dimension_1_1): {c['reset']}")
                if dim_id in edited_dimensions:
                    edited_dimensions = self.edit_dimension(edited_dimensions, [dim_id])
                else:
                    print(f"{c['red']}维度ID不存在{c['reset']}")
            
            elif choice == '2':
                # 编辑二级维度
                print(f"\n{c['bold']}请先选择一级维度:{c['reset']}")
                for dim_id in edited_dimensions.keys():
                    print(f"  {c['magenta']}{dim_id}: {edited_dimensions[dim_id]['name']}{c['reset']}")
                
                dim1_id = input(f"{c['yellow']}请输入一级维度ID: {c['reset']}")
                if dim1_id in edited_dimensions:
                    sub_dimensions = edited_dimensions[dim1_id].get('sub_dimensions', {})
                    
                    print(f"\n{c['bold']}可用的二级维度:{c['reset']}")
                    for dim_id in sub_dimensions.keys():
                        print(f"  {c['blue']}{dim_id}: {sub_dimensions[dim_id]['name']}{c['reset']}")
                    
                    dim2_id = input(f"{c['yellow']}请输入要编辑的二级维度ID(如subtopic_1): {c['reset']}")
                    if dim2_id in sub_dimensions:
                        edited_dimensions = self.edit_dimension(edited_dimensions, [dim1_id, dim2_id])
                    else:
                        print(f"{c['red']}维度ID不存在{c['reset']}")
                else:
                    print(f"{c['red']}一级维度ID不存在{c['reset']}")
            
            elif choice == '3':
                # 编辑三级维度
                print(f"\n{c['bold']}请先选择一级维度:{c['reset']}")
                for dim_id in edited_dimensions.keys():
                    print(f"  {c['magenta']}{dim_id}: {edited_dimensions[dim_id]['name']}{c['reset']}")
                
                dim1_id = input(f"{c['yellow']}请输入一级维度ID: {c['reset']}")
                if dim1_id in edited_dimensions:
                    sub_dimensions = edited_dimensions[dim1_id].get('sub_dimensions', {})
                    
                    print(f"\n{c['bold']}请选择二级维度:{c['reset']}")
                    for dim_id in sub_dimensions.keys():
                        print(f"  {c['blue']}{dim_id}: {sub_dimensions[dim_id]['name']}{c['reset']}")
                    
                    dim2_id = input(f"{c['yellow']}请输入二级维度ID: {c['reset']}")
                    if dim2_id in sub_dimensions:
                        sub_sub_dimensions = sub_dimensions[dim2_id].get('sub_dimensions', {})
                        
                        print(f"\n{c['bold']}可用的三级维度:{c['reset']}")
                        for dim_id in sub_sub_dimensions.keys():
                            print(f"  {c['cyan']}{dim_id}: {sub_sub_dimensions[dim_id]['name']}{c['reset']}")
                        
                        dim3_id = input(f"{c['yellow']}请输入要编辑的三级维度ID(如keyword_1): {c['reset']}")
                        if dim3_id in sub_sub_dimensions:
                            edited_dimensions = self.edit_dimension(edited_dimensions, [dim1_id, dim2_id, dim3_id])
                        else:
                            print(f"{c['red']}维度ID不存在{c['reset']}")
                    else:
                        print(f"{c['red']}二级维度ID不存在{c['reset']}")
                else:
                    print(f"{c['red']}一级维度ID不存在{c['reset']}")
        
        return edited_dimensions

    def edit_slogan_menu(self, slogan):
        """
        广告语编辑菜单
        
        参数:
            slogan: 当前广告语
        
        返回:
            修改后的广告语
        """
        c = self.colors
        
        print("\n" + "=" * 80)
        print(f"{c['bold']}{c['blue']}广告宣传语编辑{c['reset']}")
        print("=" * 80)
        
        print(f"{c['cyan']}当前广告宣传语: {c['reset']}{c['bold']}{slogan}{c['reset']}")
        print(f"\n{c['yellow']}请输入新的广告宣传语(留空则保持不变):{c['reset']}")
        
        new_slogan = input()
        
        if new_slogan:
            print(f"{c['green']}广告宣传语已更新为: {new_slogan}{c['reset']}")
            return new_slogan
        else:
            print(f"{c['yellow']}广告宣传语保持不变{c['reset']}")
            return slogan

    def select_end_style_menu(self):
        """
        片尾风格选择菜单
        
        返回:
            选择的风格名称
        """
        c = self.colors
        
        print("\n" + "=" * 80)
        print(f"{c['bold']}{c['blue']}片尾风格选择{c['reset']}")
        print("=" * 80)
        
        print(f"{c['cyan']}可用的片尾风格模板:{c['reset']}")
        styles = [
            ("简约", "简洁的设计，突出广告语"),
            ("动感", "动态效果，更具吸引力"),
            ("商务", "专业商务风格，适合企业宣传"),
            ("温馨", "温暖舒适的风格，强调情感连接"),
            ("现代", "现代设计风格，简约而不简单")
        ]
        
        for i, (name, desc) in enumerate(styles, 1):
            print(f"  {c['bold']}{i}. {name}{c['reset']} - {desc}")
        
        print(f"\n{c['yellow']}请选择片尾风格(1-{len(styles)}):{c['reset']}")
        
        while True:
            try:
                choice = int(input())
                if 1 <= choice <= len(styles):
                    selected_style = styles[choice-1][0]
                    print(f"{c['green']}已选择片尾风格: {selected_style}{c['reset']}")
                    
                    # 保存选择到配置
                    config.set_param('end_style', selected_style)
                    
                    return selected_style
                else:
                    print(f"{c['red']}请输入1-{len(styles)}之间的数字{c['reset']}")
            except ValueError:
                print(f"{c['red']}请输入有效的数字{c['reset']}")

    def auto_mode_process(self):
        """
        批处理模式下的自动处理
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 加载维度结构
            dimensions = self.load_dimensions()
            
            # 加载广告语
            slogan = self.load_slogan()
            
            # 保存修改后的维度结构(直接使用初始结构)
            self.save_dimensions(dimensions)
            
            # 使用默认片尾风格
            config.set_param('end_style', '简约')
            
            logger.info("批处理模式下完成用户配置")
            return True
        
        except Exception as e:
            logger.error(f"批处理模式处理失败: {e}")
            return False

    def interactive_process(self):
        """
        交互模式下的处理
        
        返回:
            成功返回True，否则返回False
        """
        c = self.colors
        
        try:
            # 打印欢迎信息
            self.print_welcome()
            
            # 加载维度结构
            dimensions = self.load_dimensions()
            
            # 加载广告语
            slogan = self.load_slogan()
            
            while True:
                print("\n" + "=" * 80)
                print(f"{c['bold']}{c['blue']}主菜单{c['reset']}")
                print("=" * 80)
                
                print(f"{c['bold']}请选择要执行的操作:{c['reset']}")
                print(f"  {c['bold']}1. 查看关键词维度结构{c['reset']}")
                print(f"  {c['bold']}2. 编辑关键词维度结构{c['reset']}")
                print(f"  {c['bold']}3. 编辑广告宣传语{c['reset']}")
                print(f"  {c['bold']}4. 选择片尾风格模板{c['reset']}")
                print(f"  {c['bold']}0. 保存并退出{c['reset']}")
                
                choice = input(f"{c['yellow']}请输入选项(0-4): {c['reset']}")
                
                if choice == '0':
                    # 保存并退出
                    self.save_dimensions(dimensions)
                    self.save_slogan(slogan)
                    print(f"{c['green']}设置已保存，正在退出...{c['reset']}")
                    return True
                
                elif choice == '1':
                    # 查看维度结构
                    print("\n" + "=" * 80)
                    print(f"{c['bold']}{c['blue']}关键词维度结构{c['reset']}")
                    print("=" * 80)
                    self.print_dimensions(dimensions)
                    
                    input(f"\n{c['yellow']}按回车键继续...{c['reset']}")
                
                elif choice == '2':
                    # 编辑维度结构
                    dimensions = self.edit_dimensions_menu(dimensions)
                
                elif choice == '3':
                    # 编辑广告语
                    slogan = self.edit_slogan_menu(slogan)
                
                elif choice == '4':
                    # 选择片尾风格
                    self.select_end_style_menu()
            
            return True
        
        except KeyboardInterrupt:
            print(f"\n{c['yellow']}用户中断，正在保存并退出...{c['reset']}")
            self.save_dimensions(dimensions)
            self.save_slogan(slogan)
            return True
        
        except Exception as e:
            logger.error(f"交互处理失败: {e}")
            return False

    def process(self):
        """
        主处理函数
        
        返回:
            成功返回True，否则返回False
        """
        if self.batch_mode:
            return self.auto_mode_process()
        else:
            return self.interactive_process()


if __name__ == "__main__":
    # 初始化配置
    config.init()
    
    # 创建用户界面并运行
    ui = UserInterface(batch_mode='--batch' in sys.argv)
    
    if ui.process():
        logger.info("用户配置完成")
        sys.exit(0)
    else:
        logger.error("用户配置失败")
        sys.exit(1)
