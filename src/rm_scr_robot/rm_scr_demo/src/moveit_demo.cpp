#include <ros/ros.h>
#include <moveit/move_group_interface/move_group_interface.h>
#include <moveit/robot_trajectory/robot_trajectory.h>
#include <cstdlib>
#include <tf/tf.h>
#include <tf_conversions/tf_eigen.h>
#include <eigen_conversions/eigen_msg.h>

#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <geometry_msgs/PointStamped.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
# define M_PI 3.1415926

double calcAngle(double x, double y){
    return atan2(x, y) - M_PI / 2;
}

double soloveQuadratic(double a, double b, double c){
    double delta = b * b - 4 * a * c;
    double x1, x2;
    double abs_x1, abs_x2;
    if (delta > 0) {
        x1 = (-b + sqrt(delta)) / (2 * a);
        x2 = (-b - sqrt(delta)) / (2 * a);
    }else if (delta == 0){
        x1 = x2 = -b / (2 * a);
    }else{
        ROS_INFO( "error in solving function");
    }
    abs_x1 = abs(x1);
    abs_x2 = abs(x2);
    if(abs_x1 > abs_x2)
    {
        return x2;
    }
    else{
        return x1;
    }
}

void quaternion2Rpy( geometry_msgs::Pose targetPoint, double &roll, double & pitch, double &yaw){
        tf::Quaternion quaternion(targetPoint.orientation.x, targetPoint.orientation.y, targetPoint.orientation.z, targetPoint.orientation.w);
        tf::Matrix3x3 m(quaternion);
        m.getRPY(roll, pitch, yaw);
}

void computePointLocationOritentation(geometry_msgs::Pose &resPoint,  geometry_msgs::Pose targetPoint, float horizontalDistance, float verticalDistance, float pitchAngle=0.0, float rollAngle=0.0){
        /*
            param resPoint:   距离目标位置一定距离的点
            param targetPoint: 目标点
            param horizontalDistance: 水平距离， 单位m
            param verticalDistance: 垂直距离，单位m
            param pitchAngle: 末端绕y轴旋转角度
            param rollAngle: 末端绕x轴旋转角度
        */       
       /*四元数转欧拉角*/
        double rollTarget, pitchTarget, yawTarget;
        quaternion2Rpy(targetPoint, rollTarget, pitchTarget, yawTarget);

        float target_pos_x = targetPoint.position.x;
        float target_pos_y = targetPoint.position.y;
        float target_pos_z = targetPoint.position.z;
        // std::cerr<<"目标中心在基坐标系上的位置："<< targetPoint.cartPos.position.x << ", " << targetPoint.cartPos.position.y << ", " << targetPoint.cartPos.position.z <<std::endl;
        // std::cerr<<"基座到目标的距离： "<<target_pos_x * target_pos_x + target_pos_y * target_pos_y + target_pos_z * target_pos_z <<std::endl;

        double target_slope = target_pos_y / target_pos_x;
        double target_a = 1 + target_slope * target_slope; 
        double target_b = - 2*(target_pos_x + target_slope*target_pos_y);
        double target_c = target_pos_x * target_pos_x + target_pos_y * target_pos_y - horizontalDistance*horizontalDistance;
        double pre_grasp_pose_x = soloveQuadratic(target_a, target_b, target_c);
        double pre_grasp_pose_y = pre_grasp_pose_x * target_slope;
        double pre_grasp_pose_z = target_pos_z;

        // double roll = calcAngle(target_pos_z - pre_grasp_pose_z, target_pos_y - pre_grasp_pose_y) - rollAngle / 180.0 * 3.1416;
        double roll = rollTarget;
        double pitch =  calcAngle(target_pos_x - pre_grasp_pose_x, target_pos_z - pre_grasp_pose_z);
        double yaw = calcAngle(target_pos_y - pre_grasp_pose_y, target_pos_x - pre_grasp_pose_x);

        if (roll < 0)
        {
            roll += M_PI;
        }

        if (yaw < 0)
        {
            yaw += M_PI;
        }

        tf::Quaternion quaternion;
        quaternion.setRPY(roll, pitch, yaw);
        resPoint.orientation.w = quaternion.w();
        resPoint.orientation.x = quaternion.x();
        resPoint.orientation.y = quaternion.y();
        resPoint.orientation.z = quaternion.z();

        pre_grasp_pose_z -=  verticalDistance;
        resPoint.position.x = pre_grasp_pose_x;
        resPoint.position.y = pre_grasp_pose_y;
        resPoint.position.z = pre_grasp_pose_z;
}

class RM65Control{
    public:
        moveit::planning_interface::MoveGroupInterface moveGroup;
        moveit::planning_interface::MoveGroupInterface::Plan myPlan;
        geometry_msgs::Pose targetPose, currentPose, prePickPose;

        RM65Control(): moveGroup("arm")
        {
            ros::NodeHandle nh;
            moveGroup.allowReplanning(true);
            moveGroup.setPoseReferenceFrame("link_arm_connector");
            moveGroup.setMaxVelocityScalingFactor(1);
            moveGroup.setMaxAccelerationScalingFactor(1);
            moveGroup.setGoalOrientationTolerance(0.002);
            moveGroup.setGoalPositionTolerance(0.05);
            moveGroup.setPlanningTime(3.0);

        }

        void move_target_position()
        {
            //x : 0.421821, y : 0.388455, z : 0.665888 
 
            currentPose = moveGroup.getCurrentPose().pose;
            printf("currentPose: x : %f, y : %f, z : %f", currentPose.position.x, currentPose.position.y, currentPose.position.z);
            double roll, pitch, yaw;
            quaternion2Rpy(currentPose, roll, pitch, yaw);
            ROS_INFO("currentPose orientation roll: %f, pitch : %f, yaw : %f", roll/M_PI*180.0, pitch/M_PI*180.0, yaw/M_PI*180.0);
            ROS_INFO("currentPose orientation x: %f, y : %f, z : %f, w : %f", currentPose.orientation.x, currentPose.orientation.y, currentPose.orientation.z, currentPose.orientation.w);

            targetPose.position.x =  0.421821;
            targetPose.position.y = 0.388455;
            targetPose.position.z = 0.665888;
            targetPose.orientation.x = currentPose.orientation.x;
            targetPose.orientation.y = currentPose.orientation.y;
            targetPose.orientation.z = currentPose.orientation.z;
            targetPose.orientation.w = currentPose.orientation.w;
            computePointLocationOritentation(prePickPose, targetPose,0.36, 0.03, 0.0);

            moveGroup.setPoseTarget(prePickPose);
            bool success = (moveGroup.plan(myPlan) == moveit::planning_interface::MoveItErrorCode::SUCCESS);
            if(success)
            {
                moveGroup.execute(myPlan);
                sleep(1);
                ROS_INFO("success");
                currentPose = moveGroup.getCurrentPose().pose;
                ROS_INFO("prePickPose x: %f, y: %f, z : %f", currentPose.position.x, currentPose.position.y, currentPose.position.z);
                quaternion2Rpy(currentPose, roll, pitch, yaw);
                ROS_INFO("prePickPose orientation roll: %f, pitch : %f, yaw : %f", roll/M_PI*180.0, pitch/M_PI*180.0, yaw/M_PI*180.0);
                ROS_INFO("prePickPose orientation x: %f, y : %f, z : %f, w : %f", currentPose.orientation.x, currentPose.orientation.y, currentPose.orientation.z, currentPose.orientation.w);
            }
            else
            {
                ROS_INFO("this is wrong");
            }

        }

        void back_middle_position()
        {
            std::vector<double> jointGroupPostion(6);
            jointGroupPostion[0] =0.15214654760360719;
            jointGroupPostion[1] = 0.9494021760940552;
            jointGroupPostion[2] = -2.003574113845825;
            jointGroupPostion[3] = 0.046190151298046114;
            jointGroupPostion[4] = -0.49812769174575805;
            jointGroupPostion[5] =  4.231258618164063;
            moveGroup.setJointValueTarget(jointGroupPostion);
            moveGroup.move();
            ROS_INFO("Movint to middle position successfully");
            sleep(1);
        }

        void back_home_position()
        {
            std::vector<double> jointGroupPostion(6);
            jointGroupPostion[0] =0.15214654760360719;
            jointGroupPostion[1] = 1.7692206085205078;
            jointGroupPostion[2] = -1.3905731021881105;
            jointGroupPostion[3] = 0.04709754793643951;
            jointGroupPostion[4] = -1.7764798149108887;
            jointGroupPostion[5] =  4.231869432067871;
            moveGroup.setJointValueTarget(jointGroupPostion);
            moveGroup.move();
            ROS_INFO("Movint to home position successfully");
            sleep(1);
        }
};

int main(int argc, char** argv)
{

    ros::init(argc, argv, "rm65_pick_place");
    ros::AsyncSpinner spin(1);
    spin.start();
    
    RM65Control rm;
    rm.back_home_position();
    // rm.back_middle_position();
    // rm.move_target_position();
    ros::waitForShutdown();
    return 0;
}
