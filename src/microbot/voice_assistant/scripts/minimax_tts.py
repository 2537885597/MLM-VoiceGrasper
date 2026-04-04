#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimax TTS语音合成节点
接收文本，调用Minimax API生成语音并播放
"""

import rospy
import requests
import json
import tempfile
import os
import time
import subprocess
from voice_assistant.msg import TTSRequest, TTSResponse

class MinimaxTTS:
    def __init__(self):
        rospy.init_node('minimax_tts_node', anonymous=True)
        rospy.loginfo("Minimax TTS语音合成节点启动中...")
        
        # 从参数服务器获取API配置
        self.group_id = rospy.get_param('~group_id', '1891387212730220598')
        self.api_key = rospy.get_param('~api_key', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiVXNlck5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiQWNjb3VudCI6IiIsIlN1YmplY3RJRCI6IjE4OTEzODcyMTI3Mzg2MDkyMDYiLCJQaG9uZSI6IjE5ODU5Nzc2NTU4IiwiR3JvdXBJRCI6IjE4OTEzODcyMTI3MzAyMjA1OTgiLCJQYWdlTmFtZSI6IiIsIk1haWwiOiIyNTM3ODg1NTk3QHFxLmNvbSIsIkNyZWF0ZVRpbWUiOiIyMDI1LTAzLTIxIDE5OjU1OjUwIiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.dSJNVnpMYUorisFR6k_3mPLCFbGN6S28xzzhPfJ4Rqd8A6eyaTXq64cHzEMERqnbQLzIlX71TNLM0yGVE1R8s8sVZ0VqPCeXKkYX0z6mOSfSmKUrYvywYbVQ8fkVCftfzxlMbi5DU6sKJ7-jHh99cift3jOD0gnon-t7Lg-CT7EbwY8YMX3_iir9e75HtYpk0pCL9qqaoL9ndN1g7CXc3iGImErjnQUGKJpjjou1P3sqjqtdsTISRr0q2U2iZw1m2wFa98MdurSGXxlCR7Btd76kLw2QIS7DJmkuVYrDQ0ZBAR9vSLpi3WESIv16MT2aCCaez9eOYcRCWk_ykXgq8g')
        
        self.base_url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={self.group_id}"
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 创建临时目录存储音频文件
        self.temp_dir = tempfile.mkdtemp(prefix="tts_audio_")
        rospy.loginfo(f"TTS音频文件存储目录: {self.temp_dir}")
        
        # 订阅TTS请求
        rospy.Subscriber('/tts_request', TTSRequest, self.tts_callback)
        
        # 发布TTS响应
        self.tts_pub = rospy.Publisher('/tts_response', TTSResponse, queue_size=10)
        
        rospy.loginfo("Minimax TTS节点初始化完成")
    
    def tts_callback(self, msg):
        """TTS请求回调"""
        rospy.loginfo(f"收到TTS请求: {msg.text}")
        
        try:
            audio_path = self.text_to_speech(msg.text)
            
            response = TTSResponse()
            response.audio_file_path = audio_path
            response.success = True
            
            self.tts_pub.publish(response)
            rospy.loginfo(f"语音合成完成: {audio_path}")
            
        except Exception as e:
            rospy.logerr(f"语音合成失败: {str(e)}")
            
            response = TTSResponse()
            response.success = False
            response.audio_file_path = ""
            
            self.tts_pub.publish(response)
    
    def text_to_speech(self, text):
        """将文本转换为语音"""
        payload = {
            "model": "speech-01-turbo",
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": "qiaopi_mengmei",
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0
            },
            "pronunciation_dict": {
                "tone": [
                    "处理/(chu3)(li3)",
                    "危险/dangerous"
                ]
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            }
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "data" in data and "audio" in data["data"]:
                    audio_base64 = data["data"]["audio"]
                    
                    # 解码Base64音频数据
                    import base64
                    audio_bytes = base64.b64decode(audio_base64)
                    
                    # 保存音频文件
                    timestamp = int(time.time())
                    audio_path = os.path.join(self.temp_dir, f"tts_{timestamp}.mp3")
                    
                    with open(audio_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    return audio_path
                else:
                    raise Exception(f"API响应格式错误: {data}")
            else:
                raise Exception(f"API请求失败: {response.status_code}, {response.text}")
                
        except Exception as e:
            raise Exception(f"语音合成失败: {str(e)}")

def main():
    try:
        tts = MinimaxTTS()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr(f"节点启动失败: {str(e)}")
