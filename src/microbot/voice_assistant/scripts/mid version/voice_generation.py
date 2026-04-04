#!/user/bin/env python3
# -*- coding: utf-8 -*-

"""
语音合成->ros节点
"""
# ros所需导入
import rospy
import std_msgs.msg
from voice_assistant.msg import TTSRequest, TTSResponse
from std_msgs.msg import String
# 原导入
import json
import subprocess
from typing import Iterator
import requests
import tempfile
import os
import time

# 请输入您的group_id，用于标识调用API的分组
group_id = '1891387212730220598'
# 请输入您的api_key，用于身份验证以调用API
api_key = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiVXNlck5hbWUiOiLmtbfonrrnlKjmiLdfMzQ3Nzk3MjcwOTEzMDU2NzY5IiwiQWNjb3VudCI6IiIsIlN1YmplY3RJRCI6IjE4OTEzODcyMTI3Mzg2MDkyMDYiLCJQaG9uZSI6IjE5ODU5Nzc2NTU4IiwiR3JvdXBJRCI6IjE4OTEzODcyMTI3MzAyMjA1OTgiLCJQYWdlTmFtZSI6IiIsIk1haWwiOiIyNTM3ODg1NTk3QHFxLmNvbSIsIkNyZWF0ZVRpbWUiOiIyMDI1LTAzLTIxIDE5OjU1OjUwIiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.dSJNVnpMYUorisFR6k_3mPLCFbGN6S28xzzhPfJ4Rqd8A6eyaTXq64cHzEMERqnbQLzIlX71TNLM0yGVE1R8s8sVZ0VqPCeXKkYX0z6mOSfSmKUrYvywYbVQ8fkVCftfzxlMbi5DU6sKJ7-jHh99cift3jOD0gnon-t7Lg-CT7EbwY8YMX3_iir9e75HtYpk0pCL9qqaoL9ndN1g7CXc3iGImErjnQUGKJpjjou1P3sqjqtdsTISRr0q2U2iZw1m2wFa98MdurSGXxlCR7Btd76kLw2QIS7DJmkuVYrDQ0ZBAR9vSLpi3WESIv16MT2aCCaez9eOYcRCWk_ykXgq8g'

# 定义音频文件的格式，支持mp3、pcm、flac三种格式
file_format = 'mp3'

# 构建语音合成API的请求URL，将group_id拼接到URL中
url = "https://api.minimax.chat/v1/t2a_v2?GroupId=" + group_id
# 定义请求头，包含内容类型和身份验证信息
headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}

# 定义mpv播放器的命令，使用标准输入作为音频源
mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]

class VoiceGeneration:
    def __init__(self):
        # 初始化ROS节点
        rospy.init_node("voice_generation_node", anonymous=True)
        rospy.loginfo("VoiceGeneration节点已启动")

        # 订阅TTS请求话题
        rospy.Subscriber("/voice_assistant_node/tts_request", TTSRequest, self.tts_request_callback)
        # 发布TTS响应话题
        self.tts_response_pub = rospy.Publisher("/voice_assistant_node/tts_response", TTSResponse, queue_size=10)

        # 创建临时目录存储音频文件
        self.temp_dir = tempfile.mkdtemp(prefix="voice_assistant_tts_")
        rospy.loginfo(f"语音合成节点已启动，音频文件存储在：{self.temp_dir}")

        # # 启动mpv播放器进程，将标准输入重定向，忽略标准输出和标准错误输出
        # self.mpv_process = subprocess.Popen(
        #     mpv_command,
        #     stdin=subprocess.PIPE,
        #     stdout=subprocess.DEVNULL,
        #     stderr=subprocess.DEVNULL,
        # )

    # 构建语音合成流式请求的请求头
    def build_tts_stream_headers(self) -> dict:
        headers = {
            # 表示客户端可以接受的响应类型
            'accept': 'application/json, text/plain, */*',
            # 表示请求体的内容类型为JSON
            'content-type': 'application/json',
            # 身份验证信息
            'authorization': "Bearer " + api_key,
        }
        return headers


    # 构建语音合成流式请求的请求体
    def build_tts_stream_body(self, text: str) -> dict:
        body = json.dumps({
            # 指定使用的语音合成模型
            "model": "speech-01-turbo",
            # 要合成语音的文本内容，这里暂时写死了一段示例文本
            "text": text,
            # 是否开启流式传输
            "stream": True,
            "voice_setting": {
                # 选择的语音ID，详情见MiniMax开发文档
                "voice_id": "qiaopi_mengmei",
                # 语音的语速，1.0 表示正常语速
                "speed": 1.0,
                # 语音的音量，1.0 表示正常音量
                "vol": 1.0,
                # 语音的音调，0 表示正常音调
                "pitch": 0
            },
            "pronunciation_dict": {
                "tone": [
                    # 自定义发音，将“处理”的发音标注为“(chu3)(li3)”
                    "处理/(chu3)(li3)",
                    # 这里将“危险”映射为“dangerous”，可能是特殊的发音需求
                    "危险/dangerous"
                ]
            },
            "audio_setting": {
                # 音频的采样率
                "sample_rate": 32000,
                # 音频的比特率
                "bitrate": 128000,
                # 音频的格式
                "format": "mp3",
                # 音频的声道数，1 表示单声道
                "channel": 1
            }
        })
        return body

    # 调用语音合成流式API，并返回音频数据的迭代器
    def call_tts_stream(self, text: str) -> Iterator[bytes]:
        # 使用之前构建的URL
        tts_url = url
        # 调用函数构建请求头
        tts_headers = self.build_tts_stream_headers()
        # 调用函数构建请求体
        tts_body = self.build_tts_stream_body(text)

        # 发送POST请求，开启流式传输
        response = requests.request("POST", tts_url, stream=True, headers=tts_headers, data=tts_body)

        # 检查请求是否成功
        if response.status_code != 200:
            error_msg = f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
            print(error_msg)
            # 返回一个空迭代器
            return iter([])

        # 遍历响应的原始数据块
        for chunk in (response.raw):
            if chunk:
                # 如果数据块以'data:'开头
                if chunk[:5] == b'data:':
                    # 解析JSON数据
                    data = json.loads(chunk[5:])
                    # 检查数据中是否包含"data"字段且不包含"extra_info"字段
                    if "data" in data and "extra_info" not in data:
                        # 检查"data"字段中是否包含"audio"字段
                        if "audio" in data["data"]:
                            # 获取音频数据
                            audio = data["data"]['audio']
                            # 通过生成器返回音频数据
                            yield audio

    # # 播放音频流并将音频数据拼接成完整的音频
    # def audio_play(self, audio_stream: Iterator[bytes]) -> bytes:
    #     audio = b""
    #     # 遍历音频流中的每个数据块
    #     for chunk in audio_stream:
    #         if chunk is not None and chunk != '\n':
    #             # 将十六进制编码的音频数据解码为字节
    #             decoded_hex = bytes.fromhex(chunk)
    #             # 将解码后的音频数据写入mpv播放器的标准输入 播放音频
    #             self.mpv_process.stdin.write(decoded_hex)  # type: ignore
    #             # 刷新标准输入缓冲区
    #             self.mpv_process.stdin.flush()
    #             # 将解码后的音频数据拼接到完整的音频中
    #             audio += decoded_hex

    #     return audio

    # 播放音频文件 - 使用系统命令播放音频，类似node_feedback.cpp的方式
    def play_audio_file(self, filepath):
        # """播放音频文件，使用系统命令，类似node_feedback.cpp的方式"""
        # try:
        #     # 使用aplay命令播放音频文件，这是Linux标准的音频播放命令
        #     # 如果系统中没有aplay，可能需要使用其他命令如paplay
        #     cmd = ["aplay", filepath]
        #     subprocess.run(cmd, check=True)
        #     rospy.loginfo(f"音频播放完成: {filepath}")
        # except subprocess.CalledProcessError as e:
        #     rospy.logerr(f"音频播放失败: {e}")
        # except FileNotFoundError:
        #     # 如果aplay命令不存在，尝试使用paplay或其他播放命令
        #     try:
        #         cmd = ["paplay", filepath]
        #         subprocess.run(cmd, check=True)
        #         rospy.loginfo(f"音频播放完成: {filepath}")
        #     except (subprocess.CalledProcessError, FileNotFoundError):
        #         rospy.logerr("系统中未找到音频播放命令(aplay或paplay)，无法播放音频")
        #         # 如果以上命令都不可用，尝试使用其他方式
        #         # 可能需要安装相应的音频播放软件包
        #         pass
        pass

    def get_full_audio_data(self, audio_stream):
        """获取完整的音频数据"""
        audio = b""
        # 遍历音频流中的每个数据块
        for chunk in audio_stream:
            if chunk is not None and chunk != '\n':
                # 将十六进制编码的音频数据解码为字节
                decoded_hex = bytes.fromhex(chunk)
                # 将解码后的音频数据拼接到完整的音频中
                audio += decoded_hex

        return audio

    def tts_request_callback(self, msg):
        """TTS请求回调函数"""
        rospy.loginfo(f"收到TTS请求：{msg.text}")
        # 创建TTS响应消息
        tts_response = TTSResponse()
        try:
            # 调用语音合成流式API，获取音频数据迭代器
            audio_chunk_iterator = self.call_tts_stream(msg.text)
            # 获取完整的音频数据
            audio_data = self.get_full_audio_data(audio_chunk_iterator)

            # 生成音频文件名
            filename = f"tts_{int(time.time())}.{file_format}"
            filepath = os.path.join(self.temp_dir, filename)

            # 将完整的音频数据写入文件
            with open(filepath, 'wb') as file:
                file.write(audio_data)
            
            # 播放音频文件
            self.play_audio_file(filepath)
            
            # 设置响应消息
            tts_response.audio_file_path = filepath
            tts_response.success = True
            rospy.loginfo(f"语音合成完成：{filepath}")
        except Exception as e:
            rospy.logerr(f"语音合成失败：{str(e)}")
            tts_response.success = False
            tts_response.audio_file_path = ""
        finally:
            # 发布TTS响应
            self.tts_response_pub.publish(tts_response)
    
    def run(self):
        """主循环 - 保持节点运行以处理回调函数"""
        rate = rospy.Rate(10) # 10Hz
        while not rospy.is_shutdown():
            rate.sleep()
