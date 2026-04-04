#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM建立、处理与响应->ros节点
"""
# 使用ros所需导入
import rospy
import numpy as np
import threading
from std_msgs.msg import String, Bool

# 原导入
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory

class MLMProcessor:
    def __init__(self):
        rospy.init_node("mlm_processor", anonymous=True)
        rospy.loginfo("MLMProcessor节点已启动")

        # 初始化大模型组件
        self.initialize_llm()
        # 状态变量
        self.is_thinking = False
        self.is_speaking = False

    def initialize_llm(self):
        """初始化大语言模型"""
        self.llm = ChatOpenAI(
            model="qwen3:4b", #qwen2.5:3b
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
        """获取会话历史"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def process_recognition_data(self, text: str) -> str:
        """处理识别数据"""
        # 生成回复
        response = self.get_llm_response(text)
        rospy.loginfo(f"小叽回复：{response}")
        return response
    
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

    def run(self):
        """主循环 - 只是保持节点活跃，不占用太多资源"""
        # MLMProcessor没有订阅消息，所以不需要复杂的循环
        # 如果MLM处理器需要持续运行的逻辑，可以在这里添加
        # 目前MLM处理器主要是响应式处理，不需要持续循环
        pass