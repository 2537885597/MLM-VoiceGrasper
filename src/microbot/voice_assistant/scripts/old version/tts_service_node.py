#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
import tempfile
from voice_assistant.msg import TTSRequest, TTSResponse
import voice_generation

class TTSServiceNode:
    def __init__(self):
        rospy.init_node("tts_service", anonymous=True)
        # 语音合成请求话题订阅者
        self.tts_sub = rospy.Subscriber('/voice_assistant/tts_request', TTSRequest, self.tts_request_cb)
        # 语音合成响应话题发布者
        self.tts_pub = rospy.Publisher('/voice_assistant/tts_response', TTSResponse, queue_size=10)
        # 正在合成语音话题发布者
        self.speaking_pub = rospy.Publisher('/voice_assistant/speaking', Bool, queue_size=10)
        # 创建临时目录存储音频文件
        self.temp_dir = tempfile.mkdtemp(prefix="voice_assistant_")
        rospy.loinfo(f"TTS服务节点已启动，音频文件存储在：{self.temp_dir}")
    
    def tts_request_cb(self, msg):
        """处理TTS请求"""
        rospy.loginfo(f"收到TTS请求：{msg.text}")
        response = TTSResponse()
        try:
            # 设置说话状态
            self.speaking_pub.publish(True)
            # 调用语音合成
            audio_chunk_iterator = voice_generation.call_tts_stream(msg.text)
            audio_data = voice_generation.audio_play(audio_chunk_iterator)
            # 保存音频文件
            import time
            filename = f"tts_{int(time.tine())}.mp3"
            filepath = os.path.join(self.temp_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            response.audio_file_path = filepath
            response.success = True

            rospy.loginfo(f"语音合成完成：{filepath}")
        except Exception as e:
            rospy.logerr(f"语音合成失败：{str(e)}")
            response.success = False
            response.audio_file_path = ""
        finally:
            # 发布响应
            self.tts_pub.publish(response)
            self.speaking_pub.publish(False)
        
    def run(self):
        """主循环"""
        rospy.spin()

if __name__ == "__main__":
    try:
        node = TTSServiceNode()
        node.run()
    except rospy.ROSInterruptException:
        pass