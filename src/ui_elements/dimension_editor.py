import streamlit as st
import json
import logging
import time
import os
from typing import Dict, List, Any

# 配置日志
logger = logging.getLogger(__name__)

def render_dimension_editor(initial_dimensions: Dict = None):
    """
    维度编辑器，使用纯函数方式实现
    
    参数:
        initial_dimensions: 初始维度结构，格式为 {"title": "标题", "level1": ["一级维度1", "一级维度2"], "level2": {"一级维度1": ["二级维度1", "二级维度2"]}}
    """
    # 初始化模板字典 - 确保templates首先被初始化
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
        load_default_templates()
    
    # 初始化会话状态
    if 'dimensions' not in st.session_state:
        if initial_dimensions and isinstance(initial_dimensions, dict):
            st.session_state.dimensions = initial_dimensions
            # 确保dimensions包含必要的结构
            if 'title' not in st.session_state.dimensions:
                st.session_state.dimensions['title'] = "品牌认知"
            if 'level1' not in st.session_state.dimensions:
                st.session_state.dimensions['level1'] = []
            if 'level2' not in st.session_state.dimensions:
                st.session_state.dimensions['level2'] = {}
        else:
            # 默认维度结构
            st.session_state.dimensions = {
                'title': "品牌认知",
                'level1': [],
                'level2': {}
            }
    
    # 初始化权重
    if 'weights' not in st.session_state:
        st.session_state.weights = initialize_weights(st.session_state.dimensions)
    
    # 初始化删除维度的存储（如果需要）
    if 'deleted_dimensions' not in st.session_state:
        st.session_state.deleted_dimensions = {'level1': [], 'level2': {}}
    
    # 渲染维度编辑器界面
    st.subheader("维度结构管理")
    
    # 显示当前维度结构
    if st.session_state.dimensions.get('level1'):
        # 获取未删除的一级维度列表
        active_level1_dims = [dim1 for dim1 in st.session_state.dimensions['level1'] 
                              if dim1 not in st.session_state.deleted_dimensions['level1']]
        
        # 遍历每个一级维度
        for i, dim1 in enumerate(active_level1_dims):
            # 创建一个可折叠区域显示每个一级维度
            with st.expander(f"**{dim1}**", expanded=True):
                # 删除当前一级维度的按钮
                delete_key = f"delete_dim1_{i}"
                if st.button(f"删除维度 '{dim1}'", key=delete_key):
                    # 在点击处理中删除维度
                    delete_level1_dimension(dim1)
                
                # 显示此一级维度下的二级维度
                if dim1 in st.session_state.dimensions.get('level2', {}) and st.session_state.dimensions['level2'][dim1]:
                    # 获取未删除的二级维度列表
                    active_level2_dims = []
                    if dim1 in st.session_state.dimensions['level2']:
                        # 过滤掉已删除的二级维度
                        deleted_dim2s = st.session_state.deleted_dimensions.get('level2', {}).get(dim1, [])
                        active_level2_dims = [dim2 for dim2 in st.session_state.dimensions['level2'][dim1] 
                                             if dim2 not in deleted_dim2s]
                    
                    if active_level2_dims:
                        # 创建表头
                        cols = st.columns([1, 3, 1])
                        cols[0].markdown("**序号**")
                        cols[1].markdown("**二级维度**")
                        cols[2].markdown("**操作**")
                        
                        st.markdown("---")  # 分隔线
                        
                        # 显示每个二级维度并添加删除按钮
                        for j, dim2 in enumerate(active_level2_dims):
                            # 使用行布局展示二级维度和删除按钮
                            row_cols = st.columns([1, 3, 1])
                            row_cols[0].text(f"{j+1}")
                            row_cols[1].text(dim2)
                            
                            # 删除二级维度的按钮
                            delete_key = f"delete_dim2_{i}_{j}"
                            if row_cols[2].button("删除", key=delete_key):
                                # 在点击处理中删除二级维度
                                delete_level2_dimension(dim1, dim2)
                else:
                    st.info(f"在 '{dim1}' 下还没有定义任何二级维度")
                
                # 添加二级维度的按钮
                st.markdown("---")
                st.write(f"添加二级维度到 '{dim1}'")
                add_cols = st.columns([4, 1])
                
                # 输入框和按钮
                input_key = f"add_dim2_input_{i}"
                button_key = f"add_dim2_button_{i}"
                
                # 如果之前没有设置输入状态，初始化为空字符串
                if input_key not in st.session_state:
                    st.session_state[input_key] = ""
                
                new_dim2 = add_cols[0].text_input("二级维度名称", key=input_key, 
                                                 placeholder=f"输入要添加到'{dim1}'的二级维度名称",
                                                 label_visibility="collapsed")
                if add_cols[1].button("添加", key=button_key):
                    add_level2_dimension(dim1, new_dim2, input_key)
    else:
        st.info("还没有定义任何维度。请使用模板或添加新维度。")
    
    # 添加新的一级维度
    st.subheader("添加新的一级维度")
    
    # 使用常规输入和按钮
    add_dim1_cols = st.columns([3, 1])
    
    # 设置唯一键
    input_key = "add_dim1_input"
    button_key = "add_dim1_button"
    
    # 如果之前没有设置输入状态，初始化为空字符串
    if input_key not in st.session_state:
        st.session_state[input_key] = ""
    
    # 输入框和按钮
    new_dim1 = add_dim1_cols[0].text_input("一级维度名称", key=input_key, 
                                         placeholder="输入一级维度名称", 
                                         label_visibility="collapsed")
    if add_dim1_cols[1].button("添加", key=button_key, type="primary"):
        add_level1_dimension(new_dim1, input_key)
    
    # 返回当前维度结构和权重
    return {
        'dimensions': st.session_state.dimensions,
        'weights': st.session_state.weights
    }

def delete_level1_dimension(dim1):
    """删除一级维度"""
    logger.info(f"尝试删除一级维度: '{dim1}'")
    
    # 初始化已删除的维度列表（如果不存在）
    if 'deleted_dimensions' not in st.session_state:
        st.session_state.deleted_dimensions = {'level1': [], 'level2': {}}
    
    # 将维度标记为已删除
    if dim1 not in st.session_state.deleted_dimensions['level1']:
        st.session_state.deleted_dimensions['level1'].append(dim1)
    
    # 从一级维度列表中删除
    if dim1 in st.session_state.dimensions['level1']:
        st.session_state.dimensions['level1'].remove(dim1)
    
    # 移除相关的权重设置和二级维度
    if dim1 in st.session_state.weights['level1']:
        del st.session_state.weights['level1'][dim1]
    if dim1 in st.session_state.weights['level2']:
        del st.session_state.weights['level2'][dim1]
    if dim1 in st.session_state.dimensions['level2']:
        del st.session_state.dimensions['level2'][dim1]
    
    # 标记维度已修改
    st.session_state.has_dimension_changes = True
    
    # 持久化维度结构
    persist_dimensions()
    
    # 显示成功消息
    st.success(f"已删除维度: {dim1}")
    
    # 设置标志，表示需要在下一次渲染时重新加载页面
    st.session_state.need_dimension_refresh = True
    
    # 强制重新运行应用以刷新界面
    st.rerun()

def delete_level2_dimension(dim1, dim2):
    """删除二级维度"""
    logger.info(f"尝试删除二级维度 '{dim2}' 从 '{dim1}'")
    
    # 初始化已删除的维度列表（如果不存在）
    if 'deleted_dimensions' not in st.session_state:
        st.session_state.deleted_dimensions = {'level1': [], 'level2': {}}
    
    # 初始化此一级维度下的已删除二级维度列表
    if dim1 not in st.session_state.deleted_dimensions['level2']:
        st.session_state.deleted_dimensions['level2'][dim1] = []
    
    # 将二级维度标记为已删除
    if dim2 not in st.session_state.deleted_dimensions['level2'][dim1]:
        st.session_state.deleted_dimensions['level2'][dim1].append(dim2)
    
    # 从二级维度列表中删除
    if dim1 in st.session_state.dimensions['level2'] and dim2 in st.session_state.dimensions['level2'][dim1]:
        st.session_state.dimensions['level2'][dim1].remove(dim2)
    
    # 移除相关的权重设置
    if dim1 in st.session_state.weights['level2'] and dim2 in st.session_state.weights['level2'][dim1]:
        del st.session_state.weights['level2'][dim1][dim2]
    
    # 标记维度已修改
    st.session_state.has_dimension_changes = True
    
    # 持久化维度结构
    persist_dimensions()
    
    # 显示成功消息
    st.success(f"已从 '{dim1}' 删除维度: {dim2}")
    
    # 强制重新运行应用以刷新界面
    st.rerun()

def add_level1_dimension(new_dim1, input_key):
    """添加一级维度"""
    if not new_dim1:
        st.warning("请输入一级维度名称")
        return
    
    logger.info(f"尝试添加一级维度: '{new_dim1}'")
    
    # 检查是否已存在同名维度
    existing_dims = st.session_state.dimensions['level1']
    
    if new_dim1 in existing_dims:
        st.warning(f"维度 '{new_dim1}' 已存在")
        return
    
    # 添加到一级维度列表
    st.session_state.dimensions['level1'].append(new_dim1)
    
    # 初始化此维度的二级维度列表
    st.session_state.dimensions['level2'][new_dim1] = []
    
    # 为新维度初始化权重
    st.session_state.weights['level1'][new_dim1] = 0.8
    st.session_state.weights['level2'][new_dim1] = {}
    
    # 标记维度已修改
    st.session_state.has_dimension_changes = True
    
    # 持久化维度结构
    persist_dimensions()
    
    # 显示成功消息
    st.success(f"已添加一级维度: {new_dim1}")
    
    # 强制重新运行应用以刷新界面
    st.rerun()

def add_level2_dimension(dim1, new_dim2, input_key):
    """添加二级维度"""
    if not new_dim2:
        st.warning("请输入二级维度名称")
        return
    
    logger.info(f"尝试添加二级维度 '{new_dim2}' 到 '{dim1}'")
    
    # 检查是否已存在同名二级维度
    existing_dim2s = st.session_state.dimensions['level2'].get(dim1, [])
    
    if new_dim2 in existing_dim2s:
        st.warning(f"维度 '{new_dim2}' 已存在于 '{dim1}' 下")
        return
    
    # 添加到二级维度列表
    if dim1 not in st.session_state.dimensions['level2']:
        st.session_state.dimensions['level2'][dim1] = []
    st.session_state.dimensions['level2'][dim1].append(new_dim2)
    
    # 为新维度初始化权重
    if dim1 not in st.session_state.weights['level2']:
        st.session_state.weights['level2'][dim1] = {}
    st.session_state.weights['level2'][dim1][new_dim2] = 0.5
    
    # 标记维度已修改
    st.session_state.has_dimension_changes = True
    
    # 持久化维度结构
    persist_dimensions()
    
    # 显示成功消息
    st.success(f"已添加二级维度 '{new_dim2}' 到 '{dim1}'")
    
    # 强制重新运行应用以刷新界面
    st.rerun()

def initialize_weights(dimensions: Dict) -> Dict:
    """初始化维度权重"""
    weights = {
        'title': 1.0,
        'level1': {},
        'level2': {}
    }
    
    # 为一级维度设置权重
    for dim1 in dimensions.get('level1', []):
        weights['level1'][dim1] = 0.8
        weights['level2'][dim1] = {}
        
        # 为二级维度设置权重
        for dim2 in dimensions.get('level2', {}).get(dim1, []):
            weights['level2'][dim1][dim2] = 0.5
    
    return weights

def load_default_templates():
    """加载默认模板"""
    # 确保templates在session_state中存在
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
        
    # 添加内置模板
    add_builtin_templates()
    
    # 加载保存的模板文件
    try:
        templates_file = os.path.join('data', 'dimensions', 'templates.json')
        if os.path.exists(templates_file):
            with open(templates_file, 'r', encoding='utf-8') as f:
                saved_templates = json.load(f)
                
                # 将加载的模板添加到session状态
                for name, data in saved_templates.items():
                    st.session_state.templates[name] = data
                    
            logger.info(f"已加载 {len(saved_templates)} 个模板")
        else:
            logger.info("模板文件不存在，使用内置模板")
    except Exception as e:
        logger.error(f"加载模板文件出错: {str(e)}")
        # 使用默认内置模板

def add_builtin_templates():
    """添加内置模板"""
    # 确保templates在session_state中存在
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
    
    # 品牌营销模板
    st.session_state.templates['产品营销'] = {
        "产品特性": {
            "性能表现": [],
            "功能特点": [],
            "外观设计": []
        },
        "用户体验": {
            "使用便捷性": [],
            "界面友好度": [],
            "交互响应": []
        },
        "价值定位": {
            "价格定位": [],
            "性价比": [],
            "差异化优势": []
        }
    }
    
    # 品牌认知模板
    st.session_state.templates['品牌认知'] = {
        "品牌形象": {
            "品牌调性": [],
            "品牌价值观": [],
            "品牌个性": []
        },
        "市场认可度": {
            "市场份额": [],
            "用户口碑": [],
            "行业评价": []
        },
        "品牌传播": {
            "传播渠道": [],
            "传播内容": [],
            "传播效果": []
        }
    }
    
    # 情感诉求模板
    st.session_state.templates['情感诉求'] = {
        "情感连接": {
            "用户情感": [],
            "情感体验": [],
            "情感价值": []
        },
        "情感需求": {
            "安全感": [],
            "归属感": [],
            "成就感": []
        },
        "情感反馈": {
            "情感回应": [],
            "情感满足": [],
            "情感认同": []
        }
    }

def persist_dimensions():
    """持久化维度结构到当前项目"""
    logger.info("持久化维度结构")
    
    try:
        # 确保项目设置中包含维度结构
        if 'settings' in st.session_state:
            st.session_state.settings['dimensions'] = st.session_state.dimensions
            st.session_state.settings['weights'] = st.session_state.weights
            st.session_state.settings['custom_dimensions'] = True
            
            # 保存到当前项目
            current_project = st.session_state.get('current_project', 'default')
            if current_project:
                # 这里应该有一个保存项目设置的函数，但本示例中我们只更新session_state
                logger.info(f"维度结构已保存到项目: {current_project}")
    except Exception as e:
        logger.error(f"持久化维度结构时出错: {str(e)}")

def apply_template(template_data: Dict):
    """应用模板到维度编辑器"""
    logger.info(f"应用模板数据: {template_data}")
    
    try:
        # 验证模板数据
        if not isinstance(template_data, dict):
            logger.error(f"无效的模板数据类型: {type(template_data)}")
            return False
        
        # 创建新的维度结构
        new_dimensions = {
            'title': st.session_state.dimensions.get('title', '品牌认知'),
            'level1': list(template_data.keys()),
            'level2': template_data
        }
        
        # 更新会话状态
        st.session_state.dimensions = new_dimensions
        
        # 重新初始化权重
        st.session_state.weights = initialize_weights(new_dimensions)
        
        # 重置已删除维度
        st.session_state.deleted_dimensions = {'level1': [], 'level2': {}}
        
        # 标记维度结构已修改
        st.session_state.has_dimension_changes = True
        
        logger.info(f"模板应用成功，新维度结构: {new_dimensions}")
        return True
    except Exception as e:
        logger.error(f"应用模板时出错: {str(e)}")
        return False

def save_template(template_path: str, template_name: str):
    """保存模板到文件和会话状态"""
    logger.info(f"保存模板: {template_name}")
    
    try:
        # 获取当前维度结构
        template_data = st.session_state.dimensions
        if not template_data:
            logger.error("无法保存模板：维度数据为空")
            return False
            
        # 保存到会话状态
        st.session_state.templates[template_name] = template_data
        
        # 写入JSON文件
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump({template_name: template_data}, f, ensure_ascii=False, indent=2)
        
        logger.info(f"模板已保存到文件: {template_path}")
        return True
    except Exception as e:
        logger.error(f"保存模板时出错: {str(e)}")
        return False

def delete_template(template_name: str):
    """删除模板"""
    logger.info(f"删除模板: {template_name}")
    
    try:
        # 从会话状态中删除
        if template_name in st.session_state.templates:
            del st.session_state.templates[template_name]
        
        # 从文件系统中删除
        template_dir = os.path.join('data', 'dimensions')
        template_file = f"{template_name.replace(' ', '_')}.json"
        template_path = os.path.join(template_dir, template_file)
        
        if os.path.exists(template_path):
            os.remove(template_path)
            logger.info(f"模板文件已删除: {template_path}")
        
        return True
    except Exception as e:
        logger.error(f"删除模板时出错: {str(e)}")
        return False

def get_template_names() -> List[str]:
    """获取所有可用的模板名称"""
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
        load_default_templates()
    
    # 返回模板名称列表
    return list(st.session_state.templates.keys()) 