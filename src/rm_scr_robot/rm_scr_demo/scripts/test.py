from robotic_arm_package.log_setting import CommonLog
from robotic_arm_package.robotic_arm import *

arm = Arm(RM65, '192.168.10.18')
retval, frame = arm.Get_Current_Work_Frame()
if retval == 0:
    print(f"当前工作坐标系：{frame.frame_name.name}")
    print(f"当前工作坐标系位置：{frame.pose.position.x}, {frame.pose.position.y}, {frame.pose.position.z}")
print(arm.Get_All_Work_Frame())
print(arm.Change_Work_Frame('Base'))
print(arm.Get_Current_Arm_State())
print(arm.Get_Arm_All_State())

arm.Movej_P_Cmd([0.3, 0.3, 0.3, 0.2, 0.2, 0.2], 20, 20)
print(arm.Get_Current_Arm_State())

