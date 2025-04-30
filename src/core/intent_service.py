import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class IntentService:
    """意图识别服务，负责加载和处理意图数据"""
    
    def __init__(self):
        self.intents = []
        self.load_intents()
        
    def load_intents(self) -> None:
        """加载预定义意图数据"""
        try:
            intents_file = os.path.join('data', 'intents', 'intents_keywords.json')
            if not os.path.exists(intents_file):
                logger.warning(f"意图文件不存在: {intents_file}")
                return
                
            with open(intents_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.intents = data.get('intents', [])
                
            logger.info(f"已加载 {len(self.intents)} 个意图")
        except Exception as e:
            logger.error(f"加载意图数据失败: {str(e)}")
            
    def get_all_intents(self) -> List[Dict[str, Any]]:
        """获取所有预定义意图"""
        return self.intents
        
    def get_intent_by_id(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取意图信息"""
        for intent in self.intents:
            if intent.get('id') == intent_id:
                return intent
        return None 