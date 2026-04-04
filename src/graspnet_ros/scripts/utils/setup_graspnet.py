#!/usr/bin/env python3
"""
GraspNet模块导入测试工具

功能:
    - 测试GraspNet模块导入
    - 添加GraspNet路径到Python路径
    - 检测和报告导入问题
"""

import os
import sys
import importlib


def test_graspnet_imports():
    """
    测试GraspNet模块导入
    
    功能:
        - 添加GraspNet-Baseline路径到Python路径
        - 添加子模块路径 (models, utils, dataset)
        - 尝试导入关键模块
        - 报告导入结果和问题
        
    注意:
        修改graspnet_path为您的GraspNet-Baseline安装目录
    """
    # 添加路径
    # 修改: 将此路径更改为您的GraspNet-Baseline安装目录
    graspnet_path = "/home/rm/realman_ws/src/graspnet-baseline"
    sys.path.insert(0, graspnet_path)
    
    # 添加子模块路径
    for subdir in ['models', 'utils', 'dataset', 'graspnetAPI']:
        subpath = os.path.join(graspnet_path, subdir)
        if os.path.exists(subpath):
            sys.path.insert(0, subpath)
            print(f"添加子路径: {subpath}")
    
    # 打印当前路径
    print("当前Python路径:")
    for p in sys.path:
        print(f"  {p}")
    
    # 尝试导入关键模块
    modules_to_test = [
        'backbone', 
        'models.graspnet', 
        'models.loss', 
        'dataset.graspnet_dataset',
        'graspnetAPI'
    ]
    
    for module_name in modules_to_test:
        try:
            module = importlib.import_module(module_name)
            print(f"成功导入 {module_name}")
        except ImportError as e:
            print(f"无法导入 {module_name}: {e}")
            
            # 尝试查找模块文件
            parts = module_name.split('.')
            if len(parts) > 1:
                base_name = parts[-1]
                for p in sys.path:
                    potential_file = os.path.join(p, f"{base_name}.py")
                    if os.path.exists(potential_file):
                        print(f"找到可能的模块文件: {potential_file}")


if __name__ == "__main__":
    test_graspnet_imports()
