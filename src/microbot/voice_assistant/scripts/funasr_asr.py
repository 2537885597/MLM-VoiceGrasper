#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FunASR 语音识别节点
功能：麦克风音频 → FunASR ASR → 发布语音识别文本
"""

import rospy
import numpy as np
import sounddevice as sd
import wave
import threading
import os
from queue import Queue
from voice_assistant.msg import ASRResponse
from funasr import AutoModel


class FunASRNode:
    def __init__(self):
        try:
            rospy.init_node('funasr_asr_node', anonymous=True)
            rospy.loginfo("FunASR 语音识别节点启动中...")
            
            # 加载 FunASR 模型
            model_name = rospy.get_param('~asr_model', 'paraformer-zh')
            rospy.loginfo(f"加载 FunASR {model_name} 模型...")
            self.asr_model = AutoModel(model=model_name, disable_update=True)
            rospy.loginfo("FunASR 模型加载完成")
            
            # 录音参数
            self.samplerate = 16000
            self.dtype = "int16"
            self.channels = 1
            self.data_queue = Queue()
            self.stop_event = threading.Event()
            self.recording_thread = None
            self.is_listening = False
            
            # 录音文件路径
            self.wav_path = rospy.get_param('~wav_path', '/home/rm/realman_ws/src/microbot/voice_assistant/scripts/audio_temp/test_record.wav')
            
            # 发布识别结果
            self.asr_pub = rospy.Publisher('/audio/asr_result', ASRResponse, queue_size=10)
            
            rospy.loginfo("FunASR 语音识别节点初始化完成")
            rospy.loginfo("按回车键开始录音...")
            
        except Exception as e:
            rospy.logfatal("❌ 节点初始化失败！")
            rospy.logfatal(f"错误信息：{str(e)}")
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
        """录音线程"""
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
        """保存录音到 WAV 文件"""
        audio_data = b"".join(self.data_queue.queue)
        with wave.open(self.wav_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(audio_data)
        rospy.loginfo(f"✅ 已保存：{self.wav_path}")
    
    def process_recorded_audio(self):
        """处理录制的音频数据"""
        try:
            self.save_to_wav()
            rospy.loginfo("正在调用 FunASR 进行语音识别...")
            result = self.asr_model.generate(input=self.wav_path)
            
            if result and len(result) > 0:
                user_text = result[0].get('text', '').strip()
            else:
                user_text = ""
            
            rospy.loginfo(f"识别结果：{user_text}")
            self.publish_asr_result(user_text)
            
        except Exception as e:
            rospy.logerr(f"语音识别失败：{str(e)}")
            import traceback
            traceback.print_exc()
            self.publish_asr_result("", success=False, error=str(e))
    
    def publish_asr_result(self, transcript, success=True, language='zh', confidence=0.95, error=""):
        """发布 ASR 结果"""
        msg = ASRResponse()
        msg.transcript = transcript
        msg.language = language
        msg.confidence = confidence
        msg.success = success
        
        if not success:
            rospy.logerr(f"语音识别失败：{error}")
        
        self.asr_pub.publish(msg)


if __name__ == "__main__":
    try:
        node = FunASRNode()
        while not rospy.is_shutdown():
            input()  # 等待回车开始录音
            node.start_recording()
            input()  # 等待回车停止录音
            node.stop_recording()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点被中断")
    except KeyboardInterrupt:
        rospy.loginfo("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点运行失败：{str(e)}")
        import traceback
        traceback.print_exc()
