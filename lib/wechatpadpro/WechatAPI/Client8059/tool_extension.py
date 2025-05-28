from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class ToolExtensionMixin(WechatAPIClientBase):
    """8059协议工具扩展功能混入类"""

    async def get_sync_msg(self, key: str = "") -> dict:
        """获取同步消息 (HTTP轮询方式)

        Args:
            key (str): 账号唯一标识

        Returns:
            dict: 同步消息数据
        """
        try:
            # 使用传入的key或实例的key
            sync_key = key or self.key

            # 8059协议的HTTP轮询接口
            response = await self._call_api(f"/message/GetSyncMsg?key={sync_key}", method="GET")

            if response and response.get("Success"):
                logger.debug("[WX8059] 获取同步消息成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取同步消息失败")
                logger.debug(f"[WX8059] 获取同步消息失败: {error_msg}")
                return {}

        except Exception as e:
            logger.debug(f"[WX8059] 获取同步消息异常: {e}")
            return {}

    async def connect_websocket(self, on_message_callback=None):
        """连接WebSocket获取实时消息

        Args:
            on_message_callback: 消息回调函数

        Returns:
            WebSocket连接对象
        """
        try:
            import websockets
            import json

            ws_url = f"ws://{self.ip}:{self.port}/ws/GetSyncMsg?key={self.key}"
            logger.info(f"[WX8059] 连接WebSocket: {ws_url}")

            async def message_handler(websocket, path=None):
                try:
                    async for message in websocket:
                        try:
                            # 解析消息
                            msg_data = json.loads(message)
                            logger.debug(f"[WX8059] 收到WebSocket消息: {msg_data}")

                            # 调用回调函数
                            if on_message_callback:
                                await on_message_callback(msg_data)

                        except json.JSONDecodeError as e:
                            logger.error(f"[WX8059] WebSocket消息JSON解析失败: {e}")
                        except Exception as e:
                            logger.error(f"[WX8059] WebSocket消息处理异常: {e}")

                except websockets.exceptions.ConnectionClosed:
                    logger.warning("[WX8059] WebSocket连接已关闭")
                except Exception as e:
                    logger.error(f"[WX8059] WebSocket连接异常: {e}")

            # 连接WebSocket
            websocket = await websockets.connect(ws_url)
            logger.info("[WX8059] WebSocket连接成功")

            # 启动消息处理
            await message_handler(websocket)

            return websocket

        except ImportError:
            logger.error("[WX8059] 缺少websockets库，请安装: pip install websockets")
            return None
        except Exception as e:
            logger.error(f"[WX8059] WebSocket连接失败: {e}")
            return None

    async def get_online_info(self) -> dict:
        """获取在线设备信息

        Returns:
            dict: 在线设备信息
        """
        try:
            response = await self._call_api("/equipment/GetOnlineInfo", method="GET")

            if response and response.get("Success"):
                logger.debug("[WX8059] 获取在线设备信息成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取在线设备信息失败")
                logger.error(f"[WX8059] 获取在线设备信息失败: {error_msg}")
                raise ToolError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取在线设备信息异常: {e}")
            raise ToolError(f"获取在线设备信息失败: {e}")

    async def get_safety_info(self) -> dict:
        """获取安全设备列表

        Returns:
            dict: 安全设备信息
        """
        try:
            response = await self._call_api("/equipment/GetSafetyInfo")

            if response and response.get("Success"):
                logger.debug("[WX8059] 获取安全设备信息成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取安全设备信息失败")
                logger.error(f"[WX8059] 获取安全设备信息失败: {error_msg}")
                raise ToolError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取安全设备信息异常: {e}")
            raise ToolError(f"获取安全设备信息失败: {e}")

    async def del_safe_device(self, device_uuid: str) -> bool:
        """删除安全设备

        Args:
            device_uuid (str): 设备UUID

        Returns:
            bool: 删除是否成功
        """
        try:
            data = {
                "DeviceUUID": device_uuid
            }

            response = await self._call_api("/equipment/DelSafeDevice", data)

            if response and response.get("Success"):
                logger.debug(f"[WX8059] 删除安全设备成功: {device_uuid}")
                return True
            else:
                error_msg = response.get("Error", "删除安全设备失败")
                logger.error(f"[WX8059] 删除安全设备失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 删除安全设备异常: {e}")
            return False

    async def _call_admin_api(self, endpoint: str, data: dict = None, method: str = "POST") -> dict:
        """调用管理API，使用ADMIN_KEY认证

        Args:
            endpoint (str): API端点
            data (dict): 请求数据
            method (str): HTTP方法

        Returns:
            dict: API响应数据
        """
        import aiohttp

        if not self.admin_key:
            raise Exception("管理功能需要设置ADMIN_KEY")

        url = self.get_api_url(endpoint)

        # 添加admin_key参数到查询字符串
        params = {"key": self.admin_key}

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, params=params) as response:
                        if response.content_type == 'application/json':
                            json_resp = await response.json()
                            self.error_handler(json_resp)
                            return json_resp
                        else:
                            raise Exception("Invalid response format")
                else:
                    async with session.post(url, params=params, json=data) as response:
                        if response.content_type == 'application/json':
                            json_resp = await response.json()
                            self.error_handler(json_resp)
                            return json_resp
                        else:
                            raise Exception("Invalid response format")
        except aiohttp.ClientError as e:
            logger.error(f"[WX8059] 管理API调用失败: {endpoint}, 错误: {e}")
            raise Exception(f"Network error: {e}")
        except Exception as e:
            logger.error(f"[WX8059] 管理API调用异常: {endpoint}, 错误: {e}")
            raise

    async def generate_auth_key(self, count: int = 1, days: int = 30) -> dict:
        """生成授权密钥

        Args:
            count (int): 生成数量
            days (int): 有效天数

        Returns:
            dict: 授权密钥信息
        """
        try:
            data = {
                "Count": count,
                "Days": days
            }

            response = await self._call_admin_api("/admin/GenAuthKey1", data)

            if response and response.get("Success"):
                logger.debug(f"[WX8059] 生成授权密钥成功: count={count}, days={days}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "生成授权密钥失败")
                logger.error(f"[WX8059] 生成授权密钥失败: {error_msg}")
                return {"Success": False, "Error": error_msg}

        except Exception as e:
            logger.error(f"[WX8059] 生成授权密钥异常: {e}")
            return {"Success": False, "Error": str(e)}

    async def delete_auth_key(self, key: str, opt: int = 0) -> bool:
        """删除授权密钥

        Args:
            key (str): 要删除的密钥
            opt (int): 删除选项 (0:仅删除授权码 1:删除授权码相关的所有数据)

        Returns:
            bool: 删除是否成功
        """
        try:
            data = {
                "Key": key,
                "Opt": opt
            }

            response = await self._call_api("/admin/DeleteAuthKey", data)

            if response and response.get("Success"):
                logger.debug(f"[WX8059] 删除授权密钥成功: {key}")
                return True
            else:
                error_msg = response.get("Error", "删除授权密钥失败")
                logger.error(f"[WX8059] 删除授权密钥失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 删除授权密钥异常: {e}")
            return False

    async def delay_auth_key(self, key: str, days: int = 30, expiry_date: str = "") -> bool:
        """延期授权密钥

        Args:
            key (str): 要延期的密钥
            days (int): 延期天数
            expiry_date (str): 到期日期 (格式: 2024-01-01)

        Returns:
            bool: 延期是否成功
        """
        try:
            data = {
                "Key": key,
                "Days": days,
                "ExpiryDate": expiry_date
            }

            response = await self._call_api("/admin/DelayAuthKey", data)

            if response and response.get("Success"):
                logger.debug(f"[WX8059] 延期授权密钥成功: {key}")
                return True
            else:
                error_msg = response.get("Error", "延期授权密钥失败")
                logger.error(f"[WX8059] 延期授权密钥失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 延期授权密钥异常: {e}")
            return False

    async def get_auth_key_list(self) -> dict:
        """获取授权密钥列表

        Returns:
            dict: 授权密钥列表
        """
        try:
            response = await self._call_api("/admin/GetAuthKeyList", method="GET")

            if response and response.get("Success"):
                logger.debug("[WX8059] 获取授权密钥列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取授权密钥列表失败")
                logger.error(f"[WX8059] 获取授权密钥列表失败: {error_msg}")
                raise ToolError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取授权密钥列表异常: {e}")
            raise ToolError(f"获取授权密钥列表失败: {e}")
