#!/usr/bin/env python3
"""
SAM+GroundingDINO视觉决策节点 - vision_processor.py

功能说明:
    该节点接收RGB图像和深度图像，使用GroundingDINO进行目标检测，
    使用SAM进行精确分割，并将检测结果发布到 /object_poses 话题。

    完整流程:
    1. 接收RGB-D图像
    2. 使用GroundingDINO进行文本提示的目标检测
    3. 使用SAM对检测到的目标进行精确分割
    4. 发布2D检测结果到 /object_poses 话题

作者: graspnet_ros团队
版本: 1.0
"""

import os
import sys

# ROS相关导入
import rospy
import cv2
import numpy as np
import message_filters
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge

# 导入自定义消息类型
from graspnet_ros.msg import DetectedObject, DetectedObjectArray

# SAM和GroundingDINO导入
sys.path.append('/home/rm/GroundingDINO')

from groundingdino.util.inference import load_model, load_image, predict, annotate
import groundingdino.datasets.transforms as T
from segment_anything import SamPredictor, sam_model_registry
import torch

import torchvision.transforms as transforms
import PIL


class SAMGroundingDINOVisualDecision:
    """
    SAM+GroundingDINO视觉决策器
    
    功能:
        - 使用GroundingDINO进行文本提示的目标检测
        - 使用SAM进行精确的实例分割
        - 提供默认检测作为备选方案
    """
    
    def __init__(self, text_prompt="object", box_threshold=0.3, text_threshold=0.3):
        """
        初始化SAM+GroundingDINO视觉决策器
        
        参数:
            text_prompt: 文本提示（想检测什么就写什么）
            box_threshold: 检测框置信度阈值（0~1），低于该值的框会被过滤
            text_threshold: 文本 - 图像匹配阈值（0~1），过滤与文本不匹配的结果
        """
        self.text_prompt = text_prompt
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        
        # 加载GroundingDINO模型（使用官方库）
        rospy.loginfo("加载GroundingDINO模型...")
        self.dino_model_dir = rospy.get_param('~model_dir', '/home/rm/realman_ws/src/graspnet_ros/models')
        self.dino_checkpoint_path = os.path.join(self.dino_model_dir, 'groundingdino_swinb_cogcoor.pth')
        self.dino_config_path = '/home/rm/GroundingDINO/groundingdino/config/GroundingDINO_SwinB_cfg.py'
        rospy.loginfo_throttle(300, f"使用GroundingDINO模型路径: {self.dino_checkpoint_path}")
        rospy.loginfo_throttle(300, f"使用GroundingDINO配置路径: {self.dino_config_path}")
        self.det_model = load_model(self.dino_config_path, self.dino_checkpoint_path)
        rospy.loginfo("GroundingDINO模型加载完成")
        
        # 加载SAM模型（使用官方库）
        rospy.loginfo("加载SAM模型...")
        self.sam_model_dir = rospy.get_param('~model_dir', '/home/rm/realman_ws/src/graspnet_ros/models')
        self.sam_checkpoint_path = os.path.join(self.sam_model_dir, 'sam_vit_b.pth')
        rospy.loginfo_throttle(300, f"使用SAM模型路径: {self.sam_checkpoint_path}")
        self.sam = sam_model_registry["vit_b"](checkpoint=self.sam_checkpoint_path)
        self.predictor = SamPredictor(self.sam)
        rospy.loginfo("SAM模型加载完成")
        
        rospy.loginfo("SAM+GroundingDINO视觉决策器初始化完成")
        rospy.loginfo_throttle(300, f"文本提示: {self.text_prompt}")
    
    def detect_and_segment(self, cv_image, user_intent=None):
        """
        运行视觉抓取决策（检测+分割）
        
        参数:
            cv_image: OpenCV图像 (numpy数组，BGR格式)
            user_intent: 用户输入的意图（可选，覆盖默认提示）
            
        返回:
            list: 检测结果列表，每个元素包含class_name, x, y, width, height, confidence, mask
        """
        try:
            # 使用用户意图或默认提示
            prompt = user_intent if user_intent else self.text_prompt
            
            rospy.loginfo(f"使用文本提示进行检测: {prompt}")

            # ===================== 保存图片 + 校验 =====================
            # 保存到当前工作目录（你能直接看到这个图片！）
            save_path = "/home/rm/realman_ws/src/graspnet_ros/imgs/detect_input.jpg"
            save_success = cv2.imwrite(save_path, cv_image)
            if not save_success:
                rospy.logerr(f"错误：无法保存图片到 {save_path}")
                return self.get_default_detections()
            rospy.loginfo(f"图片已成功保存到：{save_path}")

            # 传入路径给load_image（旧版函数只认路径！）
            image_source, image_tensor = load_image(save_path)
            # ==================================================
            
            # 第一步：GroundingDINO检测 返回检测框(0~1)、置信度分数(0~1)、目标类别名称
            with torch.no_grad():
                boxes, logits, phrases = predict(
                    model=self.det_model,       # GroundingDINO模型
                    image=image_tensor,         # 输入图像张量  
                    caption=prompt,             # 文本提示
                    box_threshold=self.box_threshold,        # 检测框置信度阈值
                    text_threshold=self.text_threshold       # 文本 - 图像匹配阈值
                )
            
            if boxes is None or len(boxes) == 0:
                rospy.logwarn("GroundingDINO未检测到任何目标")
                return self.get_default_detections()
            else:
                rospy.loginfo_throttle(10, f"GroundingDINO检测到 {len(boxes)} 个目标")
                rospy.loginfo_throttle(10, f"GroundingDINO检测到的目标类别: {phrases}")
                # ========== 可视化检测结果 ==========
                annotated_frame = annotate(image_source=image_source, boxes=boxes, logits=logits, phrases=phrases)
                cv2.imwrite(save_path.replace(".jpg", "_annotated_image.jpg"), annotated_frame)
                rospy.loginfo_throttle(10, f"boxes: {boxes}")
                # ========== 坐标转换 ==========
                h, w = cv_image.shape[:2]
                rospy.loginfo_throttle(10, f"图像尺寸: {w}x{h}")
                boxes_abs = []
                boxes_abs_sam = []
                for box in boxes:
                    xc, yc, w_box, h_box = box.detach().cpu().numpy()
                    rospy.loginfo_throttle(10, f"原始检测框坐标: {xc}, {yc}, {w_box}, {h_box}")
                    # 确保是归一化坐标（理论上 predict 返回的就是 0~1）
                    xc, yc, w_box, h_box = xc * w, yc * h, w_box * w, h_box * h
                    rospy.loginfo_throttle(10, f"检测框坐标: {xc}, {yc}, {w_box}, {h_box}")
                    boxes_abs.append([xc, yc, w_box, h_box])
                    x1 = int(xc - w_box / 2)
                    y1 = int(yc - h_box / 2)
                    x2 = int(x1 + w_box)
                    y2 = int(y1 + h_box)
                    boxes_abs_sam.append([x1, y1, x2, y2])
                    rospy.loginfo_throttle(10, f"SAM检测框坐标: {x1}, {y1}, {x2}, {y2}")


            # 第二步：SAM分割
            cv_image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)   # 转为 RGB
            self.predictor.set_image(cv_image_rgb)
            
            # 对每个检测框进行SAM分割
            masks = []
            for box in boxes_abs_sam:
                input_box_np = np.array(box)
                mask_output, _, _ = self.predictor.predict(box=input_box_np)
                if mask_output is not None and len(mask_output) > 0:
                    masks.append(mask_output[0])
                    rospy.loginfo_throttle(10, f"SAM分割到 {len(mask_output[0])} 个像素")
                    rospy.loginfo_throttle(10, f"SAM分割到的像素值: {mask_output[0]}")
                else:
                    rospy.logwarn_throttle(10, "SAM分割未返回有效像素")
                    masks.append(None)
            
            # 处理检测结果
            detections = []
            for i, (box_abs, conf, phrase) in enumerate(zip(boxes_abs, logits, phrases)):
                if conf < self.box_threshold:
                    continue
                
                # 获取边界框信息
                xc, yc, w_box, h_box = box_abs
                x_center = int(xc)
                y_center = int(yc)
                width = int(w_box)
                height = int(h_box)
                
                detection = {
                    'class_name': phrase,
                    'x': x_center,
                    'y': y_center,
                    'width': width,
                    'height': height,
                    'confidence': float(conf),
                    'mask': masks[i] if i < len(masks) and masks[i] is not None else None
                }
                detections.append(detection)
            
            if not detections:
                rospy.logwarn("未检测到满足置信度阈值的目标")
                return self.get_default_detections()
            
            rospy.loginfo(f"成功检测到 {len(detections)} 个目标")
            return detections
            
        except Exception as e:
            rospy.logerr(f"检测和分割失败: {e}")
            import traceback
            traceback.print_exc()
            return self.get_default_detections()
    
    def get_default_detections(self):
        """
        获取默认检测结果（当模型不可用时）
        
        返回:
            list: 默认检测结果列表
        """
        rospy.logwarn("使用默认检测结果（模型不可用）")
        return [{
            'class_name': 'object',
            'x': 320,
            'y': 240,
            'width': 100,
            'height': 100,
            'confidence': 0.8,
            'mask': None
        }]
    
    def set_text_prompt(self, prompt):
        """
        设置文本提示
        
        参数:
            prompt: 文本提示（例如："black cup"）
        """
        self.text_prompt = prompt
        rospy.loginfo(f"文本提示已更新: {self.text_prompt}")


class Detector3DNode:
    """
    SAM+GroundingDINO视觉决策节点类
    
    功能:
        - 接收RGB图像和深度图像
        - 使用GroundingDINO进行目标检测
        - 使用SAM进行精确分割
        - 发布2D检测结果
    """
    
    def __init__(self):
        """
        初始化SAM+GroundingDINO视觉决策节点
        """
        rospy.init_node('detector_3d_node')
        
        # 从参数服务器获取配置参数
        self.rgb_topic = rospy.get_param('~rgb_topic', '/camera/color/image_raw')
        self.depth_topic = rospy.get_param('~depth_topic', '/camera/aligned_depth_to_color/image_raw')
        self.text_prompt = rospy.get_param('~text_prompt', 'object')
        self.box_threshold = rospy.get_param('~box_threshold', 0.3)
        self.text_threshold = rospy.get_param('~text_threshold', 0.3)
        self.trigger_vision = rospy.get_param('~trigger_vision', True)
        
        # 初始化图像桥接器
        self.bridge = CvBridge()
        
        # 初始化SAM+GroundingDINO视觉决策器
        self.decision_maker = SAMGroundingDINOVisualDecision(
            text_prompt=self.text_prompt,
            box_threshold=self.box_threshold,
            text_threshold=self.text_threshold
        )
        
        rospy.loginfo(f"文本提示: {self.text_prompt}")
        rospy.loginfo(f"检测框置信度阈值: {self.box_threshold}")
        rospy.loginfo(f"文本匹配阈值: {self.text_threshold}")
        
        # 创建订阅者
        # 使用message_filters进行时间同步，确保RGB和深度图像来自同一时刻
        self.rgb_sub = message_filters.Subscriber(self.rgb_topic, Image)
        self.depth_sub = message_filters.Subscriber(self.depth_topic, Image)
        
        # 创建时间同步器，允许0.1秒的时间差
        self.ts = message_filters.ApproximateTimeSynchronizer([self.rgb_sub, self.depth_sub], 10, 0.1)
        self.ts.registerCallback(self.image_callback)
        
        # 创建发布者
        self.object_pub = rospy.Publisher('/object_poses', DetectedObjectArray, queue_size=1)
        self.detection_pub = rospy.Publisher('/detection_image', Image, queue_size=1)
        self.rgb_pub = rospy.Publisher(self.rgb_topic, Image, queue_size=1)
        self.depth_pub = rospy.Publisher(self.depth_topic, Image, queue_size=1)

        rospy.loginfo("SAM+GroundingDINO视觉决策节点初始化完成")
    
    def vision_process(self, cv_rgb, rgb_msg, depth_msg):
        """
        对RGB图像进行视觉决策处理（检测和分割）
        
        参数:
            cv_rgb: 输入的OpenCV格式RGB图像
            rgb_msg: ROS Image消息（包含图像元数据）
            depth_msg: ROS Image消息（包含深度图像元数据）
        
        返回:
            list: 检测到的目标信息列表
        """
        # 打印处理提示
        rospy.loginfo_throttle(10, "模型正在处理图像，请稍候...")
        
        # 调用SAM+GroundingDINO视觉决策器
        detections = self.decision_maker.detect_and_segment(cv_rgb)
        
        # 存储检测到的目标信息
        detected_objects = []
        
        # 处理每个检测结果
        for det in detections:
            # 获取检测信息
            class_name = det.get('class_name', 'unknown')
            conf = det.get('confidence', 0.0)
            x = int(det.get('x', 0))
            y = int(det.get('y', 0))
            width = int(det.get('width', 0))
            height = int(det.get('height', 0))
            mask = det.get('mask', None)
        
            # 打印检测信息
            rospy.logdebug(f"检测到的目标: {class_name}, 置信度: {conf:.2f}, 2D边界框: ({x}, {y}, {width}x{height})")
        
            # 创建检测对象
            detected_object = {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'label': class_name,
                'confidence': conf,
                'mask': mask
            }
        
            detected_objects.append(detected_object)
        
            # 在图像上绘制检测框和标签
            x_min = int(x - width/2)
            y_min = int(y - height/2)
            x_max = int(x + width/2)
            y_max = int(y + height/2)
        
            cv2.rectangle(cv_rgb, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
            cv2.putText(cv_rgb, f"{class_name}: {conf:.2f}", 
                       (x_min, y_min - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
            # ===================== 【修复】正确绘制SAM mask =====================
            if mask is not None:
                # 适配SAM布尔型mask，直接上色+透明叠加
                overlay = cv_rgb.copy()
                overlay[mask] = (0, 255, 0)  # 绿色遮罩
                cv_rgb = cv2.addWeighted(overlay, 0.5, cv_rgb, 0.5, 0)
        
        # 发布检测结果
        self.publish_detected_objects(rgb_msg.header, detected_objects)
        self.detection_pub.publish(self.bridge.cv2_to_imgmsg(cv_rgb, "bgr8"))
        
        # 发布RGB和深度图像（供GraspNet使用）
        self.rgb_pub.publish(rgb_msg)
        self.depth_pub.publish(depth_msg)

    def image_callback(self, rgb_msg, depth_msg):
        """
        RGB-D图像回调函数
        
        功能:
            处理接收到的RGB图像和深度图像:
            1. 转换图像格式
            2. 使用GroundingDINO进行目标检测
            3. 使用SAM进行精确分割
            4. 发布2D检测结果
            
        参数:
            rgb_msg: RGB图像消息
            depth_msg: 深度图像消息
        """
        try:
            # 将ROS图像消息转换为OpenCV图像
            cv_rgb = self.bridge.imgmsg_to_cv2(rgb_msg, "bgr8")
            cv_depth = self.bridge.imgmsg_to_cv2(depth_msg, "16UC1")
            if self.trigger_vision:
                self.vision_process(cv_rgb, rgb_msg, depth_msg)
                self.trigger_vision = False
            
        except Exception as e:
            rospy.logerr(f"处理图像时出错: {e}")
            import traceback
            traceback.print_exc()

    def publish_detected_objects(self, header, detected_objects):
        """
        发布检测到的目标列表
        
        功能:
            将检测结果封装为DetectedObjectArray消息并发布
            
        参数:
            header: 消息头 (包含时间戳和坐标系信息)
            detected_objects: 检测对象列表
        """
        try:
            # 创建DetectedObjectArray消息
            msg = DetectedObjectArray()
            msg.header = header
            
            # 处理每个检测对象
            for obj in detected_objects:
                # 创建DetectedObject消息
                det_obj = DetectedObject()
                det_obj.label = obj.get('label', '')
                det_obj.confidence = obj.get('confidence', 0.0)
                det_obj.x = obj.get('x', 0.0)
                det_obj.y = obj.get('y', 0.0)
                det_obj.width = obj.get('width', 0.0)
                det_obj.height = obj.get('height', 0.0)
                
                # 发布mask数据（转换为列表）
                mask = obj.get('mask', None)
                if mask is not None:
                    # 将布尔型mask转换为列表
                    det_obj.mask = mask.flatten().tolist()
                else:
                    det_obj.mask = []
                
                # 添加到数组
                msg.objects.append(det_obj)
            
            # 发布消息
            self.object_pub.publish(msg)
            rospy.logdebug_throttle(10, f"已发布 {len(msg.objects)} 个检测结果")
        except Exception as e:
            rospy.logerr(f"发布检测结果时出错: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    try:
        # 创建节点实例
        node = Detector3DNode()
        # 等待ROS关闭
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        # 关闭所有OpenCV窗口
        cv2.destroyAllWindows()
