#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import sys
import copy
import rospy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg
from math import pi, tau, sqrt
from std_msgs.msg import String, Bool
from moveit_commander.conversions import pose_to_list
from rm_msgs.msg import MoveJ, MoveL, JointPos, Hand_Posture
from robotic_arm_package.robotic_arm import *


class RMRobotControl:
    def __init__(self):
        # 初始化MoveIt接口
        moveit_commander.roscpp_initialize(sys.argv)
        rospy.init_node("rm_robot_control", anonymous=True)
        
        # 创建接口
        self.robot = moveit_commander.RobotCommander()
        self.scene = moveit_commander.PlanningSceneInterface()
        self.group_name = "arm"
        self.move_group = moveit_commander.MoveGroupCommander(self.group_name)
        
        # 发布者和订阅者
        self.display_trajectory_publisher = rospy.Publisher(
            "/move_group/display_planned_path",
            moveit_msgs.msg.DisplayTrajectory,
            queue_size=20,
        )
        
        # 自定义控制发布者
        self.joint_pos_pub = rospy.Publisher('/rm_driver/JointPos', JointPos, queue_size=10)
        self.hand_posture_pub = rospy.Publisher('/rm_driver/Hand_Posture', Hand_Posture, queue_size=10)
        
        # 设置规划参数
        self.set_planning_parameters()
        
        # 获取当前信息
        self.planning_frame = self.move_group.get_planning_frame()
        self.eef_link = self.move_group.get_end_effector_link()
        self.group_names = self.robot.get_group_names()
        
        print("初始化完成，规划框架:", self.planning_frame)
        print("末端执行器:", self.eef_link)
        print("机器人组:", self.group_names)

        
    def get_current_joint_angles(self):
        # 获取当前关节角度
        current_joint_values = self.move_group.get_current_joint_values()
        print("当前关节角度:", current_joint_values)
        return current_joint_values
    
    def get_current_pose(self):
        # 获取当前位姿
        current_pose = self.move_group.get_current_pose().pose
        print("当前位姿:", current_pose)
        return current_pose

    def set_planning_parameters(self):
        # 优化规划参数
        self.move_group.set_planning_time(1.0)
        self.move_group.set_num_planning_attempts(1)
        self.move_group.set_max_velocity_scaling_factor(1.0)
        self.move_group.set_max_acceleration_scaling_factor(1.0)
        self.move_group.set_goal_position_tolerance(0.01)
        self.move_group.set_goal_orientation_tolerance(0.01)
        self.move_group.set_planner_id("RRTConnect")
    
    def go_to_joint_state(self, joint_values):
        # 移动到指定关节位置
        joint_goal = self.move_group.get_current_joint_values()
        for i in range(len(joint_values)):
            if i < len(joint_goal):
                joint_goal[i] = joint_values[i]
        
        self.move_group.go(joint_goal, wait=True)
        self.move_group.stop()
        return True
    
    def go_to_home_position(self):
        # 移动到预定义的家位置
        # return self.go_to_joint_state([
        #     0.15214654760360719,
        #     1.7692206085205078,
        #     -1.3905731021881105,
        #     0.04709754793643951,
        #     -1.7764798149108887,
        #     4.231869432067871
        # ])
        return self.go_to_joint_state([-2.3009199127816844, 1.565124006725915, 1.6219170205858104, 1.0864325527814302, 1.601775921017796, 0.3278775532796548])
    
    def go_to_middle_position(self):
        # 移动到预定义的中间位置
        return self.go_to_joint_state([
            0.15214654760360719,
            0.9494021760940552,
            -2.003574113845825,
            0.046190151298046114,
            -0.49812769174575805,
            4.231258618164063
        ])
    
    def go_to_pose_goal(self, pose):
        # 移动到指定笛卡尔位姿
        self.move_group.set_pose_target(pose)
        
        # 规划并执行
        success = self.move_group.go(wait=True)
        self.move_group.stop()
        self.move_group.clear_pose_targets()
        
        return success
    
    def plan_cartesian_path(self, waypoints):
        # 规划笛卡尔路径
        (plan, fraction) = self.move_group.compute_cartesian_path(
            waypoints, 0.01, 0.0  # eef_step, jump_threshold
        )
        return plan, fraction
    
    def execute_plan(self, plan):
        # 执行预先计算的轨迹
        self.move_group.execute(plan, wait=True)
    
    def display_trajectory(self, plan):
        # 在RViz中显示轨迹
        display_trajectory = moveit_msgs.msg.DisplayTrajectory()
        display_trajectory.trajectory_start = self.robot.get_current_state()
        display_trajectory.trajectory.append(plan)
        self.display_trajectory_publisher.publish(display_trajectory)
    
    def compute_approach_pose(self, target_pose, distance=0.1):
        # 计算接近目标的预抓取位姿
        approach_pose = copy.deepcopy(target_pose)
        
        # 简单计算：沿z轴后退distance距离
        # 实际应用中可能需要更复杂的计算
        approach_pose.position.z += distance
        
        return approach_pose
    
    def open_gripper(self, width=100, speed=100, force=100):
        # 打开夹爪
        hand_msg = Hand_Posture()
        hand_msg.posture_num = width
        hand_msg.speed = speed
        hand_msg.force = force
        self.hand_posture_pub.publish(hand_msg)
        rospy.sleep(0.5)  # 等待动作完成
    
    def close_gripper(self, width=0, speed=100, force=100):
        # 关闭夹爪
        hand_msg = Hand_Posture()
        hand_msg.posture_num = width
        hand_msg.speed = speed
        hand_msg.force = force
        self.hand_posture_pub.publish(hand_msg)
        rospy.sleep(0.5)  # 等待动作完成
    
    def pick_and_place(self, pick_pose, place_pose, approach_distance=0.1):
        # 完整的抓取和放置流程
        # 1. 计算接近位姿
        pick_approach = self.compute_approach_pose(pick_pose, approach_distance)
        place_approach = self.compute_approach_pose(place_pose, approach_distance)
        
        # 2. 移动到接近抓取位姿
        print("移动到接近抓取位姿...")
        self.go_to_pose_goal(pick_approach)
        
        # 3. 打开夹爪
        print("打开夹爪...")
        self.open_gripper()
        
        # 4. 移动到抓取位姿
        print("移动到抓取位姿...")
        self.go_to_pose_goal(pick_pose)
        
        # 5. 关闭夹爪
        print("关闭夹爪...")
        self.close_gripper()
        
        # 6. 撤回到接近抓取位姿
        print("撤回到接近抓取位姿...")
        self.go_to_pose_goal(pick_approach)
        
        # 7. 移动到接近放置位姿
        print("移动到接近放置位姿...")
        self.go_to_pose_goal(place_approach)
        
        # 8. 移动到放置位姿
        print("移动到放置位姿...")
        self.go_to_pose_goal(place_pose)
        
        # 9. 打开夹爪
        print("打开夹爪...")
        self.open_gripper()
        
        # 10. 撤回到接近放置位姿
        print("撤回到接近放置位姿...")
        self.go_to_pose_goal(place_approach)
        
        print("抓取和放置完成")
        return True

def main():
    try:
        hand = Arm(RM65, '192.168.10.18')
        # 创建控制对象
        robot_control = RMRobotControl()

        hand.Set_Hand_Angle([1000,1000,1000,1000,1000,0])

        # 打印当前状态
        print("当前关节值:", robot_control.move_group.get_current_joint_values())
        print("当前位姿:", robot_control.move_group.get_current_pose().pose)

        '''
        当前关节角度: [1.5568016860961915, -0.8788517723083497, -0.15267004294395448, 0.349, -0.7820566734313965, -0.740211527633667]
记录当前关节角度: [1.5568016860961915, -0.8788517723083497, -0.15267004294395448, 0.349, -0.7820566734313965, -0.740211527633667]
输入命令: s
当前关节角度: [1.5133686637878419, -1.2586335712432861, -0.1572594014644623, 0.16026080026626588, -0.7825103239059449, -0.7401417659759522]
记录当前关节角度: [1.5133686637878419, -1.2586335712432861, -0.1572594014644623, 0.16026080026626588, -0.7825103239059449, -0.7401417659759522]
        '''


        robot_control.go_to_joint_state([1.6956513488769531, -0.8623789680480957, -0.3590162896156311, -0.27171395173072815, -0.7959119510650635, -0.4608370569229126])
        time.sleep(1)
        robot_control.go_to_joint_state([1.6955641468048095, -0.9476048149108887, -0.3584753372192383, -0.27178374667167665, -0.7948474866867066, -0.4610639154434204])
        hand.Set_Hand_Angle([500,500,500,500,500,0])
        # robot_control.go_to_middle_position()
        # # time.sleep(1)
        # robot_control.get_current_joint_angles()
        # robot_control.go_to_joint_state([-0.7554279563903809, 0.2570035945415497, 0.9406247882843017, 1.4958663425445557, -0.026471649301052093, 0.4834173345565796])
        # robot_control.get_current_joint_angles()

        
        # print("\n3. 回到家位置")
        # robot_control.go_to_home_position()
        
        # print("\n功能演示完成!")
        
    except rospy.ROSInterruptException:
        return
    except KeyboardInterrupt:
        return

if __name__ == "__main__":
    main()