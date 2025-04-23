import os
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.core.model import TextEmbeddingModel, VideoAnalysisModel

# 配置日志
logger = logging.getLogger(__name__)

class VideoProcessor:
    """视频处理器类，处理视频分析和维度匹配的核心逻辑"""
    
    def __init__(self, config: Dict = None):
        """
        初始化视频处理器
        
        参数:
            config: 配置字典，包含处理参数
        """
        self.config = config or {}
        self.text_model = TextEmbeddingModel()
        self.video_model = VideoAnalysisModel(self.text_model)
        logger.info("视频处理器初始化完成")
        
        # 确保输出目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        dirs = [
            os.path.join('data', 'raw'),
            os.path.join('data', 'processed'),
            os.path.join('data', 'cache')
        ]
        
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"创建目录: {dir_path}")
    
    def process_video_urls(self, urls: List[str], dimensions: Dict = None, keywords: List[str] = None, threshold: float = 0.7) -> Dict[str, Any]:
        """
        处理视频URL列表
        
        参数:
            urls: 视频URL列表
            dimensions: 分析维度结构
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            处理结果，包含维度和关键词匹配的视频片段
        """
        if not urls:
            logger.warning("没有URL需要处理")
            return {"status": "error", "message": "没有URL需要处理"}
        
        try:
            # 获取当前时间
            analysis_time = datetime.now()
            timestamp = analysis_time.isoformat()
            
            # 模拟分析结果，实际项目中会从URL下载视频、提取字幕并进行分析
            results = {
                "status": "success",
                "timestamp": timestamp,
                "urls_count": len(urls),
                "threshold": threshold,
                "metadata": {
                    "app_version": "0.9.0",
                    "analysis_date": analysis_time.strftime("%Y-%m-%d"),
                    "analysis_time": analysis_time.strftime("%H:%M:%S"),
                    "model_version": self.text_model.model_name,
                    "dimensions_used": bool(dimensions),
                    "keywords_used": bool(keywords),
                    "keywords_count": len(keywords) if keywords else 0
                },
                "videos": []
            }
            
            for url in urls:
                video_result = self._process_single_video(url, dimensions, keywords, threshold)
                results["videos"].append(video_result)
            
            logger.info(f"成功处理 {len(urls)} 个视频URL")
            return results
        except Exception as e:
            logger.error(f"处理视频URL出错: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _process_single_video(self, url: str, dimensions: Dict = None, keywords: List[str] = None, threshold: float = 0.7) -> Dict[str, Any]:
        """
        处理单个视频URL
        
        参数:
            url: 视频URL
            dimensions: 分析维度结构
            keywords: 关键词列表
            threshold: 匹配阈值
            
        返回:
            处理结果，包含维度和关键词匹配的视频片段
        """
        # 模拟从URL获取视频信息
        video_info = self._get_video_info(url)
        
        # 模拟从视频提取字幕片段
        subtitle_segments = self._extract_subtitles(url)
        
        # 根据维度分析字幕片段
        dimension_results = {}
        if dimensions:
            analyzed_segments = self.video_model.analyze_subtitle_segments(subtitle_segments, dimensions, threshold)
            dimension_results = self._group_by_dimensions(analyzed_segments, dimensions)
        
        # 根据关键词分析字幕片段
        keyword_results = {}
        if keywords:
            keyword_analyzed_segments = self.video_model.analyze_keywords(subtitle_segments, keywords, threshold)
            keyword_results = self._group_by_keywords(keyword_analyzed_segments, keywords)
        
        # 构建结果
        result = {
            "url": url,
            "title": video_info.get("title", "未知标题"),
            "duration": video_info.get("duration", 0),
            "duration_formatted": self._format_time(video_info.get("duration", 0)),
            "segments_count": len(subtitle_segments),
            "channel": video_info.get("channel", ""),
            "upload_date": video_info.get("upload_date", ""),
            "dimension_matches": dimension_results,
            "keyword_matches": keyword_results,
            "summary": {
                "total_matches": self._count_total_matches(dimension_results, keyword_results),
                "top_dimensions": self._get_top_dimensions(dimension_results, limit=3),
                "top_keywords": self._get_top_keywords(keyword_results, limit=3)
            }
        }
        
        return result
    
    def _get_video_info(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息
        
        参数:
            url: 视频URL
            
        返回:
            视频信息字典
        """
        # 模拟从URL获取视频信息
        # 实际项目中会调用视频平台API或使用yt-dlp等工具获取视频信息
        return {
            "title": f"视频 {url.split('/')[-1]}",
            "duration": 300,  # 模拟视频时长5分钟
            "channel": "示例频道",
            "upload_date": "2023-01-01"
        }
    
    def _extract_subtitles(self, url: str) -> List[Dict[str, Any]]:
        """
        从视频中提取字幕片段
        
        参数:
            url: 视频URL
            
        返回:
            字幕片段列表
        """
        # 模拟从视频提取字幕片段
        # 实际项目中会使用语音识别或字幕提取工具
        segments = []
        
        # 生成10个模拟字幕片段
        for i in range(10):
            start_time = i * 30  # 每30秒一个片段
            end_time = start_time + 30
            
            segment = {
                "index": i,
                "start": start_time,
                "end": end_time,
                "start_formatted": self._format_time(start_time),
                "end_formatted": self._format_time(end_time),
                "text": f"这是第{i+1}个字幕片段，讨论了产品特性和用户需求。" if i % 2 == 0 else f"这是第{i+1}个字幕片段，说明了产品的功能和性能。"
            }
            
            segments.append(segment)
        
        return segments
    
    def _format_time(self, seconds: int) -> str:
        """
        格式化时间
        
        参数:
            seconds: 秒数
            
        返回:
            格式化后的时间字符串 (HH:MM:SS)
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _group_by_dimensions(self, segments: List[Dict[str, Any]], dimensions: Dict) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        按维度分组字幕片段
        
        参数:
            segments: 分析后的字幕片段列表
            dimensions: 维度结构
            
        返回:
            按维度分组的片段字典
        """
        results = {
            "level1": {},
            "level2": {}
        }
        
        # 遍历每个片段
        for segment in segments:
            matches = segment.get('dimension_matches', {})
            
            # 处理一级维度匹配
            level1_matches = matches.get('level1', {})
            for dim1, score in level1_matches.items():
                if dim1 not in results['level1']:
                    results['level1'][dim1] = []
                results['level1'][dim1].append({
                    "segment": segment,
                    "score": score
                })
            
            # 处理二级维度匹配
            level2_matches = matches.get('level2', {})
            for dim1, dim2_dict in level2_matches.items():
                if dim1 not in results['level2']:
                    results['level2'][dim1] = {}
                
                for dim2, score in dim2_dict.items():
                    if dim2 not in results['level2'][dim1]:
                        results['level2'][dim1][dim2] = []
                    results['level2'][dim1][dim2].append({
                        "segment": segment,
                        "score": score
                    })
        
        return results
    
    def _group_by_keywords(self, segments: List[Dict[str, Any]], keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        按关键词分组字幕片段
        
        参数:
            segments: 分析后的字幕片段列表
            keywords: 关键词列表
            
        返回:
            按关键词分组的片段字典
        """
        results = {}
        
        # 遍历每个片段
        for segment in segments:
            keyword_matches = segment.get('keyword_matches', {})
            
            for keyword, score in keyword_matches.items():
                if keyword not in results:
                    results[keyword] = []
                results[keyword].append({
                    "segment": segment,
                    "score": score
                })
        
        return results
    
    def _count_total_matches(self, dimension_results: Dict, keyword_results: Dict) -> Dict[str, int]:
        """
        计算总匹配数
        
        参数:
            dimension_results: 维度匹配结果
            keyword_results: 关键词匹配结果
            
        返回:
            各类匹配的计数
        """
        level1_matches = sum(len(segments) for segments in dimension_results.get('level1', {}).values())
        
        level2_matches = 0
        for dim1_dict in dimension_results.get('level2', {}).values():
            for segments in dim1_dict.values():
                level2_matches += len(segments)
        
        keyword_matches = sum(len(segments) for segments in keyword_results.values())
        
        return {
            "dimension_level1": level1_matches,
            "dimension_level2": level2_matches,
            "keywords": keyword_matches,
            "total": level1_matches + level2_matches + keyword_matches
        }
    
    def _get_top_dimensions(self, dimension_results: Dict, limit: int = 3) -> List[Dict[str, Any]]:
        """
        获取匹配度最高的维度
        
        参数:
            dimension_results: 维度匹配结果
            limit: 返回的最大数量
            
        返回:
            匹配度最高的维度列表
        """
        # 处理一级维度
        level1_stats = []
        for dim1, segments in dimension_results.get('level1', {}).items():
            if segments:
                avg_score = sum(item['score'] for item in segments) / len(segments)
                level1_stats.append({
                    "dimension": dim1,
                    "level": "level1",
                    "matches": len(segments),
                    "avg_score": avg_score
                })
        
        # 处理二级维度
        level2_stats = []
        for dim1, dim2_dict in dimension_results.get('level2', {}).items():
            for dim2, segments in dim2_dict.items():
                if segments:
                    avg_score = sum(item['score'] for item in segments) / len(segments)
                    level2_stats.append({
                        "dimension": f"{dim1} > {dim2}",
                        "level": "level2",
                        "matches": len(segments),
                        "avg_score": avg_score
                    })
        
        # 合并并按匹配数量和平均分数排序
        all_stats = level1_stats + level2_stats
        sorted_stats = sorted(all_stats, key=lambda x: (x['matches'], x['avg_score']), reverse=True)
        
        # 返回前N个
        return sorted_stats[:limit]
    
    def _get_top_keywords(self, keyword_results: Dict, limit: int = 3) -> List[Dict[str, Any]]:
        """
        获取匹配度最高的关键词
        
        参数:
            keyword_results: 关键词匹配结果
            limit: 返回的最大数量
            
        返回:
            匹配度最高的关键词列表
        """
        # 计算每个关键词的统计数据
        keyword_stats = []
        for keyword, segments in keyword_results.items():
            if segments:
                avg_score = sum(item['score'] for item in segments) / len(segments)
                keyword_stats.append({
                    "keyword": keyword,
                    "matches": len(segments),
                    "avg_score": avg_score
                })
        
        # 按匹配数量和平均分数排序
        sorted_stats = sorted(keyword_stats, key=lambda x: (x['matches'], x['avg_score']), reverse=True)
        
        # 返回前N个
        return sorted_stats[:limit]
    
    def save_analysis_results(self, results: Dict[str, Any], output_path: Optional[str] = None, pretty_print: bool = True) -> str:
        """
        保存分析结果到JSON文件
        
        参数:
            results: 分析结果字典
            output_path: 输出文件路径，默认为自动生成
            pretty_print: 是否美化输出JSON文件，默认为True
            
        返回:
            保存的文件路径
        """
        try:
            # 如果没有指定输出路径，自动生成
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join('data', 'processed', f"analysis_results_{timestamp}.json")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存结果
            with open(output_path, 'w', encoding='utf-8') as f:
                if pretty_print:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(results, f, ensure_ascii=False)
            
            logger.info(f"分析结果已保存到: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"保存分析结果出错: {str(e)}")
            return ""
    
    def load_analysis_results(self, file_path: str) -> Dict[str, Any]:
        """
        从JSON文件加载分析结果
        
        参数:
            file_path: 文件路径
            
        返回:
            加载的分析结果字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            logger.info(f"从文件加载分析结果: {file_path}")
            return results
        except Exception as e:
            logger.error(f"加载分析结果出错: {str(e)}")
            return {"status": "error", "message": f"加载分析结果出错: {str(e)}"}
