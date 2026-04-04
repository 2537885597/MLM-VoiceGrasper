#!/usr/bin/env python3
"""
GraspNet ROS节点 - 抓取位姿生成核心模块

功能:
    - 接收RGB图像、深度图像和目标检测结果
    - 使用GraspNet模型生成抓取位姿
    - 发布最佳抓取位姿和相关可视化信息
    - 支持单目标和多目标抓取位姿生成
"""

import os
import sys

# 获取当前脚本目录并添加到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

# 导入ROS相关库
import rospy
import numpy as np
import cv2
import torch
import traceback
import tf2_ros
import message_filters
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField
import sensor_msgs.point_cloud2 as pc2
from geometry_msgs.msg import PoseArray, Pose, PoseStamped
from visualization_msgs.msg import Marker, MarkerArray 
from std_srvs.srv import Empty
from std_msgs.msg import String
from cv_bridge import CvBridge

# 导入自定义模块
from utils.pointcloud_utils import create_mask_from_bbox
from utils.dl_model_utils import load_graspnet_model, create_camera_info, predict_grasps
from utils.grasp_utils import create_default_grasp
from utils.visualization import create_grasp_marker

# 导入自定义消息类型
from graspnet_ros.msg import DetectedObject, DetectedObjectArray


class GraspNetROS:
    """
    GraspNet ROS节点主类
    
    功能:
        - 初始化GraspNet模型和ROS节点
        - 接收RGB图像、深度图像和检测结果
        - 生成抓取位姿并发布
        - 处理多目标场景的抓取位姿生成
    """
    
    def __init__(self):
        """
        初始化GraspNet ROS节点
        
        参数:
            rgb_topic: RGB图像话题名称 (默认: /rgb/image_raw)
            depth_topic: 深度图像话题名称 (默认: /depth_to_rgb/image_raw)
            camera_info_topic: 相机内参话题名称 (默认: /rgb/camera_info)
            detection_topic: 检测结果话题名称 (默认: /object_poses)
            model_dir: GraspNet模型目录路径
        """
        rospy.init_node('graspnet_ros')
        
        # 从参数服务器获取配置参数
        self.rgb_topic = rospy.get_param('~rgb_topic', '/rgb/image_raw')
        self.depth_topic = rospy.get_param('~depth_topic', '/depth_to_rgb/image_raw')
        self.camera_info_topic = rospy.get_param('~camera_info', '/rgb/camera_info')
        self.detection_topic = rospy.get_param('~detection_topic', '/object_poses')
        
        # 设置GraspNet模型路径
        self.model_dir = rospy.get_param('~model_dir', 
                                        '/home/rm/realman_ws/src/graspnet_ros/models/graspnet')
        self.checkpoint_path = os.path.join(self.model_dir, 'checkpoint.tar')
        
        rospy.loginfo_throttle(300, f"使用模型路径: {self.checkpoint_path}")
        
        # 初始化图像转换桥接
        self.bridge = CvBridge()
        
        # 设置发布器
        self.grasp_pub = rospy.Publisher('/best_grasp_pose', PoseStamped, queue_size=1)
        # self.all_grasps_pub = rospy.Publisher('/all_grasp_poses', PoseArray, queue_size=1)
        # self.debug_pub = rospy.Publisher('/grasp_debug', Image, queue_size=1)
        self.marker_pub = rospy.Publisher('/grasp_markers', MarkerArray, queue_size=1)
        self.grasp_cloud_pub = rospy.Publisher('/grasp_cloud', PointCloud2, queue_size=1)
        self.grasp_info_pub = rospy.Publisher('/grasp_info', String, queue_size=10)
        
        # 初始化消息缓存 - 只缓存检测结果，不缓存图像
        self.poses_msg = None
        self.rgb_msg = None
        self.depth_msg = None
        
        # 只订阅检测结果话题，不订阅图像话题
        self.detection_sub = rospy.Subscriber(self.detection_topic, DetectedObjectArray, self.detection_callback, queue_size=1)
        
        # 维护最新检测结果的字典用于标签映射
        self.latest_detections = {}
        
        # 获取相机内参
        self.camera_info = None
        self.camera_matrix = None
        self.get_camera_info()
        
        # 初始化TF监听器
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        
        # 加载GraspNet模型
        self.net, self.pred_decode, self.device = load_graspnet_model(self.checkpoint_path)
        self.model_loaded = self.net is not None
        
        rospy.loginfo_throttle(300, "GraspNet ROS节点初始化完成")
    
    def get_camera_info(self):
        """
        获取相机内参矩阵
        
        功能:
            - 等待相机内参消息
            - 提取相机内参矩阵K
            - 如果获取失败，使用默认参数
        """
        try:
            self.camera_info = rospy.wait_for_message(self.camera_info_topic, CameraInfo, timeout=5.0)
            K = self.camera_info.K
            self.camera_matrix = np.array([[K[0], K[1], K[2]], 
                                          [K[3], K[4], K[5]], 
                                          [K[6], K[7], K[8]]])
            rospy.loginfo_throttle(300, "相机内参初始化成功")
            rospy.logdebug_throttle(300, f"相机矩阵: \n{self.camera_matrix}")
        except rospy.ROSException:
            rospy.logerr_throttle(10, "无法获取相机内参")
            self.camera_matrix = np.array([[550.0, 0, 320.0], [0, 550.0, 240.0], [0, 0, 1]])
    
    def detection_callback(self, msg):
        """
        目标检测结果回调函数
        
        参数:
            msg: DetectedObjectArray消息，包含多个检测目标
            
        功能:
            - 直接处理检测结果，不再等待定时器
            - 从mlm_vision_processor获取RGB和Depth图像
        """
        rospy.loginfo("接收到检测结果，开始处理")
        self.poses_msg = msg
        
        # 立即处理检测结果
        self.process_detections_directly(msg)
    
    def process_detections_directly(self, poses_msg):
        """
        直接处理检测结果（不使用定时器）
        
        参数:
            poses_msg: DetectedObjectArray消息
        """
        try:
            # 等待RGB和深度图像
            rospy.loginfo("等待RGB和深度图像...")
            rgb_msg = rospy.wait_for_message(self.rgb_topic, Image, timeout=10.0)
            depth_msg = rospy.wait_for_message(self.depth_topic, Image, timeout=10.0)
            
            rospy.loginfo("接收到RGB和深度图像，开始处理")
            
            # 转换图像
            try:
                rgb = self.bridge.imgmsg_to_cv2(rgb_msg, "rgb8").astype(np.float32) / 255.0
                depth = self.bridge.imgmsg_to_cv2(depth_msg)
            except Exception as e:
                rospy.logerr_throttle(10, f"图像转换失败: {e}")
                return
            
            # 配置相机内参
            camera_info = create_camera_info(
                rgb.shape[1],              # 宽度
                rgb.shape[0],              # 高度
                self.camera_matrix[0, 0],  # fx
                self.camera_matrix[1, 1],  # fy
                self.camera_matrix[0, 2],  # cx
                self.camera_matrix[1, 2]   # cy
            )
            
            # 有检测结果，为每个目标生成抓取位姿
            self.process_detected_objects(rgb, depth, poses_msg, rgb_msg.header, camera_info)
            
        except rospy.ROSException as e:
            rospy.logerr_throttle(10, f"等待图像超时: {e}")
        except Exception as e:
            rospy.logerr_throttle(10, f"处理检测结果时出错: {e}")
            import traceback
            rospy.logerr_throttle(10, traceback.format_exc())
    
    def process_detected_objects(self, rgb, depth, poses_msg, header, camera_info):
        """
        处理检测到的目标，为每个目标生成抓取位姿 (完全按照 demo.py 的推理逻辑)
        
        参数:
            rgb: RGB图像 (numpy数组, float32, 0-1)
            depth: 深度图像 (numpy数组, uint16, 单位:mm)
            poses_msg: 检测结果消息
            header: 消息头，包含时间戳和坐标系信息
            camera_info: 相机内参信息
            
        功能:
            - 遍历每个检测目标
            - 使用SAM的mask或从2D边界框创建掩码
            - 为每个目标调用GraspNet生成抓取位姿
            - 收集所有抓取结果并处理
        """
        all_grasps = []
        
        # 遍历每个检测目标
        for i, obj in enumerate(poses_msg.objects):
            # 只处理第一个（置信度最高的）检测目标
            if i > 0:
                rospy.logdebug(f"跳过目标 {i+1} ({getattr(obj, 'label', '')})，只处理最优目标")
                continue
            
            # 获取2D边界框信息
            x_2d = obj.x
            y_2d = obj.y
            width = obj.width
            height = obj.height
            label = getattr(obj, 'label', '')
            
            # 计算2D中心点
            center_x = int(x_2d)
            center_y = int(y_2d)
            
            rospy.loginfo(f"为置信度最优目标 {i+1} ({label}) 生成抓取位姿，2D边界框: ({center_x}, {center_y}, {int(width)}x{int(height)})")
            
            # 优先使用SAM的mask，如果没有则从2D边界框创建掩码
            if hasattr(obj, 'mask') and len(obj.mask) > 0:
                # 将列表转换回布尔型mask
                mask = np.array(obj.mask, dtype=bool)
                # 重塑为原始图像尺寸（从vision_processor获取）
                mask = mask.reshape(rgb.shape[0], rgb.shape[1])
                mask = mask.astype(np.uint8) * 255
                rospy.loginfo_throttle(10, "使用SAM生成的mask")
            else:
                # 从2D边界框创建掩码 (按照 demo.py 的逻辑)
                mask = create_mask_from_bbox(rgb.shape[1], rgb.shape[0], 
                                            center_x, center_y, width, height)
                rospy.loginfo_throttle(10, "使用2D边界框创建的mask")
            
            # 使用GraspNet生成抓取位姿 (传递mask进行裁剪)
            gg, cloud_o3d = predict_grasps(self.net, self.pred_decode, self.device,
                                          rgb, depth, camera_info, mask=mask)
            
            # 检查预测结果
            if gg is None or cloud_o3d is None:
                rospy.logwarn(f"为目标 {i+1} ({label}) 未能生成有效的抓取位姿或点云")
                continue
            
            # 可视化抓取位姿
            self.vis_grasps(gg, cloud_o3d)
            
            # 将目标信息添加到抓取结果中
            if gg is not None and len(gg) > 0:
                # 通过 GraspGroup 获取抓取位姿
                grasp_list = []
                for i in range(len(gg)):
                    grasp = {
                        'score': gg.scores[i],
                        'width': gg.widths[i],
                        'height': gg.heights[i],
                        'depth': gg.depths[i],
                        'rotation': gg.rotation_matrices[i],
                        'point': gg.translations[i],
                        'obj_id': gg.object_ids[i],
                        'label': label,
                        'detected_center': (center_x, center_y)
                    }
                    grasp_list.append(grasp)
                
                rospy.logdebug(f"为目标 {i+1} ({label}) 生成了{len(grasp_list)}个抓取候选")
                all_grasps.extend(grasp_list)
            else:
                rospy.logdebug_throttle(10, f"为目标 {i+1} ({label}) 未生成有效的抓取候选")
        
        # 处理所有收集的抓取结果
        if all_grasps:
            self.process_grasp_results(all_grasps, header)
        else:
            rospy.logdebug_throttle(10, "未为任何目标生成有效的抓取位姿")
            self.publish_default_grasp(header)
    
    def process_grasp_results(self, grasp_results, header=None):
        """
        处理抓取结果并发布 (完全按照 demo.py 的推理逻辑)
        
        参数:
            grasp_results: 抓取结果列表，每个元素包含point, rotation, score, label等信息
            header: 消息头信息
            
        功能:
            - 选择最佳抓取位姿
            - 发布抓取位姿、标记和点云
        """
        try:
            if not grasp_results:
                rospy.logdebug_throttle(10, "未找到有效的抓取位姿")
                self.publish_default_grasp(header)
                return
                    
            # 发布最佳抓取位姿 (结果已按分数排序)
            best_grasp = grasp_results[0]
            
            # 创建PoseStamped消息
            pose_stamped = PoseStamped()
            
            # 使用提供的header或创建新的
            if header:
                pose_stamped.header = header
            else:
                pose_stamped.header.stamp = rospy.Time.now()
                pose_stamped.header.frame_id = "camera_color_optical_frame"
            
            # 设置位置 (转换为米)
            pose_stamped.pose.position.x = best_grasp['point'][0]
            pose_stamped.pose.position.y = best_grasp['point'][1]
            pose_stamped.pose.position.z = best_grasp['point'][2]
            
            # 设置方向 (将旋转矩阵转换为四元数)
            q = self._rotation_matrix_to_quaternion(best_grasp['rotation'])
            pose_stamped.pose.orientation.x = q[0]
            pose_stamped.pose.orientation.y = q[1]
            pose_stamped.pose.orientation.z = q[2]
            pose_stamped.pose.orientation.w = q[3]
            
            # 创建文本标记，显示目标标签和分数
            text_marker = Marker()
            text_marker.header = pose_stamped.header
            text_marker.ns = "grasp_labels"
            text_marker.id = 0
            text_marker.type = Marker.TEXT_VIEW_FACING
            text_marker.action = Marker.ADD
            text_marker.pose = pose_stamped.pose
            text_marker.pose.position.z += 0.05
            score_text = f"{best_grasp['score']:.2f}"
            
            if 'label' in best_grasp and best_grasp['label']:
                score_text = f"{best_grasp['label']}: {score_text}"
                
            text_marker.text = score_text
            text_marker.scale.z = 0.02
            text_marker.color.a = 1.0
            text_marker.color.r = 1.0
            text_marker.color.g = 1.0
            text_marker.color.b = 1.0
            
            # 创建MarkerArray并添加文本标记
            marker_array = MarkerArray()
            marker_array.markers.append(text_marker)
            
            # 发布抓取位姿和标记
            self.grasp_pub.publish(pose_stamped)
            self.marker_pub.publish(marker_array)
            
            # 创建包含完整信息的字符串
            label_info = best_grasp.get('label', 'Unknown object')
            grasp_info = f"目标类别: {label_info}\n" + \
                         f"位置: ({pose_stamped.pose.position.x:.3f}, {pose_stamped.pose.position.y:.3f}, {pose_stamped.pose.position.z:.3f})\n" + \
                         f"方向: 四元数({pose_stamped.pose.orientation.x:.3f}, {pose_stamped.pose.orientation.y:.3f}, " + \
                         f"{pose_stamped.pose.orientation.z:.3f}, {pose_stamped.pose.orientation.w:.3f})\n" + \
                         f"抓取分数: {best_grasp['score']:.3f}"
            
            self.grasp_info_pub.publish(grasp_info)
            
            # 发布点云
            self.publish_grasp_cloud(grasp_results)
            
            rospy.loginfo_throttle(10, f"已发布抓取位姿: 目标={label_info}, " +
                        f"位置=({pose_stamped.pose.position.x:.3f}, {pose_stamped.pose.position.y:.3f}, {pose_stamped.pose.position.z:.3f}), " +
                        f"方向=({pose_stamped.pose.orientation.x:.3f}, {pose_stamped.pose.orientation.y:.3f}, " +
                        f"{pose_stamped.pose.orientation.z:.3f}, {pose_stamped.pose.orientation.w:.3f}), " +
                        f"分数={best_grasp['score']:.2f}")
        
        except Exception as e:
            rospy.logerr_throttle(10, f"处理抓取结果失败: {e}")
            import traceback
            rospy.logerr_throttle(10, traceback.format_exc())
            self.publish_default_grasp(header)

    def vis_grasps(self, gg, cloud):
        """
        可视化抓取位姿
        
        参数:
            gg: GraspGroup对象
            cloud: 3D点云
        """
        import open3d as o3d
        
        # 检查gg是否有效
        if gg is None:
            rospy.logwarn("gg为None，无法可视化")
            return
        
        # 检查cloud是否有效
        if cloud is None:
            rospy.logwarn("cloud为None，无法可视化")
            return
        
        grippers = gg.to_open3d_geometry_list()
        o3d.visualization.draw_geometries([cloud, *grippers])
    
    def _rotation_matrix_to_quaternion(self, rot_matrix):
        """
        将旋转矩阵转换为四元数
        
        参数:
            rot_matrix: 3x3旋转矩阵
            
        返回:
            list: 四元数 [qx, qy, qz, qw]
        """
        if isinstance(rot_matrix, np.ndarray) and rot_matrix.shape != (3, 3):
            rospy.logwarn_throttle(10, f"旋转矩阵形状不正确: {rot_matrix.shape}")
            return [0, 0, -0.707, 0.707]
        
        try:
            trace = np.trace(rot_matrix)
            
            if trace > 0:
                S = np.sqrt(trace + 1.0) * 2
                qw = 0.25 * S
                qx = (rot_matrix[2, 1] - rot_matrix[1, 2]) / S
                qy = (rot_matrix[0, 2] - rot_matrix[2, 0]) / S
                qz = (rot_matrix[1, 0] - rot_matrix[0, 1]) / S
            elif rot_matrix[0, 0] > rot_matrix[1, 1] and rot_matrix[0, 0] > rot_matrix[2, 2]:
                S = np.sqrt(1.0 + rot_matrix[0, 0] - rot_matrix[1, 1] - rot_matrix[2, 2]) * 2
                qw = (rot_matrix[2, 1] - rot_matrix[1, 2]) / S
                qx = 0.25 * S
                qy = (rot_matrix[0, 1] + rot_matrix[1, 0]) / S
                qz = (rot_matrix[0, 2] + rot_matrix[2, 0]) / S
            elif rot_matrix[1, 1] > rot_matrix[2, 2]:
                S = np.sqrt(1.0 + rot_matrix[1, 1] - rot_matrix[0, 0] - rot_matrix[2, 2]) * 2
                qw = (rot_matrix[0, 2] - rot_matrix[2, 0]) / S
                qx = (rot_matrix[0, 1] + rot_matrix[1, 0]) / S
                qy = 0.25 * S
                qz = (rot_matrix[1, 2] + rot_matrix[2, 1]) / S
            else:
                S = np.sqrt(1.0 + rot_matrix[2, 2] - rot_matrix[0, 0] - rot_matrix[1, 1]) * 2
                qw = (rot_matrix[1, 0] - rot_matrix[0, 1]) / S
                qx = (rot_matrix[0, 2] + rot_matrix[2, 0]) / S
                qy = (rot_matrix[1, 2] + rot_matrix[2, 1]) / S
                qz = 0.25 * S
            
            return [qx, qy, qz, qw]
        except Exception as e:
            rospy.logerr_throttle(10, f"四元数转换错误: {e}")
            return [0, 0, -0.707, 0.707]
    
    def publish_default_grasp(self, header=None):
        """
        发布默认抓取位姿
        
        参数:
            header: 消息头 (可选)
        """
        default_pose = create_default_grasp()
        
        if header:
            default_pose.header = header
        
        self.grasp_pub.publish(default_pose)
        rospy.logdebug_throttle(10, "已发布默认抓取位姿")
    
    def publish_grasp_cloud(self, grasp_results):
        """
        发布抓取点云用于可视化
        
        参数:
            grasp_results: 抓取结果列表
            
        功能:
            - 提取所有抓取点
            - 根据分数设置颜色 (高分绿色，低分红色)
            - 发布为PointCloud2消息
        """
        if not grasp_results:
            return
            
        cloud_msg = PointCloud2()
        cloud_msg.header.frame_id = "camera_color_optical_frame"
        cloud_msg.header.stamp = rospy.Time.now()
        
        points = []
        for grasp in grasp_results:
            x, y, z = grasp['point'] / 1000.0
            r, g, b = int(255 * (1.0 - grasp['score'])), int(255 * grasp['score']), 0
            points.append([x, y, z, r, g, b])
        
        fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='r', offset=12, datatype=PointField.UINT8, count=1),
            PointField(name='g', offset=13, datatype=PointField.UINT8, count=1),
            PointField(name='b', offset=14, datatype=PointField.UINT8, count=1),
        ]
        
        cloud_msg = pc2.create_cloud(cloud_msg.header, fields, points)
        self.grasp_cloud_pub.publish(cloud_msg)


if __name__ == "__main__":
    try:
        graspnet_node = GraspNetROS()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
