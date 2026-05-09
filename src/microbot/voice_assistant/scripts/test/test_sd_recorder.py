import sounddevice as sd
import numpy as np
from queue import Queue
import threading
import wave

class SDRecorderTest:
    def __init__(self):
        self.is_listening = False
        self.data_queue = Queue()
        self.stop_event = threading.Event()
        self.recording_thread = None

        # 音频参数（和你代码完全一致）
        self.samplerate = 16000
        self.dtype = "int16"
        self.channels = 1

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
        print(">>>>> 开始录音........")

    def stop_recording(self):
        """停止录音并保存文件"""
        if self.is_listening:
            self.stop_event.set()
            self.recording_thread.join()
            self.is_listening = False
            print(">>>>> 停止录音........")
            self.save_to_wav()

    def record_audio(self, stop_event, data_queue):
        """sd 录音线程（和你源码一模一样）"""
        def callback(indata, frames, time, status):
            if status:
                print(f"警告：{status}")
            data_queue.put(bytes(indata))  # 存入字节

        with sd.RawInputStream(
            samplerate=self.samplerate,
            dtype=self.dtype,
            channels=self.channels,
            callback=callback,
            device=1, # 录音设备号
        ):
            while not stop_event.is_set():
                continue

    def save_to_wav(self):
        """把录音保存成 WAV 文件，方便 aplay 播放"""
        audio_data = b"".join(self.data_queue.queue)
        
        # 保存 WAV
        wav_path = "test_record.wav"
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16 = 2字节
            wf.setframerate(self.samplerate)
            wf.writeframes(audio_data)
        
        print(f"✅ 录音已保存：{wav_path}")
        print(f"▶️  播放命令：aplay {wav_path}")

if __name__ == "__main__":
    recorder = SDRecorderTest()

    print("按回车开始录音，再按回车停止...")
    input()
    recorder.start_recording()
    
    input()
    recorder.stop_recording()