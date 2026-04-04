#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper语音识别节点
接收麦克风音频数据，调用Whisper模型进行语音识别
"""

import rospy
import numpy as np
import torch
import whisper
from voice_assistant.msg import ASRRequest, ASRResponse
import tempfile
import os
import wave
import struct

class WhisperASR:
    def __init__(self):
        rospy.init_node('whisper_asr_node', anonymous=True)
        rospy.loginfo("Whisper语音识别节点启动中...")
        
        # 加载Whisper模型
        model_name = rospy.get_param('~model', 'base')
        rospy.loginfo(f"加载Whisper {model_name} 模型...")
        self.model = whisper.load_model(model_name)
        rospy.loginfo("Whisper模型加载完成")
        
        # 订阅麦克风音频数据
        rospy.Subscriber('/audio/audio_data', ASRRequest, self.audio_callback)
        
        # 发布识别结果
        self.asr_pub = rospy.Publisher('/audio/asr_result', ASRResponse, queue_size=10)
        
        rospy.loginfo("Whisper语音识别节点初始化完成")
    
    def audio_callback(self, msg):
        """音频数据回调函数"""
        rospy.loginfo(f"收到音频数据: 采样率={msg.sample_rate}Hz, 通道数={msg.channels}, 时长={msg.duration_ms}ms")
        
        try:
            # 将字节数据转换为numpy数组
            audio_data = self.bytes_to_numpy(msg.audio_data, msg.sample_rate, msg.channels)
            
            # 调用Whisper进行语音识别
            result = self.model.transcribe(audio_data, language='zh')
            
            # 发布识别结果
            self.publish_result(result['text'], msg.sample_rate)
            
        except Exception as e:
            rospy.logerr(f"语音识别失败: {str(e)}")
            self.publish_result("", 0, success=False, error=str(e))
    
    def bytes_to_numpy(self, audio_bytes, sample_rate, channels):
        """将字节数据转换为numpy数组"""
        # 假设音频数据是16位PCM
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # 转换为浮点数并归一化
        audio_np = audio_np.astype(np.float32) / 32768.0
        
        # 如果是立体声，转换为单声道
        if channels == 2:
            audio_np = audio_np.reshape(-1, 2).mean(axis=1)
        
        return audio_np
    
    def publish_result(self, transcript, sample_rate, success=True, language='zh', confidence=0.95, error=""):
        """发布识别结果"""
        msg = ASRResponse()
        msg.transcript = transcript
        msg.language = language
        msg.confidence = confidence
        msg.success = success
        
        if not success:
            rospy.logerr(f"语音识别失败: {error}")
        else:
            rospy.loginfo(f"识别结果: {transcript}")
        
        self.asr_pub.publish(msg)

def main():
    try:
        asr = WhisperASR()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr(f"节点启动失败: {str(e)}")
