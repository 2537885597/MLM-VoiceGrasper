from robotic_arm_package.robotic_arm import *
import time

class planning:
    def __init__(self):
        # 连接机械臂 RM65
        self.robot = Arm(RM65, "192.168.10.18")
        # 存储当前位姿 [x,y,z,rx,ry,rz]
        self.current_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # 初始化获取当前真实位姿
        self.update_current_pose()

    def update_current_pose(self):
        """获取并更新机械臂当前末端位姿"""
        try:
            res, joint, pose, arm_err = self.robot.Get_Current_Arm_State()
            self.current_pose = pose.copy()
            print(f"\n✅ 当前末端位姿：")
            print(f"位置 -> x:{pose[0]:.3f}m  y:{pose[1]:.3f}m  z:{pose[2]:.3f}m")
            print(f"姿态 -> rx:{pose[3]:.3f}  ry:{pose[4]:.3f}  rz:{pose[5]:.3f}")
            print(f"⚠️ 获取当前位姿失败，错误码：{res}")
        except Exception as e:
            print(f"❌ 获取位姿异常：{str(e)}")

    def FK(self, input_joint):
        """正运动学：关节角度控制"""
        ret = self.robot.Movej_Cmd(input_joint, 20, 20)
        if ret:
            print(f"❌ 正运动失败：{ret}")
        else:
            print(f"✅ 正运动成功")
            self.update_current_pose()

    def IK(self, input_pose):
        """逆运动学：位姿控制"""
        # ret = self.robot.Movep_Follow(input_pose)
        ret = self.robot.Movej_P_Cmd(input_pose, 20, 20)

        if ret:
            print(f"❌ 逆运动失败：{ret}")
        else:
            print(f"✅ 逆运动成功")
            self.update_current_pose()

    def step_move(self, axis, step):
        """
        末端步进控制（核心功能）
        :param axis: 'x'/'y'/'z'
        :param step: 步长（米，正数正向，负数反向）
        """
        self.update_current_pose()
        target_pose = self.current_pose.copy()

        if axis == "x":
            target_pose[0] += step
        elif axis == "y":
            target_pose[1] += step
        elif axis == "z":
            target_pose[2] += step
        else:
            print("❌ 仅支持 x/y/z 轴！")
            return

        print(f"\n🔹 沿 {axis} 轴步进：{step}m")
        self.IK(target_pose)
    
    def step_rotate(self, axis, step):
        """
        末端旋转控制（新增功能）
        :param axis: 'rx'/'ry'/'rz'
        :param step: 步长（度，正数正向，负数反向）
        """
        self.update_current_pose()
        target_pose = self.current_pose.copy()

        if axis == "rx":
            target_pose[3] += step
        elif axis == "ry":
            target_pose[4] += step
        elif axis == "rz":
            target_pose[5] += step
        else:
            print("❌ 仅支持 rx/ry/rz 轴！")
            return

        print(f"\n🔹 沿 {axis} 轴旋转：{step}°")
        self.IK(target_pose)

    def shut_down(self):
        """安全断开连接"""
        print("\n🔌 断开机械臂连接...")
        self.robot.RM_API_UnInit()
        self.robot.Arm_Socket_Close()
        print("✅ 已安全断开")

if __name__ == "__main__":
    plan = planning()
    try:
        while True:
            print("\n===== 机械臂控制菜单 =====")
            print(f"当前位置：x={plan.current_pose[0]:.3f}m | y={plan.current_pose[1]:.3f}m | z={plan.current_pose[2]:.3f}m")
            choice = input("1-关节正运动  | 2-位姿逆运动  | 3-末端x/y/z步进  |4-末端旋转  | 5-更新当前位姿  | 6 q-退出\n请输入：")

            if choice.lower() == "q":
                break

            # 1. 关节空间运动
            elif choice == "1":
                joint_str = input("输入6个关节角度（空格分隔）：")
                try:
                    joint = [float(i) for i in joint_str.split()]
                    if len(joint) != 6:
                        print("❌ 必须输入6个角度！")
                        continue
                    plan.FK(joint)
                except:
                    print("❌ 输入格式错误")

            # 2. 位姿逆运动
            elif choice == "2":
                pose_str = input("输入6位姿(x y z rx ry rz 空格分隔)：")
                try:
                    pose = [float(i) for i in pose_str.split()]
                    if len(pose) != 6:
                        print("❌ 必须输入6个参数！")
                        continue
                    plan.IK(pose)
                except:
                    print("❌ 输入格式错误")

            # 3. 末端步进（新增功能）
            elif choice == "3":
                axis = input("输入步进轴（x/y/z）：").strip().lower()
                if axis not in ["x", "y", "z"]:
                    print("❌ 仅支持 x/y/z！")
                    continue
                try:
                    step = float(input("输入步长（米，如0.01正向/-0.01反向）："))
                    plan.step_move(axis, step)
                except:
                    print("❌ 步长必须是数字")
            elif choice == "4":
                # 5. 末端旋转（新增功能）
                axis = input("输入旋转轴（rx/ry/rz）：").strip().lower()
                if axis not in ["rx", "ry", "rz"]:
                    print("❌ 仅支持 rx/ry/rz！")
                    continue
                try:
                    step = float(input("输入旋转步长（度，如0.1正向/-0.1反向）："))
                    plan.step_rotate(axis, step)    
                except:
                    print("❌ 步长必须是数字")
            elif choice == "5":
                # 4. 更新当前位姿
                print("更新当前位姿...")
                plan.update_current_pose()
                print("更新完成")

            else:
                print("❌ 无效输入")

    except KeyboardInterrupt:
        print("\n⚠️ 程序强制停止")
    finally:
        plan.shut_down()