# 语音助手系统 - 完整实现说明

## 系统概述

本系统完全替代了原来的AIUI语音识别系统，采用以下技术栈：

- **语音识别 (ASR)**: Whisper模型（本地运行，无需网络）
- **语音合成 (TTS)**: Minimax API（云端服务）
- **音频采集**: PyAudio（直接访问麦克风硬件）

## 系统架构

```
┌─────────────┐
│   麦克风     │
│ (M2麦克风)   │
└──────┬──────┘
       │
       │ ALSA驱动
       ▼
┌─────────────────────┐
│ audio_publisher.py  │
│ - 采集音频数据      │
│ - 发布到ROS话题     │
└──────────┬──────────┘
           │ /audio/audio_data
           ▼
┌─────────────────────┐
│   whisper_asr.py    │
│ - Whisper模型识别   │
│ - 本地ASR处理       │
└──────────┬──────────┘
           │ /audio/asr_result
           ▼
┌─────────────────────┐
│ minimax_tts.py      │
│ - 文本转语音        │
│ - 调用Minimax API   │
└──────────┬──────────┘
           │ /tts_response
           ▼
┌─────────────────────┐
│    音频播放器       │
│ - 播放合成语音      │
└─────────────────────┘
```

## 新增文件

### 1. 消息类型定义

- **ASRRequest.msg**: 语音识别请求消息
  - `sample_rate`: 采样率 (Hz)
  - `channels`: 声道数
  - `duration_ms`: 音频时长 (ms)
  - `audio_data`: 音频字节数据

- **ASRResponse.msg**: 语音识别响应消息
  - `transcript`: 识别的文本
  - `language`: 语言
  - `confidence`: 置信度
  - `success`: 是否成功

### 2. Python脚本

- **audio_publisher.py**: 音频发布节点
  - 使用PyAudio采集麦克风数据
  - 发布到`/audio/audio_data`话题

- **whisper_asr.py**: Whisper语音识别节点
  - 加载Whisper模型
  - 接收音频数据并进行识别
  - 发布识别结果到`/audio/asr_result`

- **minimax_tts.py**: Minimax语音合成节点
  - 接收文本请求
  - 调用Minimax API合成语音
  - 保存音频文件并发布路径

- **voice_assistant_system.py**: 完整语音助手系统（可选）
  - 集成ASR和TTS功能
  - 单一节点处理完整流程

### 3. 配置文件

- **voice_assistant.launch**: 启动文件
- **README.md**: 使用说明文档
- **start_voice_assistant.sh**: 启动脚本

### 4. 修改的文件

- **CMakeLists.txt**: 添加消息生成配置
- **package.xml**: 添加message_generation依赖
- **AudioListenThread.cpp/h**: 修改为音频发布器（可选）

## 使用方法

### 方法1: 使用独立节点（推荐）

```bash
# 启动整个语音助手系统
roslaunch voice_assistant voice_assistant.launch
```

### 方法2: 使用完整系统节点

修改`voice_assistant.launch`文件，启用`voice_assistant_system`节点：

```xml
<node name="voice_assistant_system" pkg="voice_assistant" type="voice_assistant_system.py" 
      output="screen">
    <param name="asr_model" value="base"/>
    <param name="group_id" value="1891387212730220598"/>
    <param name="api_key" value="your_api_key"/>
</node>
```

### 方法3: 使用启动脚本

```bash
# 运行启动脚本
./scripts/start_voice_assistant.sh
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

## ROS话题

### 输入话题

- `/audio/audio_data` (voice_assistant/ASRRequest) - 音频数据
- `/tts_request` (voice_assistant/TTSRequest) - TTS请求

### 输出话题

- `/audio/asr_result` (voice_assistant/ASRResponse) - ASR结果
- `/tts_response` (voice_assistant/TTSResponse) - TTS响应

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

## 与AIUI系统的对比

| 特性 | AIUI系统 | 新语音助手系统 |
|------|---------|---------------|
| 语音识别 | 云端API | 本地Whisper模型 |
| 语音合成 | 云端API | Minimax云端API |
| 网络依赖 | 高 | 中等（TTS需要网络） |
| 隐私性 | 低 | 高（ASR本地处理） |
| 延迟 | 中等 | 低（ASR）+ 中等（TTS） |
| 成本 | 按使用量收费 | TTS按使用量收费 |
| 准确性 | 依赖网络质量 | 本地模型，稳定性高 |

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

## 技术细节

### Whisper模型

Whisper是OpenAI开发的通用语音识别模型，具有以下特点：

- 支持多语言识别
- 本地运行，无需网络
- 多种模型大小可选
- 对噪声和口音有较好的鲁棒性

### Minimax TTS

Minimax是国内领先的AI语音合成服务，具有以下特点：

- 高质量的语音合成
- 支持多种声音风格
- API调用简单
- 按使用量计费

### PyAudio

PyAudio是Python的音频I/O库，具有以下特点：

- 直接访问ALSA/PulseAudio
- 简单易用的API
- 支持多种音频格式

## 许可证

本系统遵循ROS许可证。

## 联系方式

如有问题，请参考README.md或查看代码注释。
