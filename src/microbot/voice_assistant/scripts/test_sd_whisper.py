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
            self.save_to_wav()
            self.recognize()

    def record_audio(self, stop_event, data_queue):
        def callback(indata, frames, time, status):
            if status:
                print(f"警告：{status}")
            # ✅ 唯一正确的存储方式
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
        self.wav_path = "test_record.wav"
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

    # def recognize(self):
    #     print("开始识别...")
    #     audio_data = b"".join(self.data_queue.queue)
    #     audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    #     print(f"音频长度：{len(audio_np)} 样本，约 {len(audio_np)/16000:.2f} 秒")
    #     print(f"最小值：{audio_np.min():.4f}，最大值：{audio_np.max():.4f}，均值：{audio_np.mean():.4f}，标准差：{audio_np.std():.4f}")

    #     # ✅ 安全识别
    #     result = self.model.transcribe(audio_np, fp16=False, language="zh")
    #     print("\n==================================")
    #     print("识别结果：", result["text"].strip())
    #     print("==================================\n")

if __name__ == "__main__":
    recorder = SDRecorderTest()
    print("按回车开始录音，再按回车停止...")
    input()
    recorder.start_recording()
    input()
    recorder.stop_recording()