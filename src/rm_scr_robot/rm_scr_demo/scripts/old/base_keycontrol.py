#!/usr/bin/env python3
# base_keycontrol_step.py
# 点动控制：按一次 WASD，机器人移动一小段固定距离或角度后自动停止

import sys
import socket
import time
import threading
import math

# --- 配置 ---
ROBOT_IP = "192.168.10.10"    # 修改为你的底盘 IP
ROBOT_PORT = 31001            # 修改为你的底盘端口
STEP_DISTANCE = 0.02           # 每次前进/后退距离（单位：米）
STEP_ANGLE_DEG = 5.0         # 每次旋转角度（单位：度）
MAX_LINEAR = 0.1              # 线速度 (m/s)
MAX_ANGULAR = 0.4             # 角速度 (rad/s)
SEND_INTERVAL = 0.02          # 控制指令发送间隔（秒）

# --- 平台相关的非阻塞读取单字符 ---
if sys.platform.startswith('win'):
    import msvcrt
    def get_char_nonblocking():
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch
        return None
else:
    import sys, tty, termios, select
    def get_char_nonblocking():
        dr, dw, de = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1)
        return None

    class TerminalMode:
        def __enter__(self):
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            return self
        def __exit__(self, *args):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

# --- TCP 客户端 ---
class RobotClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.lock = threading.Lock()
        self.sock = None
        self.connect()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
            print("✅ 已连接到底盘 %s:%d" % (self.ip, self.port))
        except Exception as e:
            print("❌ 连接失败 %s:%d -> %s" % (self.ip, self.port, e))
            sys.exit(1)

    def send_joy(self, linear, angular):
        cmd = "/api/joy_control?linear_velocity={:.3f}&angular_velocity={:.3f}&uuid=keyboard\n".format(linear, angular)
        with self.lock:
            try:
                self.sock.sendall(cmd.encode('utf-8'))
            except Exception as e:
                print("⚠️ 发送失败:", e)

    def close(self):
        try:
            self.sock.close()
        except:
            pass

# --- 小步进移动执行器 ---
class StepMover:
    def __init__(self, client):
        self.client = client
        self.stop_event = threading.Event()
        self.move_lock = threading.Lock()
        self.thread = None

    def _execute_move(self, linear, angular, duration):
        """在后台以恒定速度运行指定时间"""
        start = time.time()
        while time.time() - start < duration and not self.stop_event.is_set():
            self.client.send_joy(linear, angular)
            time.sleep(SEND_INTERVAL)
        # 结束时确保停止（除非已被中断）
        if not self.stop_event.is_set():
            self.client.send_joy(0.0, 0.0)

    def request_move(self, move_type, value):
        """请求一次小步进移动"""
        with self.move_lock:
            # 取消当前动作
            self.stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=0.1)

            self.stop_event.clear()

            if move_type == 'linear':
                distance = abs(value)
                duration = distance / MAX_LINEAR
                linear_vel = MAX_LINEAR if value > 0 else -MAX_LINEAR
                angular_vel = 0.0
            elif move_type == 'angular':
                angle_rad = abs(value)
                duration = angle_rad / MAX_ANGULAR
                linear_vel = 0.0
                angular_vel = MAX_ANGULAR if value > 0 else -MAX_ANGULAR
            else:
                return

            # 启动新移动线程
            self.thread = threading.Thread(
                target=self._execute_move,
                args=(linear_vel, angular_vel, duration),
                daemon=True
            )
            self.thread.start()

    def stop_all(self):
        """立即停止所有移动"""
        self.stop_event.set()
        self.client.send_joy(0.0, 0.0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)

# --- 主控制循环 ---
def control_loop(client):
    mover = StepMover(client)
    print("\n🤖 点动控制模式（小步进）")
    print(f"  W: 前进 {STEP_DISTANCE:.2f} 米")
    print(f"  S: 后退 {STEP_DISTANCE:.2f} 米")
    print(f"  A: 左转 {STEP_ANGLE_DEG}°")
    print(f"  D: 右转 {STEP_ANGLE_DEG}°")
    print("  空格 / X: 紧急停止")
    print("  Q / ESC: 退出程序\n")

    try:
        while True:
            ch = get_char_nonblocking()
            if ch:
                key = ch.lower()
                if key == 'w':
                    mover.request_move('linear', STEP_DISTANCE)
                elif key == 's':
                    mover.request_move('linear', -STEP_DISTANCE)
                elif key == 'a':
                    mover.request_move('angular', math.radians(STEP_ANGLE_DEG))
                elif key == 'd':
                    mover.request_move('angular', -math.radians(STEP_ANGLE_DEG))
                elif key in (' ', 'x'):
                    mover.stop_all()
                    print("🛑 已紧急停止")
                elif key in ('q', '\x1b'):  # ESC or Q
                    print("👋 正在退出...")
                    break
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        mover.stop_all()
        client.close()
        print("✅ 控制已退出。")

# --- 启动入口 ---
if __name__ == '__main__':
    client = RobotClient(ROBOT_IP, ROBOT_PORT)
    if sys.platform.startswith('win'):
        control_loop(client)
    else:
        with TerminalMode():
            control_loop(client)