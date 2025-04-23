#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
维度分析模块
-----------
基于字幕内容生成多层级关键词维度结构，包括:
- 一级维度: 核心主题分类
- 二级维度: 每个主题的子类别
- 三级维度: 具体关键词
使用BERTopic或大型语言模型进行分析。
"""

import os
import sys
import json
import logging
from pathlib import Path
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("dimension_analyzer")

# 导入工具模块
from utils import config, io_handlers, text_analysis, model_handlers

class DimensionAnalyzer:
    """
    维度分析器类
    """
    def __init__(self, batch_mode=False):
        """
        初始化维度分析器
        
        参数:
            batch_mode: 是否批处理模式(无交互)
        """
        self.batch_mode = batch_mode
        
        # 获取路径配置
        self.subtitles_dir = os.path.join(config.get_path('root_output_dir'), 'Subtitles')
        self.output_dir = os.path.join(config.get_path('root_output_dir'), 'Analysis')
        
        # 确保输出目录存在
        io_handlers.ensure_directory(self.output_dir)
        
        # 输出文件路径
        self.output_file = os.path.join(self.output_dir, 'initial_key_dimensions.json')
        
        # 分析配置
        self.topic_count = 5  # 一级维度数量
        self.subtopic_count = 3  # 每个一级维度下的二级维度数量
        self.keyword_count = 5  # 每个二级维度下的三级关键词数量
        
        # 分析方法
        self.analysis_method = 'llm'  # 'bertopic' 或 'llm'
        self.model_name = 'qwen-max'  # 大型语言模型名称

    def extract_text_from_subtitles(self):
        """
        从字幕文件中提取文本
        
        返回:
            字幕文本列表，每项包含文件名和文本内容
        """
        subtitle_files = io_handlers.list_subtitles(self.subtitles_dir)
        
        if not subtitle_files:
            logger.warning(f"没有找到字幕文件: {self.subtitles_dir}")
            return []
        
        texts = []
        
        for subtitle_file in subtitle_files:
            try:
                # 提取文件名(不含扩展名)
                base_name = os.path.splitext(os.path.basename(subtitle_file))[0]
                
                # 提取字幕文本
                text = text_analysis.extract_text_from_srt(subtitle_file)
                
                if text:
                    texts.append({
                        'file': base_name,
                        'text': text
                    })
                    logger.debug(f"已提取字幕文本: {base_name}")
                else:
                    logger.warning(f"字幕文件无内容: {subtitle_file}")
            
            except Exception as e:
                logger.error(f"处理字幕文件失败 {subtitle_file}: {e}")
        
        logger.info(f"共提取出 {len(texts)} 个字幕文本")
        return texts

    def analyze_with_bertopic(self, texts):
        """
        使用BERTopic进行主题分析
        
        参数:
            texts: 文本列表
        
        返回:
            维度结构字典
        """
        if not texts:
            return {}
        
        try:
            # 提取纯文本列表
            pure_texts = [item['text'] for item in texts]
            
            # 使用BERTopic提取主题
            topics = model_handlers.extract_topics_from_texts(
                texts=pure_texts,
                n_topics=self.topic_count,
                language='chinese'
            )
            
            if not topics:
                logger.error("主题提取失败")
                return {}
            
            # 构建维度结构
            dimensions = {}
            
            # 一级维度(主题)
            for topic_id, topic_info in topics.items():
                dimensions[f"dimension_1_{topic_id}"] = {
                    "name": topic_info['label'],
                    "keywords": topic_info['keywords'][:5],
                    "weight": 1.0,
                    "sub_dimensions": {}
                }
                
                # 二级维度(子主题)
                # 此处简化处理，使用关键词组合作为子维度
                keywords = topic_info['keywords']
                
                for i in range(min(self.subtopic_count, len(keywords) // 2)):
                    subtopic_id = f"subtopic_{i}"
                    subtopic_keywords = keywords[i*2:(i+1)*2]
                    
                    dimensions[f"dimension_1_{topic_id}"]["sub_dimensions"][subtopic_id] = {
                        "name": f"{topic_info['label']}_{i+1}",
                        "keywords": subtopic_keywords,
                        "weight": 1.0,
                        "sub_dimensions": {}
                    }
                    
                    # 三级维度(关键词)
                    for j, keyword in enumerate(subtopic_keywords):
                        keyword_id = f"keyword_{j}"
                        dimensions[f"dimension_1_{topic_id}"]["sub_dimensions"][subtopic_id]["sub_dimensions"][keyword_id] = {
                            "name": keyword,
                            "keywords": [keyword],
                            "weight": 1.0
                        }
            
            return dimensions
        
        except Exception as e:
            logger.error(f"BERTopic分析失败: {e}")
            return {}

    def analyze_with_llm(self, texts):
        """
        使用大型语言模型进行主题分析
        
        参数:
            texts: 文本列表
        
        返回:
            维度结构字典
        """
        if not texts:
            return {}
        
        try:
            # 将所有文本合并
            combined_text = "\n\n".join([f"视频 {item['file']}:\n{item['text']}" for item in texts])
            
            # 截取过长的文本
            if len(combined_text) > 8000:
                combined_text = combined_text[:8000] + "...(文本已截断)"
            
            # 构造提示词
            prompt = f"""
            请分析以下视频字幕文本，提取出三层层次化关键词维度结构。

            第一级维度(一级分类)：提取{self.topic_count}个核心主题，作为最高层级的分类维度。
            第二级维度(二级分类)：对每个一级维度，提取{self.subtopic_count}个子类别，构成第二层级。
            第三级维度(关键词)：对每个二级维度，提取{self.keyword_count}个具体关键词，构成第三层级。

            要求：
            1. 每个维度需包含名称和权重(0.1-1.0之间)，名称要简洁明了。
            2. 第一级维度要足够宽泛以涵盖多种内容，一级维度之间要互不重叠。
            3. 第二级维度应该是第一级维度的细分，二级维度之间可以有少量交叉。
            4. 第三级维度应该是具体关键词，可以是名词、动词或形容词。
            5. 相同层级的维度之间应有明显区别。

            文本内容：
            {combined_text}

            请以JSON格式返回结果，格式如下：
            {{
              "dimension_1_1": {{
                "name": "一级维度1名称",
                "keywords": ["关键词1", "关键词2", ...],
                "weight": 权重值,
                "sub_dimensions": {{
                  "subtopic_1": {{
                    "name": "二级维度1名称",
                    "keywords": ["关键词1", "关键词2", ...],
                    "weight": 权重值,
                    "sub_dimensions": {{
                      "keyword_1": {{
                        "name": "三级关键词1",
                        "keywords": ["同义词1", "同义词2", ...],
                        "weight": 权重值
                      }},
                      ...
                    }}
                  }},
                  ...
                }}
              }},
              ...
            }}

            只返回JSON，不要有其他说明文字。
            """
            
            # 调用大型语言模型
            response = model_handlers.generate_text(
                prompt=prompt,
                model=self.model_name,
                temperature=0.2,
                max_tokens=4000
            )
            
            if not response:
                logger.error("语言模型返回为空")
                return {}
            
            # 提取JSON部分
            try:
                # 尝试找到JSON的开始和结束
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx+1]
                    dimensions = json.loads(json_str)
                else:
                    dimensions = json.loads(response)
                
                logger.info("LLM分析成功")
                return dimensions
            
            except json.JSONDecodeError as e:
                logger.error(f"解析模型返回的JSON失败: {e}")
                logger.debug(f"模型返回: {response}")
                
                # 如果失败，返回空的结构
                return {}
        
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {}

    def analyze_dimensions(self, texts):
        """
        分析维度结构
        
        参数:
            texts: 文本列表
        
        返回:
            维度结构字典
        """
        if self.analysis_method == 'bertopic':
            return self.analyze_with_bertopic(texts)
        else:
            return self.analyze_with_llm(texts)

    def create_example_dimensions(self):
        """
        创建示例维度结构(用于测试)
        
        返回:
            示例维度结构字典
        """
        logger.info("创建示例维度结构")
        
        # 基础维度模板 - 婴幼儿奶粉产品相关维度
        base_template = {
          "产品特性": {
            "科学配方": ["HMO", "母乳低聚糖", "A2奶源", "配方", "科学", "专业", "延续敏养"],
            "水奶特性": ["水奶", "即开即饮", "便携", "无需冲泡", "开盖", "即时", "轻便"],
            "产品矩阵": ["蕴淳", "启赋", "混合喂养", "同品牌", "系列", "矩阵"]
          },
          "使用场景": {
            "户外使用": ["户外", "出门", "旅行", "带娃", "携带", "外出", "包里"],
            "夜间喂养": ["夜奶", "夜晚", "睡眠", "起夜", "困", "熬夜"],
            "转奶期": ["转奶", "混合喂养", "断奶", "衔接", "母乳不足", "乳腺炎"]
          },
          "目标人群": {
            "新手妈妈": ["新手妈妈", "第一次", "一胎", "刚生", "经验", "焦虑"],
            "职场妈妈": ["职场", "工作", "忙碌", "效率", "时间", "高效", "来回"],
            "家庭协作": ["爸爸", "月嫂", "阿姨", "家人", "代喂", "代养", "帮忙"]
          },
          "情感诉求": {
            "解决焦虑": ["焦虑", "担心", "困难", "不安", "遭罪", "恐惧", "难题"],
            "建立信任": ["信任", "放心", "安全", "专业认可", "品牌", "大品牌", "权威"],
            "自我实现": ["自我", "解放", "喘息", "时间", "状态", "平衡", "缓冲"]
          },
          "产品效果": {
            "健康成长": ["体质", "结实", "肉嘟嘟", "不敏感", "健康", "棒棒", "长肉"],
            "舒适感受": ["爱喝", "味道", "不咽奶", "吸收", "消化", "舒服", "开朗"],
            "性价比": ["性价比", "划算", "混喂", "高性价比", "不贵", "经济", "性价"]
          }
        }
        
        # 将基础模板转换为所需的维度结构格式
        dimensions = {}
        dimension_index = 1
        
        for dim1_name, dim1_content in base_template.items():
            dim1_id = f"dimension_1_{dimension_index}"
            dimension_index += 1
            
            # 提取第一级维度的所有关键词
            all_dim1_keywords = []
            for keywords_list in dim1_content.values():
                all_dim1_keywords.extend(keywords_list[:2])  # 只取每个子维度的前两个关键词
            all_dim1_keywords = all_dim1_keywords[:5]  # 最多取5个关键词
            
            # 创建第一级维度
            dimensions[dim1_id] = {
                "name": dim1_name,
                "keywords": all_dim1_keywords,
                "weight": 1.0,
                "sub_dimensions": {}
            }
            
            # 创建第二级维度
            subtopic_index = 1
            for dim2_name, dim2_keywords in dim1_content.items():
                subtopic_id = f"subtopic_{subtopic_index}"
                subtopic_index += 1
                
                dimensions[dim1_id]["sub_dimensions"][subtopic_id] = {
                    "name": dim2_name,
                    "keywords": dim2_keywords[:5],  # 最多取5个关键词
                    "weight": 0.9,
                    "sub_dimensions": {}
                }
                
                # 创建第三级维度（关键词）
                for i, keyword in enumerate(dim2_keywords[:3], 1):  # 最多取3个关键词作为三级维度
                    keyword_id = f"keyword_{i}"
                    dimensions[dim1_id]["sub_dimensions"][subtopic_id]["sub_dimensions"][keyword_id] = {
                        "name": keyword,
                        "keywords": [keyword],
                        "weight": 0.8
                    }
        
        return dimensions

    def process(self):
        """
        处理维度分析
        
        返回:
            成功返回True，否则返回False
        """
        try:
            # 检查输出文件是否已存在
            if os.path.exists(self.output_file) and not self.batch_mode:
                logger.info(f"维度分析文件已存在: {self.output_file}")
                
                # 询问是否覆盖
                response = input(f"维度分析文件已存在: {self.output_file}，是否覆盖？(y/n): ")
                if response.lower() != 'y':
                    logger.info("跳过维度分析")
                    return True
            
            # 从字幕文件中提取文本
            texts = self.extract_text_from_subtitles()
            
            # 如果没有找到字幕文件，创建示例维度结构
            if not texts:
                logger.warning("没有找到字幕文件，将创建示例维度结构")
                dimensions = self.create_example_dimensions()
            else:
                # 分析维度结构
                dimensions = self.analyze_dimensions(texts)
                
                # 如果分析失败，使用示例维度结构
                if not dimensions:
                    logger.warning("维度分析失败，使用示例维度结构")
                    dimensions = self.create_example_dimensions()
            
            # 保存维度结构
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(dimensions, f, ensure_ascii=False, indent=2)
            
            logger.info(f"维度分析结果已保存: {self.output_file}")
            return True
        
        except Exception as e:
            logger.error(f"维度分析失败: {e}")
            return False


if __name__ == "__main__":
    # 初始化配置
    config.init()
    
    # 创建维度分析器并运行
    analyzer = DimensionAnalyzer(batch_mode='--batch' in sys.argv)
    
    if analyzer.process():
        logger.info("维度分析完成")
        sys.exit(0)
    else:
        logger.error("维度分析失败")
        sys.exit(1)
