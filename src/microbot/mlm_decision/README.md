# MLM 决策中枢

基于 Qwen3-VL-8B 多模态大模型的决策中枢系统，实现语音 + 视觉的智能交互。

## 功能特性

### 1. 图像描述
当用户问"你能看到什么？"时：
- MLM 对 Realsense RGB 图像进行描述
- 生成自然语言回复
- 通过 TTS 播放语音

### 2. 视觉抓取
当用户说"把玩偶抓起来"时：
- MLM 提取抓取意图的对象（如"玩偶"）
- 将中文对象名翻译为英文（如"doll"）
- 根据选择的方案执行抓取流程

## 视觉抓取方案

系统提供两种视觉抓取方案，通过 `grasp_scheme` 参数选择：

### 方案 1：GraspNet 完整流程（graspnet）

**流程**：
```
MLM 提取物体名称 → GroundingDINO 检测 → SAM 分割 → GraspNet 抓取位姿生成 → 手眼标定 → 机械臂抓取
```

**特点**：
- ✅ 使用 GraspNet 生成高质量抓取位姿
- ✅ 使用 SAM 进行精确实例分割
- ✅ 支持多目标检测和抓取
- ❌ 计算复杂度较高，速度较慢

**组件**：
- `vision_processor.py`: GroundingDINO + SAM 检测分割
- `graspnet_generator_with_dl.py`: GraspNet 抓取位姿生成

### 方案 2：简化方案（simplified）

**流程**：
```
MLM 提取物体名称 → GroundingDINO 检测 → 深度信息获取 3D 位置 → 固定姿态抓取位姿 → 手眼标定 → 机械臂抓取
```

**特点**：
- ✅ 简单快速，计算量小
- ✅ 直接生成抓取位姿，无需 GraspNet
- ❌ 使用固定抓取姿态（从上往下）
- ❌ 精度略低于方案 1

**组件**：
- `visual_grasping_skill.py`: GroundingDINO 检测 + 3D 位置计算

## 系统架构

```
麦克风 → Whisper ASR → 语音识别文本
                      ↓
Realsense RGB 图像 → MLM 决策中枢 (Qwen3-VL-8B)
                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
   图像描述 Skill           视觉抓取 Skill
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

## 安装

### 1. 依赖安装

```bash
# 安装 Python 依赖
pip install ollama opencv-python sensor-msgs cv-bridge

# 安装 GroundingDINO（两种方案都需要）
cd /home/rm/GroundingDINO
pip install -e .

# 安装 SAM（方案 1 需要）
pip install segment-anything

# 安装 GraspNet（方案 1 需要）
cd /home/rm/realman_ws/src/graspnet-baseline
pip install -e .
```

### 2. 下载模型

```bash
# 下载 Qwen3-VL-8B 模型
ollama pull qwen3-vl:8b

# 下载 GroundingDINO 模型（两种方案都需要）
# 路径：/home/rm/realman_ws/src/graspnet_ros/models/groundingdino_swint_ogc.pth

# 下载 SAM 模型（方案 1 需要）
# 路径：/home/rm/realman_ws/src/graspnet_ros/models/sam_vit_b.pth

# 下载 GraspNet 模型（方案 1 需要）
# 路径：/home/rm/realman_ws/src/graspnet_ros/models/graspnet/
```

## 使用方法

### 方式 1：启动完整系统（默认使用简化方案）

```bash
# 使用简化方案（方案 2）
roslaunch mlm_decision mlm_system.launch

# 使用 GraspNet 完整流程（方案 1）
roslaunch mlm_decision mlm_system.launch grasp_scheme:=graspnet
```

这会启动：
- Realsense 相机（RGB + 深度 + 对齐）
- 语音对话节点（Whisper ASR + TTS）
- MLM 决策中枢
- 视觉抓取技能（根据 grasp_scheme 选择）
- 抓取执行节点（grasp_executor）

### 方式 2：单独启动 MLM 决策中枢

```bash
roslaunch mlm_decision mlm_decision.launch
```

### 方式 3：命令行测试

```bash
# 启动 MLM 决策节点
rosrun mlm_decision mlm_decision_node.py

# 在另一个终端发布语音识别结果
rostopic pub /audio/asr_result voice_assistant/ASRResponse "transcript: '你能看到什么' success: true"

# 或发布抓取指令
rostopic pub /audio/asr_result voice_assistant/ASRResponse "transcript: '把玩偶抓起来' success: true"
```

## 话题和服务

### 订阅的话题
- `/audio/asr_result` (ASRResponse): 语音识别结果
- `/camera/color/image_raw` (Image): Realsense RGB 图像
- `/camera/aligned_depth_to_color/image_raw` (Image): Realsense 对齐深度图像
- `/grasp_target` (String): MLM 发布的抓取目标（两种方案都使用）

### 发布的话题
- `/tts_request` (TTSRequest): TTS 请求
- `/best_grasp_pose` (PoseStamped): 抓取位姿（两种方案都发布）
- `/object_poses` (DetectedObjectArray): 检测结果（方案 1 发布）

### 提供的服务
- `/vision_grasp` (GraspRequest): 视觉抓取服务（两种方案都提供）

## 示例对话

### 示例 1：语音交互（图像理解）
```
用户：你能看到什么？
MLM：我看到桌子上有一个红色的玩偶，旁边还有一个蓝色的杯子。玩偶在图像的左侧，杯子在右侧。
```

### 示例 2：语音交互（知识问答）
```
用户：天空为什么是蓝色的？
MLM：天空呈现蓝色是因为瑞利散射。太阳光中的蓝光波长较短，容易被大气中的分子散射...
```

### 示例 3：视觉抓取（两种方案）
```
用户：把玩偶抓起来
MLM：好的，我将抓取玩偶

方案 1（GraspNet）:
  → vision_processor 检测"doll"
  → SAM 分割玩偶区域
  → GraspNet 生成抓取位姿
  → grasp_executor 执行抓取

方案 2（简化）:
  → GroundingDINO 检测"doll"
  → 计算 3D 位置（固定姿态）
  → 发布抓取位姿
  → grasp_executor 执行抓取
```

## 配置参数

### mlm_system.launch 参数
- `mlm_model`: MLM 模型名称，默认 `qwen3-vl:8b`
- `asr_model`: Whisper ASR 模型，默认 `base`
- `use_camera`: 是否启动相机，默认 `true`
- `grasp_scheme`: 视觉抓取方案，默认 `simplified`（简化方案）
  - `simplified`: 简化方案（GroundingDINO + 深度）
  - `graspnet`: GraspNet 完整流程

### visual_grasping_skill 参数（方案 2）
- `grounding_dino_model`: GroundingDINO 模型
- `model_dir`: 模型目录
- `box_threshold`: 检测框置信度阈值，默认 `0.35`
- `text_threshold`: 文本匹配阈值，默认 `0.25`

### vision_processor 参数（方案 1）
- `text_prompt`: 文本提示（会被 MLM 动态更新）
- `box_threshold`: 检测框置信度阈值
- `text_threshold`: 文本 - 图像匹配阈值

## 方案选择建议

### 使用方案 1（GraspNet）的场景：
- 需要高质量、多样化的抓取位姿
- 物体形状复杂，需要精确分割
- 对抓取成功率要求高
- 计算资源充足

### 使用方案 2（简化）的场景：
- 需要快速响应
- 物体比较简单（如玩偶、杯子等）
- 计算资源有限
- 抓取姿态固定即可满足需求

## 故障排除

### 1. MLM 响应慢
- 检查 Ollama 服务是否正常运行
- 确保 qwen3-vl:8b 模型已下载
- 考虑使用更小的模型（如 qwen3-vl:2b）

### 2. GroundingDINO 检测失败
- 检查模型文件路径是否正确
- 调整 BOX_THRESHOLD 和 TEXT_THRESHOLD 参数
- 确保图像质量良好

### 3. 深度值无效
- 检查 Realsense 相机是否正常工作
- 确保深度对齐已启用（align_depth=true）
- 检查物体是否在相机有效深度范围内

### 4. 抓取执行失败
- 检查手眼标定矩阵是否正确
- 验证机械臂工作空间是否可达
- 检查 grasp_executor 节点是否正常启动

## 扩展开发

### 添加新的 Skill

1. 在 `mlm_decision_node.py` 中添加意图判断逻辑
2. 创建新的 Skill 处理函数
3. 实现具体的业务逻辑

### 自定义 MLM 提示词

修改 `mlm_decision_node.py` 中的 `call_mlm()` 函数，调整提示词模板。

### 切换默认方案

修改 `mlm_system.launch` 中的默认值：
```xml
<arg name="grasp_scheme" default="graspnet"/>
```

## 许可证

MIT License
