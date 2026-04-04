#!/usr/bin/env python3
"""
点云处理工具模块 - 重构版

功能:
    - 根据2D检测框创建目标掩码
"""

import numpy as np


def create_mask_from_bbox(width, height, x_center, y_center, bbox_width, bbox_height):
    """
    从2D边界框创建掩码 (按照 demo.py 的逻辑)
    
    参数:
        width: 图像宽度
        height: 图像高度
        x_center: 目标中心x坐标
        y_center: 目标中心y坐标
        bbox_width: 边界框宽度
        bbox_height: 边界框高度
        
    返回:
        numpy.ndarray: 掩码 [H, W], uint8
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    
    # 计算边界框的四个角
    x_min = int(max(0, x_center - bbox_width / 2))
    x_max = int(min(width, x_center + bbox_width / 2))
    y_min = int(max(0, y_center - bbox_height / 2))
    y_max = int(min(height, y_center + bbox_height / 2))
    
    # 在掩码上绘制矩形区域
    mask[y_min:y_max, x_min:x_max] = 255
    
    return mask
