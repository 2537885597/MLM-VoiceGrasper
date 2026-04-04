#!/usr/bin/env python3
"""
可视化工具模块

功能:
    - 绘制边界框
    - 可视化检测结果
    - 创建抓取位姿标记
    - 创建标记数组
"""

import rospy
import numpy as np
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA
from geometry_msgs.msg import Point
import cv2


def draw_bounding_boxes(image, boxes, scores, classes, class_names):
    """
    在图像上绘制边界框
    
    参数:
        image: 输入图像 (numpy数组)
        boxes: 边界框列表，格式为 [x1, y1, x2, y2]
        scores: 置信度分数列表
        classes: 类别ID列表
        class_names: 类别名称列表
        
    返回:
        numpy.ndarray: 绘制了边界框的图像
        
    功能:
        - 根据置信度过滤边界框
        - 绘制绿色边界框
        - 添加类别和置信度标签
    """
    for box, score, cls in zip(boxes, scores, classes):
        # ⚠️ 修改: 根据您的应用调整置信度阈值
        if score < 0.5:  # 显示框的阈值
            continue
        x1, y1, x2, y2 = box
        # ⚠️ 可选: 为不同类别自定义颜色
        color = (0, 255, 0)  # 边界框的绿色
        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        label = f"{class_names[cls]}: {score:.2f}"
        cv2.putText(image, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return image


def visualize_detections(image, detections, class_names):
    """
    可视化检测结果
    
    参数:
        image: 输入图像 (numpy数组)
        detections: 检测结果字典，包含'boxes', 'scores', 'classes'键
        class_names: 类别名称列表
        
    返回:
        numpy.ndarray: 绘制了检测结果的图像
    """
    boxes = detections['boxes']
    scores = detections['scores']
    classes = detections['classes']
    return draw_bounding_boxes(image, boxes, scores, classes, class_names)


def create_grasp_marker(position, rotation, width, score, id=0):
    """
    为抓取位姿创建可视化标记
    
    参数:
        position: 抓取点位置 (3D向量)
        rotation: 抓取方向旋转矩阵 (3x3)
        width: 抓取宽度
        score: 抓取分数
        id: 标记ID (默认0)
        
    返回:
        Marker: 抓取位姿标记
        
    功能:
        - 创建箭头标记表示抓取位姿
        - 将旋转矩阵转换为四元数
        - 根据分数设置颜色 (高分绿色，低分红色)
    """
    marker = Marker()
    # 修改: 将frame_id更改为匹配您的相机坐标系
    marker.header.frame_id = "camera_color_optical_frame"
    marker.header.stamp = rospy.Time.now()
    marker.ns = "grasp_markers"
    marker.id = id
    marker.type = Marker.ARROW
    marker.action = Marker.ADD
    
    # 设置位置
    marker.pose.position.x = float(position[0])
    marker.pose.position.y = float(position[1])
    marker.pose.position.z = float(position[2])
    
    # 从旋转矩阵计算四元数
    try:
        import tf.transformations
        matrix = np.eye(4)
        matrix[:3, :3] = rotation
        q = tf.transformations.quaternion_from_matrix(matrix)
        marker.pose.orientation.x = q[0]
        marker.pose.orientation.y = q[1]
        marker.pose.orientation.z = q[2]
        marker.pose.orientation.w = q[3]
    except:
        # 如果转换失败，使用默认方向
        marker.pose.orientation.w = 1.0
    
    # 设置箭头尺寸
    marker.scale.x = width  # 长度
    marker.scale.y = 0.01   # 宽度
    marker.scale.z = 0.01   # 高度
    
    # 根据分数设置颜色
    marker.color.r = 1.0 - score  # 分数低时更红
    marker.color.g = score        # 分数高时更绿
    marker.color.b = 0.0
    marker.color.a = 0.7
    
    # 设置生命周期
    marker.lifetime = rospy.Duration(2.0)  # 2秒
    
    return marker


def create_marker_array(pose_list, scores=None):
    """
    从多个位姿创建标记数组
    
    参数:
        pose_list: 位姿列表
        scores: 分数列表 (可选)
        
    返回:
        MarkerArray: 标记数组
    """
    marker_array = MarkerArray()
    
    for i, pose in enumerate(pose_list):
        score = scores[i] if scores is not None and i < len(scores) else 0.5
        marker = create_grasp_marker(pose, score, i)
        marker_array.markers.append(marker)
    
    return marker_array


def create_grasp_poses_marker_array(grasp_results, frame_id="camera_color_optical_frame"):
    """
    从GraspNet结果创建标记数组
    
    参数:
        grasp_results: 抓取结果列表
        frame_id: 坐标系ID (默认: "camera_color_optical_frame")
        
    返回:
        MarkerArray: 抓取位姿标记数组
        
    功能:
        - 从抓取结果创建标记
        - 限制显示前20个抓取位姿
        - 将旋转矩阵转换为四元数
    """
    from visualization_msgs.msg import MarkerArray
    from scipy.spatial.transform import Rotation
    from geometry_msgs.msg import Pose
    
    marker_array = MarkerArray()
    
    # 修改: 根据您的需求调整显示的抓取数量
    for i, grasp in enumerate(grasp_results[:20]):  # 仅显示前20个
        pose = Pose()
        pose.position.x = grasp['point'][0]
        pose.position.y = grasp['point'][1]
        pose.position.z = grasp['point'][2]
        
        # 将旋转矩阵转换为四元数
        r = Rotation.from_matrix(grasp['rotation'])
        quat = r.as_quat()  # [x, y, z, w]
        pose.orientation.x = quat[0]
        pose.orientation.y = quat[1]
        pose.orientation.z = quat[2]
        pose.orientation.w = quat[3]
        
        # 创建标记
        marker = create_grasp_marker(pose, grasp['score'], f"grasp", i)
        marker.header.frame_id = frame_id
        marker_array.markers.append(marker)
    
    return marker_array
