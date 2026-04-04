#!/usr/bin/env python3
"""
抓取执行节点 - grasp_executor.py

功能说明:
    该节点订阅GraspNet发布的最优抓取位姿，进行手眼标定坐标转换，
    对机械臂进行IK规划，并控制灵巧手完成抓取动作。

    完整流程:
    1. 订阅 /grasp_pose 话题获取抓取位姿
    2. 使用手眼标定矩阵将相机坐标系转换到机械臂基座标系
    3. 对机械臂进行逆运动学规划
    4. 控制灵巧手执行抓取动作
"""

import sys
import os
import numpy as np
import tf.transformations as tf_trans
import tf2_ros
import tf2_geometry_msgs

import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

from robotic_arm_package.robotic_arm import *
import sys
import os

# 添加手眼标定模块路径
handeye_path = os.path.join(os.path.dirname(__file__), 'out_of_hand_homogeneous_matrix')
if handeye_path not in sys.path:
    sys.path.insert(0, handeye_path)

from eye2hand_calibration import load_hand_eye_calib
# from joint_space_planning import planning
from inspire_hand import set_hand_posture


class GraspExecutor:
    """
    抓取执行器类
    
    功能:
        - 订阅GraspNet发布的抓取位姿
        - 执行手眼标定坐标转换
        - 进行机械臂IK规划
        - 控制灵巧手抓取
    """
    
    def __init__(self):
        """
        初始化抓取执行器
        """
        rospy.init_node('grasp_executor', anonymous=True)
        
        # 初始化机械臂
        self.robot = Arm(RM65, "192.168.10.18")
        
        # # 🔥 初始化TF监听（读取easy_handeye发布的手眼标定结果）
        # self.tf_buffer = tf2_ros.Buffer()
        # self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        # # 等待手眼标定TF发布成功
        # rospy.loginfo("等待 easy_handeye 发布手眼标定TF...")
        # try:
        #     self.tf_buffer.lookup_transform("arm_link1", "camera_link", rospy.Time(0), rospy.Duration(5.0))
        #     rospy.loginfo("✅ 手眼标定TF读取成功！")
        # except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
        #     rospy.logerr("❌ 未找到手眼标定TF，请先启动 publish.launch！")
        #     sys.exit(-1)

        # 初始化手眼标定变换矩阵（直接加载保存的结果）
        self.homo_mat = load_hand_eye_calib(use_homo=True)
        self.R_handeye = self.homo_mat[:3, :3]
        self.t_handeye = self.homo_mat[:3, 3].reshape(3, 1)
        rospy.loginfo("手眼标定矩阵加载完成")
        
        # 初始化逆运动学规划器
        # self.planner = planning()
        
        # 订阅抓取位姿
        self.grasp_sub = rospy.Subscriber('/best_grasp_pose', PoseStamped, self.grasp_callback)
        
        # 订阅抓取指令
        self.command_sub = rospy.Subscriber('/grasp_command', String, self.command_callback)
        
        # 抓取位姿缓存
        self.current_grasp = None
        
        rospy.loginfo("抓取执行器初始化完成 ✅")
        rospy.loginfo("触发方式：1.相机检测 /best_grasp_pose  2.指令默认位姿 /grasp_command")

    # ===================== 【核心封装】默认抓取位姿生成方法（解耦核心）=====================
    def _get_default_grasp_pose(self):
        """
        封装默认抓取位姿：从日志中获取的娃娃抓取位姿（相机坐标系）
        单一职责：仅生成并返回标准默认抓取位姿
        """
        default_pose = PoseStamped()
        # 相机坐标系（与GraspNet发布一致）
        default_pose.header.frame_id = "camera_color_optical_frame"
        # 日志中的抓取位姿
        default_pose.pose.position.x = -0.021
        default_pose.pose.position.y = 0.096
        default_pose.pose.position.z = 0.866
        # 四元数
        default_pose.pose.orientation.x = -0.348
        default_pose.pose.orientation.y = -0.397
        default_pose.pose.orientation.z = -0.561
        default_pose.pose.orientation.w = 0.638
        return default_pose
    
    def grasp_callback(self, msg):
        """
        抓取位姿回调函数
        
        功能:
            接收GraspNet发布的抓取位姿并立即执行抓取流程
            
        参数:
            msg: PoseStamped消息
        """
        self.current_grasp = msg
        rospy.loginfo(f"收到抓取位姿: 位置=({msg.pose.position.x:.3f}, {msg.pose.position.y:.3f}, {msg.pose.position.z:.3f})")
        
        # 立即执行抓取流程
        self.execute_grasp()
        
        # 抓取完成后执行释放
        rospy.sleep(3.0)  # 等待抓取动作完成
        self.execute_release()
        
        # 清空抓取位姿
        self.current_grasp = None
    
    def command_callback(self, msg):
        """
        抓取指令回调函数
        
        功能:
            根据指令执行相应的抓取动作
            
        参数:
            msg: String消息，内容为 "grasp" 或 "release"
        """
        if msg.data == "grasp":
            rospy.loginfo("收到抓取指令 → 调用方法生成默认抓取位姿")
            # 核心：调用封装方法，赋值缓存变量
            self.current_grasp = self._get_default_grasp_pose()
            self.execute_grasp()
            rospy.Timer(rospy.Duration(3), lambda _: self.execute_release(), oneshot=True)
            rospy.Timer(rospy.Duration(3.5), lambda _: setattr(self, 'current_grasp', None), oneshot=True)
        elif msg.data == "release":
            rospy.loginfo("收到释放指令")
            self.execute_release()
        else:
            rospy.logwarn(f"未知指令: {msg.data}")
    
    # 🔥 核心：从easy_handeye获取手眼齐次矩阵
    def _get_handeye_matrix(self):
        """读取TF，生成 arm_link1 -> camera_link 的齐次矩阵"""
        trans = self.tf_buffer.lookup_transform("arm_link1", "camera_link", rospy.Time(0))

        # 平移
        x = trans.transform.translation.x
        y = trans.transform.translation.y
        z = trans.transform.translation.z
        # 旋转
        q = [
            trans.transform.rotation.x,
            trans.transform.rotation.y,
            trans.transform.rotation.z,
            trans.transform.rotation.w
        ]
        # 构建齐次矩阵
        mat = tf_trans.quaternion_matrix(q)
        mat[:3, 3] = [x, y, z]
        return mat
    
    def transform_pose_to_base(self, grasp_pose):
        """
        🔥 最终版：完全匹配睿尔曼 + 相机轴定义
        变换链：相机光学帧 → 轴方向修正 → camera_link → 手眼标定 → arm_link1
        
        参数:
            grasp_pose: PoseStamped消息（camera_color_optical_frame坐标系）
        返回:
            PoseStamped: 转换后的位姿（arm_link1基座标系）
        """
        # 1. 读取相机光学帧的抓取位姿
        x = grasp_pose.pose.position.x
        y = grasp_pose.pose.position.y
        z = grasp_pose.pose.position.z
        q = [
            grasp_pose.pose.orientation.x,
            grasp_pose.pose.orientation.y,
            grasp_pose.pose.orientation.z,
            grasp_pose.pose.orientation.w
        ]
        T_opt = tf_trans.quaternion_matrix(q)
        T_opt[:3, 3] = [x, y, z]

        # # 2. 相机内部变换（optical → camera_link）
        # T_cam_link = self.tf_buffer.lookup_transform("camera_link", "camera_color_optical_frame", rospy.Time(0))
        # mat_opt2cam = tf_trans.quaternion_matrix([
        #     T_cam_link.transform.rotation.x, T_cam_link.transform.rotation.y,
        #     T_cam_link.transform.rotation.z, T_cam_link.transform.rotation.w
        # ])
        # mat_opt2cam[:3, 3] = [
        #     T_cam_link.transform.translation.x, T_cam_link.transform.translation.y,
        #     T_cam_link.transform.translation.z
        # ]
        
        # # 修正后的相机位姿
        # T_cam = mat_opt2cam @ T_opt
        
        # # 3. 手眼标定变换（arm_link1 → camera_link）
        # T_base_cam = self._get_handeye_matrix()
        # T_base = T_base_cam @ T_cam
        
        # # 4. 安全限制（Z轴必须>0.1m）
        # if T_base[2, 3] < 0.1:
        #     T_base[2, 3] = 0.3

        T_base = self.homo_mat @ T_opt

        # # 2. 🔥 新增：定义相机到基座标系的轴对齐旋转矩阵 (关键修正点)
        # # 根据你的描述建立映射关系：
        # # 目标：将相机坐标系的点，旋转到与机械臂基座标系对齐的方向
        # # 相机 X轴(右)  -> 基座 Z轴(右)  : 所以 R[2][0] = 1
        # # 相机 Y轴(下)  -> 基座 X轴(下)  : 所以 R[0][1] = 1
        # # 相机 Z轴(前)  -> 基座 Y轴(前)  : 所以 R[1][2] = 1
        # R_align = np.array([
        #     [0, 1, 0], # 基座 X轴 由 相机 Y轴 构成 (下)
        #     [0, 0, 1], # 基座 Y轴 由 相机 Z轴 构成 (前)
        #     [1, 0, 0]  # 基座 Z轴 由 相机 X轴 构成 (右)
        # ])
        
        # # 构建4x4齐次变换矩阵
        # T_align = np.eye(4)
        # T_align[:3, :3] = R_align

        # 3. 计算最终变换：先应用轴对齐，再应用手眼标定
        # 注意：矩阵乘法顺序非常重要
        # T_base = HandEye_Matrix @ Alignment_Matrix @ Camera_Pose
        # T_base = self.homo_mat @ T_align @ T_opt
        
        # 转回位姿
        transformed_pose = PoseStamped()
        transformed_pose.header.frame_id = "arm_link1"
        transformed_pose.header.stamp = rospy.Time.now()
        transformed_pose.pose.position.x = T_base[0, 3]
        transformed_pose.pose.position.y = T_base[1, 3]
        transformed_pose.pose.position.z = T_base[2, 3]
        q_base = tf_trans.quaternion_from_matrix(T_base)
        transformed_pose.pose.orientation.x = q_base[0]
        transformed_pose.pose.orientation.y = q_base[1]
        transformed_pose.pose.orientation.z = q_base[2]
        transformed_pose.pose.orientation.w = q_base[3]
        
        rospy.loginfo("✅ 轴方向修正完成：相机→机械臂 完美匹配！")
        return transformed_pose

    # def transform_pose_to_base(self, grasp_pose):
    #     try:
    #         # 确保时间戳同步，或者使用 rospy.Time(0) 获取最新
    #         grasp_pose.header.stamp = rospy.Time(0)
            
    #         # 直接让 tf2 把位姿从相机光学帧转到机械臂基座帧
    #         # 这会自动处理 [optical -> camera_link -> arm_link1] 的所有链条
    #         base_pose = self.tf_buffer.transform(grasp_pose, "arm_link1", timeout=rospy.Duration(1.0))
            
    #         rospy.loginfo(f"TF2 转换完成: X={base_pose.pose.position.x:.3f}, Y={base_pose.pose.position.y:.3f}, Z={base_pose.pose.position.z:.3f}")
    #         return base_pose
    #     except Exception as e:
    #         rospy.logerr(f"TF 转换失败: {e}")
    #         return None
    
    def pose_to_robot_pose(self, grasp_pose):
        """
        将抓取位姿转换为机器人末端位姿格式 [x, y, z, rx, ry, rz]
        
        参数:
            grasp_pose: PoseStamped消息
            
        返回:
            list: 机器人末端位姿 [x, y, z, rx, ry, rz]
        """
        # 提取位置
        x = grasp_pose.pose.position.x
        y = grasp_pose.pose.position.y
        z = grasp_pose.pose.position.z
        
        # 从四元数获取欧拉角
        q = [
            grasp_pose.pose.orientation.x,
            grasp_pose.pose.orientation.y,
            grasp_pose.pose.orientation.z,
            grasp_pose.pose.orientation.w
        ]
        euler = tf_trans.euler_from_quaternion(q)
        
        # 转换为度数
        rx = np.degrees(euler[0])
        ry = np.degrees(euler[1])
        rz = np.degrees(euler[2])
        
        return [x, y, z, rx, ry, rz]
    
    def execute_grasp(self):
        """
        执行抓取动作
        
        功能:
            1. 检查是否有抓取位姿
            2. 转换坐标系
            3. 进行IK规划
            4. 控制灵巧手抓取
        """
        if self.current_grasp is None:
            rospy.logwarn("未收到抓取位姿，无法执行抓取")
            return
        
        rospy.loginfo("开始执行抓取流程...")
        
        # 1. 坐标系转换
        rospy.loginfo("进行坐标系转换...")
        base_pose = self.transform_pose_to_base(self.current_grasp)
        rospy.loginfo(f"基座标系下的抓取位姿: ({base_pose.pose.position.x:.3f}, {base_pose.pose.position.y:.3f}, {base_pose.pose.position.z:.3f})")
        
        # 2. 转换为机器人末端位姿
        robot_pose = self.pose_to_robot_pose(base_pose)
        rospy.loginfo(f"基座标系下的抓取位姿对应的机器人末端位姿: {robot_pose}")
        
        # 3. 进行IK规划
        rospy.loginfo("进行逆运动学规划...")
        ret = self.robot.Movep_Follow(robot_pose)
        if ret:
            rospy.logerr(f"逆运动学规划失败: {ret}")
            return
        rospy.loginfo("逆运动学规划成功")
        
        # 等待机械臂运动完成
        rospy.sleep(5.0)
        
        # 4. 控制灵巧手抓取
        rospy.loginfo("控制灵巧手抓取...")
        self.robot.Set_Hand_Force(600)  # 设置手指力度
        self.robot.Set_Hand_Seq(2)  # 执行预设抓取手势 闭合（根据需要调整）
        rospy.loginfo("抓取动作完成")
        
        rospy.loginfo("抓取流程执行完毕")
    
    def execute_release(self):
        """
        执行释放动作
        
        功能:
            控制灵巧手张开，释放物体
        """
        rospy.loginfo("开始执行释放流程...")
        
        # 控制灵巧手张开
        rospy.loginfo("控制灵巧手张开...")
        self.robot.Set_Hand_Force(600)  # 设置手指力度
        self.robot.Set_Hand_Seq(1)  # 执行预设释放手势 张开（根据需要调整）
        rospy.loginfo("释放动作完成")
        
        rospy.loginfo("释放流程执行完毕")
    
    def run(self):
        """
        运行抓取执行器
        
        功能:
            等待抓取指令并执行（可选的手动触发方式）
        """
        rospy.loginfo("抓取执行器启动，等待抓取指令...")
        
        # 发布抓取指令示例
        command_pub = rospy.Publisher('/grasp_command', String, queue_size=1)
        
        # 等待抓取指令
        rate = rospy.Rate(1.0)
        while not rospy.is_shutdown():
            rospy.loginfo_throttle(10, "等待抓取指令或抓取位姿...")
            rate.sleep()


if __name__ == '__main__':
    try:
        executor = GraspExecutor()
        executor.run()
    except rospy.ROSInterruptException:
        pass
    finally:
        # 断开连接
        if 'executor' in locals():
            executor.robot.RM_API_UnInit()
            executor.robot.Arm_Socket_Close()
