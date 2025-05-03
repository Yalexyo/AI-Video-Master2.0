#!/usr/bin/env python3
"""
视频修复工具测试

整合测试各种视频修复工具的功能，包括：
1. VideoFixTools类的验证和安全加载功能
2. video_fix_tools模块的验证、修复和安全加载功能
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径中
sys.path.append(str(Path(__file__).parent.parent.parent))

# 导入两种不同的视频修复工具
from src.core.magic_video_fix import VideoFixTools
from src.core.magic_video_fix import video_fix_tools

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_test_videos():
    """获取测试视频列表"""
    # 获取视频目录
    video_dir = os.path.join("data", "test_samples", "input", "video")
    if not os.path.exists(video_dir):
        logger.warning(f"视频目录不存在: {video_dir}")
        return []
    
    # 获取目录下的所有视频文件
    video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) 
                  if f.endswith(('.mp4', '.avi', '.mov', '.MOV'))]
    
    if not video_files:
        logger.warning(f"未找到视频文件，请确保 {video_dir} 目录下有视频文件")
        return []
    
    logger.info(f"找到 {len(video_files)} 个视频文件进行测试")
    return video_files

def test_video_fix_tools_class():
    """测试VideoFixTools类功能"""
    logger.info("===== 测试VideoFixTools类功能 =====")
    
    fix_tools = VideoFixTools()
    video_files = get_test_videos()
    
    if not video_files:
        return
    
    # 测试视频验证功能
    for video_path in video_files[:1]:  # 只测试第一个视频文件
        logger.info(f"测试视频: {os.path.basename(video_path)}")
        
        # 检查视频是否有效
        is_valid, error_msg = fix_tools.validate_video_file(video_path)
        logger.info(f"视频有效性检查结果: {is_valid}, {'无错误' if is_valid else error_msg}")
        
        # 测试安全加载
        clip, error = fix_tools.safe_get_video_clip(video_path)
        if clip is not None:
            logger.info("视频安全加载成功")
            # 获取视频信息
            logger.info(f"- 时长: {clip.duration:.2f}秒") 
            logger.info(f"- 分辨率: {clip.size[0]}x{clip.size[1]}")
            logger.info(f"- FPS: {clip.fps}")
            
            # 释放视频
            clip.close()
        else:
            logger.error(f"视频安全加载失败: {error}")
    
    # 测试空视频处理能力
    logger.info("测试空视频/损坏视频处理功能")
    non_existent_file = "data/non_existent_video.mp4"
    is_valid, error_msg = fix_tools.validate_video_file(non_existent_file)
    logger.info(f"不存在文件的有效性检查结果: {is_valid}, {'无错误' if is_valid else error_msg}")
    
    clip, error = fix_tools.safe_get_video_clip(non_existent_file)
    if clip is None:
        logger.info(f"正确处理了不存在的视频文件: {error}")
    else:
        logger.error("在处理不存在的视频文件时出现问题")
        clip.close()

def test_video_fix_tools_module():
    """测试video_fix_tools模块功能"""
    logger.info("===== 测试video_fix_tools模块功能 =====")
    
    video_files = get_test_videos()
    
    if not video_files:
        return
    
    # 测试视频验证功能
    for video_path in video_files[:1]:  # 只测试第一个视频文件
        logger.info(f"测试视频: {os.path.basename(video_path)}")
        
        # 验证视频
        valid, error_msg = video_fix_tools.validate_video_file(video_path)
        if valid:
            logger.info("✅ 视频有效")
        else:
            logger.info(f"❌ 视频无效: {error_msg}")
            
            # 测试修复功能
            logger.info("尝试修复视频...")
            fixed, result = video_fix_tools.repair_video_file(video_path)
            
            if fixed:
                logger.info(f"✅ 视频修复成功: {result}")
                
                # 验证修复后的视频
                valid, error_msg = video_fix_tools.validate_video_file(video_path)
                if valid:
                    logger.info("✅ 修复后的视频有效")
                else:
                    logger.info(f"❌ 修复后的视频仍然无效: {error_msg}")
            else:
                logger.info(f"❌ 视频修复失败: {result}")
    
    # 测试安全视频加载功能
    logger.info("测试安全视频加载功能")
    video_path = video_files[0]  # 使用第一个视频文件
    
    # 安全加载视频
    clip, error = video_fix_tools.safe_get_video_clip(video_path)
    
    if clip is not None:
        logger.info("✅ 视频加载成功")
        logger.info(f"- 时长: {clip.duration:.2f}秒")
        logger.info(f"- 分辨率: {clip.size[0]}x{clip.size[1]}")
        logger.info(f"- FPS: {clip.fps}")
        
        # 关闭视频
        clip.close()
    else:
        logger.info(f"❌ 视频加载失败: {error}")

def test_comparison():
    """比较两种视频修复工具的性能和结果"""
    logger.info("===== 比较两种视频修复工具 =====")
    
    video_files = get_test_videos()
    
    if not video_files:
        return
    
    fix_tools_class = VideoFixTools()
    video_path = video_files[0]  # 使用第一个视频文件
    
    # 测试VideoFixTools类
    logger.info(f"使用VideoFixTools类验证视频: {os.path.basename(video_path)}")
    is_valid_class, error_msg_class = fix_tools_class.validate_video_file(video_path)
    logger.info(f"VideoFixTools类结果: {'有效' if is_valid_class else f'无效: {error_msg_class}'}")
    
    # 测试video_fix_tools模块
    logger.info(f"使用video_fix_tools模块验证视频: {os.path.basename(video_path)}")
    is_valid_module, error_msg_module = video_fix_tools.validate_video_file(video_path)
    logger.info(f"video_fix_tools模块结果: {'有效' if is_valid_module else f'无效: {error_msg_module}'}")
    
    # 对比结果
    if is_valid_class == is_valid_module:
        logger.info("✅ 两种工具的验证结果一致")
    else:
        logger.info("❌ 两种工具的验证结果不一致，可能需要进一步调查")

if __name__ == "__main__":
    logger.info("===== 开始视频修复工具测试 =====")
    
    # 测试VideoFixTools类功能
    test_video_fix_tools_class()
    
    # 测试video_fix_tools模块功能
    test_video_fix_tools_module()
    
    # 比较两种工具的结果
    test_comparison()
    
    logger.info("===== 视频修复工具测试完成 =====") 