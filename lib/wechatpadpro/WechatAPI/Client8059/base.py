import aiohttp
from typing import Optional, Dict, Any
from loguru import logger
from ..errors import (
    APIError, AuthenticationError, PermissionError, NotFoundError,
    RateLimitError, MessageError, FriendError, ChatroomError,
    UserError, ToolError, PaymentError, SnsError
)

class Proxy:
    """代理配置类"""
    def __init__(self, proxy_ip: str = "", proxy_user: str = "", proxy_password: str = ""):
        self.ProxyIp = proxy_ip
        self.ProxyUser = proxy_user
        self.ProxyPassword = proxy_password

class Section:
    """数据分包类"""
    def __init__(self, start_pos: int = 0, data_len: int = 61440):
        self.StartPos = start_pos
        self.DataLen = data_len

class WechatAPIClientBase:
    """8059协议微信API客户端基类

    Args:
        ip (str): 服务器IP地址
        port (int): 服务器端口

    Attributes:
        wxid (str): 微信ID
        nickname (str): 昵称
        alias (str): 别名
        phone (str): 手机号
        key (str): 8059协议账号唯一标识
        ignore_protect (bool): 是否忽略保护机制
    """
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port

        self.wxid = ""
        self.nickname = ""
        self.alias = ""
        self.phone = ""
        self.key = ""  # TOKEN_KEY
        self.admin_key = ""  # ADMIN_KEY for management functions

        self.ignore_protect = False

        # 8059协议特有配置
        self.protocol_version = "8059"
        self.api_base_path = ""  # 8059协议不使用/api前缀

        # 调用所有 Mixin 的初始化方法
        super().__init__()

    @staticmethod
    def error_handler(json_resp):
        """处理API响应中的错误码 - 适配8059协议

        Args:
            json_resp (dict or list): API响应的JSON数据

        Raises:
            相应的异常类型
        """

        if not json_resp:
            raise APIError("Empty response")

        # 处理列表响应格式
        if isinstance(json_resp, list):
            if len(json_resp) == 0:
                raise APIError("Empty response list")
            # 对于列表响应，检查第一个元素
            first_item = json_resp[0]
            if isinstance(first_item, dict):
                response_code = first_item.get("Code", 0)
                if response_code != 200:
                    error_msg = first_item.get("Text", "Unknown error")
                    raise APIError(f"API Error: {error_msg} (Code: {response_code})")
            # 如果列表中的元素不是字典，假设是成功响应
            return

        # 处理字典响应格式
        if isinstance(json_resp, dict):
            # 8059协议使用Code字段，200表示成功
            response_code = json_resp.get("Code", 0)

            if response_code != 200:
                error_msg = json_resp.get("Text", "Unknown error")

                # 根据错误码抛出相应异常
                if response_code == 401:
                    raise AuthenticationError(error_msg)
                elif response_code == 403:
                    raise PermissionError(error_msg)
                elif response_code == 404:
                    raise NotFoundError(error_msg)
                elif response_code == 429:
                    raise RateLimitError(error_msg)
                else:
                    raise APIError(f"API Error: {error_msg} (Code: {response_code})")

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
        return f"ws://{self.ip}:{self.port}/ws/GetSyncMsg?key={self.key}"

    async def _call_api(self, endpoint: str, data: dict = None, method: str = "POST", use_admin_key: bool = False) -> dict:
        """
        调用API的基础方法，适配8059协议

        Args:
            endpoint (str): API端点
            data (dict): 请求数据
            method (str): HTTP方法
            use_admin_key (bool): 是否使用管理员key

        Returns:
            dict: API响应数据
        """
        url = self.get_api_url(endpoint)

        # 根据use_admin_key参数选择使用哪个key
        if use_admin_key:
            key_to_use = self.admin_key if hasattr(self, 'admin_key') and self.admin_key else self.key
        else:
            key_to_use = self.key

        # 添加key参数到查询字符串
        params = {"key": key_to_use} if key_to_use else {}

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, params=params) as response:
                        if response.content_type == 'application/json':
                            json_resp = await response.json()
                            self.error_handler(json_resp)
                            return json_resp
                        else:
                            raise APIError("Invalid response format")
                else:
                    async with session.post(url, params=params, json=data) as response:
                        if response.content_type == 'application/json':
                            json_resp = await response.json()
                            self.error_handler(json_resp)
                            return json_resp
                        else:
                            raise APIError("Invalid response format")
        except aiohttp.ClientError as e:
            logger.error(f"[WX8059] API调用失败: {endpoint}, 错误: {e}")
            raise APIError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"[WX8059] API调用异常: {endpoint}, 错误: {e}")
            raise
