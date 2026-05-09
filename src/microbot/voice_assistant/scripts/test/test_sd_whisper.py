import sounddevice as sd
import numpy as np
from queue import Queue
import threading
import wave
import whisper

class SDRecorderTest:
    def __init__(self):
        self.is_listening = False
        self.data_queue = Queue()
        self.stop_event = threading.Event()
        self.recording_thread = None

        self.samplerate = 16000
        self.dtype = "int16"
        self.channels = 1
        self.wav_path = "test_record.wav"

        print("加载Whisper模型...")
        self.model = whisper.load_model("base").float()
        print("✅ Whisper 加载成功")

    def start_recording(self):
        self.is_listening = True
        self.data_queue = Queue()
        self.stop_event.clear()

        self.recording_thread = threading.Thread(
            target=self.record_audio,
            args=(self.stop_event, self.data_queue),
        )
        self.recording_thread.start()
        print(">>>>> 开始录音........")

    def stop_recording(self):
        if self.is_listening:
            self.stop_event.set()
            self.recording_thread.join()
            self.is_listening = False
            print(">>>>> 停止录音........")
            self.save_to_wav() # 保存后才能识别
            self.recognize()

    def record_audio(self, stop_event, data_queue):
        def callback(indata, frames, time, status):
            if status:
                print(f"警告：{status}")
            data_queue.put(bytes(indata))  # 存入字节

        with sd.RawInputStream(
            samplerate=self.samplerate,
            dtype=self.dtype,
            channels=self.channels,
            callback=callback,
            device=1,
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

    def recognize(self):
        print("开始识别...")
        result = self.model.transcribe(self.wav_path, fp16 = False, language="zh")
        print("识别结果：", result["text"].strip())

if __name__ == "__main__":
    recorder = SDRecorderTest()
    print("==================================")
    print("指令说明：")
    print("1. 直接按回车 → 开始录音")
    print("2. 再按回车 → 停止并识别")
    print("3. 输入 k 回车 → 使用上次录音重新识别")
    print("==================================")

    while True:
        user_input = input("\n请输入指令（回车/ k）：").strip().lower()

        if user_input == "":
            # 第一次回车：开始录音
            recorder.start_recording()
            # 第二次回车：停止
            input()
            recorder.stop_recording()

        elif user_input == "k":
            # 输入 k：直接使用已有文件识别
            print("🔁 使用上次录音进行识别...")
            try:
                recorder.recognize()
            except:
                print("❌ 未找到上次录音，请先录音一次！")

        else:
            print("❌ 无效指令，请输入 回车 或 k")