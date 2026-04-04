# 语音助手系统使用说明

## 系统概述

这个语音助手系统完全替代了原来的AIUI语音识别系统，使用以下技术栈：

- **语音识别 (ASR)**: Whisper模型（本地运行）
- **语音合成 (TTS)**: Minimax API
- **音频采集**: PyAudio（直接访问麦克风）

## 系统架构

```
麦克风 → audio_publisher → /audio/audio_data
                              ↓
                         whisper_asr
                              ↓
                         /audio/asr_result
                              ↓
                    voice_assistant_system
                              ↓
                         /tts_request
                              ↓
                         minimax_tts
                              ↓
                         /tts_response
```

## 安装依赖

### Python依赖

```bash
pip install torch numpy requests pyaudio
pip install openai-whisper
```

### 系统依赖

```bash
# 安装PyAudio依赖
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio

# 安装音频播放工具（可选）
sudo apt-get install -y mpv
```

## 使用方法

### 方法1: 使用独立节点（推荐）

启动整个语音助手系统：

```bash
roslaunch voice_assistant voice_assistant.launch
```

这个命令会启动三个独立的节点：
1. `audio_publisher` - 音频发布节点
2. `whisper_asr` - Whisper语音识别节点
3. `minimax_tts` - Minimax语音合成节点

### 方法2: 使用完整系统节点

如果只需要一个统一的节点，可以修改launch文件，启用 `voice_assistant_system` 节点：

```xml
<node name="voice_assistant_system" pkg="voice_assistant" type="voice_assistant_system.py" 
      output="screen">
    <param name="asr_model" value="base"/>
    <param name="group_id" value="1891387212730220598"/>
    <param name="api_key" value="your_api_key"/>
</node>
```

## ROS话题

### 输入话题

- `/audio/audio_data` (voice_assistant/ASRRequest) - 音频数据
  - `sample_rate`: 采样率 (Hz)
  - `channels`: 声道数
  - `duration_ms`: 音频时长 (ms)
  - `audio_data`: 音频字节数据

- `/tts_request` (voice_assistant/TTSRequest) - TTS请求
  - `text`: 要合成的文本
  - `voice_preset`: 语音预设（可选）

### 输出话题

- `/audio/asr_result` (voice_assistant/ASRResponse) - ASR结果
  - `transcript`: 识别的文本
  - `language`: 语言
  - `confidence`: 置信度
  - `success`: 是否成功

- `/tts_response` (voice_assistant/TTSResponse) - TTS响应
  - `audio_file_path`: 音频文件路径
  - `success`: 是否成功

## 消息类型定义

### ASRRequest.msg

```
uint32 sample_rate
uint32 channels
uint32 duration_ms
bytes audio_data
```

### ASRResponse.msg

```
string transcript
string language
float32 confidence
bool success
```

### TTSRequest.msg

```
string text
string voice_preset
```

### TTSResponse.msg

```
string audio_file_path
bool success
```

## 配置参数

### audio_publisher

- `sample_rate`: 音频采样率，默认16000 Hz
- `channels`: 声道数，默认1（单声道）
- `chunk_size`: 每次读取的音频帧数，默认4000

### whisper_asr

- `model`: Whisper模型大小，默认'base'
  - 可选值: 'tiny', 'base', 'small', 'medium', 'large'
  - 模型越大，识别越准确，但需要更多计算资源

### minimax_tts

- `group_id`: Minimax API组ID
- `api_key`: Minimax API密钥

## 故障排除

### 1. 音频采集失败

检查麦克风是否正确连接：

```bash
# 列出音频设备
arecord -l

# 测试录音
arecord -D hw:0 -f cd test.wav
```

### 2. Whisper模型加载失败

确保已安装PyTorch和Whisper：

```bash
pip install torch torchvision torchaudio
pip install openai-whisper
```

### 3. Minimax API调用失败

检查API密钥是否有效：

```bash
curl -X POST https://api.minimax.chat/v1/t2a_v2?GroupId=1891387212730220598 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_key" \
  -d '{"model":"speech-01-turbo","text":"测试","stream":false}'
```

### 4. 音频播放失败

安装音频播放工具：

```bash
sudo apt-get install -y mpv
```

## 性能优化建议

1. **使用更小的Whisper模型**: 如果计算资源有限，使用`tiny`或`base`模型
2. **调整采样率**: 根据实际需求调整采样率，较低的采样率可以减少数据量
3. **批量处理**: 如果需要处理长时间音频，可以考虑批量处理

## 扩展功能

### 添加自定义TTS语音

在`minimax_tts.py`中修改`voice_id`参数：

```python
"voice_id": "your_custom_voice_id"
```

### 添加语音唤醒

可以添加一个独立的唤醒词检测节点，在检测到唤醒词后才启动录音。

## 与AIUI系统的对比

| 特性 | AIUI系统 | 新语音助手系统 |
|------|---------|---------------|
| 语音识别 | 云端API | 本地Whisper模型 |
| 语音合成 | 云端API | Minimax云端API |
| 网络依赖 | 高 | 中等（TTS需要网络） |
| 隐私性 | 低 | 高（ASR本地处理） |
| 延迟 | 中等 | 低（ASR）+ 中等（TTS） |
| 成本 | 按使用量收费 | TTS按使用量收费 |

## 许可证

本系统遵循ROS许可证。
