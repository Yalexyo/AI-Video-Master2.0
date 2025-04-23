import streamlit as st
import os
import json
import logging
import sys
import glob  # Import glob
from datetime import datetime
from src.config.settings import DIMENSIONS_DIR, INITIAL_DIMENSION_FILENAME
from src.ui_elements.dimension_editor import render_dimension_editor, save_template  # Removed apply_template, load_default_templates, get_template_names, delete_template
from src.ui_elements.simple_nav import create_sidebar_navigation

# 添加src目录到路径，以便导入UI组件
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logger = logging.getLogger(__name__)

def get_available_templates():
    """获取data/dimensions目录下所有json模板文件名"""
    template_files = glob.glob(os.path.join(DIMENSIONS_DIR, '*.json'))
    # 提取文件名（不含扩展名）作为模板名
    template_names = [os.path.splitext(os.path.basename(f))[0] for f in template_files]
    return template_names

def load_dimension_template(template_name):
    """根据模板名称加载维度模板文件"""
    file_path = os.path.join(DIMENSIONS_DIR, f"{template_name}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 解析JSON数据
                data = json.load(f)
                # 假设模板文件顶层是一个字典，键是模板的逻辑名称
                # 我们需要获取这个字典的值作为模板内容
                if isinstance(data, dict) and len(data) == 1:
                    return list(data.values())[0]
                else:
                    # 如果格式不符合预期，记录错误并返回空
                    logger.error(f"模板文件 {template_name}.json 格式不符合预期: 顶层应为包含单个键值对的字典")
                    return None
        except json.JSONDecodeError as e:
            logger.error(f"加载模板文件 {template_name}.json 时JSON解析出错: {str(e)}")
            st.error(f"无法解析模板文件 {template_name}.json，请检查文件内容是否为有效的JSON格式。")
            return None
        except Exception as e:
            logger.error(f"加载模板文件 {template_name}.json 出错: {str(e)}")
            st.error(f"加载模板文件 {template_name}.json 时发生错误。")
            return None
    else:
        logger.warning(f"模板文件 {template_name}.json 不存在")
        return None

def show():
    """显示分析维度管理页面"""
    st.set_page_config(
        page_title="AI视频大师 - 分析维度管理",
        page_icon="🎬",
        layout="wide"
    )
    
    # 使用通用导航组件
    create_sidebar_navigation("分析维度管理")
    
    # 页面主体内容
    st.title("分析维度管理")
    st.markdown("定义或加载分析维度模板")
    
    # Function to load dimensions into session state
    def load_dimensions_from_template(template_name):
        template_data = load_dimension_template(template_name)
        if template_data and isinstance(template_data, dict) and 'level1' in template_data and 'level2' in template_data:
            # Directly use the loaded structure if it matches the expected format
            st.session_state.dimensions = template_data
            st.session_state.current_template_name = template_name # Track loaded template
            logger.info(f"成功加载模板: {template_name}")
            return True
        else:
            st.error(f"加载模板 '{template_name}' 失败或模板格式不正确。请确保模板包含 'level1' 和 'level2' 键。")
            # Fallback or clear dimensions if load fails
            if 'dimensions' in st.session_state:
                del st.session_state['dimensions']
            if 'current_template_name' in st.session_state:
                del st.session_state.current_template_name
            return False

    # Initialize session state for dimensions if not present
    if 'dimensions' not in st.session_state:
        # Try loading the initial template by default
        initial_template_name = os.path.splitext(INITIAL_DIMENSION_FILENAME)[0]
        logger.info(f"页面首次加载，尝试加载初始模板: {initial_template_name}")
        if load_dimensions_from_template(initial_template_name):
             st.toast(f"已自动加载初始模板: {initial_template_name}")
        else:
            logger.warning(f"无法自动加载初始模板 {initial_template_name}，编辑器将为空。")
            # Initialize with empty structure if initial load fails
            st.session_state.dimensions = {'title': '', 'level1': [], 'level2': {}}
            st.session_state.current_template_name = None

    # 创建两栏布局 - 左侧为编辑器，右侧为模板操作
    col1, col2 = st.columns([2, 1])
    
    # 右侧模板操作区域
    with col2:
        st.subheader("模板操作")
        
        # 显示模板选择和加载区域
        available_templates = get_available_templates()
        if available_templates:
            # 确定默认选择的模板
            default_index = 0
            current_template = st.session_state.get('current_template_name')
            initial_template_name = os.path.splitext(INITIAL_DIMENSION_FILENAME)[0]

            if current_template and current_template in available_templates:
                default_index = available_templates.index(current_template)
            elif initial_template_name in available_templates:
                 default_index = available_templates.index(initial_template_name)

            # 使用选择框让用户选择模板
            selected_template_name = st.selectbox(
                "选择要加载的模板",
                available_templates,
                index=default_index,
                key="template_selector",
                help="从 data/dimensions 文件夹加载模板文件"
            )

            # 添加加载按钮
            if st.button("加载选中模板", type="primary", key="load_template_btn"):
                with st.spinner(f"正在加载模板 {selected_template_name}..."):
                    if load_dimensions_from_template(selected_template_name):
                        st.success(f"已成功加载模板: {selected_template_name}")
                        # 重新运行应用以更新编辑器
                        st.rerun()
        else:
            st.info("在 data/dimensions 目录下未找到任何模板文件 (.json)")
        
        # 保存当前结构为新模板区域
        st.markdown("---")
        st.subheader("保存当前结构为模板")
        
        # 新模板名称输入框
        new_template_name_input = st.text_input("新模板名称", placeholder="输入新模板名称 (例如: my_custom_template)", key="new_template_name_input")
        
        # 保存按钮
        if st.button("保存为模板", key="save_template_btn", type="primary"):
            if new_template_name_input:
                # 简单清理模板名称
                clean_template_name = new_template_name_input.strip().replace(" ", "_")
                if not clean_template_name:
                     st.warning("模板名称不能为空或仅包含空格。")
                elif f"{clean_template_name}.json" == INITIAL_DIMENSION_FILENAME:
                     st.warning(f"不能覆盖初始模板 '{INITIAL_DIMENSION_FILENAME}'。请使用其他名称。")
                else:
                    # 从会话状态获取当前维度数据
                    if 'dimensions' not in st.session_state:
                        st.error("当前没有可保存的维度数据")
                    else:
                        # 确保维度目录存在
                        os.makedirs(DIMENSIONS_DIR, exist_ok=True)
                        
                        # 保存模板
                        template_path = os.path.join(DIMENSIONS_DIR, f"{clean_template_name}.json")
                        if save_template(template_path, clean_template_name, st.session_state.dimensions):
                            st.success(f"模板已保存至 {template_path}")
                            # 更新当前模板名称
                            st.session_state.current_template_name = clean_template_name
                            # 强制刷新以更新模板列表
                            st.rerun()
                        else:
                            st.error(f"保存模板 '{clean_template_name}' 时出错")
            else:
                st.warning("请输入模板名称")
        
        # 删除当前模板区域
        if 'current_template_name' in st.session_state and st.session_state.current_template_name:
            st.markdown("---")
            # 检查是否为初始模板
            if st.session_state.current_template_name != os.path.splitext(INITIAL_DIMENSION_FILENAME)[0]:
                # 显示提示和删除按钮
                st.info(f"当前加载的模板: {st.session_state.current_template_name}")
                if st.button("删除当前模板", key="delete_template_btn", type="secondary"):
                    template_path = os.path.join(DIMENSIONS_DIR, f"{st.session_state.current_template_name}.json")
                    if os.path.exists(template_path):
                        try:
                            # 删除文件
                            os.remove(template_path)
                            st.success(f"已删除模板文件: {template_path}")
                            # 重置当前模板名称
                            st.session_state.current_template_name = None
                            # 加载初始模板
                            initial_template_name = os.path.splitext(INITIAL_DIMENSION_FILENAME)[0]
                            load_dimensions_from_template(initial_template_name)
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除模板文件失败: {str(e)}")
                    else:
                        st.warning(f"模板文件不存在: {template_path}")
            else:
                st.warning("初始模板不可删除")
    
        # 添加帮助信息
        st.markdown("---")
        with st.expander("帮助信息"):
            st.markdown("""
            ### 关于分析维度
            分析维度用于组织视频分析结果，通常包含：
            
            - **一级维度**: 主要分析类别（如产品特性、价格感知等）
            - **二级维度**: 一级维度下的具体分析点
            
            ### 操作指南
            1. 创建新维度：使用左侧编辑器添加维度
            2. 保存模板：为当前维度结构取名并保存
            3. 加载模板：选择已有模板快速应用
            
            模板文件保存在 `data/dimensions` 目录中，格式为JSON。
            """)
    
    # 左侧维度编辑器
    with col1:
        st.subheader("分析维度编辑器")
        # 使用维度编辑器组件渲染编辑界面
        render_dimension_editor()

if __name__ == "__main__":
    show() 