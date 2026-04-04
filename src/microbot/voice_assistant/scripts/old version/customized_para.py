#!/user/bin/env python3     # 指定Python解释器路径
# -*- coding: utf-8 -*-     # 指定文件编码为UTF-8

from enum import Enum       # 导入枚举类模块


class WhisperType(Enum):
    """
    Whisper语音识别模型类型枚举类

    功能:
        定义OpenAI Whisper模型的不同版本和语言变体

    枚举值:
        - tiny: 最小模型（多语言）
        - tiny_en: 最小模型（仅英语）
        - base: 基础模型（多语言）
        - base_en: 基础模型（仅英语）
        - small: 小型模型（多语言）
        - small_en: 小型模型（仅英语）
        - medium: 中型模型（多语言）
        - medium_en: 中型模型（仅英语）
        - large_en: 大型模型（仅英语）
        - turbo_en: 极速模型（仅英语）

    方法:
        __str__: 返回枚举值的字符串表示
    """
    tiny = "tiny"
    tiny_en = "tiny.en"
    base = "base"
    base_en = "base.en"
    small = "small"
    small_en = "small.en"
    medium = "medium"
    medium_en = "medium.en"
    large_en = "large.en"
    turbo_en = "turbo_en"

    def __str__(self):
        """
        返回枚举值的字符串表示

        返回:
            str: 枚举值的字符串形式
        """
        return f"{self.value}"


class BarkType(Enum):
    """
    Bark语音合成模型类型枚举类

    功能:
        定义Bark模型的不同语言和发音人配置

    枚举值:
        - ENGLISH: 英语发音人前缀
        - CHINESE: 中文发音人前缀

    方法:
        __new__: 自定义枚举成员创建逻辑
        __call__: 允许通过调用枚举值生成具体发音人配置
    """
    ENGLISH = "v2/en_speaker_"          # 英语发音人前缀
    CHINESE = "v2/zh_speaker_"          # 中文发音人前缀

    def __new__(cls, value):
        """
        自定义枚举成员创建逻辑

        参数:
            cls: 当前类
            value: 枚举值

        返回:
            枚举成员实例
        """
        member = object.__new__(cls)    # 创建枚举成员实例
        member._value_ = value          # 设置枚举值
        return member

    def __call__(self, num):
        """
        允许通过调用枚举值生成具体发音人配置

        参数:
            num (int): 发音人编号

        返回:
            str: 完整的发音人配置字符串
        """
        return f"{self._value_}{num}"           # 拼接前缀和编号
