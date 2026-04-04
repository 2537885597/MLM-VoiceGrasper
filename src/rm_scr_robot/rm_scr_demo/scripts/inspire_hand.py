#!/usr/bin/env python3
import sys
import tty
import termios
from robotic_arm_package.robotic_arm import *

# 初始化机械臂
robot = Arm(RM65, "192.168.10.18")  # 根据实际型号修改

# 手指初始角度（全开状态）
finger_angles = [1000, 1000, 1000, 1000, 1000, 1000]  # 6个手指，范围0（完全闭合）~1000（完全张开）
STEP_SIZE = 50  # 单次按键调整步长

# 按键映射（每个手指2个按键：增加/减少）
KEY_BINDINGS = {
    'a': (0, +STEP_SIZE),  # 手指1 增加（张开）
    'z': (0, -STEP_SIZE),  # 手指1 减少（闭合）
    's': (1, +STEP_SIZE),  # 手指2 增加
    'x': (1, -STEP_SIZE),  # 手指2 减少
    'd': (2, +STEP_SIZE),  # 手指3 增加
    'c': (2, -STEP_SIZE),  # 手指3 减少
    'f': (3, +STEP_SIZE),  # 手指4 增加
    'v': (3, -STEP_SIZE),  # 手指4 减少
    'g': (4, +STEP_SIZE),  # 手指5 增加
    'b': (4, -STEP_SIZE),  # 手指5 减少
    'h': (5, +STEP_SIZE),  # 手指6 增加
    'n': (5, -STEP_SIZE)   # 手指6 减少
}

def getch():
    """获取单个键盘输入（无需回车）"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def update_fingers():
    """发送当前角度到机械手"""
    # 限制角度范围在0-1000之间
    clamped_angles = [max(0, min(1000, angle)) for angle in finger_angles]
    robot.Set_Hand_Angle(clamped_angles)
    print(f"当前角度: {clamped_angles}")

def print_help():
    """显示帮助信息"""
    print("\n=== 灵巧手直接控制 ===")
    print("按键分配（每个手指2个键）：")
    print("  a/z - 手指1增加/减少 (0-1000)")
    print("  s/x - 手指2增加/减少")
    print("  d/c - 手指3增加/减少")
    print("  f/v - 手指4增加/减少")
    print("  g/b - 手指5增加/减少")
    print("  h/n - 手指6增加/减少")
    print("  q   - 退出程序")
    print("---------------------")

def change_finger_angle():
    print_help()
    #update_fingers()
    while True:
        key = getch().lower()
        
        # 退出程序
        if key == 'q':
            print("退出控制程序")
            break
        
        # 检查是否为有效控制键
        if key in KEY_BINDINGS:
            finger_idx, delta = KEY_BINDINGS[key]
            # 更新角度，确保不超过范围
            new_angle = finger_angles[finger_idx] + delta
            if new_angle < 0:
                finger_angles[finger_idx] = 0  # 最小值限制
            elif new_angle > 1000:
                finger_angles[finger_idx] = 1000  # 最大值限制
            else:
                finger_angles[finger_idx] = new_angle  # 更新角度

            update_fingers()
        else:
            print_help()

def set_hand_posture():
    """执行预设手势 万不得以不要用"""
    print("可用预设手势编号：1-40，按q退出")
    while True:
        posture_num = int(input("输入预设手势编号: ").strip())
        if posture_num == 'q':
            print("退出预设手势控制")
            break
        if 1 <= posture_num <= 40:
            robot.Set_Hand_Posture(posture_num)
            print(f"已设置预设手势 {posture_num}")
        else:
            print("无效的手势编号，请输入1-40之间的数字。")

def reset_finger_angles():
    """重置手指角度"""
    finger_angles_reset = [-1, -1, -1, 1000, 1000, 1000]
    # robot.Set_Hand_Follow_Angle(finger_angles_reset)
    robot.Set_Hand_Angle(finger_angles_reset)

def set_hand_seq():
    """执行预设手势序列 1张开 2闭合 是安全的操作"""
    print("可用预设动作序列编号：1-40，按q退出")
    while True:
        posture_num = int(input("输入预设动作序列编号: ").strip())
        if posture_num == 'q':
            print("退出预设动作序列控制")
            break
        if 1 <= posture_num <= 40:
            robot.Set_Hand_Seq(posture_num)
            print(f"已设置预设动作序列 {posture_num}")
        else:
            print("无效的动作序列编号，请输入1-40之间的数字。")

def set_hand_force():
    """设置手指力度"""
    force = int(input("输入手指力度（0-1000）: ").strip())
    robot.Set_Hand_Force(force)
    print(f"已设置手指力度为 {force}")

if __name__ == "__main__":
    robot.Set_Hand_Force(1000)  # 设置手指力度（根据需要调整）
    print("""
    === 灵巧手控制程序 ===
    请选择控制模式：1. 手动控制 2. 执行预设手势 3. 重置手指角度 4. 执行动作序列""")
    choice = input("输入选项 (1/2/3/4): ").strip()
    if choice == '1':
        change_finger_angle()   # 启动手动控制
    elif choice == '2':
        set_hand_posture()      # 启动预设手势控制
    elif choice == '3':
        reset_finger_angles()   # 重置手指角度
    elif choice == '4':
        set_hand_seq()          # 启动动作序列控制
    else:
        print("无效选项，程序退出。")