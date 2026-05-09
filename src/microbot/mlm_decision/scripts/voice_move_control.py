#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音移动控制技能节点
功能：
1. 订阅 MLM 决策中枢发布的移动指令
2. 通过 TCP 连接移动底盘（Wheeltec），发送控制指令
3. 支持普通移动控制：前进/后退指定距离、左转/右转指定角度
4. 支持目标点位移动：使用点位代号或坐标进行导航

底盘 API（基于 Wheeltec HTTP API over TCP）：
- 速度控制：/api/joy_control?linear_velocity=X&angular_velocity=Y
  线速度范围：-0.5~0.5 m/s，角速度范围：-1.0~1.0 rad/s
  单个命令持续时间 0.5 秒，需连续发送保持运动
- 目标点导航：/api/move?marker=点位代号 或 /api/move?location=x,y,theta
- 取消导航：/api/move/cancel
"""

import rospy
import socket
import time
import threading
import json
import math
from std_msgs.msg import String


class VoiceMoveControl:
    def __init__(self):
        try:
            rospy.loginfo("语音移动控制技能节点启动中...")

            self.chassis_ip = rospy.get_param('~chassis_ip', '192.168.10.10')
            self.chassis_port = rospy.get_param('~chassis_port', 31001)
            self.max_linear = rospy.get_param('~max_linear', 0.3)
            self.max_angular = rospy.get_param('~max_angular', 0.8)
            self.send_interval = rospy.get_param('~send_interval', 0.1)
            self.distance_tolerance = rospy.get_param('~distance_tolerance', 0.1)
            self.theta_tolerance = rospy.get_param('~theta_tolerance', 0.1)

            rospy.loginfo(f"底盘配置：{self.chassis_ip}:{self.chassis_port}")
            rospy.loginfo(f"最大线速度：{self.max_linear} m/s, 最大角速度：{self.max_angular} rad/s")

            self.sock = None
            self.sock_lock = threading.Lock()
            self.move_thread = None
            self.stop_event = threading.Event()
            self.is_moving = False

            self.connect_chassis()

            self.cmd_sub = rospy.Subscriber(
                '/move_command',
                String,
                self.move_command_callback,
                queue_size=10
            )

            self.status_pub = rospy.Publisher('/move_status', String, queue_size=10)

            rospy.loginfo("语音移动控制技能节点初始化完成")
            rospy.loginfo("等待移动指令...")
            rospy.loginfo("订阅话题：/move_command")

        except Exception as e:
            rospy.logfatal("语音移动控制技能节点初始化失败！")
            rospy.logfatal(f"错误信息：{str(e)}")
            import traceback
            traceback.print_exc()
            rospy.signal_shutdown("初始化失败")

    def connect_chassis(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.chassis_ip, self.chassis_port))
            self.sock.settimeout(None)
            rospy.loginfo(f"已连接到底盘 {self.chassis_ip}:{self.chassis_port}")
        except Exception as e:
            rospy.logerr(f"连接底盘失败 {self.chassis_ip}:{self.chassis_port} -> {str(e)}")
            self.sock = None

    def send_http_request(self, path, params=None):
        if self.sock is None:
            rospy.logwarn("底盘未连接，尝试重连...")
            self.connect_chassis()
            if self.sock is None:
                return False

        query_string = ""
        if params:
            query_parts = [f"{k}={v}" for k, v in params.items()]
            query_string = "&".join(query_parts)

        if query_string:
            request_line = f"{path}?{query_string}\n"
        else:
            request_line = f"{path}\n"

        with self.sock_lock:
            try:
                self.sock.sendall(request_line.encode('utf-8'))
                return True
            except Exception as e:
                rospy.logerr(f"发送指令失败：{str(e)}")
                self.sock = None
                return False

    def send_joy_control(self, linear, angular):
        linear = max(-0.5, min(0.5, linear))
        angular = max(-1.0, min(1.0, angular))
        params = {
            "linear_velocity": f"{linear:.3f}",
            "angular_velocity": f"{angular:.3f}"
        }
        return self.send_http_request("/api/joy_control", params)

    def send_move_marker(self, marker):
        params = {
            "marker": marker,
            "distance_tolerance": f"{self.distance_tolerance}",
            "theta_tolerance": f"{self.theta_tolerance}"
        }
        return self.send_http_request("/api/move", params)

    def send_move_location(self, x, y, theta):
        params = {
            "location": f"{x:.3f},{y:.3f},{theta:.3f}",
            "distance_tolerance": f"{self.distance_tolerance}",
            "theta_tolerance": f"{self.theta_tolerance}"
        }
        return self.send_http_request("/api/move", params)

    def send_cancel_move(self):
        return self.send_http_request("/api/move/cancel")

    def stop_move(self):
        self.stop_event.set()
        self.send_joy_control(0.0, 0.0)
        self.is_moving = False

    def move_command_callback(self, msg):
        try:
            command_str = msg.data.strip()
            rospy.loginfo(f"收到移动指令：{command_str}")

            try:
                command = json.loads(command_str)
            except json.JSONDecodeError:
                command = {"action": command_str}

            action = command.get("action", "").lower()

            if self.is_moving:
                self.stop_move()
                if self.move_thread and self.move_thread.is_alive():
                    self.move_thread.join(timeout=0.5)

            if action == "stop":
                self.stop_move()
                self.publish_status("stopped", "已停止")
                return

            elif action == "forward":
                distance = command.get("distance", 0.5)
                self.start_distance_move(distance, "前进")

            elif action == "backward":
                distance = command.get("distance", 0.5)
                self.start_distance_move(-distance, "后退")

            elif action == "left":
                angle_deg = command.get("angle", 90)
                self.start_angle_move(math.radians(angle_deg), "左转")

            elif action == "right":
                angle_deg = command.get("angle", 90)
                self.start_angle_move(-math.radians(angle_deg), "右转")

            elif action == "move_to_marker":
                marker = command.get("marker", "")
                if marker:
                    self.start_marker_navigation(marker)
                else:
                    rospy.logwarn("未提供点位代号")
                    self.publish_status("error", "未提供点位代号")

            elif action == "move_to_location":
                x = command.get("x", 0.0)
                y = command.get("y", 0.0)
                theta = command.get("theta", 0.0)
                self.start_location_navigation(x, y, theta)

            elif action == "cancel_move":
                self.send_cancel_move()
                self.publish_status("cancelled", "移动已取消")

            else:
                rospy.logwarn(f"未知的移动指令：{action}")
                self.publish_status("unknown_command", f"未知指令：{action}")

        except Exception as e:
            rospy.logerr(f"处理移动指令失败：{str(e)}")
            import traceback
            traceback.print_exc()

    def start_distance_move(self, distance, description):
        self.stop_event.clear()
        self.is_moving = True

        self.move_thread = threading.Thread(
            target=self._execute_distance_move,
            args=(distance, description),
            daemon=True
        )
        self.move_thread.start()

    def _execute_distance_move(self, distance, description):
        abs_distance = abs(distance)
        direction = 1.0 if distance > 0 else -1.0
        duration = abs_distance / self.max_linear

        rospy.loginfo(f"开始{description} {abs_distance:.2f} 米，预计持续 {duration:.1f} 秒")
        self.publish_status("moving", f"正在{description} {abs_distance:.2f} 米")

        start_time = time.time()
        while time.time() - start_time < duration and not self.stop_event.is_set():
            self.send_joy_control(direction * self.max_linear, 0.0)
            time.sleep(self.send_interval)

        if not self.stop_event.is_set():
            self.send_joy_control(0.0, 0.0)
            rospy.loginfo(f"{description}完成")
            self.publish_status("completed", f"{description} {abs_distance:.2f} 米完成")

        self.is_moving = False

    def start_angle_move(self, angle_rad, description):
        self.stop_event.clear()
        self.is_moving = True

        self.move_thread = threading.Thread(
            target=self._execute_angle_move,
            args=(angle_rad, description),
            daemon=True
        )
        self.move_thread.start()

    def _execute_angle_move(self, angle_rad, description):
        abs_angle = abs(angle_rad)
        direction = 1.0 if angle_rad > 0 else -1.0
        duration = abs_angle / self.max_angular

        angle_deg = math.degrees(abs_angle)
        rospy.loginfo(f"开始{description} {angle_deg:.0f} 度，预计持续 {duration:.1f} 秒")
        self.publish_status("moving", f"正在{description} {angle_deg:.0f} 度")

        start_time = time.time()
        while time.time() - start_time < duration and not self.stop_event.is_set():
            self.send_joy_control(0.0, direction * self.max_angular)
            time.sleep(self.send_interval)

        if not self.stop_event.is_set():
            self.send_joy_control(0.0, 0.0)
            rospy.loginfo(f"{description}完成")
            self.publish_status("completed", f"{description} {angle_deg:.0f} 度完成")

        self.is_moving = False

    def start_marker_navigation(self, marker):
        rospy.loginfo(f"开始导航到目标点位：{marker}")
        self.publish_status("navigating", f"导航到 {marker}")

        success = self.send_move_marker(marker)
        if not success:
            self.publish_status("error", "导航指令发送失败")
            return

        self.is_moving = True

        self.move_thread = threading.Thread(
            target=self._monitor_navigation,
            args=(f"点位 {marker}",),
            daemon=True
        )
        self.move_thread.start()

    def start_location_navigation(self, x, y, theta):
        rospy.loginfo(f"开始导航到目标坐标：x={x:.2f}, y={y:.2f}, theta={theta:.2f}")
        self.publish_status("navigating", f"导航到坐标 ({x:.2f}, {y:.2f})")

        success = self.send_move_location(x, y, theta)
        if not success:
            self.publish_status("error", "导航指令发送失败")
            return

        self.is_moving = True

        self.move_thread = threading.Thread(
            target=self._monitor_navigation,
            args=(f"坐标 ({x:.2f}, {y:.2f})",),
            daemon=True
        )
        self.move_thread.start()

    def _monitor_navigation(self, target_desc):
        timeout = 120.0
        start_time = time.time()

        while time.time() - start_time < timeout and not self.stop_event.is_set():
            time.sleep(0.5)

        if self.stop_event.is_set():
            self.send_cancel_move()
            self.publish_status("cancelled", "导航已取消")
        else:
            self.publish_status("navigation_timeout", f"导航到 {target_desc} 超时或完成")

        self.is_moving = False

    def publish_status(self, status, message):
        try:
            status_msg = String()
            status_data = json.dumps({
                "status": status,
                "message": message,
                "timestamp": time.time()
            })
            status_msg.data = status_data
            self.status_pub.publish(status_msg)
        except Exception as e:
            rospy.logerr(f"发布状态失败：{str(e)}")

    def shutdown(self):
        rospy.loginfo("关闭移动控制技能节点...")
        self.stop_move()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        rospy.loginfo("移动控制技能节点已关闭")


if __name__ == "__main__":
    try:
        rospy.init_node('voice_move_control', anonymous=True)
        node = VoiceMoveControl()
        rospy.on_shutdown(node.shutdown)
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点运行失败：{str(e)}")
        import traceback
        traceback.print_exc()
