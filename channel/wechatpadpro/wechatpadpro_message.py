import os
import time
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any

from bridge.context import ContextType
from channel.chat_message import ChatMessage
from config import conf

class WechatPadProMessage(ChatMessage):
    """
    WechatPadPro 消息处理类 - 微信iPad协议消息处理
    """
    def __init__(self, msg: Dict[str, Any], is_group: bool = False):
        super().__init__(msg)
        self.msg = msg

        # 提取消息基本信息 - 支持8059协议的嵌套字段格式
        self.msg_id = msg.get("msg_id", msg.get("msgid", msg.get("MsgId", msg.get("id", ""))))
        if not self.msg_id:
            self.msg_id = f"msg_{int(time.time())}_{hash(str(msg))}"

        self.create_time = msg.get("create_time", msg.get("timestamp", msg.get("CreateTime", msg.get("createTime", int(time.time())))))
        self.is_group = is_group

        # 提取发送者和接收者ID - 8059协议字段格式处理
        self.from_user_id = self._get_string_value(msg.get("from_user_name", msg.get("fromUserName", msg.get("FromUserName", ""))))
        self.to_user_id = self._get_string_value(msg.get("to_user_name", msg.get("toUserName", msg.get("ToUserName", ""))))

        # 提取消息内容 - 8059协议字段格式处理
        self.content = self._get_string_value(msg.get("content", msg.get("Content", "")))

        # 获取消息类型 - 8059协议字段格式处理
        self.msg_type = msg.get("msg_type", msg.get("type", msg.get("Type", msg.get("MsgType", 0))))

        # 初始化其他字段
        self.sender_wxid = ""      # 实际发送者ID
        self.at_list = []          # 被@的用户列表
        self.ctype = ContextType.UNKNOWN
        self.self_display_name = "" # 机器人在群内的昵称

        # 添加actual_user_id和actual_user_nickname字段，与sender_wxid保持一致
        self.actual_user_id = ""    # 实际发送者ID
        self.actual_user_nickname = "" # 实际发送者昵称

        # --- 在这里或附近添加以下两行 ---
        self.is_processed_text_quote: bool = False
        self.is_processed_image_quote: bool = False
        # --- 添加结束 ---

        self._convert_msg_type_to_ctype()
        self.type = self.ctype  # Ensure self.type attribute exists and holds the ContextType value

        # 尝试从MsgSource中提取机器人在群内的昵称
        try:
            msg_source = msg.get("MsgSource", "")
            if msg_source and ("<msgsource>" in msg_source.lower() or msg_source.startswith("<")):
                root = ET.fromstring(msg_source if "<msgsource>" in msg_source.lower() else f"<msgsource>{msg_source}</msgsource>")

                # 查找displayname或其他可能包含群昵称的字段
                for tag in ["selfDisplayName", "displayname", "nickname"]:
                    elem = root.find(f".//{tag}")
                    if elem is not None and elem.text:
                        self.self_display_name = elem.text
                        break
        except Exception as e:
            # 解析失败，保持为空字符串
            pass

    def _convert_msg_type_to_ctype(self):
        """
        Converts the raw message type (self.msg_type) to ContextType (self.ctype).
        8059协议消息类型枚举:
        1: 文本消息
        3: 图片消息
        6: 文件消息
        42: 名片
        47: 视频消息
        47: 表情消息
        48: 地理位置消息
        49: 引用消息
        50: 语音/视频
        51: 状态通知
        490: 小程序消息
        491: 合并转发消息
        492: 链接消息
        493: 动画表情
        494: 音乐消息
        495: 红包消息
        496: 转账消息
        497: 拍一拍
        2001: 支付消息
        10000: 系统消息
        10002: 撤回消息
        """
        raw_type = str(self.msg_type) # Ensure it's a string

        if raw_type == "1":
            self.ctype = ContextType.TEXT
        elif raw_type == "3":
            self.ctype = ContextType.IMAGE
        elif raw_type == "6":
            self.ctype = ContextType.FILE if hasattr(ContextType, 'FILE') else ContextType.XML
        elif raw_type == "42":
            self.ctype = ContextType.XML  # 名片
        elif raw_type == "47":
            # 47可能是视频或表情，需要进一步判断
            self.ctype = ContextType.VIDEO  # 默认视频，可能需要内容分析
        elif raw_type == "48":
            self.ctype = ContextType.XML  # 地理位置
        elif raw_type == "49":
            self.ctype = ContextType.XML  # 引用消息
        elif raw_type == "50":
            self.ctype = ContextType.VOICE  # 语音/视频
        elif raw_type == "51":
            # 状态通知
            if hasattr(ContextType, 'STATUS_SYNC'):
                self.ctype = ContextType.STATUS_SYNC
            else:
                self.ctype = ContextType.SYSTEM
        elif raw_type in ["490", "491", "492", "493", "494", "495", "496", "497"]:
            # 小程序、合并转发、链接、动画表情、音乐、红包、转账、拍一拍
            self.ctype = ContextType.XML
        elif raw_type == "2001":
            self.ctype = ContextType.XML  # 支付消息
        elif raw_type == "10000":
            self.ctype = ContextType.SYSTEM  # 系统消息
        elif raw_type == "10002":
            # 撤回消息
            if hasattr(ContextType, 'RECALLED'):
                self.ctype = ContextType.RECALLED
            else:
                self.ctype = ContextType.SYSTEM
        else:
            # self.ctype remains ContextType.UNKNOWN (as initialized)
            pass

    def _get_string_value(self, value):
        """确保值为字符串类型 - 支持8059协议的嵌套字段格式"""
        if isinstance(value, dict):
            # 8059协议格式: {'str': '实际值'}
            if 'str' in value:
                return value['str']
            # 其他协议格式: {'string': '实际值'}
            elif 'string' in value:
                return value['string']
            else:
                return ""
        return str(value) if value is not None else ""

    # 以下是公开接口方法，提供给外部使用
    def get_content(self):
        """获取消息内容"""
        return self.content

    def get_type(self):
        """获取消息类型"""
        return self.ctype

    def get_msg_id(self):
        """获取消息ID"""
        return self.msg_id

    def get_create_time(self):
        """获取消息创建时间"""
        return self.create_time

    def get_from_user_id(self):
        """获取原始发送者ID"""
        return self.from_user_id

    def get_sender_id(self):
        """获取处理后的实际发送者ID（群聊中特别有用）"""
        return self.sender_wxid or self.from_user_id

    def get_to_user_id(self):
        """获取接收者ID"""
        return self.to_user_id

    def get_at_list(self):
        """获取被@的用户列表"""
        return self.at_list

    def is_at(self, wxid):
        """检查指定用户是否被@"""
        return wxid in self.at_list

    def is_group_message(self):
        """判断是否为群消息"""
        return self.is_group
