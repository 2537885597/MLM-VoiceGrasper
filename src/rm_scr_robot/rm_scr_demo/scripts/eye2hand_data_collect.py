#!/usr/bin/env python
# coding=utf-8
#拍照
import logging
import numpy as np
import cv2
import pyrealsense2 as rs

from robotic_arm_package.log_setting import CommonLog
from robotic_arm_package.robotic_arm import *
import os

root_path = os.path.dirname(os.path.abspath(__file__))
cam0_path = os.path.join(root_path, 'images')  # 提前建立好的存储照片文件的目录

logger_ = logging.getLogger(__name__)
logger_ = CommonLog(logger_)

count = 0

def callback(frame):
    # define picture to_down' coefficient of ratio
    scaling_factor = 2.0
    global count

    cv_img = cv2.resize(frame, None, fx=scaling_factor, fy=scaling_factor, interpolation=cv2.INTER_AREA)
    cv2.imshow("Capture_Video", cv_img)  # 窗口显示，显示名为 Capture_Video

    k = cv2.waitKey(30) & 0xFF  # 每帧数据延时 1ms，延时不能为 0，否则读取的结果会是静态帧
    if k == ord('s'):  # 若检测到按键 ‘s’，打印字符串
        _, joint, pose_, error_code = arm.Get_Current_Arm_State()  # 获取当前机械臂状态
        # logger_.info(f'获取状态：{"成功" if error_code == 0 else "失败"}，{f"当前位姿为{pose_}" if error_code == 0 else None} ')
        # if error_code == 0:
        print(f"当前位姿为{pose_}")
        with open('./images/poses.txt', 'a+') as f:
            # 将列表中的元素用空格连接成一行
            pose_ = [str(i) for i in pose_]
            new_line = f'{",".join(pose_)}\n'
            # 将新行附加到文件的末尾
            f.write(new_line)

        count += 1
        cv2.imwrite(os.path.join(cam0_path, str(count) + '.jpg'), cv_img)
        print(f"已保存第{count}张照片")  # 打印保存的照片数量
    else:
        pass


def displayD435():

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    pipeline.start(config)

    global count

    try:
        while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            callback(color_image)

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    arm = Arm(RM65, '192.168.10.18')
    # 获取全部工作坐标系名称
    print(f"工作坐标系：{arm.Get_All_Work_Frame()}")
    # 设置 Base 为当前工作坐标系
    arm.Change_Work_Frame("Base")
    # 显示D435采集图像并保存
    displayD435()
