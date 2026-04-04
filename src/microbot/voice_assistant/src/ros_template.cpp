#include <ros.ros.h>
#include <std_msgs/String.h>
// 可以根据需要包含其他ROS消息头文件
// #include <sensor_msgs/LaserScan.h>
// #include <geometry_msgs/Twist.h>
// #include <nav_msgs/Odometry.h>

/*
 * ROS节点通用C++模板
*/

class RosTemplate
{
public:
    RosTemplate()
    {
        // 初始化发布者
        pub = n.advertise<std_msgs::String>("topic_name", 10);
        // 初始化订阅者
        sub = n.subscribe("topic_name", 10, &ROSTemplate::callback, this);
        // 设置循环频率 10Hz
        loop_rate = ros::Rate(10);
    }
    
    // 回调函数
    void callback(const std_msgs::String::ConstPtr& msg)
    {
        ROS_INFO("收到消息：[%s]", msg->data.c_str());
        // 处理接收到的消息
    }

    void run()
    {
        while(ros::ok())
        {
            // 主循环逻辑 如发布消息、处理消息
            
            // 处理回调函数
            ros::spinOnce();
            // 根据设置的频率休眠
            loop_rate.sleep();
        }
    }
private:
    ros::NodeHandle n;
    ros::Publisher pub;
    ros::Subscriber sub;
    ros::Rate loop_rate;
};

int main(int argc, char **argv)
{
    // 初始化ROS节点
    ros::init(argc, argv, "ros_template");
    ROS_INFO("ROS模板节点已启动")
    // 运行节点
    ROSTemplate template_node;
    template_node.run();
    return 0;
}