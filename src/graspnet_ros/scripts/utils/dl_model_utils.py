#!/usr/bin/env python3
"""
深度学习模型工具模块 - 完全按照 demo.py 的推理逻辑重构

功能:
    - GraspNet模型路径配置
    - GraspNet模块导入
    - 相机内参创建
    - GraspNet模型加载
    - 抓取位姿预测 (完全按照 demo.py 的推理逻辑)
"""

import rospy
import numpy as np
import os
import sys

import torch

ROOT_DIR = "/home/rm/realman_ws/src/graspnet-baseline"
sys.path.append(ROOT_DIR)
sys.path.append(os.path.join(ROOT_DIR, 'models'))
sys.path.append(os.path.join(ROOT_DIR, 'utils'))
sys.path.append(os.path.join(ROOT_DIR, 'dataset'))


def setup_graspnet_paths():
    """
    配置GraspNet路径
    
    功能:
        - 添加GraspNet-Baseline路径到Python路径
        - 添加子模块路径 (models, utils, dataset)
        - 验证路径是否存在
        
    返回:
        bool: 路径配置是否成功
    """
    graspnet_baseline_path = "/home/rm/realman_ws/src/graspnet-baseline"
    
    if not os.path.exists(graspnet_baseline_path):
        rospy.logerr_throttle(300, f"GraspNet-Baseline路径不存在: {graspnet_baseline_path}")
        return False
        
    if graspnet_baseline_path not in sys.path:
        sys.path.insert(0, graspnet_baseline_path)
        rospy.logdebug_throttle(300, f"添加路径: {graspnet_baseline_path}")
    
    for subdir in ['models', 'utils', 'dataset']:
        subpath = os.path.join(graspnet_baseline_path, subdir)
        if os.path.exists(subpath) and subpath not in sys.path:
            sys.path.insert(0, subpath)
            rospy.logdebug_throttle(300, f"添加子路径: {subpath}")
        
    return True


def load_graspnet_model(checkpoint_path):
    """
    加载GraspNet模型
    
    参数:
        checkpoint_path: 模型检查点路径
        
    返回:
        tuple: (模型对象, 解码函数, 设备)
    """
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    rospy.loginfo_throttle(300, f"使用设备: {device}")
    
    try:
        from graspnet import GraspNet, pred_decode
    except ImportError as e:
        rospy.logerr_throttle(10, f"无法导入GraspNet模块: {e}")
        rospy.logerr_throttle(10, "请确保 graspnet-baseline 已正确安装")
        return None, None, device
    
    try:
        net = GraspNet(input_feature_dim=0, num_view=300, num_angle=12, num_depth=4,
                      cylinder_radius=0.05, hmin=-0.02, hmax_list=[0.01, 0.02, 0.03, 0.04], 
                      is_training=False)
        net.to(device)
        
        checkpoint = torch.load(checkpoint_path, map_location=device)
        net.load_state_dict(checkpoint['model_state_dict'])
        start_epoch = checkpoint['epoch']
        rospy.loginfo_throttle(300, f"-> 加载检查点 {checkpoint_path} (epoch: {start_epoch})")
        
        net.eval()
        rospy.loginfo_throttle(300, "GraspNet模型加载成功")
        
        return net, pred_decode, device
        
    except Exception as e:
        rospy.logerr_throttle(10, f"加载GraspNet模型失败: {e}")
        import traceback
        rospy.logerr_throttle(10, traceback.format_exc())
        return None, None, device


def create_camera_info(width, height, fx, fy, cx, cy, scale=1000.0):
    """
    创建CameraInfo对象
    
    参数:
        width: 图像宽度
        height: 图像高度
        fx: X轴焦距
        fy: Y轴焦距
        cx: 主点x坐标
        cy: 主点y坐标
        scale: 深度缩放因子 (默认1000.0，即深度值单位为mm)
        
    返回:
        CameraInfo: 相机内参对象
    """
    try:
        from data_utils import CameraInfo
        return CameraInfo(width, height, fx, fy, cx, cy, scale)
    except ImportError:
        rospy.logerr_throttle(10, "无法导入CameraInfo类")
        return None


def predict_grasps(net, pred_decode, device, color, depth, camera_info, mask=None, 
                  num_point=20000, collision_thresh=0.01, voxel_size=0.01):
    """
    使用GraspNet预测抓取位姿 (完全按照 demo.py 的推理逻辑)
    
    参数:
        net: GraspNet模型
        pred_decode: 预测解码函数
        device: 设备 (CPU/GPU)
        color: RGB图像 [H, W, 3], numpy.float32 (0-1)
        depth: 深度图像 [H, W], numpy.uint16 (单位:mm)
        camera_info: CameraInfo对象
        mask: 掩码 [H, W], numpy.uint8 (可选，用于裁剪目标区域)
        num_point: 采样点数 (默认20000，与demo.py一致)
        collision_thresh: 碰撞阈值 (默认0.01，与demo.py一致)
        voxel_size: 体素大小 (默认0.01，与demo.py一致)
        
    返回:
        tuple: (gg, cloud_o3d)
            - gg: GraspGroup 抓取组对象，包含NMS和碰撞检测后的抓取
            - cloud_o3d: Open3D点云对象 (用于可视化)
    """
    try:
        from data_utils import create_point_cloud_from_depth_image
    except ImportError:
        rospy.logerr_throttle(10, "无法导入create_point_cloud_from_depth_image")
        return None
    
    try:
        from graspnetAPI import GraspGroup
    except ImportError:
        rospy.logerr_throttle(10, "无法导入GraspGroup类")
        return None

    try:
        # 1. 从深度图创建点云 (organized=True 保持图像形状)
        cloud = create_point_cloud_from_depth_image(depth, camera_info, organized=True)

        # 2. 如果提供了掩码，只保留掩码内的点
        if mask is not None:
            # 确保mask是二值的 (0或255)
            if mask.dtype != np.uint8:
                mask_binary = (mask > 0.5).astype(np.uint8) * 255
            else:
                mask_binary = mask
            mask_valid = (mask_binary > 0)
            cloud_masked = cloud[mask_valid]
            color_masked = color[mask_valid]
        else:
            cloud_masked = cloud.reshape(-1, 3)
            color_masked = color.reshape(-1, 3)
        
        # ====================== ✅ 深度过滤（关键） ======================
        depth_mask = (cloud[..., 2] > 0.05) & (cloud[..., 2] < 1.5)
        cloud = cloud[depth_mask]
        color = color[depth_mask]
        # =================================================================
        
        # 检查掩码内是否有足够的点
        if len(cloud_masked) == 0:
            rospy.logwarn("掩码内没有有效的点云数据")
            return None, None
        
        if len(cloud_masked) < 100:
            rospy.logwarn(f"掩码内点云数量过少 ({len(cloud_masked)}), 可能mask有问题")
        
        # 3. 采样点云 (demo.py 使用20000个点)
        if len(cloud_masked) >= num_point:
            idxs = np.random.choice(len(cloud_masked), num_point, replace=False)
        else:
            idxs1 = np.arange(len(cloud_masked))
            if len(cloud_masked) > 0:
                idxs2 = np.random.choice(len(cloud_masked), num_point - len(cloud_masked), replace=True)
                idxs = np.concatenate([idxs1, idxs2], axis=0)
            else:
                idxs = idxs1
        
        cloud_sampled = cloud_masked[idxs]
        color_sampled = color_masked[idxs]
        
        # 4. 转换为open3d格式 (demo.py 使用open3d)
        import open3d as o3d
        cloud_o3d = o3d.geometry.PointCloud()
        cloud_o3d.points = o3d.utility.Vector3dVector(cloud_masked.astype(np.float32))
        cloud_o3d.colors = o3d.utility.Vector3dVector(color_masked.astype(np.float32))

        # ====================== ✅ 关键修复：滤波 ======================
        # 下采样
        cloud_o3d = cloud_o3d.voxel_down_sample(voxel_size=0.005)
        # 去离群点（去掉乱飞的噪声点）
        cloud_o3d, _ = cloud_o3d.remove_statistical_outlier(nb_neighbors=20, std_ratio=1.0)
        # =================================================================

        # 5. 准备输入数据 (完全按照 demo.py 的逻辑)
        cloud_sampled_torch = torch.from_numpy(cloud_sampled[np.newaxis].astype(np.float32)).to(device)
        
        end_points = dict()
        end_points['point_clouds'] = cloud_sampled_torch
        end_points['cloud_colors'] = color_sampled
        
        # 6. 前向传播 (get_grasps)
        with torch.no_grad():
            end_points = net(end_points)
            grasp_preds = pred_decode(end_points)
        
        # 7. 创建 GraspGroup (get_grasps)
        gg_array = grasp_preds[0].detach().cpu().numpy()
        gg = GraspGroup(gg_array)
        
        # 8. 碰撞检测 (collision_detection)
        if collision_thresh > 0:
            cloud_array = np.array(cloud_o3d.points)
            gg = collision_detection(gg, cloud_array, voxel_size=voxel_size, 
                                    approach_dist=0.05, collision_thresh=collision_thresh)
        
        # 9. NMS 和排序 (vis_grasps)
        gg.nms()
        gg.sort_by_score()
        
        # 10. 限制抓取数量 (demo.py 限制为3个)
        gg = gg[:3]
        
        rospy.loginfo_throttle(10, f"生成了 {len(gg)} 个抓取候选 (使用 GraspGroup + NMS + 碰撞检测)")
        return gg, cloud_o3d
        
    except Exception as e:
        rospy.logerr_throttle(10, f"抓取预测失败: {e}")
        import traceback
        rospy.logerr_throttle(10, traceback.format_exc())
        return None, None


def collision_detection(gg, cloud, voxel_size=0.01, approach_dist=0.05, collision_thresh=0.01):
    """
    碰撞检测 (完全按照 demo.py 的推理逻辑)
    
    参数:
        gg: GraspGroup 对象
        cloud: 点云 [N, 3]
        voxel_size: 体素大小
        approach_dist: 接近距离
        collision_thresh: 碰撞阈值
        
    返回:
        GraspGroup: 过滤后的抓取组
    """
    try:
        from collision_detector import ModelFreeCollisionDetector
        mfcdetector = ModelFreeCollisionDetector(cloud, voxel_size=voxel_size)
        collision_mask = mfcdetector.detect(gg, approach_dist=approach_dist, 
                                           collision_thresh=collision_thresh)
        valid_mask = ~collision_mask
        return gg[valid_mask]
    except ImportError:
        rospy.logwarn_throttle(10, "无法导入碰撞检测器，跳过碰撞检测")
        return gg
