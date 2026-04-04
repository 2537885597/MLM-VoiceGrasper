#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主程序app -> ros节点
"""
# 使用ros所需导入 
import rospy
import numpy as np
import threading
from queue import Queue
import sounddevice as sd
from std_msgs.msg import String, Bool
from voice_assistant.msg import ASRResult, TTSRequest, TTSResponse

# 原导入不变
import whisper
from customized_para import WhisperType
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
import voice_generation

class VoiceAssistantNode:
    def __init__(self):
        rospy.init_node("voice_assistant", annoymous=True)
        # 语音识别话题发布者、语音合成请求话题发布者
        self.asr_pub = rospy.Publisher("/voice_assistant/asr_result", ASRResult, queue_size=10)
        self.tts_request_pub = rospy.Publisher("/voice_assistant/tts_request", TTSRequest, queue_size=10)
        # 机器人思考中话题、说话中话题发布者
        self.thinking_pub = rospy.Publisher("/voice_assistant/thinking", Bool, queue_size=10)
        self.speaking_pub = rospy.Publisher("/voice_assistant/speaking", Bool, queue_size=10)
        # 机器人开始录音话题、停止录音话题订阅者
        rospy.Subscriber("/voice_assistant/start_listening", Bool, self.start_listening_cb)
        rospy.Subscriber("/voice_assistant/stop_listening", Bool, self.stop_listening_cb)
        # 语音合成响应话题订阅者
        rospy.Subscriber("/voice_assistant/tts_response", TTSResponse, self.tts_response_cb)
        
        # 初始化原有的组件
        self.stt = whisper.load_model(str(WhisperType.base))
        self.initialize_llm()
        # 状态变量
        self.is_listening = False
        self.is_thinking = False
        self.is_speaking = False
        self.data_queue = Queue()
        self.stop_event = threading.Event()
        self.recording_thread = None

        rospy.loginfo("Voice Assistant节点已启动")
    
    def initialize_llm(self):
        """初始化大语言模型"""
        self.llm = ChatOpenAI(
            model="qwen2.5:3b",
            max_tokens=4096,
            base_url='http://localhost:11434/v1',
            api_key='ollama'
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你叫小叽，是个元气满满的AI小助手！(✧ω✧) 说话时会用可可爱爱的颜文字，\
                    喜欢在句尾加波浪号～回答要简短活泼（30字以内），多用这些语气词：呢、呀、啦、喔、嘛～"
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ]
        )
        self.chain = prompt | self.llm
        self.store = {}
    
    def get_session_history(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]
    
    def start_listening_cb(self, msg):
        """开始监听回调"""
        if msg.data and not self.is_listening:
            self.start_recording()
    
    def stop_listening_cb(self, msg):
        """停止监听回调"""
        if msg.data and self.is_listening:
            self.stop_recording()
    
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
        rospy.loginfo("开始录音...")
    
    def stop_recording(self):
        """停止录音并处理"""
        if self.is_listening:
            self.stop_event.set()
            if self.recording_thread:
                self.recording_thread.join()
            self.is_listening = False
            # 处理录音数据
            self.process_audio_data()
    
    def record_audio(self, stop_event, data_queue):
        """录音线程函数"""
        def callback(indata, frames, time, status):
            if status:
                rospy.logwarn(f"Audio status：{status}")
            data_queue.put(bytes(indata))
        
        with sd.RawInputStream(
            samplerate=16000,
            dtype="int16",
            channels=1,
            callback=callback
        ):
            while not stop_event.is_set() and not rospy.is_shutdown():
                rospy.sleep(0.1)
    
    def process_audio_data(self):
        """处理录音数据"""
        audio_data = b"".join(list(self.data_queue.queue))
        audio_np = (
            np.frombuffer(audio_data, dtype=np.int16).astyep(np.float32) / 32768.0
        )
        if audio_np.size > 0:
            # 语音识别
            self.thinking_pub.publish(True)
            text = self.transcribe(audio_np)
            if not text:
                text = "你好，我是小叽"
            # 发布识别结果
            asr_msg = ASRResult()
            asr_msg.text = text
            asr_msg.is_final = True
            asr_msg.confidence = 1.0
            self.asr_pub.publish(asr_msg)
            rospy.loginfo(f"识别结果：{text}")
            # 生成回复
            response = self.get_llm_response(text)
            rospy.loginfo(f"小叽恢复：{response}")
            # 发布TTS语音合成请求
            tts_request = TTSRequest()
            tts_request.text = response
            tts_request.voice_preset = "default"
            self.tts_request_pub.publish(tts_request)

            self.thinking_pub.publish(False)
        else:
            rospy.logwarn("没有检测到音频数据")
    
    def transcribe(self, audio_np: np.ndarray) -> str:
        """语音识别"""
        result = self.stt.transcribe(audio_np, fp16=False)
        return result["text"].strip()
    
    def get_llm_response(self, text: str) -> str:
        """获取LLM回复"""
        with_message_history = RunnableWithMessageHistory(
            self.chain,
            self.get_session_history,
            input_message_key="input",
            history_message_key="history",
        )
        response = with_message_history.invoke(
            {"input": text},
            config={"configurable": {"session_id": "ros_user"}}
        )
        return response.content

    def tts_response_cb(self, msg):
        """TTS响应回调"""
        if msg.success:
            rospy.loginfo(f"语音合成完成：{msg.audio_file_path}")
        else:
            rospy.logerr("语音合成失败")
    
    def run(self):
        """主循环"""
        rate = rospy.Rate(10) # 10Hz
        while not rospy.is_shutdown():
            rate.sleep()

if __name__ == "__main__":
    try:
        node = VoiceAssistantNode()
        node.run()
    except rospy.ROSInterruptException:
        pass