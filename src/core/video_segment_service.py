import os
import json
import logging
from typing import Dict, Any, List, Optional, Literal, Tuple
import pandas as pd
from datetime import datetime
import asyncio

from utils.analyzer import VideoAnalyzer
from src.api.llm_service import LLMService
from src.core.intent_service import IntentService

logger = logging.getLogger(__name__)

class VideoSegmentService:
    """视频片段处理服务，负责获取和处理视频片段"""
    
    def __init__(self, llm_provider: str = "deepseek", max_concurrent_tasks: int = 3):
        """
        初始化视频片段服务
        
        参数:
            llm_provider: LLM服务提供商，可选值为 "deepseek" 或 "openrouter"
            max_concurrent_tasks: 最大并行任务数
        """
        self.analyzer = VideoAnalyzer()
        self.llm_service = LLMService(provider=llm_provider)
        self.intent_service = IntentService()
        self.max_concurrent_tasks = max_concurrent_tasks  # 控制并发数量
        logger.info(f"视频片段服务初始化完成，使用{llm_provider}作为LLM提供商")
        
    async def analyze_video_content(self, 
                           video_id: str, 
                           subtitle_df: pd.DataFrame,
                                mode: Literal['intent', 'prompt'],
                                selected_intent_ids: Optional[List[str]] = None,
                                user_description: Optional[str] = None) -> Dict[str, Any]:
        """
        分析视频内容，支持基于预定义意图或自由文本Prompt两种模式
        
        参数:
            video_id: 视频的唯一标识符
            subtitle_df: 包含'timestamp'和'text'列的字幕DataFrame
            mode: 分析模式，'intent' 或 'prompt'
            selected_intent_ids: 模式为'intent'时，用户选择的意图ID列表
            user_description: 模式为'prompt'时，用户的自由文本描述
            
        返回:
            包含分析结果的字典
        """
        
        start_time = datetime.now()
        results = {
            "video_id": video_id,
            "mode": mode,
            "analysis_start_time": start_time.isoformat(),
            "matches": [] if mode == 'prompt' else {},
            "errors": []
        }

        if subtitle_df is None or subtitle_df.empty:
            logger.error("字幕数据为空，无法进行内容分析")
            results["errors"].append("字幕数据为空")
            results["analysis_end_time"] = datetime.now().isoformat()
            return results

        subtitles_list = subtitle_df.to_dict('records')

        if mode == 'intent':
            if not selected_intent_ids:
                logger.error("意图模式下未提供selected_intent_ids")
                results["errors"].append("意图模式下缺少意图ID")
                results["analysis_end_time"] = datetime.now().isoformat()
                return results
                
            logger.info(f"开始基于意图的分析，意图IDs: {selected_intent_ids}")
            
            # 获取所有选定意图的详细信息
            intents_to_process = []
            for intent_id in selected_intent_ids:
                selected_intent = self.intent_service.get_intent_by_id(intent_id)
                if not selected_intent:
                    logger.warning(f"未找到ID为 {intent_id} 的意图，跳过")
                    results["errors"].append(f"未找到意图ID: {intent_id}")
                    continue
                intents_to_process.append(selected_intent)
            
            # 并行处理所有意图
            all_matches = await self._process_intents_parallel(intents_to_process, subtitles_list)
            
            # 记录每个意图的错误信息
            for intent_id, error in all_matches.get("errors", []):
                logger.error(f"处理意图 {intent_id} 时出错: {error}")
                results["errors"].append(f"意图 {intent_id} 分析错误: {error}")
            
            # 过滤并分组结果
            grouped_results = self._group_intent_results(all_matches.get("matches", []))
            results["matches"] = grouped_results
            
            # 记录匹配数量
            match_count = sum(len(intent_data.get("matches", [])) for intent_data in grouped_results.values())
            logger.info(f"所有意图共找到 {match_count} 个有效匹配项")
        
        elif mode == 'prompt':
            if not user_description:
                logger.error("Prompt模式下未提供user_description")
                results["errors"].append("Prompt模式下缺少用户描述")
                results["analysis_end_time"] = datetime.now().isoformat()
                return results
                
            logger.info(f"开始基于自由文本Prompt的分析: {user_description[:100]}...")
            try:
                prompt_matches = await self.llm_service.refine_intent_matching(
                    user_description=user_description,
                    subtitles=subtitles_list,
                    selected_intent=None  # 模式2不提供预选意图
                )
                
                if prompt_matches and isinstance(prompt_matches, list) and prompt_matches[0].get('error'):
                    error_msg = prompt_matches[0]['error']
                    logger.error(f"自由文本Prompt分析时LLM服务返回错误: {error_msg}")
                    results["errors"].append(f"自由文本Prompt分析错误: {error_msg}")
                    results["matches"] = []
                elif prompt_matches:
                    filtered_matches = [m for m in prompt_matches if isinstance(m, dict) and m.get('score', 0) >= 60]
                    filtered_matches.sort(key=lambda x: x.get('score', 0), reverse=True)
                    results["matches"] = filtered_matches
                    logger.info(f"自由文本Prompt分析完成，找到 {len(filtered_matches)} 个得分 >= 60 的有效匹配项")
                else:
                     logger.info(f"自由文本Prompt分析未找到匹配项")
                     results["matches"] = []

            except Exception as e:
                logger.exception(f"自由文本Prompt分析时发生异常: {str(e)}")
                results["errors"].append(f"自由文本Prompt分析时异常: {str(e)}")
                results["matches"] = []
        else:
            logger.error(f"无效的分析模式: {mode}")
            results["errors"].append(f"无效的分析模式: {mode}")

        results["analysis_end_time"] = datetime.now().isoformat()
        analysis_duration = (datetime.now() - start_time).total_seconds()
        results["analysis_duration_seconds"] = round(analysis_duration, 2)
        logger.info(f"视频内容分析完成，模式: {mode}，耗时: {analysis_duration:.2f}秒")
        
        return results
            
    async def _process_intents_parallel(self, intents: List[Dict[str, Any]], subtitles: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        并行处理多个意图
        
        参数:
            intents: 要处理的意图列表
            subtitles: 字幕列表
            
        返回:
            包含处理结果的字典，格式为 {"matches": [...], "errors": [...]}
        """
        logger.info(f"开始并行处理 {len(intents)} 个意图，最大并行任务数: {self.max_concurrent_tasks}")
        
        all_matches = []
        all_errors = []
        
        # 创建所有意图的任务
        tasks = []
        for intent in intents:
            intent_id = intent.get('id')
            intent_name = intent.get('name')
            
            # 为每个意图创建一个描述
            intent_user_description = f"查找视频中与 '{intent_name}' 意图相关的内容，意图描述为：{intent.get('description')}"
            
            # 创建异步任务
            task = self._process_single_intent(intent, intent_user_description, subtitles)
            tasks.append((intent_id, task))
        
        # 使用信号量控制并发数量
        sem = asyncio.Semaphore(self.max_concurrent_tasks)
        
        async def bounded_process(intent_id, task):
            async with sem:
                try:
                    logger.info(f"开始处理意图: {intent_id}")
                    start_time = datetime.now()
                    result = await task
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"意图 {intent_id} 处理完成，耗时: {duration:.2f}秒")
                    return intent_id, result, None
                except Exception as e:
                    logger.exception(f"处理意图 {intent_id} 时发生异常: {str(e)}")
                    return intent_id, None, str(e)
        
        # 并行执行所有任务
        bounded_tasks = [bounded_process(intent_id, task) for intent_id, task in tasks]
        results = await asyncio.gather(*bounded_tasks)
        
        # 处理结果
        for intent_id, matches, error in results:
            if error:
                all_errors.append((intent_id, error))
            elif matches:
                if matches and isinstance(matches, list) and matches[0].get('error'):
                    # LLM服务返回了错误
                    error_msg = matches[0]['error']
                    all_errors.append((intent_id, error_msg))
                else:
                    # 给匹配结果添加意图信息
                    for match in matches:
                        if isinstance(match, dict):
                            match['intent_id'] = intent_id
                            intent_data = next((i for i in intents if i.get('id') == intent_id), None)
                            if intent_data:
                                match['intent_name'] = intent_data.get('name')
                    
                    # 添加到总结果列表
                    all_matches.extend(matches)
                    logger.info(f"意图 {intent_id} 分析找到 {len(matches)} 个匹配项")
        
        return {
            "matches": all_matches,
            "errors": all_errors
        }
    
    async def _process_single_intent(self, intent: Dict[str, Any], user_description: str, subtitles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """处理单个意图"""
        return await self.llm_service.refine_intent_matching(
            selected_intent=intent,
            user_description=user_description,
            subtitles=subtitles
        )
    
    def _group_intent_results(self, matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        将匹配结果按意图分组，并按分数排序
        
        参数:
            matches: 所有匹配结果列表
        
        返回:
            按意图ID分组的结果字典
        """
        # 过滤得分低于60的结果
        filtered_matches = [m for m in matches if isinstance(m, dict) and m.get('score', 0) >= 60]
        
        # 按意图分组
        grouped_results = {}
        for match in filtered_matches:
            intent_id = match.get('intent_id')
            if not intent_id:
                continue
                
            if intent_id not in grouped_results:
                grouped_results[intent_id] = {
                    "intent_id": intent_id,
                    "intent_name": match.get('intent_name', '未知意图'),
                    "matches": []
                }
                
            # 移除意图信息，避免重复
            match_data = {k: v for k, v in match.items() if k not in ['intent_id', 'intent_name']}
            grouped_results[intent_id]["matches"].append(match_data)
        
        # 对每个意图的匹配结果按分数排序
        for intent_id in grouped_results:
            grouped_results[intent_id]["matches"].sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return grouped_results
    
    async def get_all_intents_analysis(self, video_id: str, subtitle_df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析视频中所有预定义意图
        
        参数:
            video_id: 视频的唯一标识符
            subtitle_df: 包含'timestamp'和'text'列的字幕DataFrame
            
        返回:
            包含所有意图分析结果的字典
        """
        # 获取所有预定义意图
        all_intents = self.intent_service.get_all_intents()
        intent_ids = [intent['id'] for intent in all_intents]
        
        if not intent_ids:
            return {
                "video_id": video_id,
                "error": "未找到任何预定义意图",
                "matches": {}
            }
        
        # 使用意图模式分析所有意图
        logger.info(f"分析视频 {video_id} 的所有意图，共 {len(intent_ids)} 个")
        return await self.analyze_video_content(
            video_id=video_id,
            subtitle_df=subtitle_df,
            mode='intent',
            selected_intent_ids=intent_ids
        )

    async def get_batch_analysis(self, videos: List[Tuple[str, pd.DataFrame]], analysis_type: Literal['all_intents', 'custom'], 
                                custom_intent_ids: Optional[List[str]] = None, custom_prompt: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        批量分析多个视频
        
        参数:
            videos: 待分析视频的列表，每项为 (video_id, subtitle_df) 元组
            analysis_type: 分析类型，'all_intents'表示分析所有预定义意图，'custom'表示自定义分析
            custom_intent_ids: 自定义分析时的意图ID列表
            custom_prompt: 自定义分析时的提示词
            
        返回:
            视频ID到分析结果的映射
        """
        if not videos:
            return {}
            
        logger.info(f"开始批量分析 {len(videos)} 个视频，分析类型: {analysis_type}")
        
        # 创建分析任务
        tasks = {}
        for video_id, subtitle_df in videos:
            if analysis_type == 'all_intents':
                task = self.get_all_intents_analysis(video_id, subtitle_df)
            elif analysis_type == 'custom':
                if custom_intent_ids:
                    # 模式1：使用自定义意图列表
                    task = self.analyze_video_content(
                        video_id=video_id,
                        subtitle_df=subtitle_df,
                        mode='intent',
                        selected_intent_ids=custom_intent_ids
                    )
                elif custom_prompt:
                    # 模式2：使用自定义提示词
                    task = self.analyze_video_content(
                        video_id=video_id,
                        subtitle_df=subtitle_df,
                        mode='prompt',
                        user_description=custom_prompt
                    )
                else:
                    logger.error(f"自定义分析需要提供意图ID或提示词，跳过视频 {video_id}")
                    continue
            else:
                logger.error(f"不支持的分析类型: {analysis_type}，跳过视频 {video_id}")
                continue
                
            tasks[video_id] = task
            
        # 使用信号量控制并发数量
        sem = asyncio.Semaphore(self.max_concurrent_tasks)
        
        async def bounded_analysis(video_id, task):
            async with sem:
                try:
                    logger.info(f"开始分析视频: {video_id}")
                    start_time = datetime.now()
                    result = await task
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"视频 {video_id} 分析完成，耗时: {duration:.2f}秒")
                    return video_id, result
                except Exception as e:
                    logger.exception(f"分析视频 {video_id} 时发生异常: {str(e)}")
                    return video_id, {"error": str(e)}
                    
        # 并行执行所有视频分析
        bounded_tasks = [bounded_analysis(video_id, task) for video_id, task in tasks.items()]
        results = await asyncio.gather(*bounded_tasks)
        
        # 整理结果
        return {video_id: result for video_id, result in results}
    
    async def get_video_segments(self, 
                           video_id: str, 
                           subtitle_df: pd.DataFrame,
                           selected_intent: Dict[str, Any],
                           user_description: str) -> Dict[str, Any]:
        """ 
        [已弃用] 请使用 analyze_video_content 方法替代。
        旧的获取视频片段方法，主要用于LLM精确匹配。
        """
        logger.warning("get_video_segments 方法已弃用，请使用 analyze_video_content")
        return await self.analyze_video_content(
            video_id=video_id,
            subtitle_df=subtitle_df,
            mode='intent',
            selected_intent_ids=[selected_intent['id']] if selected_intent and 'id' in selected_intent else None,
            user_description=user_description
        ) 