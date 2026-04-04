#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主程序app -> ros节点（处理中枢）
"""
# ros所需导入
import rospy

# 原导入
import rospy
from std_msgs.msg import String
from voice_assistant.msg import TTSRequest, TTSResponse
import time
import mlm_processor
import voice_generation

class VoiceAssistant:
    def __init__(self):
        # 初始化ROS节点
        rospy.init_node("voice_assistant_node", anonymous=True)
        rospy.loginfo("VoiceAssistant节点已启动")

        # 订阅完整识别结果话题，xf_asr_offline_node 就是 voice_control 节点
        rospy.Subscriber("/xf_asr_offline_node/whole_voice_result", String, self.whole_result_callback)
        
        # 语音合成请求话题发布者
        self.tts_request_pub = rospy.Publisher("/voice_assistant_node/tts_request", TTSRequest, queue_size=10)
        # 语音合成响应话题订阅者
        rospy.Subscriber("/voice_assistant_node/tts_response", TTSResponse, self.tts_response_cb)

        # 创建mlm_processor节点实例
        self.mlm_processor_node = mlm_processor.MLMProcessor()
        # 创建voice_generation节点实例
        self.voice_generation_node = voice_generation.VoiceGeneration()

    def whole_result_callback(self, msg):
        """完整识别结果回调函数"""
        rospy.loginfo(f"收到完整识别结果：[{msg.data}]")
        # 自定义处理：发送给大模型进行问答对话
        mlm_response = self.mlm_processor_node.process_recognition_data(msg.data)
        # 发布TTS语音合成请求
        tts_request = TTSRequest()
        tts_request.text = mlm_response
        tts_request.voice_preset = "default"
        self.tts_request_pub.publish(tts_request)

    def tts_response_cb(self, msg):
        """TTS响应回调"""
        if msg.success:
            rospy.loginfo(f"语音合成完成：{msg.audio_file_path}")
        else:
            rospy.logerr("语音合成失败")

    def run(self):
        """主循环"""
        # 让子节点也运行
        self.mlm_processor_node.run()
        self.voice_generation_node.run()
        
        rate = rospy.Rate(10) # 10Hz
        while not rospy.is_shutdown():
            rate.sleep()

if __name__ == "__main__":
    try:
        node = VoiceAssistant()
        node.run()
    except rospy.ROSInterruptException:
        pass