#!/usr/bin/env python3
import rospy
import moveit_commander
import sys
import copy
import tty
import termios
from rm_robot_control import RMRobotControl
from robotic_arm_package.robotic_arm import *

class RobotPathRecorder:
    def __init__(self):
        # 初始化机械臂连接
        self.arm = Arm(RM65, "192.168.10.18")
        
        # 初始化ROS节点和MoveIt接口
        moveit_commander.roscpp_initialize(sys.argv)
        self.robot_control = RMRobotControl()
        
        # 存储路径点 [(joint_angles, hand_angles), ...]
        self.waypoints = []  
        # 灵巧手初始角度（全开状态）
        self.current_hand_angles = [1000] * 6  
        self.STEP_SIZE = 50  # 灵巧手单次调整步长
        
        # 灵巧手控制按键映射
        self.KEY_BINDINGS = {
            'a': (0, +self.STEP_SIZE), 'z': (0, -self.STEP_SIZE),
            's': (1, +self.STEP_SIZE), 'x': (1, -self.STEP_SIZE),
            'd': (2, +self.STEP_SIZE), 'c': (2, -self.STEP_SIZE),
            'f': (3, +self.STEP_SIZE), 'v': (3, -self.STEP_SIZE),
            'g': (4, +self.STEP_SIZE), 'b': (4, -self.STEP_SIZE),
            'h': (5, +self.STEP_SIZE), 'n': (5, -self.STEP_SIZE)
        }
        
        # 设置灵巧手初始状态
        self.arm.Set_Hand_Force(600)
        self.update_hand_angles()

    def getch(self):
        """获取单个键盘输入（无需回车）"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def update_hand_angles(self):
        """更新灵巧手角度并发送到机械臂"""
        clamped_angles = [max(0, min(1000, angle)) for angle in self.current_hand_angles]
        self.arm.Set_Hand_Angle(clamped_angles)
        print(f"当前灵巧手角度: {clamped_angles}")
        return clamped_angles

    def print_help(self):
        """显示帮助信息"""
        print("\n=== 路径记录控制 ===")
        print("  o - 记录当前关节和灵巧手角度")
        print("  p - 仅更新灵巧手角度")
        print("  q - 停止记录并执行路径")
        print("\n=== 灵巧手控制 ===")
        print("  a/z - 手指1增加/减少 (0-1000)")
        print("  s/x - 手指2增加/减少")
        print("  d/c - 手指3增加/减少")
        print("  f/v - 手指4增加/减少")
        print("  g/b - 手指5增加/减少")
        print("  h/n - 手指6增加/减少")
        print("---------------------")

    def save_path_to_file(self, filename="saved_path.txt"):
        """将记录的路径点保存到文件"""
        if not self.waypoints:
            print("没有路径点可保存")
            return
        
        with open(filename, 'w') as f:
            for i, (joint_angles, hand_angles) in enumerate(self.waypoints):
                # 写入序号
                f.write(f"# 路径点 {i+1}\n")
                
                # 写入关节角度
                f.write("joint_angles: [")
                f.write(", ".join(f"{angle:.4f}" for angle in joint_angles))
                f.write("]\n")
                
                # 写入灵巧手角度
                f.write("hand_angles: [")
                f.write(", ".join(str(angle) for angle in hand_angles))
                f.write("]\n\n")
        
        print(f"路径已保存到 {filename}")

    def record_path(self):
        """记录路径点（关节角度和灵巧手角度）"""
        print("开始路径记录，输入 'h' 查看帮助")
        while True:
            self.print_help()
            key = self.getch().lower()
            
            if key == 'o':
                # 记录关节角度
                current_joints = self.robot_control.get_current_joint_angles()
                current_degree = self.arm.Get_Joint_Degree()
                print(f"记录关节角度: {current_joints}")
                print(f"记录关节角度(度数): {current_degree[1][0:6]}")
                
                # 记录当前灵巧手状态
                hand_angles = self.update_hand_angles()
                
                # 保存路径点
                self.waypoints.append((copy.deepcopy(current_joints), copy.deepcopy(hand_angles)))
                rospy.sleep(0.5)
                
            elif key == 'p':
                # 只记录灵巧手角度
                hand_angles = self.update_hand_angles()
                if self.waypoints:
                    # 更新最后一个路径点的灵巧手角度
                    last_joints, _ = self.waypoints[-1]
                    self.waypoints[-1] = (last_joints, copy.deepcopy(hand_angles))
                    print("更新最后一个路径点的灵巧手角度")
                else:
                    print("请先记录关节角度（按'o'）")
                
            elif key in self.KEY_BINDINGS:
                # 调整灵巧手角度
                finger_idx, delta = self.KEY_BINDINGS[key]
                self.current_hand_angles[finger_idx] += delta
                self.current_hand_angles[finger_idx] = max(0, min(1000, self.current_hand_angles[finger_idx]))
                self.update_hand_angles()
                
            elif key == 'q':
                print("停止记录，准备执行路径")
                save = input("是否保存路径到文件? (y/n): ").lower()
                if save == 'y':
                    filename = input("输入保存文件名(默认:saved_path.txt): ") or "saved_path.txt"
                    self.save_path_to_file(filename)
                break
                
            elif key == 'h':
                self.print_help()

    def execute_path(self):
        """执行记录的路径"""
        if not self.waypoints:
            print("没有记录任何路径点，无法执行。")
            return
        
        print(f"准备执行 {len(self.waypoints)} 个路径点...")
        input("按Enter键开始执行路径...")
        
        # 保存初始状态
        initial_hand = copy.deepcopy(self.current_hand_angles)
        initial_joints = self.robot_control.get_current_joint_angles()
        

        # 1. 执行前归位：先灵巧手归位，再关节归位
        print("\n执行前归位...")
        print("灵巧手归位...")
        self.arm.Set_Hand_Angle([1000]*6)  # 全开状态
        rospy.sleep(0.5)
        
        print("关节归位...")
        self.robot_control.go_to_joint_state(initial_joints)
        rospy.sleep(1.0)
        
        # 2. 开始执行记录的路径
        for i, (joint_state, hand_angles) in enumerate(self.waypoints):
            print(f"\n执行路径点 {i + 1}/{len(self.waypoints)}")
            print(f"关节目标角度: {joint_state}")
            print(f"灵巧手目标角度: {hand_angles}")
            
            # 先移动关节
            print("移动关节到目标位置...")
            self.robot_control.go_to_joint_state(joint_state)
            rospy.sleep(1.0)
            
            # 再设置灵巧手角度
            print("设置灵巧手角度...")
            self.arm.Set_Hand_Angle(hand_angles)
            rospy.sleep(0.5)
        
        print("\n路径执行完成！")

            # 3. 执行完成后归位：先灵巧手归位，再关节归位
            # print("\n执行完成后归位...")
            # print("灵巧手归位...")
            # self.arm.Set_Hand_Angle([1000]*6)  # 全开状态
            # rospy.sleep(0.5)
            
            # print("关节归位...")
            # self.robot_control.go_to_joint_state(initial_joints)
            # rospy.sleep(1.0)
            
            # print("已完全归位")
        

if __name__ == "__main__":
    try:
        recorder = RobotPathRecorder()
        recorder.record_path()
        recorder.execute_path()
        
    except rospy.ROSInterruptException:
        print("ROS中断异常")
    except KeyboardInterrupt:
        print("用户中断程序")
    except Exception as e:
        print(f"程序异常: {str(e)}")
    finally:
        # 确保关闭连接oo
        recorder.arm.Arm_Socket_Close()
        print("机械臂连接已关闭")