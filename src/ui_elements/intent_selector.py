import streamlit as st
import logging
from typing import Dict, Any, List, Optional

from src.core.intent_service import IntentService

logger = logging.getLogger(__name__)

def render_intent_selector() -> Optional[List[Dict[str, Any]]]:
    """
    渲染意图选择器UI组件，支持多选和全选
    
    返回:
        用户选择的意图字典列表或None
    """
    try:
        # 初始化服务
        intent_service = IntentService()
        intents = intent_service.get_all_intents()
        
        if not intents:
            st.warning("⚠️ 未加载到预定义意图，请检查配置")
            return None
        
        # 创建UI
        st.subheader("选择内容意图 (必选)")
        st.caption("👇 请从下列选项中选择需要分析的意图")
        
        # 添加全选复选框
        select_all = st.checkbox("全选", key="select_all_intents", 
                               help="选择所有可用意图")
        
        # 为每个意图创建复选框
        selected_intent_ids = []
        intent_objects = {}
        
        # 保存所有意图的字典，便于后续查找
        for intent in intents:
            intent_objects[intent['id']] = intent
        
        # 使用列表推导式创建所有意图ID的列表
        all_intent_ids = [intent['id'] for intent in intents]
            
        # 如果用户选择全选，则默认选中所有意图
        default_values = all_intent_ids if select_all else []
        
        # 使用多选框展示所有意图选项
        options = st.multiselect(
            "选择意图(支持多选)",
            options=all_intent_ids,
            default=default_values,
            format_func=lambda x: f"{intent_objects[x]['name']} - {intent_objects[x]['description']}",
            key="intent_multiselect"
        )
        
        selected_intent_ids = options
        
        # 如果有选择，显示选中数量
        if selected_intent_ids:
            # 获取选中的意图详情
            selected_intents = [intent_service.get_intent_by_id(intent_id) for intent_id in selected_intent_ids]
            selected_intents = [intent for intent in selected_intents if intent is not None]
            
            if selected_intents:
                # 显示选中的意图
                st.success(f"✅ 已选择 {len(selected_intents)} 个意图")
                
                # 展示选中的意图名称
                intent_names = [intent['name'] for intent in selected_intents]
                st.caption(f"选中的意图: {', '.join(intent_names)}")
                
                # 如果只选择了一个意图，显示相关关键词
                if len(selected_intents) == 1 and 'keywords' in selected_intents[0] and selected_intents[0]['keywords']:
                    keywords_text = ", ".join(selected_intents[0]['keywords'])
                    st.caption(f"相关关键词: {keywords_text}")
                
                return selected_intents
        else:
            st.info("⚠️ 请至少选择一个意图才能继续")
            return None
        
    except Exception as e:
        logger.error(f"渲染意图选择器时出错: {str(e)}")
        st.error("意图选择器加载失败，请刷新页面重试")
        return None

def render_description_input() -> str:
    """
    渲染详细描述输入框
    
    返回:
        用户输入的详细描述
    """
    st.caption("在已选择的意图基础上，您可以输入更精确的描述")
    
    user_description = st.text_area(
        "请输入更详细的需求描述 (可选)", 
        placeholder="例如：我想找出视频中提到A2奶源好处的部分",
        help="输入越具体，匹配结果越精确",
        max_chars=200
    )
    
    return user_description 