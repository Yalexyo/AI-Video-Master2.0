import streamlit as st
import logging
from typing import Dict, Any, List, Optional

from src.core.intent_service import IntentService

logger = logging.getLogger(__name__)

def render_intent_selector() -> Optional[Dict[str, Any]]:
    """
    渲染意图选择器UI组件
    
    返回:
        用户选择的意图字典或None
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
        st.caption("👇 请先从下列选项中选择一个主要意图")
        
        # 使用单选按钮展示所有意图选项
        intent_options = [(intent['id'], f"{intent['name']} - {intent['description']}") 
                          for intent in intents]
        
        selected_id = st.radio(
            "选择一个意图类别",
            options=[id for id, _ in intent_options],
            format_func=lambda x: next((name for id, name in intent_options if id == x), x),
            horizontal=False,
            key="intent_radio"
        )
        
        if selected_id:
            # 获取选中的意图详情
            selected_intent = intent_service.get_intent_by_id(selected_id)
            
            if selected_intent:
                # 显示选中的意图
                st.success(f"✅ 已选择: **{selected_intent['name']}**")
                
                # 显示相关关键词
                if 'keywords' in selected_intent and selected_intent['keywords']:
                    keywords_text = ", ".join(selected_intent['keywords'])
                    st.caption(f"相关关键词: {keywords_text}")
                
                return selected_intent
        
        st.info("⚠️ 请先选择一个意图类别才能继续")
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