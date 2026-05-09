# -*- coding: utf-8 -*-
"""
眼在手外 用采集到的图片信息和机械臂位姿信息计算 相机坐标系相对于机械臂基座标的 旋转矩阵和平移向量
A2^{-1}*A1*X=X*B2*B1^{−1}
新增：手眼标定结果 保存/加载 功能
"""

import os
import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R
from save_poses2matrix import poses2_main
import yaml  # 用于工程格式保存，需安装：pip install pyyaml

np.set_printoptions(precision=8, suppress=True)

# ====================== 路径配置 ======================
#手眼标定采集的标定版图片所在路径
images_path = r'/home/rm/realman_ws/src/rm_scr_robot/rm_scr_demo/scripts/images'
#采集标定板图片时对应的机械臂末端的位姿 从 第一行到最后一行 需要和采集的标定板的图片顺序进行对应
file_path = r'/home/rm/realman_ws/src/rm_scr_robot/rm_scr_demo/scripts/images/poses.txt'
# 标定结果保存路径（脚本同级目录）
SAVE_PATH = os.path.join(os.path.dirname(__file__), "hand_eye_calib_result")
os.makedirs(SAVE_PATH, exist_ok=True)  # 自动创建文件夹

# ====================== 标定核心函数 ======================
def calibrate_eye_in_hand():
    """手眼标定主函数，返回旋转矩阵、平移向量、4x4齐次矩阵"""
    # 角点的个数以及棋盘格间距
    XX, YY = 5, 5 # 11 #标定板的中长度对应的角点的个数, # 8  #标定板的中宽度对应的角点的个数
    L = 0.015 # 标定板一格的长度 单位为米
    # 设置寻找亚像素角点的参数，采用的停止准则是最大循环次数30和最大误差容限0.001
    criteria = (cv2.TERM_CRITERIA_MAX_ITER | cv2.TERM_CRITERIA_EPS, 30, 0.001)

    # 标定板角点的3D位置
    objp = np.zeros((XX * YY, 3), np.float32)
    objp[:, :2] = np.mgrid[0:XX, 0:YY].T.reshape(-1, 2) * L  # 将世界坐标系建在标定板上，所有点的Z坐标全部为0，所以只需要赋值x和y
    obj_points, img_points = [], []  # 存储3D点和2D角点的坐标

    # 遍历图片 标定好的图片在images_path路径下，从0.jpg到x.jpg
    # 一次采集的图片最多不超过50张，我们遍历从0.jpg到50.jpg ，选择能够读取的到的图片
    for i in range(50):
        img_path = os.path.join(images_path, f"{i}.jpg")
        if not os.path.exists(img_path):
            continue
        img = cv2.imread(img_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, (XX, YY), None)
        if ret:
            obj_points.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)
            img_points.append(corners2 if [corners2] else corners)

    N = len(img_points)
    # 相机标定
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, gray.shape[::-1], None, None)
    print("内参矩阵:\n", mtx)
    print("畸变系数:\n", dist)
    print("-" * 50)

    # 读取机械臂位姿
    poses2_main(file_path)
    tool_pose = np.loadtxt('RobotToolPose.csv', delimiter=',')
    R_tool, t_tool = [], []
    for i in range(N):
        R_tool.append(tool_pose[0:3, 4*i:4*i+3])
        t_tool.append(tool_pose[0:3, 4*i+3])

    # 手眼标定（TSAI算法）
    R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(R_tool, t_tool, rvecs, tvecs, cv2.CALIB_HAND_EYE_TSAI)
    
    # 生成4x4齐次变换矩阵（相机 -> 机械臂末端  眼在手外标准格式）
    homo_mat = np.eye(4)
    homo_mat[:3, :3] = R_cam2gripper
    homo_mat[:3, 3] = t_cam2gripper.reshape(3)

    print("旋转矩阵 R:\n", R_cam2gripper)
    print("平移向量 t:\n", t_cam2gripper)
    return R_cam2gripper, t_cam2gripper, homo_mat

# ====================== 标定结果保存函数 ======================
def save_hand_eye_calib(R_mat, t_vec, homo_mat):
    """
    保存手眼标定结果
    :param R_mat: 3x3旋转矩阵
    :param t_vec: 3x1平移向量
    :param homo_mat: 4x4齐次矩阵
    """
    # 1. numpy二进制格式（加载最快，推荐使用）
    np.save(os.path.join(SAVE_PATH, "rotation_matrix.npy"), R_mat)
    np.save(os.path.join(SAVE_PATH, "translation_vector.npy"), t_vec)
    np.save(os.path.join(SAVE_PATH, "homogeneous_matrix.npy"), homo_mat)

    # 2. 文本格式（可读，方便查看）
    np.savetxt(os.path.join(SAVE_PATH, "homogeneous_matrix.txt"), homo_mat, fmt='%.8f')

    # 3. YAML格式（工程部署常用）
    quat = R.from_matrix(R_mat).as_quat()  # 四元数 [qx,qy,qz,qw]
    calib_dict = {
        "rotation_matrix": R_mat.tolist(),
        "translation_vector": t_vec.flatten().tolist(),
        "homogeneous_matrix": homo_mat.tolist(),
        "quaternion": {"qx": quat[0], "qy": quat[1], "qz": quat[2], "qw": quat[3]},
        "translation": {"x": t_vec[0,0], "y": t_vec[1,0], "z": t_vec[2,0]}
    }
    with open(os.path.join(SAVE_PATH, "calib_config.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(calib_dict, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ 标定结果已保存至：{SAVE_PATH}")

# ====================== 标定结果加载函数 ======================
def load_hand_eye_calib(use_homo=True):
    """
    加载手眼标定结果
    :param use_homo: True=直接加载4x4齐次矩阵，False=分开加载R和t
    :return: 齐次矩阵 / (旋转矩阵, 平移向量)
    """
    if use_homo:
        homo_mat = np.load(os.path.join(SAVE_PATH, "homogeneous_matrix.npy"))
        return homo_mat
    else:
        R_mat = np.load(os.path.join(SAVE_PATH, "rotation_matrix.npy"))
        t_vec = np.load(os.path.join(SAVE_PATH, "translation_vector.npy"))
        return R_mat, t_vec

# ====================== 主程序 ======================
if __name__ == '__main__':
    # 1. 执行标定（第一次运行）
    R_mat, t_vec, homo_mat = calibrate_eye_in_hand()
    
    # 2. 保存标定结果（只需执行一次，后续直接加载）
    save_hand_eye_calib(R_mat, t_vec, homo_mat)

    # 3. 输出四元数+平移（原功能保留）
    rotation = R.from_matrix(R_mat)
    quaternion = rotation.as_quat()
    qw, qx, qy, qz = quaternion
    x, y, z = t_vec.flatten()
    print(f"\n最终标定结果：")
    print(f"qw: {qw}\nqx: {qx}\nqy: {qy}\nqz: {qz}\nx: {x}\ny: {y}\nz: {z}")

    # ============== 后续使用：直接加载标定结果 ==============
    print("\n" + "="*50)
    print("🔍 测试加载标定结果：")
    # 方式1：加载4x4齐次矩阵（最常用）
    loaded_homo = load_hand_eye_calib()
    print("加载的4x4齐次变换矩阵：\n", loaded_homo)
    
    # 方式2：单独加载旋转矩阵+平移向量
    # loaded_R, loaded_t = load_hand_eye_calib(use_homo=False)
    # print("加载的旋转矩阵：\n", loaded_R)
    # print("加载的平移向量：\n", loaded_t)