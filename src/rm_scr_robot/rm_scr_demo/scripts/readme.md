# 启动抓取执行节点
rosrun rm_scr_demo grasp_executor.py

# 或者发布抓取指令
rostopic pub /grasp_command std_msgs/String "data: 'grasp'" -1