#!/usr/bin/env python3
import sys
import time
from navigation import *
from robotic_arm_package.robotic_arm import *

def main(work_mode):
    arm = Arm(RM65, "192.168.10.18")
    
    if work_mode == "0":
        # 充电模式
        arm.Movej_Cmd([171, -85, -3, -15, -20, -90], 50, 0, 0, False)
        time.sleep(1)
        go_to_marker("charger")
        
    elif work_mode == "1":
        # 任务模式
        go_to_marker("work")
        time.sleep(5)
        arm.Movej_Cmd([171, -85, -3, -15, -20, -90], 50, 0, 0, False)
        
    else:
        raise ValueError("无效的工作模式，请输入 0 或 1")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python script.py [0|1]")
        print("  0 - 充电模式")
        print("  1 - 任务模式")
        sys.exit(1)
    
    try:
        main(sys.argv[1])
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)