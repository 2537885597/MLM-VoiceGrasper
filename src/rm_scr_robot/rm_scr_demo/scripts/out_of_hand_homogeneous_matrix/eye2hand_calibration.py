# -*- coding: utf-8 -*-
"""
眼在手外（Eye-to-Hand）手眼标定：
利用采集到的棋盘图像 + 机械臂位姿，计算相机坐标系相对于机械臂基座坐标系的位姿（R_cam2base, t_cam2base）

关系式（相对运动形式）可写为：
A2^{-1} * A1 * X = X * B2 * B1^{-1}

新增功能：
- 手眼标定结果保存/加载（仅 YAML 格式）
"""

import os
import re
import cv2
import yaml
import numpy as np
from scipy.spatial.transform import Rotation as R
from save_poses2matrix import poses2_main

np.set_printoptions(precision=8, suppress=True)

# ====================== 路径配置 ======================
# 手眼标定采集的标定板图片路径
images_path = r'/home/rm/realman_ws/src/rm_scr_robot/rm_scr_demo/scripts/images'
# 采集标定板图片时对应机械臂末端位姿文件（顺序需与图片一一对应）
file_path = r'/home/rm/realman_ws/src/rm_scr_robot/rm_scr_demo/scripts/images/poses.txt'

# 标定结果保存路径（脚本同级目录）
SAVE_PATH = os.path.join(os.path.dirname(__file__), "hand_eye_calib_result")
os.makedirs(SAVE_PATH, exist_ok=True)

# poses2_main 生成的 csv 路径（建议与本脚本同目录，避免 cwd 影响）
ROBOT_POSE_CSV = os.path.join(os.path.dirname(__file__), "RobotToolPose.csv")


def _is_valid_rotation_matrix(Rm: np.ndarray, atol: float = 1e-3) -> bool:
    """检查旋转矩阵正交性和行列式。"""
    if Rm.shape != (3, 3):
        return False
    should_be_I = Rm.T @ Rm
    I = np.eye(3)
    return np.allclose(should_be_I, I, atol=atol) and np.isclose(np.linalg.det(Rm), 1.0, atol=atol)


def _collect_image_indices(img_dir: str):
    """收集目录下数字命名的 jpg：0.jpg, 1.jpg ...，并按数字升序返回索引列表。"""
    if not os.path.isdir(img_dir):
        raise FileNotFoundError(f"图片目录不存在: {img_dir}")

    indices = []
    for name in os.listdir(img_dir):
        m = re.fullmatch(r"(\d+)\.jpg", name, re.IGNORECASE)
        if m:
            indices.append(int(m.group(1)))
    indices.sort()
    return indices


# ====================== 标定核心函数 ======================
def calibrate_eye_out_hand():
    """手眼标定主函数，返回旋转矩阵、平移向量、4x4齐次矩阵"""
    # 角点的个数以及棋盘格间距
    XX, YY = 7, 4 # 棋盘格内角点数量（**必须和实际标定板一致**）
    L = 0.03 # 标定板一格的长度 单位为米
    # 设置寻找亚像素角点的参数
    criteria = (cv2.TERM_CRITERIA_MAX_ITER | cv2.TERM_CRITERIA_EPS, 30, 0.001)

    # 标定板角点的3D位置
    objp = np.zeros((XX * YY, 3), np.float32)
    objp[:, :2] = np.mgrid[0:XX, 0:YY].T.reshape(-1, 2) * L
    obj_points, img_points = [], []

    # 遍历有效图片
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
            img_points.append(corners2)

    N = len(img_points)
    if N == 0:
        raise ValueError("未检测到有效标定板图片！")
    print(f"有效标定图片数量：{N}")

    # 相机标定（获取内参+外参）
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, gray.shape[::-1], None, None)
    print("内参矩阵:\n", mtx)
    print("畸变系数:\n", dist)
    print("-" * 50)

    # ====================== 【核心修正1】旋转向量 → 旋转矩阵 ======================
    # OpenCV手眼标定强制要求输入旋转矩阵，不能直接传旋转向量rvecs！
    R_target2cam = []  # 标定板 -> 相机 的旋转矩阵
    t_target2cam = []  # 标定板 -> 相机 的平移向量
    for rvec, tvec in zip(rvecs, tvecs):
        rmat, _ = cv2.Rodrigues(rvec)  # 旋转向量转矩阵
        R_target2cam.append(rmat)
        t_target2cam.append(tvec)

    # 读取机械臂位姿（末端 -> 基座，符合OpenCV输入要求）
    poses2_main(file_path)
    tool_pose = np.loadtxt(ROBOT_POSE_CSV, delimiter=',')  # 修复硬编码路径
    R_gripper2base = []  # 末端 -> 基座
    t_gripper2base = []
    for i in range(N):
        R_gripper2base.append(tool_pose[0:3, 4*i:4*i+3])
        t_gripper2base.append(tool_pose[0:3, 4*i+3])

    # ====================== 【核心修正2】正确调用眼在手外标定 ======================
    # 官方参数：calibrateHandEye(R_gripper2base, t_gripper2base, R_target2cam, t_target2cam)
    # 眼在手外 → 返回值：相机 -> 机械臂基坐标系（最终需要的结果）
    R_cam2base, t_cam2base = cv2.calibrateHandEye(
        R_gripper2base, t_gripper2base,
        R_target2cam, t_target2cam,
        cv2.CALIB_HAND_EYE_TSAI
    )

    # 生成4x4齐次变换矩阵（相机 -> 机械臂基座 ✅ 眼在手外最终结果）
    homo_mat = np.eye(4)
    homo_mat[:3, :3] = R_cam2base
    homo_mat[:3, 3] = t_cam2base.reshape(3)

    print("\n✅ 眼在手外标定结果（相机 → 机械臂基坐标系）")
    print("旋转矩阵 R:\n", R_cam2base)
    print("平移向量 t:\n", t_cam2base)
    return R_cam2base, t_cam2base, homo_mat


# ====================== 标定结果保存函数 ======================
def save_hand_eye_calib(R_mat, t_vec, homo_mat):
    """
    保存手眼标定结果（仅 YAML）
    :param R_mat: 3x3 旋转矩阵
    :param t_vec: 3x1 平移向量
    :param homo_mat: 4x4 齐次矩阵
    """
    rotation = R.from_matrix(R_mat)
    qx, qy, qz, qw = rotation.as_quat()  # scipy 顺序: x,y,z,w

    calib_dict = {
        "rotation_matrix": [[float(v) for v in row] for row in R_mat.tolist()],
        "translation_vector": [float(v) for v in t_vec.flatten().tolist()],
        "homogeneous_matrix": [[float(v) for v in row] for row in homo_mat.tolist()],
        "quaternion": {
            "qx": float(qx),
            "qy": float(qy),
            "qz": float(qz),
            "qw": float(qw)
        },
        "translation": {
            "x": float(t_vec[0, 0]),
            "y": float(t_vec[1, 0]),
            "z": float(t_vec[2, 0])
        }
    }

    yaml_path = os.path.join(SAVE_PATH, "calib_config.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            calib_dict,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )

    print(f"\n✅ 标定结果已保存至：{yaml_path}")


# ====================== 标定结果加载函数 ======================
def load_hand_eye_calib():
    """
    从 YAML 加载手眼标定结果
    :return: 4x4 齐次矩阵
    """
    yaml_path = os.path.join(SAVE_PATH, "calib_config.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML 标定文件未找到: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if "homogeneous_matrix" not in data:
        raise KeyError(f"'homogeneous_matrix' not found in {yaml_path}")

    homo_mat = np.array(data["homogeneous_matrix"], dtype=np.float64)
    if homo_mat.shape != (4, 4):
        raise ValueError(f"homogeneous_matrix 形状错误: {homo_mat.shape}，应为 (4,4)")

    print(f"[INFO] 从 {yaml_path} 加载手眼标定矩阵")
    if "translation" in data:
        tx = data["translation"].get("x", 0.0)
        ty = data["translation"].get("y", 0.0)
        tz = data["translation"].get("z", 0.0)
        print(f"[INFO] 标定结果: x={tx:.6f}, y={ty:.6f}, z={tz:.6f}")

    return homo_mat


# ====================== 主程序 ======================
if __name__ == '__main__':
    # 1) 执行标定（首次运行）
    R_mat, t_vec, homo_mat = calibrate_eye_out_hand()

    # 2) 保存标定结果（后续可直接加载）
    save_hand_eye_calib(R_mat, t_vec, homo_mat)

    # 3) 输出四元数 + 平移
    qx, qy, qz, qw = R.from_matrix(R_mat).as_quat()
    x, y, z = t_vec.flatten()
    print("\n最终标定结果（相机→基座）：")
    print(f"qw: {qw}\nqx: {qx}\nqy: {qy}\nqz: {qz}\nx: {x}\ny: {y}\nz: {z}")

    # 4) 测试加载
    print("\n" + "=" * 50)
    print("🔍 测试加载标定结果：")
    loaded_homo = load_hand_eye_calib()
    print("加载的 4x4 齐次变换矩阵：\n", loaded_homo)