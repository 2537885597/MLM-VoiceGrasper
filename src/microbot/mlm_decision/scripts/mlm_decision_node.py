#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MLM 决策中枢节点（简化版）
功能：
1. 接收语音识别的文本信息
2. 接收 Realsense RGB 图像
3. 调用 Qwen3.5-0.8B MLM 进行意图理解和决策
4. 根据用户意图选择不同的 skill 执行：
   - 图像描述：对 RGB 图像进行描述并生成语音回复
   - 视觉抓取：一体化分析用户意图，提取抓取物体名称并翻译为英文，调用视觉抓取流程

注意：
- 使用键盘输入作为技能选择（后续会换成 MCP 技能调用）
- 移除了关键词判断逻辑
"""

import rospy
import cv2
import numpy as np
import base64
import json
import requests
from sensor_msgs.msg import Image
from std_msgs.msg import String
from voice_assistant.msg import ASRResponse, TTSRequest
from cv_bridge import CvBridge
from ollama import chat
import threading


class MLMDecisionNode:
    def __init__(self):
        try:
            rospy.init_node('mlm_decision_node', anonymous=True)
            rospy.loginfo("MLM 决策中枢节点启动中...")
            
            # Ollama MLM 配置
            self.ollama_url = rospy.get_param('~ollama_url', 'http://localhost:11434/v1')
            self.mlm_model = rospy.get_param('~mlm_model', 'qwen3.5:0.8b')
            rospy.loginfo(f"MLM 配置：{self.ollama_url}, 模型：{self.mlm_model}")
            
            # 图像相关
            self.bridge = CvBridge()
            self.current_image = None
            self.image_lock = threading.Lock()
            
            # 语音识别文本
            self.current_text = None
            
            # 订阅者
            self.asr_sub = rospy.Subscriber(
                '/audio/asr_result',
                ASRResponse,
                self.asr_callback,
                queue_size=10
            )
            
            self.image_sub = rospy.Subscriber(
                '/camera/color/image_raw',
                Image,
                self.image_callback,
                queue_size=10
            )
            
            # 发布者
            self.tts_pub = rospy.Publisher('/tts_request', TTSRequest, queue_size=10)
            
            # 发布抓取目标物体名称（用于 GroundingDINO 的 text_prompt）
            self.grasp_target_name_pub = rospy.Publisher('/grasp_target_name', String, queue_size=10)
            self.simple_target_name_pub = rospy.Publisher('/simple_target_name', String, queue_size=10)
            
            # 发布移动控制指令
            self.move_command_pub = rospy.Publisher('/move_command', String, queue_size=10)
            
            # 技能选择模式
            self.skill_mode = None  # 'conversation' 或 'grasping' 或 'move_control'
            
            rospy.loginfo("MLM 决策中枢节点初始化完成")
            rospy.loginfo("等待语音识别和图像数据...")
            rospy.loginfo("请输入技能选择：1-语音交互，2-视觉抓取，3-移动控制")
            
        except Exception as e:
            rospy.logfatal("❌ 节点初始化失败！")
            rospy.logfatal(f"错误信息：{str(e)}")
            import traceback
            traceback.print_exc()
            rospy.signal_shutdown("初始化失败")
    
    def asr_callback(self, msg):
        """语音识别结果回调"""
        if msg.success and msg.transcript:
            rospy.loginfo(f"收到语音识别结果：{msg.transcript}")
            self.current_text = msg.transcript
            # 根据技能模式处理决策
            if self.skill_mode == 'conversation':
                self.handle_voice_conversation_skill()
            elif self.skill_mode == 'grasping':
                self.handle_visual_grasping_skill()
            elif self.skill_mode == 'move_control':
                self.handle_move_control_skill()
            else:
                rospy.logwarn("未选择技能模式，请输入技能选择：1-语音交互，2-视觉抓取，3-移动控制")
        else:
            rospy.logwarn("语音识别失败或为空")
    
    def image_callback(self, msg):
        """RGB 图像回调"""
        try:
            with self.image_lock:
                self.current_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            rospy.logerr(f"图像转换失败：{str(e)}")
    
    def encode_image_to_base64(self, image):
        """将 OpenCV 图像编码为 base64"""
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    def call_mlm(self, prompt, user_text, image=None):
        """
            调用 Qwen3.5-0.8B MLM 进行推理 仅Ollama API支持视觉图片
            :param prompt: 输入的文本提示
            :param user_text: 用户语音识别文本
            :param image: Base64 编码的 RGB 图像
            :param max_tokens: 最大生成 token 数量
            :return: MLM 推理结果
        """
        try:
            messages = []
            
            if image is not None:
                image_base64 = self.encode_image_to_base64(image)
                messages = [
                    {
                        'role': 'system',
                        'content': f"{prompt}"
                    },
                    {
                        'role': 'user',
                        'content': f"{user_text}",
                        'images': [image_base64],
                    }
                ]
            else:
                messages = [
                    {
                        'role': 'system',
                        'content': f"{prompt}"
                    },
                    {
                        'role': 'user',
                        'content': f"{user_text}"
                    }
                ]
            
            response = chat(
                model=self.mlm_model,
                messages=messages,
                stream=False,
                options={
                    "temperature": 0.1
                    # "max_tokens": max_tokens
                }
            )
            
            result = response.message.content.strip()
            return result

        except Exception as e:
            rospy.logerr(f"MLM 调用失败：{str(e)}")
            return None
    
    def handle_voice_conversation_skill(self):
        """处理语音交互技能（支持图像理解、知识问答、闲聊等）"""
        if not self.current_text:
            rospy.logwarn("当前没有语音识别文本")
            return
        
        user_text = self.current_text
        rospy.loginfo(f"处理语音交互：{user_text}")
        
        with self.image_lock:
            current_image = self.current_image.copy() if self.current_image is not None else None
        
        if current_image is None:
            rospy.logwarn("当前没有图像数据，等待图像...")
            return
        
        try:
            # 灵活的语音交互提示词，支持图像理解、知识问答、闲聊等
            prompt = """
                你是一个智能语音助手，具备视觉理解能力。
                请根据用户的输入和当前图像，给出自然、简洁、有帮助的回复。
                
                要求：
                1. 如果用户询问图像内容，请详细描述图像中的物体、颜色、位置关系等
                2. 如果用户提问知识性问题，请给出准确、简洁的答案
                3. 如果用户只是闲聊，请友好地回应
                4. 使用中文回答，回复简洁明了
                
                示例：
                用户：你能看到什么？
                回复：我看到桌子上有一个红色的玩偶，旁边还有一个蓝色的杯子...
                
                用户：天空为什么是蓝色的？
                回复：天空呈现蓝色是因为瑞利散射。太阳光中的蓝光波长较短，容易被大气中的分子散射...
                
                用户：今天心情怎么样？
                回复：我是一个 AI 助手，没有情感，但我很高兴为您服务！
            """
            
            response = self.call_mlm(prompt, user_text, current_image)
            
            if response:
                rospy.loginfo(f"语音交互回复：{response}")
                self.publish_tts(response)
            else:
                rospy.logerr("语音交互失败")
                self.publish_tts("抱歉，我无法回答您的问题。")
        
        except Exception as e:
            rospy.logerr(f"语音交互技能失败：{str(e)}")
            import traceback
            traceback.print_exc()
    
    def handle_visual_grasping_skill(self):
        """处理视觉抓取技能（一体化分析用户意图，提取抓取物体名称并翻译为英文）"""
        if not self.current_text:
            rospy.logwarn("当前没有语音识别文本")
            return
        
        user_text = self.current_text
        rospy.loginfo(f"处理视觉抓取技能：{user_text}")
        
        with self.image_lock:
            current_image = self.current_image.copy() if self.current_image is not None else None
        
        if current_image is None:
            rospy.logwarn("当前没有图像数据，等待图像...")
            return
        
        try:
            # 一体化分析用户意图，提取抓取物体名称并翻译为英文
            prompt = f"""
                请分析用户的抓取意图，完成以下任务：
                1. 提取用户想要抓取的物体名称
                2. 将物体名称翻译为英文

                要求：
                1. 输出格式为：中文物体名称|英文物体名称
                2. 如果没有明确指定物体，输出：未指定物体|unknown
                3. 使用常见的简洁的物体名称

                示例：
                用户：把玩偶抓起来
                输出：玩偶|doll

                用户：抓取那个红色的杯子
                输出：杯子|cup

                用户：把盒子拿起来
                输出：盒子|box
            """
            
            result = self.call_mlm(prompt, user_text, current_image)
            
            if result and '|' in result:
                parts = result.strip().split('|')
                if len(parts) == 2:
                    object_name_zh = parts[0].strip()
                    object_name_en = parts[1].strip().lower()
                    
                    rospy.loginfo(f"提取的物体名称：中文={object_name_zh}, 英文={object_name_en}")
                    
                    if object_name_zh != "未指定物体" and object_name_en != "unknown":
                        rospy.loginfo(f"有效抓取目标：{object_name_zh} ({object_name_en})")
                        self.publish_tts(f"好的，我将抓取{object_name_zh}")
                        
                        # 发布抓取目标到两个话题（方案 1 和方案 2 都使用）
                        self.publish_grasp_target_name(object_name_en)
                        self.publish_simple_target_name(object_name_en)
                    else:
                        rospy.logwarn("未提取到有效的抓取物体")
                        self.publish_tts("抱歉，我没有理解您要抓取什么物体。")
                else:
                    rospy.logerr(f"MLM 输出格式错误：{result}")
                    self.publish_tts("抱歉，我无法解析抓取目标。")
            else:
                rospy.logerr(f"MLM 输出格式错误：{result}")
                self.publish_tts("抱歉，我无法解析抓取目标。")
        
        except Exception as e:
            rospy.logerr(f"视觉抓取技能失败：{str(e)}")
            import traceback
            traceback.print_exc()
    
    def handle_move_control_skill(self):
        """处理移动控制技能（解析语音指令，控制底盘移动）"""
        if not self.current_text:
            rospy.logwarn("当前没有语音识别文本")
            return

        user_text = self.current_text
        rospy.loginfo(f"处理移动控制：{user_text}")

        try:
            prompt = """
                你是一个机器人移动控制助手。请根据用户的语音指令，解析出移动意图并输出 JSON 格式的移动命令。

                支持的移动动作：
                1. 普通移动（指定距离或角度）：
                   - forward: 前进，参数 distance（米），如 0.5、1.0
                   - backward: 后退，参数 distance（米），如 0.5、1.0
                   - left: 左转，参数 angle（度），如 45、90
                   - right: 右转，参数 angle（度），如 45、90
                   - stop: 停止

                2. 目标点位移动（带路径规划和自动避障）：
                   - move_to_marker: 移动到预设点位代号，参数 marker（字符串）
                     常用点位代号：charge_point、desk_front、voice_test
                   - move_to_location: 移动到指定坐标，参数 x, y, theta（米和弧度）

                3. 取消移动：
                   - cancel_move: 取消当前正在执行的移动任务

                输出格式必须是严格的JSON格式，不要包含任何额外文本：
                前进0.5米：{"action": "forward", "distance": 0.5}
                后退1米：{"action": "backward", "distance": 1.0}
                左转90度：{"action": "left", "angle": 90}
                右转45度：{"action": "right", "angle": 45}
                停止：{"action": "stop"}
                去充电点：{"action": "move_to_marker", "marker": "charge_point"}
                去桌子前面：{"action": "move_to_marker", "marker": "desk_front"}
                移动到坐标：{"action": "move_to_location", "x": 1.5, "y": 0.8, "theta": 0.0}
                取消移动：{"action": "cancel_move"}

                示例：
                用户：前进0.5米
                输出：{"action": "forward", "distance": 0.5}

                用户：后退一米
                输出：{"action": "backward", "distance": 1.0}

                用户：左转90度
                输出：{"action": "left", "angle": 90}

                用户：右转45度
                输出：{"action": "right", "angle": 45}

                用户：停下来
                输出：{"action": "stop"}

                用户：去充电点
                输出：{"action": "move_to_marker", "marker": "charge_point"}

                用户：移动到桌子前面
                输出：{"action": "move_to_marker", "marker": "desk_front"}

                用户：去语音测试点
                输出：{"action": "move_to_marker", "marker": "voice_test"}

                请直接输出JSON结果，不要包含任何解释或额外文本。
            """

            result = self.call_mlm(prompt, user_text)

            if result:
                rospy.loginfo(f"MLM 移动解析结果：{result}")
                try:
                    command = json.loads(result)
                    action = command.get("action", "")

                    action_descriptions = {
                        "forward": f"前进 {command.get('distance', 0.5):.1f} 米",
                        "backward": f"后退 {command.get('distance', 0.5):.1f} 米",
                        "left": f"左转 {command.get('angle', 90):.0f} 度",
                        "right": f"右转 {command.get('angle', 90):.0f} 度",
                        "stop": "停止",
                        "move_to_marker": f"导航到点位 {command.get('marker', '')}",
                        "move_to_location": f"导航到坐标 ({command.get('x', 0):.1f}, {command.get('y', 0):.1f})",
                        "cancel_move": "取消移动"
                    }

                    description = action_descriptions.get(action, action)
                    self.publish_tts(f"好的，{description}")
                    self.publish_move_command(result)

                except json.JSONDecodeError:
                    rospy.logerr(f"MLM 输出不是有效的 JSON：{result}")
                    self.publish_tts("抱歉，我无法理解您的移动指令。")
            else:
                rospy.logerr("移动控制解析失败")
                self.publish_tts("抱歉，我无法理解您的移动指令。")

        except Exception as e:
            rospy.logerr(f"移动控制技能失败：{str(e)}")
            import traceback
            traceback.print_exc()

    def publish_move_command(self, command_json):
        """发布移动控制指令"""
        try:
            msg = String()
            msg.data = command_json
            self.move_command_pub.publish(msg)
            rospy.loginfo(f"已发布移动指令：{command_json}")
        except Exception as e:
            rospy.logerr(f"发布移动指令失败：{str(e)}")

    def publish_tts(self, text):
        """发布 TTS 请求"""
        try:
            msg = TTSRequest()
            msg.text = text
            self.tts_pub.publish(msg)
            rospy.loginfo(f"已发布 TTS 请求：{text}")
        except Exception as e:
            rospy.logerr(f"发布 TTS 请求失败：{str(e)}")
    
    def publish_grasp_target_name(self, object_name_en):
        """发布抓取目标物体名称 方案 1：原方案使用（用于 GroundingDINO 的 text_prompt）"""
        try:
            msg = String()
            msg.data = object_name_en
            self.grasp_target_name_pub.publish(msg)
            rospy.loginfo(f"已发布抓取目标物体名称：{object_name_en}")
        except Exception as e:
            rospy.logerr(f"发布抓取目标物体名称失败：{str(e)}")
    
    def publish_simple_target_name(self, object_name_en):
        """发布视觉抓取目标物体名称 方案 2：简化方案使用"""
        try:
            msg = String()
            msg.data = object_name_en
            self.simple_target_name_pub.publish(msg)
            rospy.loginfo(f"已发布视觉抓取目标物体名称：{object_name_en}")
        except Exception as e:
            rospy.logerr(f"发布视觉抓取目标物体名称失败：{str(e)}")


if __name__ == "__main__":
    try:
        node = MLMDecisionNode()
        
        # 启动键盘输入线程，用于选择技能
        import threading
        
        def keyboard_input():
            """键盘输入选择技能"""
            while not rospy.is_shutdown():
                try:
                    choice = input("\n请选择技能 (1-语音交互，2-视觉抓取，3-移动控制): ").strip()
                    if choice == '1':
                        node.skill_mode = 'conversation'
                        rospy.loginfo("已选择语音交互技能")
                    elif choice == '2':
                        node.skill_mode = 'grasping'
                        rospy.loginfo("已选择视觉抓取技能")
                    elif choice == '3':
                        node.skill_mode = 'move_control'
                        rospy.loginfo("已选择移动控制技能")
                    else:
                        rospy.logwarn("无效输入，请输入 1、2 或 3")
                except Exception as e:
                    if "EOF" not in str(e):  # 忽略 EOF 错误（非交互式输入）
                        rospy.logerr(f"键盘输入错误：{str(e)}")
                    break
        
        # 启动键盘输入线程
        keyboard_thread = threading.Thread(target=keyboard_input, daemon=True)
        keyboard_thread.start()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("节点被中断")
    except Exception as e:
        rospy.logerr(f"节点运行失败：{str(e)}")
        import traceback
        traceback.print_exc()
