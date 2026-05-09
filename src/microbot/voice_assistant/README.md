# 模块化语音视觉交互系统

## 系统架构

本系统采用模块化设计，将功能拆分为独立的节点，降低耦合度，提高可维护性。

### 核心组件

```
麦克风 → 语音识别 (Whisper ASR) → 语音识别文本
                                      ↓
Realsense RGB 图像 → MLM 决策中枢 (Qwen3-VL-8B)
                                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
   图像描述技能              视觉抓取技能
         ↓                         ↓
      TTS 播放              ┌──────┴──────┐
                          ↓               ↓
                   方案 1: GraspNet    方案 2: 简化方案
                          ↓               ↓
                   GraspNet 位姿      GroundingDINO+深度
                          ↓               ↓
                          └──────┬────────┘
                                 ↓
                        手眼标定 + grasp_executor
                                 ↓
                          机械臂抓取
```

## 节点说明

### 1. Whisper ASR 节点 (`whisper_asr.py`)

**功能**：麦克风音频 → Whisper ASR → 发布语音识别文本

**订阅话题**：无（直接读取麦克风）

**发布话题**：
- `/audio/asr_result` (ASRResponse): 语音识别结果

**参数**：
- `asr_model`: Whisper 模型名称，默认 `base`
- `wav_path`: 录音文件路径，默认 `test_record.wav`

**使用方法**：
```bash
rosrun voice_assistant whisper_asr.py
# 按回车开始录音，再次按回车停止录音并识别
```

### 2. Minimax TTS 节点 (`minimax_tts.py`)

**功能**：接收 TTS 请求 → Minimax TTS → 播放语音

**订阅话题**：
- `/tts_request` (TTSRequest): TTS 请求

**发布话题**：无（直接播放音频）

**参数**：
- `temp_dir`: 临时文件目录，默认 `audio_temp`

**使用方法**：
```bash
rosrun voice_assistant minimax_tts.py
# 自动等待/tts_request 话题
```

### 3. MLM 决策中枢节点 (`mlm_decision_node.py`)

**功能**：
- 接收语音识别文本和 Realsense RGB 图像
- 调用 Qwen3-VL-8B MLM 进行意图理解和决策
- 根据技能选择执行不同的处理流程

**订阅话题**：
- `/audio/asr_result` (ASRResponse): 语音识别结果
- `/camera/color/image_raw` (Image): Realsense RGB 图像

**发布话题**：
- `/tts_request` (TTSRequest): TTS 请求
- `/grasp_target_name` (String): 抓取目标物体名称（方案 1 使用）
- `/simple_target_name` (String): 抓取目标物体名称（方案 2 使用）

**参数**：
- `ollama_url`: Ollama API 地址，默认 `http://localhost:11434/v1`
- `mlm_model`: MLM 模型名称，默认 `qwen3-vl:8b`

**技能选择**：
- 通过键盘输入选择技能（后续会换成 MCP 技能调用）
  - `1`: 语音交互技能（支持图像理解、知识问答、闲聊）
  - `2`: 视觉抓取技能

**使用方法**：
```bash
rosrun mlm_decision mlm_decision_node.py
# 在终端输入 1 或 2 选择技能
```

### 4. 视觉抓取技能节点

#### 方案 1：GraspNet 完整流程

**组件**：
- `vision_processor.py`: GroundingDINO + SAM 检测分割
- `graspnet_generator_with_dl.py`: GraspNet 抓取位姿生成

**订阅话题**：
- `/camera/color/image_raw` (Image): RGB 图像
- `/camera/aligned_depth_to_color/image_raw` (Image): 深度图像
- `/grasp_target_name` (String): 抓取目标物体名称

**发布话题**：
- `/object_poses` (DetectedObjectArray): 检测结果
- `/best_grasp_pose` (PoseStamped): 抓取位姿

#### 方案 2：简化方案

**组件**：
- `visual_grasping_skill.py`: GroundingDINO 检测 + 3D 位置计算

**订阅话题**：
- `/camera/color/image_raw` (Image): RGB 图像
- `/camera/aligned_depth_to_color/image_raw` (Image): 深度图像
- `/simple_target_name` (String): 抓取目标物体名称

**发布话题**：
- `/best_grasp_pose` (PoseStamped): 抓取位姿

### 5. 抓取执行节点 (`grasp_executor.py`)

**功能**：订阅抓取位姿并执行抓取

**订阅话题**：
- `/best_grasp_pose` (PoseStamped): 抓取位姿

**发布话题**：无（控制机械臂执行）

## 一键启动

### 完整系统启动

```bash
# 默认使用简化方案（方案 2）
roslaunch mlm_decision mlm_system.launch

# 使用 GraspNet 完整流程（方案 1）
roslaunch mlm_decision mlm_system.launch grasp_scheme:=graspnet
```

这会启动：
- 麦克风节点（`wheeltec_mic`）
- Realsense 相机（RGB + 深度 + 对齐）
- Whisper ASR 节点
- Minimax TTS 节点
- MLM 决策中枢节点
- 视觉抓取技能（根据 `grasp_scheme` 选择）
- 抓取执行节点

### 单独启动组件

```bash
# 启动麦克风
roslaunch voice_assistant mic.launch

# 启动相机
roslaunch realsense2_camera rs_camera.launch align_depth:=true

# 启动 Whisper ASR
rosrun voice_assistant whisper_asr.py

# 启动 Minimax TTS
rosrun voice_assistant minimax_tts.py

# 启动 MLM 决策中枢
rosrun mlm_decision mlm_decision_node.py

# 启动视觉抓取技能（方案 2）
rosrun mlm_decision visual_grasping_skill.py

# 启动抓取执行器
rosrun rm_scr_demo grasp_executor.py
```

## 使用流程

### 1. 启动系统

```bash
roslaunch mlm_decision mlm_system.launch
```

### 2. 选择技能

在 MLM 决策中枢节点的终端输入：
- `1`: 语音交互技能（支持图像理解、知识问答、闲聊）
- `2`: 视觉抓取技能

### 3. 语音输入

在 Whisper ASR 节点的终端：
- 按回车开始录音
- 说话（如"你能看到什么？"或"把玩偶抓起来"）
- 再次按回车停止录音并识别

### 4. 系统响应

- **语音交互技能**：MLM 理解用户意图（支持图像理解、知识问答、闲聊） → TTS 播放回复
- **视觉抓取技能**：MLM 提取物体 → GroundingDINO 检测 → 生成抓取位姿 → 机械臂执行抓取

## 模块化优势

### 1. 低耦合
- 各节点独立运行，通过 ROS 话题通信
- 易于替换组件（如更换 ASR 引擎或 TTS 服务）

### 2. 高内聚
- 每个节点专注于单一功能
- 代码结构清晰，易于维护

### 3. 灵活部署
- 可以按需启动部分组件
- 支持分布式部署（不同节点运行在不同机器上）

### 4. 易于扩展
- 添加新技能只需创建新的技能节点
- 支持多种视觉抓取方案并存

## 话题汇总

### 核心话题
- `/audio/asr_result` (ASRResponse): 语音识别结果
- `/tts_request` (TTSRequest): TTS 请求
- `/camera/color/image_raw` (Image): RGB 图像
- `/camera/aligned_depth_to_color/image_raw` (Image): 深度图像

### 抓取相关话题
- `/grasp_target_name` (String): 抓取目标名称（方案 1）
- `/simple_target_name` (String): 抓取目标名称（方案 2）
- `/object_poses` (DetectedObjectArray): 检测结果（方案 1）
- `/best_grasp_pose` (PoseStamped): 抓取位姿（两种方案都发布）

## 故障排除

### 1. Whisper ASR 节点无响应
- 检查麦克风连接是否正常
- 确认 sounddevice 库已安装
- 检查音频设备权限

### 2. Minimax TTS 节点播放失败
- 检查 API Key 是否有效
- 确认网络连接正常
- 检查 aplay 是否可用

### 3. MLM 决策节点响应慢
- 检查 Ollama 服务是否运行
- 确认 qwen3-vl:8b 模型已下载
- 考虑使用更小的模型

### 4. 视觉抓取失败
- 检查 GroundingDINO 模型路径
- 调整检测阈值参数
- 确保深度图像对齐正确

## 开发指南

### 添加新技能

1. 在 MLM 决策节点中添加技能模式
2. 创建新的技能处理函数
3. 实现技能逻辑（可以调用其他节点或创建新节点）

### 更换 ASR 引擎

1. 修改 `whisper_asr.py` 或创建新的 ASR 节点
2. 确保发布相同的话题格式（`/audio/asr_result`）
3. 更新启动文件

### 更换 TTS 服务

1. 修改 `minimax_tts.py` 或创建新的 TTS 节点
2. 确保订阅相同的话题（`/tts_request`）
3. 更新启动文件

## 许可证

MIT License
