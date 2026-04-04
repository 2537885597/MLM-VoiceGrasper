#! /usr/bin/env python3
"""
ROS节点通用Python模板
"""
import rospy
from std_msgs.msg import String
# 可以根据需要导入其他ROS消息类型
# from sensor_msgs.msg import LaserScan
# from geometry_msgs.msg import Twist
# from nav_msgs.msg import Odometry

class RosTemplate:
    def __init__(self):
        # 初始化ROS节点
        rospy.init_node("ros_template_node", anonymous=True)
        rospy.loginfo("ROS模板节点已启动")
        # 获取参数
        param_eg = rospy.get_param("~param_name", "default_value")
        # 创建发布者
        self.pub = rospy.Publisher("topic_name", String, queue_size=10) # MessageType
        # 创建订阅者
        self.sub = self.Subscriber("topic_name", String, self.subscribe_callback) # MessageType
        # 创建服务服务端
        self.service = rospy.Service("service_name", String, self.service_callback) # ServiceType
        # 创建服务客户端
        self.client = rospy.ServiceProxy("service_name", String) # ServiceType
        # 设置循环频率 10Hz
        self.rate = rospy.Rate(10)
    
    def subscribe_callback(self, msg):
        """订阅回调函数"""
        rospy.loginfo(f"收到消息：{msg.data}")
        # 处理接收到的消息
    
    def service_callback(self, req):
        """服务回调函数"""
        rospy.loginfo("收到服务请求")
        # 处理服务请求

        # 返回响应
        return String("服务响应") # ReponseType()

    def run(self):
        """主循环"""
        while not rospy.is_shutdown():
            # 添加主要逻辑 如发布消息、处理数据
            
            # 根据设置的频率休眠
            self.rate.sleep()
    
if __name__ == "__main__":
    try:
        # 创建模板实例
        template = RosTemplate()
        # 运行节点
        template.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点中断")
        pass
