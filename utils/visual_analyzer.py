#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
视觉分析工具：提供物体检测等功能
"""

import cv2
import os
import logging
from typing import List, Tuple, Dict
import numpy as np

logger = logging.getLogger(__name__)

class VisualAnalyzer:
    """执行视觉分析任务，如物体检测"""

    def __init__(self, model_dir='data/models/object_detection'):
        """
        初始化VisualAnalyzer

        参数:
            model_dir: 存放物体检测模型文件的目录
        """
        prototxt_path = os.path.join(model_dir, 'MobileNetSSD_deploy.prototxt')
        model_path = os.path.join(model_dir, 'MobileNetSSD_deploy.caffemodel')
        class_file = os.path.join(model_dir, 'object_detection_classes_pascal_voc.txt')

        if not all(os.path.exists(p) for p in [prototxt_path, model_path, class_file]):
            logger.error(f"模型文件缺失，请确保以下文件在 {model_dir} 目录下: MobileNetSSD_deploy.prototxt, MobileNetSSD_deploy.caffemodel, object_detection_classes_pascal_voc.txt")
            self.net = None
            self.classes = None
            return

        try:
            self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
            logger.info("物体检测模型加载成功")

            # 加载类别标签
            with open(class_file, 'r') as f:
                self.classes = [line.strip() for line in f.readlines()]
            logger.info(f"加载了 {len(self.classes)} 个物体类别")

        except cv2.error as e:
            logger.exception(f"加载物体检测模型失败: {e}")
            self.net = None
            self.classes = None

    def detect_objects_in_frame(self, frame, confidence_threshold=0.4) -> List[str]:
        """
        检测单帧图像中的物体

        参数:
            frame: OpenCV图像帧 (numpy array)
            confidence_threshold: 检测置信度阈值

        返回:
            检测到的物体标签列表
        """
        if self.net is None or self.classes is None:
            logger.warning("物体检测模型未加载，无法执行检测")
            return []

        try:
            (h, w) = frame.shape[:2]
            # 将图像转换为Blob
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)

            # 设置输入并进行前向传播
            self.net.setInput(blob)
            detections = self.net.forward()

            detected_objects = set() # 使用集合避免重复

            # 遍历检测结果
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                # 过滤低置信度的检测
                if confidence > confidence_threshold:
                    idx = int(detections[0, 0, i, 1])
                    if 0 <= idx < len(self.classes):
                        label = self.classes[idx]
                        # 添加我们关心的物体标签 (可以根据需要扩展)
                        relevant_labels = ['background','aeroplane','bicycle','bird','boat','bottle','bus','car','cat','chair','cow','diningtable','dog','horse','motorbike','person','pottedplant','sheep','sofa','train','tvmonitor']
                        # 特别关注与产品相关的标签
                        product_related = ['bottle'] # 暂时只用bottle代表奶粉罐等
                        people_related = ['person'] # 包含'baby'概念

                        if label in relevant_labels or label in product_related or label in people_related:
                           # 对 'person' 进行细化判断 (非常粗略，仅示例)
                           if label == 'person':
                               # 尝试根据包围框大小或比例判断是否可能是'baby'
                               box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                               (startX, startY, endX, endY) = box.astype("int")
                               obj_h = endY - startY
                               obj_w = endX - startX
                               # 简单规则：如果高度小于整体高度的一半，可能是小孩或坐着的人
                               if obj_h < h * 0.5:
                                   detected_objects.add('baby/child') # 标记为宝宝/小孩
                               else:
                                   detected_objects.add('person')
                           elif label == 'bottle':
                               detected_objects.add('bottle/packaging') # 标记为瓶子/包装
                           else:
                               detected_objects.add(label)

            # 添加场景分类标签
            # 根据已检测物体添加高级场景标签
            if detected_objects:
                # 家庭场景特征
                home_indicators = {'sofa', 'chair', 'diningtable', 'tvmonitor', 'pottedplant'}
                # 育儿场景特征 
                childcare_indicators = {'baby/child', 'bottle/packaging'}
                # 户外场景特征
                outdoor_indicators = {'car', 'bus', 'bicycle', 'aeroplane', 'boat', 'bird', 'horse', 'sheep', 'cow'}
                
                # 添加场景类型标签
                if 'baby/child' in detected_objects:
                    detected_objects.add('scene/childcare')
                if len(detected_objects.intersection(home_indicators)) >= 1:
                    detected_objects.add('scene/home')
                if len(detected_objects.intersection(outdoor_indicators)) >= 1:
                    detected_objects.add('scene/outdoor')
                if 'bottle/packaging' in detected_objects and 'baby/child' in detected_objects:
                    detected_objects.add('scene/feeding')  # 喂养场景特殊标记
                    
                # 添加产品相关标签 (在实际应用中可用训练好的专门模型)
                if 'bottle/packaging' in detected_objects:
                    detected_objects.add('product/formula')  # 假设奶粉相关

            return list(detected_objects)

        except Exception as e:
            logger.exception(f"帧物体检测时出错: {e}")
            return []

    def detect_objects_in_video_segment(self, video_path: str, start_time: float, end_time: float, frames_to_sample: int = 5) -> List[str]:
        """
        检测视频片段中的物体

        参数:
            video_path: 视频文件路径
            start_time: 片段开始时间 (秒)
            end_time: 片段结束时间 (秒)
            frames_to_sample: 在片段中采样多少帧进行检测

        返回:
            该片段中检测到的所有不重复物体标签列表
        """
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return []
        if self.net is None:
            logger.error("物体检测模型未初始化")
            return []

        cap = None
        all_detected_objects = set()

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"无法打开视频: {video_path}")
                return []

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30 # 假设默认帧率
                logger.warning(f"无法获取视频帧率，使用默认值: {fps}")

            start_frame_idx = int(start_time * fps)
            end_frame_idx = int(end_time * fps)
            total_frames_in_segment = max(1, end_frame_idx - start_frame_idx)

            # 计算采样间隔
            sample_interval = max(1, total_frames_in_segment // frames_to_sample)

            current_frame_idx = start_frame_idx
            frames_sampled = 0

            while current_frame_idx <= end_frame_idx and frames_sampled < frames_to_sample:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
                success, frame = cap.read()

                if not success or frame is None:
                    logger.warning(f"无法读取视频 {video_path} 的第 {current_frame_idx} 帧")
                    current_frame_idx += sample_interval # 即使读取失败也继续尝试下一帧
                    continue

                # 检测当前帧的物体
                frame_objects = self.detect_objects_in_frame(frame)
                all_detected_objects.update(frame_objects) # 添加到集合中去重

                current_frame_idx += sample_interval
                frames_sampled += 1

            return list(all_detected_objects)

        except Exception as e:
            logger.exception(f"处理视频片段 {video_path} ({start_time}-{end_time}) 时出错: {e}")
            return []
        finally:
            if cap is not None:
                cap.release()

# 示例用法
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    analyzer = VisualAnalyzer()

    if analyzer.net:
        # 示例：检测单个图像文件 (如果需要)
        # image_path = 'path/to/your/image.jpg'
        # if os.path.exists(image_path):
        #     frame = cv2.imread(image_path)
        #     if frame is not None:
        #         objects = analyzer.detect_objects_in_frame(frame)
        #         print(f"检测到物体 (图像: {os.path.basename(image_path)}): {objects}")
        #     else:
        #         print(f"无法读取图像: {image_path}")

        # 示例：检测视频片段
        # 注意：确保测试视频路径正确
        test_video = '../../data/input/通用-保护薄弱期-HMO&自御力-启赋-CTA4修改.mp4' # 调整为实际路径
        if os.path.exists(test_video):
            start = 5.0
            end = 10.0
            video_objects = analyzer.detect_objects_in_video_segment(test_video, start, end)
            print(f"检测到物体 (视频: {os.path.basename(test_video)}, {start}-{end}s): {video_objects}")
        else:
            print(f"测试视频文件不存在: {test_video}")
    else:
        print("无法初始化视觉分析器，请检查模型文件路径和OpenCV安装。") 