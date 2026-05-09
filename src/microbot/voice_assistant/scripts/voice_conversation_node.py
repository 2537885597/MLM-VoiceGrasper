#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音对话节点
完整流程：麦克风音频(sounddevice) → Whisper ASR → Ollama LLM → Minimax TTS → 播放
"""

import rospy
import requests
import json
import base64
import os
import time
import numpy as np
import torch
import whisper
import sounddevice as sd
import wave
import threading
from queue import Queue
from voice_assistant.msg import ASRRequest, ASRResponse, TTSRequest, TTSResponse
import subprocess
from ollama import chat

from mic_msg.msg import mic_pcm_msg

class VoiceConversationNode:
    def __init__(self):
        try:
            rospy.init_node('voice_conversation_node', anonymous=True)
            rospy.loginfo("语音对话节点启动中...")
            
            # 加载Whisper模型
            model_name = rospy.get_param('~asr_model', 'base')
            rospy.loginfo(f"加载Whisper {model_name} 模型...")
            self.asr_model = whisper.load_model(model_name)
            rospy.loginfo("Whisper模型加载完成")
            self.wav_path = "test_record.wav"
            
            # Ollama LLM配置
            self.ollama_url = rospy.get_param('~ollama_url', 'http://localhost:11434/v1')
            self.llm_model = rospy.get_param('~llm_model', 'qwen3:4b')
            rospy.loginfo(f"Ollama LLM配置: {self.ollama_url}, 模型: {self.llm_model}")
            
            # Minimax TTS配置
            self.group_id = '1891387212730220598'
            self.api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiVXNlck5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiQWNjb3VudCI6IiIsIlN1YmplY3RJRCI6IjE4OTEzODcyMTI3Mzg2MDkyMDYiLCJQaG9uZSI6IjE5ODU5Nzc2NTU4IiwiR3JvdXBJRCI6IjE4OTEzODcyMTI3MzAyMjA1OTgiLCJQYWdlTmFtZSI6IiIsIk1haWwiOiIyNTM3ODg1NTk3QHFxLmNvbSIsIkNyZWF0ZVRpbWUiOiIyMDI1LTAzLTIxIDE5OjU1OjUwIiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.dSJNVnpMYUorisFR6k_3mPLCFbGN6S28xzzhPfJ4Rqd8A6eyaTXq64cHzEMERqnbQLzIlX71TNLM0yGVE1R8s8sVZ0VqPCeXKkYX0z6mOSfSmKUrYvywYbVQ8fkVCftfzxlMbi5DU6sKJ7-jHh99cift3jOD0gnon-t7Lg-CT7EbwY8YMX3_iir9e75HtYpk0pCL9qqaoL9ndN1g7CXc3iGImErjnQUGKJpjjou1P3sqjqtdsTISRr0q2U2iZw1m2wFa98MdurSGXxlCR7Btd76kLw2QIS7DJmkuVYrDQ0ZBAR9vSLpi3WESIv16MT2aCCaez9eOYcRCWk_ykXgq8g'
            
            self.tts_url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={self.group_id}"
            self.tts_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 创建临时目录
            self.temp_dir = "audio_temp"
            rospy.loginfo(f"临时文件目录: {self.temp_dir}")
            
            # sounddevice录音参数
            self.samplerate = 16000
            self.dtype = "int16"
            self.channels = 1
            self.data_queue = Queue()
            self.stop_event = threading.Event()
            self.recording_thread = None
            self.is_listening = False
            
            # 发布识别结果
            self.asr_pub = rospy.Publisher('/audio/asr_result', ASRResponse, queue_size=10)
            
            # 发布TTS请求
            self.tts_pub = rospy.Publisher('/tts_request', TTSRequest, queue_size=10)
            
            # 播放进程
            self.play_process = None
            
            rospy.loginfo("语音对话节点初始化完成")
        except Exception as e:
            rospy.logfatal("❌ 节点初始化失败！")
            rospy.logfatal(f"错误信息: {str(e)}")
            import traceback
            traceback.print_exc()
            rospy.signal_shutdown("初始化失败")
    
    def start_recording(self):
        """开始录音"""
        self.is_listening = True
        self.data_queue = Queue()
        self.stop_event.clear()
        
        self.recording_thread = threading.Thread(
            target=self.record_audio,
            args=(self.stop_event, self.data_queue),
        )
        self.recording_thread.start()
        rospy.loginfo(">>>>> 开始录音........")
    
    def stop_recording(self):
        """停止录音并处理音频"""
        if self.is_listening:
            self.stop_event.set()
            self.recording_thread.join()
            self.is_listening = False
            rospy.loginfo(">>>>> 停止录音........")
            self.process_recorded_audio()
    
    def record_audio(self, stop_event, data_queue):
        """sd 录音线程"""
        def callback(indata, frames, time, status):
            if status:
                rospy.logwarn(f"警告：{status}")
            data_queue.put(bytes(indata))
        
        with sd.RawInputStream(
            samplerate=self.samplerate,
            dtype=self.dtype,
            channels=self.channels,
            callback=callback
        ):
            while not stop_event.is_set():
                continue

    def save_to_wav(self):
        audio_data = b"".join(self.data_queue.queue)
        with wave.open(self.wav_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(audio_data)
        print(f"✅ 已保存：{self.wav_path}")
    
    def process_recorded_audio(self):
        """处理录制的音频数据"""
        try:
            # 1. Whisper ASR: 音频转文本
            # audio_data = b"".join(self.data_queue.queue)
            # audio_np = np.frombuffer(audio_data, dtype=np.int16)
            # audio_np = audio_np.astype(np.float32) / 32768.0
            # rospy.loginfo("正在调用Whisper进行语音识别...")
            # result = self.asr_model.transcribe(audio_np, language='zh', fp16=False)

            self.save_to_wav()
            rospy.loginfo("正在调用Whisper进行语音识别...")
            result = self.asr_model.transcribe(self.wav_path, language='zh', fp16=False)
            user_text = result['text'].strip()
            
            rospy.loginfo(f"识别结果: {user_text}")
            self.publish_asr_result(user_text)
            
            if not user_text:
                rospy.logwarn("识别结果为空，跳过对话")
                return
            
            # 2. Ollama LLM: 生成回复
            rospy.loginfo("正在调用Ollama LLM生成回复...")
            llm_response = self.call_ollama_llm(user_text)
            
            if not llm_response:
                rospy.logerr("LLM响应为空")
                return
            
            rospy.loginfo(f"LLM回复: {llm_response}")
            
            # 3. Minimax TTS: 合成语音
            rospy.loginfo("正在调用Minimax TTS合成语音...")
            audio_path = self.text_to_speech(llm_response)
            
            if audio_path and os.path.exists(audio_path):
                rospy.loginfo(f"语音合成完成: {audio_path}")
                self.play_audio(audio_path)
            else:
                rospy.logerr("语音合成失败")
                
        except Exception as e:
            rospy.logerr(f"对话流程失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def call_ollama_llm(self, user_text):
        """调用Ollama LLM生成回复"""
        try:
            # 构建对话提示
            conversation_prompt = f"""你是一个智能语音助手。请根据用户的输入给出自然、简洁的回复。"""
            
            # 调用Ollama API
            response = chat(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": conversation_prompt},
                    {"role": "user", "content": user_text}
                ],
                stream=False,
                options={
                    "temperature": 0.7,
                    "max_tokens": 2048
                }
            )

            result = response.message.content.strip()
            return result
                
        except requests.exceptions.RequestException as e:
            rospy.logerr(f"LLM API调用失败: {str(e)}")
            return None
        except Exception as e:
            rospy.logerr(f"LLM处理异常: {str(e)}")
            return None
    
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
                "format": "wav",  # 32khz mp3
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
                    # 👈 后缀直接改成 .wav 就行
                    audio_path = os.path.join(self.temp_dir, f"tts_{timestamp}.wav")
                    
                    with open(audio_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    return audio_path
                else:
                    rospy.logerr(f"TTS API响应格式错误: {data}")
                    return None
            else:
                rospy.logerr(f"TTS API请求失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            rospy.logerr(f"TTS合成失败: {str(e)}")
            return None
    
    def play_audio(self, audio_path):
        """播放音频文件"""
        try:
            # 停止之前的播放
            if self.play_process and self.play_process.poll() is None:
                self.play_process.terminate()
                self.play_process.wait()
            
            # 直接播放WAV格式，（Minimax TTS返回的是32kHz MP3）
            # aplay支持WAV格式
            self.play_process = subprocess.Popen(
                ['aplay', audio_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            rospy.loginfo("开始播放语音...")
            
        except subprocess.CalledProcessError as e:
            rospy.logerr(f"音频播放失败: {str(e)}")
        except Exception as e:
            rospy.logerr(f"音频播放失败: {str(e)}")
    
    def bytes_to_numpy(self, audio_bytes):
        """将字节数据转换为numpy数组"""
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0
        return audio_np
    
    def pcm_bytes_to_numpy(self, pcm_buf):
        """将PCM缓冲区转换为numpy数组（16位PCM）"""
        audio_np = np.frombuffer(pcm_buf, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0
        return audio_np
    
    def publish_asr_result(self, transcript, success=True, language='zh', confidence=0.95, error=""):
        """发布ASR结果"""
        msg = ASRResponse()
        msg.transcript = transcript
        msg.language = language
        msg.confidence = confidence
        msg.success = success
        
        if not success:
            rospy.logerr(f"语音识别失败: {error}")
        else:
            rospy.logdebug(f"识别结果: {transcript}")
        
        self.asr_pub.publish(msg)

if __name__ == "__main__":
    try:
        node = VoiceConversationNode()
        rospy.loginfo("语音对话节点已启动，按回车键开始录音...")
        input()
        node.start_recording()
        input()
        node.stop_recording()
        rospy.spin()
    except rospy.ROSInterruptException:
        print("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点启动失败: {str(e)}")
        import traceback
        traceback.print_exc()
