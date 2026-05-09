#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
视觉抓取技能节点（简化方案）
订阅 MLM 决策中枢发布的抓取目标，调用 GroundingDINO 进行物体检测，
根据检测框中心和 Realsense 深度信息生成 3D 位置，固定姿态发布抓取位姿
"""

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from cv_bridge import CvBridge
import message_filters
import sys


class VisualGraspingSkill:
    def __init__(self):
        try:
            rospy.loginfo("视觉抓取技能节点（简化方案）启动中...")
            
            # GroundingDINO 配置
            self.grounding_dino_model = rospy.get_param('~grounding_dino_model', 'GroundingDINO_SwinT_OGC')
            rospy.loginfo(f"GroundingDINO 模型：{self.grounding_dino_model}")
            
            # 模型路径
            self.model_dir = rospy.get_param('~model_dir', '/home/rm/realman_ws/src/graspnet_ros/models')
            self.dino_checkpoint_path = f"{self.model_dir}/groundingdino_swinb_cogcoor.pth"
            self.dino_config_path = '/home/rm/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py'
            
            # 检测阈值
            self.box_threshold = rospy.get_param('~box_threshold', 0.35)
            self.text_threshold = rospy.get_param('~text_threshold', 0.25)
            
            # 相机内参
            self.camera_matrix = None
            self.depth_scale = 0.001  # Realsense 深度图比例因子
            
            # 图像缓存
            self.rgb_image = None
            self.depth_image = None
            
            # 当前正在处理的目标（防止重复处理）
            self.processing_target = False
            
            # 桥接器
            self.bridge = CvBridge()
            
            # 订阅者
            self.rgb_sub = message_filters.Subscriber('/camera/color/image_raw', Image)
            self.depth_sub = message_filters.Subscriber('/camera/aligned_depth_to_color/image_raw', Image)
            self.camera_info_sub = rospy.Subscriber('/camera/color/camera_info', CameraInfo, self.camera_info_callback)
            
            # 同步订阅 RGB 和深度图像
            self.ts = message_filters.ApproximateTimeSynchronizer(
                [self.rgb_sub, self.depth_sub], 
                queue_size=10, 
                slop=0.1
            )
            self.ts.registerCallback(self.image_callback)
            
            # 订阅 MLM 发布的抓取目标（方案 2 使用）
            self.target_sub = rospy.Subscriber('/simple_target_name', String, self.target_callback, queue_size=10)
            
            # 发布抓取位姿
            self.grasp_pub = rospy.Publisher('/best_grasp_pose', PoseStamped, queue_size=10)
            
            rospy.loginfo("视觉抓取技能节点（简化方案）初始化完成")
            rospy.loginfo("等待抓取目标和图像数据...")
            rospy.loginfo("订阅话题：/simple_target_name")
            
        except Exception as e:
            rospy.logfatal("❌ 视觉抓取技能节点初始化失败！")
            rospy.logfatal(f"错误信息：{str(e)}")
            import traceback
            traceback.print_exc()
            rospy.signal_shutdown("初始化失败")
    
    def camera_info_callback(self, msg):
        """相机内参回调"""
        K = msg.K
        self.camera_matrix = np.array([[K[0], K[1], K[2]], 
                                       [K[3], K[4], K[5]], 
                                       [K[6], K[7], K[8]]])
        rospy.loginfo_throttle(100, "相机内参获取成功")
    
    def target_callback(self, msg):
        """抓取目标回调（在回调函数中调用视觉抓取流程）"""
        try:
            # 防止重复处理
            if self.processing_target:
                rospy.logwarn("正在处理上一个目标，忽略当前请求")
                return
            
            object_name = msg.data
            rospy.loginfo(f"收到抓取目标：{object_name}")
            
            # 检查是否有图像数据
            if self.rgb_image is None or self.depth_image is None:
                rospy.logwarn("当前没有图像数据，等待图像...")
                return
            
            self.processing_target = True
            
            # 调用视觉抓取流程
            success = self.detect_and_generate_grasp(object_name)
            
            if success:
                rospy.loginfo(f"✅ 成功生成{object_name}的抓取位姿")
            else:
                rospy.logwarn(f"❌ 未检测到物体：{object_name}")
            
            self.processing_target = False
                
        except Exception as e:
            rospy.logerr(f"抓取目标处理失败：{str(e)}")
            import traceback
            traceback.print_exc()
            self.processing_target = False
    
    def image_callback(self, rgb_msg, depth_msg):
        """RGB-D 图像回调（仅缓存图像）"""
        try:
            # 转换图像（仅缓存，不主动触发抓取）
            self.rgb_image = self.bridge.imgmsg_to_cv2(rgb_msg, "bgr8")
            self.depth_image = self.bridge.imgmsg_to_cv2(depth_msg, "16UC1")
                
        except Exception as e:
            rospy.logerr(f"图像处理失败：{str(e)}")
    
    def detect_and_generate_grasp(self, object_name):
        """调用 GroundingDINO 检测并生成抓取位姿"""
        try:
            # 导入 GroundingDINO
            sys.path.append('/home/rm/GroundingDINO')
            from groundingdino.util.inference import load_model, load_image, predict, annotate
            import torch
            
            # 加载模型
            model = load_model(self.dino_config_path, self.dino_checkpoint_path)
            
            # 保存当前图像用于检测
            image_path = "/home/rm/realman_ws/src/microbot/mlm_decision/scripts/images/detect_input.jpg"
            cv2.imwrite(image_path, self.rgb_image)
            
            # 加载图像
            image_source, image_tensor = load_image(image_path)
            
            # GroundingDINO 检测
            with torch.no_grad():
                boxes, logits, phrases = predict(
                    model=model,
                    image=image_tensor,
                    caption=object_name,
                    box_threshold=self.box_threshold,
                    text_threshold=self.text_threshold
                )
            
            if boxes is None or len(boxes) == 0:
                rospy.logwarn(f"GroundingDINO 未检测到物体：{object_name}")
                return False
            
            rospy.loginfo(f"检测到 {len(boxes)} 个目标")
            
            # 获取最佳检测结果（置信度最高）
            best_idx = torch.argmax(logits).item()
            best_box = boxes[best_idx]
            best_score = logits[best_idx].item()
            
            rospy.loginfo(f"最佳检测：{phrases[best_idx]}, 置信度：{best_score:.2f}")
            
            # 转换边界框坐标
            h, w = self.rgb_image.shape[:2]
            xc, yc, w_box, h_box = best_box.detach().cpu().numpy()
            
            # 转换为像素坐标
            x_center = int(xc * w)
            y_center = int(yc * h)
            
            rospy.loginfo(f"检测框中心：({x_center}, {y_center})")
            
            # 获取深度值
            depth_value = self.get_depth_at_pixel(x_center, y_center)
            
            if depth_value is None or depth_value < 0.1:
                rospy.logwarn("无效的深度值")
                return False
            
            # 计算 3D 位置（相机坐标系）
            x_3d, y_3d, z_3d = self.pixel_to_3d(x_center, y_center, depth_value)
            
            rospy.loginfo(f"3D 位置：({x_3d:.3f}, {y_3d:.3f}, {z_3d:.3f})")
            
            # 生成抓取位姿
            grasp_pose = self.generate_grasp_pose(x_3d, y_3d, z_3d)
            
            # 发布抓取位姿
            self.grasp_pub.publish(grasp_pose)
            rospy.loginfo(f"已发布抓取位姿：位置=({x_3d:.3f}, {y_3d:.3f}, {z_3d:.3f}), 位姿={grasp_pose}")
            
            # 可视化检测结果
            self.visualize_detection(x_center, y_center, phrases[best_idx])
            
            return True
            
        except Exception as e:
            rospy.logerr(f"检测和生成抓取位姿失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_depth_at_pixel(self, x, y, window_size=10):
        """获取像素点周围的平均深度值"""
        try:
            if self.depth_image is None:
                return None
            
            h, w = self.depth_image.shape
            x_min = max(0, x - window_size)
            x_max = min(w, x + window_size)
            y_min = max(0, y - window_size)
            y_max = min(h, y + window_size)
            
            depth_region = self.depth_image[y_min:y_max, x_min:x_max]
            valid_depths = depth_region[(depth_region > 0) & (depth_region < 10000)]
            
            if len(valid_depths) == 0:
                return None
            
            # 转换为米
            avg_depth = np.median(valid_depths) * self.depth_scale
            return avg_depth
            
        except Exception as e:
            rospy.logerr(f"获取深度值失败：{str(e)}")
            return None
    
    def pixel_to_3d(self, u, v, depth):
        """将像素坐标转换为相机坐标系下的 3D 坐标"""
        if self.camera_matrix is None:
            rospy.logerr("相机内参未初始化")
            return 0.0, 0.0, 0.0
        
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        cx = self.camera_matrix[0, 2]
        cy = self.camera_matrix[1, 2]
        
        # 相机坐标系转换（Realsense 坐标系）
        x = (u - cx) * depth / fx
        y = (v - cy) * depth / fy
        z = depth
        
        return x, y, z
    
    def generate_grasp_pose(self, x, y, z):
        """生成抓取位姿（固定姿态，从上往下抓取）"""
        grasp_pose = PoseStamped()
        
        grasp_pose.header.stamp = rospy.Time.now()
        grasp_pose.header.frame_id = "camera_color_optical_frame"
        
        # 位置
        grasp_pose.pose.position.x = x
        grasp_pose.pose.position.y = y
        grasp_pose.pose.position.z = z
        
        # 固定姿态：从上往下抓取（与 grasp_executor 默认位姿一致）
        # 四元数：[-0.072, -0.465, -0.136, 0.872]
        grasp_pose.pose.orientation.x = -0.072
        grasp_pose.pose.orientation.y = -0.465
        grasp_pose.pose.orientation.z = -0.136
        grasp_pose.pose.orientation.w = 0.872
        
        return grasp_pose
    
    def visualize_detection(self, x, y, label):
        """可视化检测结果"""
        try:
            if self.rgb_image is None:
                return
            
            # 绘制检测点
            cv2.circle(self.rgb_image, (x, y), 10, (0, 255, 0), -1)
            cv2.putText(self.rgb_image, f"{label}", (x - 20, y - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 保存可视化结果
            vis_path = "images/grasp_detection.jpg"
            cv2.imwrite(vis_path, self.rgb_image)
            rospy.loginfo(f"已保存可视化结果：{vis_path}")
            
        except Exception as e:
            rospy.logerr(f"可视化失败：{str(e)}")


if __name__ == "__main__":
    import sys
    try:
        rospy.init_node('visual_grasping_skill', anonymous=True)
        node = VisualGraspingSkill()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点运行失败：{str(e)}")
        import traceback
        traceback.print_exc()
