import aiohttp
from .base import WechatAPIClientBase
from .protect import protector
from ..errors import LoginError
from loguru import logger

class LoginMixin(WechatAPIClientBase):
    """8059协议登录相关功能混入类"""

    async def get_qr_code(self, device_name: str = "iPad", device_id: str = "", proxy: str = "", print_qr: bool = False) -> tuple:
        """获取登录二维码

        Args:
            device_name (str): 设备名称
            device_id (str): 设备ID
            proxy (str): 代理设置
            print_qr (bool): 是否打印二维码

        Returns:
            tuple: (uuid, qr_url)

        Raises:
            LoginError: 获取二维码失败
        """
        try:
            # 8059协议的获取二维码接口 - 按照API文档格式
            data = {
                "Check": False,
                "Proxy": proxy if proxy else ""
            }

            response = await self._call_api("/login/GetLoginQrCodeNew", data)

            if response and response.get("Code") == 200:
                data = response.get("Data", {})

                # 8059协议实际返回格式适配
                # 我们不需要真正的UUID，使用普通key作为会话标识即可
                session_key = data.get("Key", "")

                # 从QrCodeUrl参数中提取微信原始二维码URL
                qr_url = ""
                qr_code_url = data.get("QrCodeUrl", "")

                if qr_code_url and "weixin.qq.com" in qr_code_url:
                    # 从QrCodeUrl中提取微信原始链接
                    # 格式: https://api.pwmqr.com/qrcode/create/?url=http://weixin.qq.com/x/xxxxx
                    import re
                    match = re.search(r'url=(http://weixin\.qq\.com/[^&\s]+)', qr_code_url)
                    if match:
                        qr_url = match.group(1)
                        logger.info(f"[WX8059] 获取登录二维码成功")
                        logger.info(f"[WX8059] 微信二维码链接: {qr_url}")

                        # 如果需要显示二维码，则显示微信原始链接的二维码
                        if print_qr and qr_url:
                            self._print_qr_code(qr_url)
                    else:
                        logger.error(f"[WX8059] 无法从QrCodeUrl中提取微信链接: {qr_code_url}")
                else:
                    logger.error(f"[WX8059] QrCodeUrl为空或不包含微信链接: {qr_code_url}")
                    logger.debug(f"[WX8059] 响应数据: {data}")
                return session_key, qr_url
            else:
                error_msg = response.get("Text", "获取二维码失败")
                logger.error(f"[WX8059] 获取登录二维码失败: {error_msg}")
                raise LoginError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取登录二维码异常: {e}")
            raise LoginError(f"获取登录二维码失败: {e}")

    async def check_qr_login(self, uuid: str, device_id: str = "") -> tuple:
        """检查二维码登录状态

        Args:
            uuid (str): 二维码UUID
            device_id (str): 设备ID

        Returns:
            tuple: (success, data) - 成功状态和数据

        Raises:
            根据error_handler处理错误
        """
        try:
            # 8059协议的CheckLoginStatus是GET请求，不需要body参数
            response = await self._call_api("/login/CheckLoginStatus", {}, method="GET")

            if response and response.get("Code") == 200:
                login_data = response.get("Data", {})

                # 检查登录状态
                login_state = login_data.get("loginState", 0)
                if login_state == 1:  # 1表示在线
                    logger.info(f"[WX8059] 登录状态检查成功: 账号在线")
                    return True, login_data
                else:
                    # 返回登录状态信息
                    login_msg = login_data.get("loginErrMsg", "账号不在线")
                    logger.debug(f"[WX8059] 登录状态: {login_msg}")
                    return False, login_data
            else:
                error_msg = response.get("Text", "检查登录状态失败")
                logger.warning(f"[WX8059] 检查登录状态失败: {error_msg}")
                return False, error_msg

        except Exception as e:
            logger.error(f"[WX8059] 检查登录状态异常: {e}")
            return False, str(e)

    async def twice_login(self, wxid: str = "") -> str:
        """二次登录

        Args:
            wxid (str): 微信ID

        Returns:
            str: 登录结果信息

        Raises:
            Exception: 如果未提供wxid且未登录
        """
        if not wxid and not self.wxid:
            raise Exception("Please login using QRCode first")

        if not wxid and self.wxid:
            wxid = self.wxid

        try:
            data = {"wxid": wxid}
            response = await self._call_api("/login/WakeUpLogin", data)

            if response and response.get("Success"):
                result = response.get("Data", "")
                logger.info(f"[WX8059] 二次登录成功: wxid={wxid}")
                return result
            else:
                error_msg = response.get("Error", "二次登录失败")
                logger.error(f"[WX8059] 二次登录失败: {error_msg}")
                return ""

        except Exception as e:
            logger.error(f"[WX8059] 二次登录异常: {e}")
            return ""

    async def awaken_login(self, wxid: str = "") -> str:
        """唤醒登录

        Args:
            wxid (str): 微信ID (8059协议中此参数实际不使用)

        Returns:
            str: 登录UUID
        """
        try:
            # 8059协议的WakeUpLogin参数格式
            data = {
                "Check": False,
                "Proxy": ""
            }

            response = await self._call_api("/login/WakeUpLogin", data)

            if response and response.get("Code") == 200:
                uuid = response.get("Data", {}).get("UUID", "")
                logger.info(f"[WX8059] 唤醒登录成功: UUID={uuid}")
                return uuid
            else:
                error_msg = response.get("Text", "唤醒登录失败")
                logger.error(f"[WX8059] 唤醒登录失败: {error_msg}")
                return ""

        except Exception as e:
            logger.error(f"[WX8059] 唤醒登录异常: {e}")
            return ""

    def _print_qr_code(self, qr_url: str):
        """打印二维码到控制台"""
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(qr_url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            logger.info(f"[WX8059] 二维码URL: {qr_url}")
            logger.info("[WX8059] 安装qrcode库以显示二维码: pip install qrcode")
        except Exception as e:
            logger.warning(f"[WX8059] 打印二维码失败: {e}")
            logger.info(f"[WX8059] 二维码URL: {qr_url}")

    # 管理功能 - 基于8059协议/admin模块文档
    async def delay_auth_key(self, key: str, days: int = 30, expiry_date: str = "") -> dict:
        """授权码延期

        Args:
            key (str): 要延期的授权码
            days (int): 延期天数，默认30天
            expiry_date (str): 过期日期，可选

        Returns:
            dict: API响应结果
        """
        try:
            data = {
                "Days": days,
                "ExpiryDate": expiry_date,
                "Key": key
            }

            # 使用admin_key调用管理接口
            response = await self._call_api("/admin/DelayAuthKey", data, use_admin_key=True)

            if response and response.get("Success"):
                logger.info(f"[WX8059] 授权码延期成功: key={key}, days={days}")
                return response
            else:
                error_msg = response.get("Error", "授权码延期失败")
                logger.error(f"[WX8059] 授权码延期失败: {error_msg}")
                return response

        except Exception as e:
            logger.error(f"[WX8059] 授权码延期异常: {e}")
            return {"Success": False, "Error": str(e)}

    async def delete_auth_key(self, key: str, opt: int = 0) -> dict:
        """删除授权码

        Args:
            key (str): 要删除的授权码
            opt (int): 操作选项，默认0

        Returns:
            dict: API响应结果
        """
        try:
            data = {
                "Key": key,
                "Opt": opt
            }

            response = await self._call_api("/admin/DeleteAuthKey", data, use_admin_key=True)

            if response and response.get("Success"):
                logger.info(f"[WX8059] 授权码删除成功: key={key}")
                return response
            else:
                error_msg = response.get("Error", "授权码删除失败")
                logger.error(f"[WX8059] 授权码删除失败: {error_msg}")
                return response

        except Exception as e:
            logger.error(f"[WX8059] 授权码删除异常: {e}")
            return {"Success": False, "Error": str(e)}

    async def generate_auth_key(self, count: int = 1, days: int = 30) -> dict:
        """生成授权码(新设备) - 方式1

        Args:
            count (int): 生成数量，默认1
            days (int): 有效天数，默认30天

        Returns:
            dict: API响应结果，包含生成的授权码
        """
        try:
            data = {
                "Count": count,
                "Days": days
            }

            response = await self._call_api("/admin/GenAuthKey1", data, use_admin_key=True)

            if response and response.get("Success"):
                logger.info(f"[WX8059] 授权码生成成功: count={count}, days={days}")
                return response
            else:
                error_msg = response.get("Error", "授权码生成失败")
                logger.error(f"[WX8059] 授权码生成失败: {error_msg}")
                return response

        except Exception as e:
            logger.error(f"[WX8059] 授权码生成异常: {e}")
            return {"Success": False, "Error": str(e)}

    async def generate_auth_key_simple(self) -> dict:
        """生成授权码(新设备) - 方式2 (GET请求)

        Returns:
            dict: API响应结果，包含生成的授权码
        """
        try:
            # GET请求不需要body参数
            response = await self._call_api("/admin/GenAuthKey2", {}, use_admin_key=True, method="GET")

            # 8059协议返回格式: {"Code": 200, "Data": ["key"], "Text": "AuthKey生成成功"}
            if response and response.get("Code") == 200:
                logger.info(f"[WX8059] 授权码生成成功(简单方式)")

                # 提取生成的key
                data_list = response.get("Data", [])
                if data_list and len(data_list) > 0:
                    new_key = data_list[0]
                    # 转换为期望的格式
                    return {
                        "Success": True,
                        "Data": {
                            "Key": new_key
                        },
                        "Text": response.get("Text", "授权码生成成功")
                    }
                else:
                    logger.error(f"[WX8059] 授权码生成失败: 响应数据为空")
                    return {"Success": False, "Error": "响应数据为空"}
            else:
                error_msg = response.get("Text", "授权码生成失败")
                logger.error(f"[WX8059] 授权码生成失败: {error_msg}")
                return {"Success": False, "Error": error_msg}

        except Exception as e:
            logger.error(f"[WX8059] 授权码生成异常: {e}")
            return {"Success": False, "Error": str(e)}
