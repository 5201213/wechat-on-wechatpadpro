from ..errors import *
from .base import WechatAPIClientBase, Proxy, Section
from .chatroom import ChatroomMixin
from .friend import FriendMixin
from .hongbao import HongBaoMixin
from .login import LoginMixin
from .message import MessageMixin
from .protect import protector
from .tool import ToolMixin
from .tool_extension import ToolExtensionMixin
from .user import UserMixin
from .pyq import PyqMixin
import sqlite3
import os
from loguru import logger

class WechatAPIClient8059(LoginMixin, MessageMixin, FriendMixin, ChatroomMixin, UserMixin,
                          ToolMixin, ToolExtensionMixin, HongBaoMixin, PyqMixin):
    """
    WeChatPadPro-8059协议客户端
    适配8059协议的API接口和认证方式
    """

    def __init__(self, ip: str, port: int, key: str = "", admin_key: str = ""):
        super().__init__(ip, port)
        self.key = key  # TOKEN_KEY - 用于普通API调用
        self.admin_key = admin_key  # ADMIN_KEY - 用于管理功能
        self.contacts_db = None
        self.protocol_version = "8059"

        # 8059协议特有的配置
        self.api_base_path = ""  # 8059协议不使用/api前缀
        self.ws_path = "/ws/GetSyncMsg"

        logger.info(f"[WX8059] 初始化8059协议客户端: {ip}:{port}, key={key[:8]}..., admin_key={'已设置' if admin_key else '未设置'}")

    def set_key(self, key: str):
        """设置账号唯一标识key (TOKEN_KEY)"""
        self.key = key
        logger.info(f"[WX8059] 设置TOKEN_KEY: {key[:8]}...")

    def set_admin_key(self, admin_key: str):
        """设置管理密钥 (ADMIN_KEY)"""
        self.admin_key = admin_key
        logger.info(f"[WX8059] 设置ADMIN_KEY: {'已设置' if admin_key else '未设置'}")

    def get_api_url(self, endpoint: str) -> str:
        """获取API完整URL，适配8059协议路径"""
        # 移除开头的/api/前缀（如果存在）
        if endpoint.startswith("/api/"):
            endpoint = endpoint[4:]

        # 确保以/开头
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        return f"http://{self.ip}:{self.port}{endpoint}"

    def get_ws_url(self) -> str:
        """获取WebSocket连接URL"""
        return f"ws://{self.ip}:{self.port}{self.ws_path}?key={self.key}"

    async def _call_api_with_key(self, endpoint: str, data: dict = None, method: str = "POST") -> dict:
        """
        调用API，自动添加key参数
        适配8059协议的认证方式
        """
        import aiohttp

        url = self.get_api_url(endpoint)

        # 添加key参数到查询字符串
        params = {"key": self.key} if self.key else {}

        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, params=params) as response:
                    if response.content_type == 'application/json':
                        return await response.json()
                    else:
                        return {"Success": False, "Error": "Invalid response format"}
            else:
                async with session.post(url, params=params, json=data) as response:
                    if response.content_type == 'application/json':
                        return await response.json()
                    else:
                        return {"Success": False, "Error": "Invalid response format"}
