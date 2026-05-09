#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import argparse
import os
from datetime import datetime
from scipy.spatial.transform import Rotation as R


def euler_to_rotation_matrix(rx, ry, rz):
    """
    将欧拉角 (rx, ry, rz) 转换为旋转矩阵
    假设欧拉角单位为弧度
    """
    r = R.from_euler('xyz', [rx, ry, rz])
    return r.as_matrix()


def rotation_matrix_to_euler(rotation_matrix):
    """
    将旋转矩阵转换为欧拉角 (rx, ry, rz)
    返回值为弧度
    """
    r = R.from_matrix(rotation_matrix)
    return r.as_euler('xyz')


def quaternion_to_rotation_matrix(qx, qy, qz, qw):
    """
    将四元数 (qx, qy, qz, qw) 转换为旋转矩阵
    """
    r = R.from_quat([qx, qy, qz, qw])
    return r.as_matrix()


def rotation_matrix_to_quaternion(rotation_matrix):
    """
    将旋转矩阵转换为四元数 (qx, qy, qz, qw)
    """
    r = R.from_matrix(rotation_matrix)
    return r.as_quat()


def pose_quaternion_to_homogeneous(x, y, z, qx, qy, qz, qw):
    """
    将位姿 (x, y, z, qx, qy, qz, qw) 转换为 4x4 齐次变换矩阵
    """
    rotation_matrix = quaternion_to_rotation_matrix(qx, qy, qz, qw)
    homogeneous = np.eye(4)
    homogeneous[:3, :3] = rotation_matrix
    homogeneous[:3, 3] = [x, y, z]
    return homogeneous


def pose_euler_to_homogeneous(x, y, z, rx, ry, rz):
    """
    将位姿 (x, y, z, rx, ry, rz) 转换为 4x4 齐次变换矩阵
    rx, ry, rz 为弧度
    """
    rotation_matrix = euler_to_rotation_matrix(rx, ry, rz)
    homogeneous = np.eye(4)
    homogeneous[:3, :3] = rotation_matrix
    homogeneous[:3, 3] = [x, y, z]
    return homogeneous


def homogeneous_to_pose_euler(homogeneous):
    """
    将 4x4 齐次变换矩阵转换为位姿 (x, y, z, rx, ry, rz)
    返回的欧拉角为弧度
    """
    x, y, z = homogeneous[:3, 3]
    rx, ry, rz = rotation_matrix_to_euler(homogeneous[:3, :3])
    return x, y, z, rx, ry, rz


def homogeneous_to_pose_quaternion(homogeneous):
    """
    将 4x4 齐次变换矩阵转换为位姿 (x, y, z, qx, qy, qz, qw)
    """
    x, y, z = homogeneous[:3, 3]
    qx, qy, qz, qw = rotation_matrix_to_quaternion(homogeneous[:3, :3])
    return x, y, z, qx, qy, qz, qw


def calibrate_hand_eye(camera_pose, grasp_pose_base):
    """
    根据相机坐标系下的目标位姿和基坐标系下的期望抓取位姿，
    计算相机到基坐标的手眼标定矩阵 T_base_camera

    原理:
    T_base_grasp = T_base_camera * T_camera_grasp
    因此：T_base_camera = T_base_grasp * T_camera_grasp^(-1)

    参数:
        camera_pose: 相机坐标系下的目标位姿 (x, y, z, qx, qy, qz, qw)
        grasp_pose_base: 基坐标系下的期望抓取位姿 (x, y, z, rx, ry, rz)，弧度

    返回:
        T_base_camera: 4x4 齐次变换矩阵，表示相机到基坐标的变换
    """
    T_camera_grasp = pose_quaternion_to_homogeneous(*camera_pose)
    T_base_grasp = pose_euler_to_homogeneous(*grasp_pose_base)

    T_camera_grasp_inv = np.linalg.inv(T_camera_grasp)

    T_base_camera = T_base_grasp @ T_camera_grasp_inv

    return T_base_camera


def parse_camera_pose_input(input_str):
    """
    解析相机坐标系下的目标位姿输入
    格式：x y z qx qy qz qw (四元数)
    x, y, z 单位为米 (m)，旋转为四元数
    """
    values = list(map(float, input_str.strip().split()))
    if len(values) != 7:
        raise ValueError(f"需要 7 个值 (x y z qx qy qz qw)，但得到 {len(values)} 个")
    x, y, z, qx, qy, qz, qw = values
    return x, y, z, qx, qy, qz, qw


def parse_grasp_pose_input(input_str):
    """
    解析基坐标系下的期望抓取位姿输入
    格式：x y z rx ry rz (欧拉角，弧度制)
    x, y, z 单位为米 (m)，rx, ry, rz 单位为弧度 (rad)
    """
    values = list(map(float, input_str.strip().split()))
    if len(values) != 6:
        raise ValueError(f"需要 6 个值 (x y z rx ry rz)，但得到 {len(values)} 个")
    x, y, z, rx, ry, rz = values
    return x, y, z, rx, ry, rz


def save_to_yaml(T_base_camera, output_dir, filename=None):
    """
    将手眼标定矩阵保存为 YAML 格式
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"calib_result_{timestamp}.yaml"
    
    output_path = os.path.join(output_dir, filename)
    
    with open(output_path, 'w') as f:
        f.write("rotation_matrix:\n")
        for i in range(3):
            row = ", ".join([f"{T_base_camera[i, j]:.16f}" for j in range(3)])
            f.write(f"- [{row}]\n")
        
        f.write("translation_vector:\n")
        trans = ", ".join([f"{T_base_camera[i, 3]:.16f}" for i in range(3)])
        f.write(f"- [{trans}]\n")
        
        f.write("homogeneous_matrix:\n")
        for i in range(4):
            row = ", ".join([f"{T_base_camera[i, j]:.16f}" for j in range(4)])
            f.write(f"- [{row}]\n")
        
        rotation_matrix = T_base_camera[:3, :3]
        qx, qy, qz, qw = rotation_matrix_to_quaternion(rotation_matrix)
        
        f.write("quaternion:\n")
        f.write(f"  qx: {qx:.16f}\n")
        f.write(f"  qy: {qy:.16f}\n")
        f.write(f"  qz: {qz:.16f}\n")
        f.write(f"  qw: {qw:.16f}\n")
        
        f.write("translation:\n")
        f.write(f"  x: {T_base_camera[0, 3]:.16f}\n")
        f.write(f"  y: {T_base_camera[1, 3]:.16f}\n")
        f.write(f"  z: {T_base_camera[2, 3]:.16f}\n")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='根据相机坐标系下的目标位姿和期望抓取位姿，逆解算手眼标定矩阵'
    )
    parser.add_argument(
        '--camera-pose',
        type=float,
        nargs=7,
        help='相机坐标系下的目标位姿：x y z qx qy qz qw (四元数，x/y/z 单位：m，旋转：rad)'
    )
    parser.add_argument(
        '--grasp-pose',
        type=float,
        nargs=6,
        help='基坐标系下的期望抓取位姿：x y z rx ry rz (欧拉角，x/y/z 单位：m，旋转：rad)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='/home/rm/realman_ws/src/rm_scr_robot/rm_scr_demo/scripts/out_of_hand_homogeneous_matrix/hand_eye_calib_result',
        help='结果保存目录'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        help='输出文件名 (可选，默认自动生成带时间戳的文件名)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='不保存到文件，仅输出到控制台'
    )

    args = parser.parse_args()

    if args.camera_pose and args.grasp_pose:
        camera_pose = tuple(args.camera_pose)
        grasp_pose = tuple(args.grasp_pose)
    else:
        print("=" * 60)
        print("手眼标定矩阵计算工具")
        print("=" * 60)
        print("\n请输入相机坐标系下的目标位姿:")
        print("格式：x y z qx qy qz qw (四元数，x/y/z 单位：m，旋转：rad)")
        camera_input = input("> ")
        
        try:
            camera_pose = parse_camera_pose_input(camera_input)
        except ValueError as e:
            print(f"错误：{e}")
            return
        
        print("\n请输入基坐标系下的期望抓取位姿:")
        print("格式：x y z rx ry rz (欧拉角，x/y/z 单位：m，旋转：rad)")
        grasp_input = input("> ")
        
        try:
            grasp_pose = parse_grasp_pose_input(grasp_input)
        except ValueError as e:
            print(f"错误：{e}")
            return

    T_base_camera = calibrate_hand_eye(camera_pose, grasp_pose)

    print("\n" + "=" * 60)
    print("计算结果：相机到基坐标的手眼标定矩阵")
    print("=" * 60)
    
    print("\nrotation_matrix:")
    for i in range(3):
        row = ", ".join([f"{T_base_camera[i, j]:.16f}" for j in range(3)])
        print(f"- [{row}]")
    
    print("translation_vector:")
    trans = ", ".join([f"{T_base_camera[i, 3]:.16f}" for i in range(3)])
    print(f"- [{trans}]")
    
    print("homogeneous_matrix:")
    for i in range(4):
        row = ", ".join([f"{T_base_camera[i, j]:.16f}" for j in range(4)])
        print(f"- [{row}]")
    
    rotation_matrix = T_base_camera[:3, :3]
    qx, qy, qz, qw = rotation_matrix_to_quaternion(rotation_matrix)
    
    print("quaternion:")
    print(f"  qx: {qx:.16f}")
    print(f"  qy: {qy:.16f}")
    print(f"  qz: {qz:.16f}")
    print(f"  qw: {qw:.16f}")
    
    print("translation:")
    print(f"  x: {T_base_camera[0, 3]:.16f}")
    print(f"  y: {T_base_camera[1, 3]:.16f}")
    print(f"  z: {T_base_camera[2, 3]:.16f}")
    
    x, y, z, rx, ry, rz = homogeneous_to_pose_euler(T_base_camera)
    print("\n位姿 (欧拉角，x/y/z 单位：m，旋转：rad):")
    print(f"  x: {x:.6f}")
    print(f"  y: {y:.6f}")
    print(f"  z: {z:.6f}")
    print(f"  rx: {rx:.6f}")
    print(f"  ry: {ry:.6f}")
    print(f"  rz: {rz:.6f}")

    if not args.no_save:
        output_dir = args.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = save_to_yaml(T_base_camera, output_dir, args.output_file)
        print(f"\n结果已保存到：{output_path}")


if __name__ == '__main__':
    main()
