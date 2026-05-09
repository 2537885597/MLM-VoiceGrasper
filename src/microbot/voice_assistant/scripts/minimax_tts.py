#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimax 语音合成节点
功能：接收 TTS 请求 → Minimax TTS → 播放语音
"""

import rospy
import requests
import json
import base64
import os
import time
import subprocess
from voice_assistant.msg import TTSRequest, TTSResponse
import threading


class MinimaxTTSNode:
    def __init__(self):
        try:
            rospy.init_node('minimax_tts_node', anonymous=True)
            rospy.loginfo("Minimax 语音合成节点启动中...")
            
            # Minimax TTS 配置
            self.group_id = '1891387212730220598'
            self.api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiVXNlck5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiQWNjb3VudCI6IiIsIlN1YmplY3RJRCI6IjE4OTEzODcyMTI3Mzg2MDkyMDYiLCJQaG9uZSI6IjE5ODU5Nzc2NTU4IiwiR3JvdXBJRCI6IjE4OTEzODcyMTI3MzAyMjA1OTgiLCJQYWdlTmFtZSI6IiIsIk1haWwiOiIyNTM3ODg1NTk3QHFxLmNvbSIsIkNyZWF0ZVRpbWUiOiIyMDI1LTAzLTIxIDE5OjU1OjUwIiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.dSJNVnpMYUorisFR6k_3mPLCFbGN6S28xzzhPfJ4Rqd8A6eyaTXq64cHzEMERqnbQLzIlX71TNLM0yGVE1R8s8sVZ0VqPCeXKkYX0z6mOSfSmKUrYvywYbVQ8fkVCftfzxlMbi5DU6sKJ7-jHh99cift3jOD0gnon-t7Lg-CT7EbwY8YMX3_iir9e75HtYpk0pCL9qqaoL9ndN1g7CXc3iGImErjnQUGKJpjjou1P3sqjqtdsTISRr0q2U2iZw1m2wFa98MdurSGXxlCR7Btd76kLw2QIS7DJmkuVYrDQ0ZBAR9vSLpi3WESIv16MT2aCCaez9eOYcRCWk_ykXgq8g'
            
            self.tts_url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={self.group_id}"
            self.tts_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 创建临时目录
            self.temp_dir = rospy.get_param('~temp_dir', 'audio_temp')
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
            rospy.loginfo(f"临时文件目录：{self.temp_dir}")
            
            # 播放进程
            self.play_process = None
            self.play_lock = threading.Lock()
            
            # 订阅 TTS 请求
            self.tts_sub = rospy.Subscriber('/tts_request', TTSRequest, self.tts_callback, queue_size=10)
            
            rospy.loginfo("Minimax 语音合成节点初始化完成")
            rospy.loginfo("等待 TTS 请求...")
            
        except Exception as e:
            rospy.logfatal("❌ 节点初始化失败！")
            rospy.logfatal(f"错误信息：{str(e)}")
            import traceback
            traceback.print_exc()
            rospy.signal_shutdown("初始化失败")
    
    def tts_callback(self, msg):
        """TTS 请求回调"""
        try:
            if msg.text:
                rospy.loginfo(f"收到 TTS 请求：{msg.text}")
                self.process_tts(msg.text)
            else:
                rospy.logwarn("TTS 请求文本为空")
        except Exception as e:
            rospy.logerr(f"TTS 处理失败：{str(e)}")
    
    def process_tts(self, text):
        """处理 TTS 请求"""
        try:
            # 调用 Minimax TTS API
            audio_path = self.text_to_speech(text)
            
            if audio_path and os.path.exists(audio_path):
                rospy.loginfo(f"语音合成完成：{audio_path}")
                self.play_audio(audio_path)
            else:
                rospy.logerr("语音合成失败")
                
        except Exception as e:
            rospy.logerr(f"TTS 流程失败：{str(e)}")
            import traceback
            traceback.print_exc()
    
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
                "format": "wav",
                "channel": 1
            }
        }
        
        try:
            response = requests.post(
                self.tts_url,
                headers=self.tts_headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "data" in data and "audio" in data["data"]:
                    audio_hex = data["data"]["audio"]
                    audio_bytes = bytes.fromhex(audio_hex)
                    
                    timestamp = int(time.time())
                    audio_path = os.path.join(self.temp_dir, f"tts_{timestamp}.wav")
                    
                    with open(audio_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    return audio_path
                else:
                    rospy.logerr(f"TTS API 响应格式错误：{data}")
                    return None
            else:
                rospy.logerr(f"TTS API 请求失败：{response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            rospy.logerr(f"TTS 合成失败：{str(e)}")
            return None
    
    def play_audio(self, audio_path):
        """播放音频文件"""
        try:
            with self.play_lock:
                # 停止之前的播放
                if self.play_process and self.play_process.poll() is None:
                    self.play_process.terminate()
                    self.play_process.wait()
                
                # 播放 WAV 文件
                self.play_process = subprocess.Popen(
                    ['aplay', audio_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                rospy.loginfo("开始播放语音...")
                
        except subprocess.CalledProcessError as e:
            rospy.logerr(f"音频播放失败：{str(e)}")
        except Exception as e:
            rospy.logerr(f"音频播放失败：{str(e)}")


if __name__ == "__main__":
    try:
        node = MinimaxTTSNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点被中断")
    except KeyboardInterrupt:
        rospy.loginfo("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点运行失败：{str(e)}")
        import traceback
        traceback.print_exc()
