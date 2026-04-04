#!/usr/bin/env python3
"""
抓取位姿工具模块

功能:
    - 根据目标位姿生成抓取位姿
    - 从点云计算抓取位姿
    - 从点和方向创建抓取位姿
    - 创建默认抓取位姿
"""

import rospy
import numpy as np
import tf.transformations
from geometry_msgs.msg import PoseStamped

def generate_grasp_pose(obj_pose, frame_id="rgb_camera_link", height_offset=0.05):
    """
    根据目标位姿生成抓取位姿
    
    参数:
        obj_pose: 目标位姿 (Pose消息)
        frame_id: 坐标系ID (默认: "rgb_camera_link")
        height_offset: 高度偏移量 (默认: 0.05m，在目标上方)
        
    返回:
        PoseStamped: 抓取位姿消息
        
    功能:
        - 在目标位置上方生成抓取点
        - 设置朝下的抓取方向
        - 创建PoseStamped消息
    """
    grasp_pose = PoseStamped()
    grasp_pose.header.stamp = rospy.Time.now()
    # 修改: 将frame_id更改为匹配您的相机/机器人坐标系
    grasp_pose.header.frame_id = frame_id
    
    # 设置位置 (在目标上方)
    grasp_pose.pose.position.x = obj_pose.position.x
    grasp_pose.pose.position.y = obj_pose.position.y
    grasp_pose.pose.position.z = obj_pose.position.z + height_offset  # 抓取位置在目标上方
    
    # 设置方向 (朝下抓取)
    q = tf.transformations.quaternion_from_euler(-np.pi/2, 0, 0)
    grasp_pose.pose.orientation.x = q[0]
    grasp_pose.pose.orientation.y = q[1]
    grasp_pose.pose.orientation.z = q[2]
    grasp_pose.pose.orientation.w = q[3]
    
    return grasp_pose

def compute_grasp_from_pointcloud(pcd, camera_matrix=None):
    """
    从点云计算抓取位姿
    
    参数:
        pcd: 输入点云 (open3d.geometry.PointCloud)
        camera_matrix: 相机内参矩阵 (可选)
        
    返回:
        tuple: (PoseStamped, score) 抓取位姿和分数
        
    功能:
        - 处理点云 (下采样、去噪、法线估计)
        - 计算抓取点和抓取方向
        - 评估抓取质量分数
    """
    try:
        from . import pointcloud_utils
        
        # 处理点云
        pcd, grasp_point, grasp_direction = pointcloud_utils.process_pointcloud(pcd)
        
        if grasp_point is None:
            return None, 0.0
            
        # 计算抓取分数
        compactness = 0.5  # 默认值
        size_score = min(1.0, len(np.asarray(pcd.points)) / 100.0)  # 归一化大小
        score = 0.5 * compactness + 0.5 * size_score
        
        # 创建抓取位姿
        grasp_pose = create_grasp_pose_from_point_and_direction(grasp_point, grasp_direction)
        
        return grasp_pose, score
    except Exception as e:
        rospy.logerr(f"点云抓取计算错误: {e}")
        return None, 0.0

def create_grasp_pose_from_point_and_direction(point, direction, frame_id="camera_color_optical_frame"):
    """
    从抓取点和方向创建PoseStamped消息
    
    参数:
        point: 抓取点坐标 (3D向量)
        direction: 抓取方向 (3D向量)
        frame_id: 坐标系ID (默认: "camera_color_optical_frame")
        
    返回:
        PoseStamped: 抓取位姿消息
        
    功能:
        - 将抓取点设置为位姿位置
        - 将抓取方向转换为四元数
        - 使用轴角法计算旋转
    """
    pose = PoseStamped()
    pose.header.stamp = rospy.Time.now()
    # 修改: 将frame_id更改为匹配您的相机坐标系
    pose.header.frame_id = frame_id
    
    # 设置位置
    pose.pose.position.x = point[0]
    pose.pose.position.y = point[1]
    pose.pose.position.z = point[2]
    
    # 归一化方向向量
    direction = direction / np.linalg.norm(direction)
    
    # 创建从Z轴到目标方向的旋转
    z_axis = np.array([0, 0, 1])
    
    # 计算旋转轴和角度
    rotation_axis = np.cross(z_axis, direction)
    
    if np.linalg.norm(rotation_axis) < 1e-6:
        # 向量平行，设置默认旋转轴
        rotation_axis = np.array([1, 0, 0])
        angle = 0 if direction[2] > 0 else np.pi
    else:
        rotation_axis = rotation_axis / np.linalg.norm(rotation_axis)
        angle = np.arccos(np.dot(z_axis, direction))
    
    # 轴角到四元数
    sin_half = np.sin(angle / 2)
    qx = rotation_axis[0] * sin_half
    qy = rotation_axis[1] * sin_half
    qz = rotation_axis[2] * sin_half
    qw = np.cos(angle / 2)
    
    pose.pose.orientation.x = qx
    pose.pose.orientation.y = qy
    pose.pose.orientation.z = qz
    pose.pose.orientation.w = qw
    
    return pose

def create_default_grasp():
    """
    创建默认抓取位姿
    
    返回:
        PoseStamped: 默认抓取位姿消息
        
    功能:
        - 创建一个明显的默认抓取位姿
        - 设置在相机坐标系前方0.5m处
        - 朝下的抓取方向
    """
    pose = PoseStamped()
    pose.header.stamp = rospy.Time.now()
    # 修改: 将frame_id更改为匹配您的相机坐标系
    pose.header.frame_id = "camera_color_optical_frame"
    
    # 明显不同的默认位置
    pose.pose.position.x = 0.0
    pose.pose.position.y = 0.0
    pose.pose.position.z = 0.5
    
    # 默认方向 (朝下抓取)
    q = tf.transformations.quaternion_from_euler(-np.pi/2, 0, 0)
    pose.pose.orientation.x = q[0]
    pose.pose.orientation.y = q[1]
    pose.pose.orientation.z = q[2]
    pose.pose.orientation.w = q[3]
    
    return pose
