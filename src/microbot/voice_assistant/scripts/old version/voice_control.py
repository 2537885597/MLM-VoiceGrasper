#! /usr/bin/env python3
import rospy
from std_msgs.msg import Bool
import threading
import time

class VoiceControl:
    def __init__(self):
        self.start_pub = rospy.Publisher('/voice_assistant/start_listening', Bool, queue_size=1)
        self.stop_pub = rospy.Publisher('/voice_assistant/stop_listening', Bool, queue_size=1)
    
    def start_listening(self):
        """开始监听"""
        msg = Bool()
        msg.data = True
        self.start_pub.publish(msg)
        print("开始监听...")
    
    def stop_listening(self):
        """停止监听"""
        msg = Bool()
        msg.data = True
        self.stop_pub.publish(msg)
        print("停止监听...")

def main():
    rospy.init_node('voice_control', anonymous=True)
    controller = VoiceControl()
    print("语音助手控制界面")
    print("输入 'e' 开始录音")
    print("输入 's' 停止录音")
    print("输入 'q' 退出")

    while not rospy.is_shutdown():
        cmd = input("> ").strip().lower
        if cmd == "e":
            controller.start_listening()
        elif cmd == "s":
            controller.stop_listening()
        elif cmd == 'q':
            break
        else:
            print("未知命令")

if __name__ == "__main__":
    main()