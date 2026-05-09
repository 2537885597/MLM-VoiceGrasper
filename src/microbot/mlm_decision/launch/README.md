# 系统启动说明

## 一键启动

```bash
roslaunch mlm_decision mlm_system.launch
```

## 终端窗口说明

启动后会自动打开 **3 个独立的终端窗口**：

### 1️⃣ Whisper ASR 终端窗口
- **功能**：语音识别
- **用户操作**：
  - 按 `Enter` 键：开始录音
  - 按 `Enter` 键：停止录音并识别
- **输出话题**：`/audio/asr_result`

### 2️⃣ MLM 决策中枢终端窗口
- **功能**：多模态决策
- **用户操作**：
  - 输入 `1` + `Enter`：选择语音交互技能（图像理解、知识问答、闲聊）
  - 输入 `2` + `Enter`：选择视觉抓取技能
- **订阅话题**：`/audio/asr_result`
- **发布话题**：`/tts_request`、`/grasp_target_name`、`/simple_target_name`

### 3️⃣ 主终端窗口（launch 文件所在终端）
- **功能**：显示所有节点的日志输出
- **包含节点**：
  - 麦克风节点（wheeltec_mic）
  - Realsense 相机节点
  - Minimax TTS 节点
  - 视觉抓取技能节点（方案 2）
  - 抓取执行节点

## 使用流程

### 步骤 1：启动系统
```bash
roslaunch mlm_decision mlm_system.launch
```
系统会自动打开 3 个终端窗口。

### 步骤 2：选择技能
在 **MLM 决策中枢终端窗口** 中输入：
- `1`：语音交互技能
- `2`：视觉抓取技能

### 步骤 3：语音输入
在 **Whisper ASR 终端窗口** 中：
- 按 `Enter` 开始录音
- 说话（例如："你能看到什么？"或"把玩偶抓起来"）
- 按 `Enter` 停止录音

### 步骤 4：系统响应
- **语音交互技能**：MLM 分析 → TTS 播放回复
- **视觉抓取技能**：MLM 提取物体 → GroundingDINO 检测 → 机械臂抓取

## 终端窗口示意图

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Whisper ASR    │  │  MLM Decision   │  │   Main Launch   │
│                 │  │                 │  │                 │
│ 按回车开始录音  │  │ 1-语音交互      │  │ [INFO] 节点启动 │
│ 按回车停止录音  │  │ 2-视觉抓取      │  │ [INFO] 相机就绪 │
│                 │  │                 │  │ [INFO] TTS 就绪  │
│                 │  │ 输入：1         │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## 注意事项

1. **不要关闭独立的终端窗口**：关闭后对应的节点会停止运行
2. **确保有图形界面**：`gnome-terminal` 需要 X11 图形环境
3. **终端焦点**：确保在正确的终端窗口中输入
4. **技能选择**：每次语音输入前需要先选择技能模式

## 故障排除

### 问题 1：无法打开新终端窗口
**原因**：没有安装 gnome-terminal 或没有 X11 环境

**解决方案**：
```bash
# 安装 gnome-terminal（Ubuntu/Debian）
sudo apt-get install gnome-terminal

# 或者使用其他终端模拟器（如 xterm）
# 修改 launch 文件中的 launch-prefix 为：
# launch-prefix="xterm -e"
```

### 问题 2：输入无响应
**原因**：终端焦点不在正确的窗口

**解决方案**：
- 点击对应的终端窗口，确保获得焦点
- 检查输入是否正确（数字 1 或 2，回车键）

### 问题 3：节点日志混乱
**原因**：所有节点日志输出到同一个终端

**解决方案**：
- 查看主终端窗口的日志
- 使用 `rqt_console` 查看 ROS 日志

## 高级配置

### 使用不同的终端模拟器

如果使用 `xterm`：
```xml
<node name="whisper_asr" pkg="voice_assistant" type="whisper_asr.py" 
      output="screen" launch-prefix="xterm -e">
```

如果使用 `konsole`（KDE）：
```xml
<node name="whisper_asr" pkg="voice_assistant" type="whisper_asr.py" 
      output="screen" launch-prefix="konsole -e">
```

### 不使用独立终端（后台运行）

如果不需要键盘输入，可以去掉 `launch-prefix`：
```xml
<node name="whisper_asr" pkg="voice_assistant" type="whisper_asr.py" 
      output="screen">
```

## 技能说明

### 技能 1：语音交互
支持以下场景：
- **图像理解**："你能看到什么？"
- **知识问答**："天空为什么是蓝色的？"
- **闲聊**："今天心情怎么样？"

### 技能 2：视觉抓取
- **指令示例**："把玩偶抓起来"、"抓取杯子"
- **流程**：MLM 提取物体名称 → GroundingDINO 检测 → 生成抓取位姿 → 机械臂执行

## 系统架构

```
Whisper ASR 终端
    ↓
/audio/asr_result
    ↓
MLM Decision 终端
    ↓
/tts_request → Minimax TTS（播放）
/grasp_target_name → GraspNet（方案 1）
/simple_target_name → Visual Grasping（方案 2）
    ↓
/best_grasp_pose → Grasp Executor（机械臂）
```
