#!/user/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
from typing import Iterator
import requests

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


# 构建语音合成流式请求的请求头
def build_tts_stream_headers() -> dict:
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
def build_tts_stream_body(text: str) -> dict:
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


# 定义mpv播放器的命令，使用标准输入作为音频源
mpv_command = ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"]
# 启动mpv播放器进程，将标准输入重定向，忽略标准输出和标准错误输出
mpv_process = subprocess.Popen(
    mpv_command,
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)


# 调用语音合成流式API，并返回音频数据的迭代器
def call_tts_stream(text: str) -> Iterator[bytes]:
    # 使用之前构建的URL
    tts_url = url
    # 调用函数构建请求头
    tts_headers = build_tts_stream_headers()
    # 调用函数构建请求体
    tts_body = build_tts_stream_body(text)

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


# 播放音频流并将音频数据拼接成完整的音频
def audio_play(audio_stream: Iterator[bytes]) -> bytes:
    audio = b""
    # 遍历音频流中的每个数据块
    for chunk in audio_stream:
        if chunk is not None and chunk != '\n':
            # 将十六进制编码的音频数据解码为字节
            decoded_hex = bytes.fromhex(chunk)
            # 将解码后的音频数据写入mpv播放器的标准输入
            mpv_process.stdin.write(decoded_hex)  # type: ignore
            # 刷新标准输入缓冲区
            mpv_process.stdin.flush()
            # 将解码后的音频数据拼接到完整的音频中
            audio += decoded_hex

    return audio


if __name__ == "__main__":
    # 调用语音合成流式API，获取音频数据迭代器
    audio_chunk_iterator = call_tts_stream('你是大笨蛋')
    # 播放音频流并获取完整的音频数据
    audio = audio_play(audio_chunk_iterator)

    # 构建输出文件名，包含时间戳和文件格式
    file_name = f'output_total.{file_format}'
    # 以二进制写入模式打开文件
    with open(file_name, 'wb') as file:
        # 将完整的音频数据写入文件
        file.write(audio)
