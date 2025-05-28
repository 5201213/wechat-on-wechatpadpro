from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class UserMixin(WechatAPIClientBase):
    """8059协议用户相关功能混入类"""

    async def get_user_info(self) -> dict:
        """获取用户信息

        Returns:
            dict: 用户信息
        """
        try:
            response = await self._call_api("/user/GetProfile", method="GET")

            if response and response.get("Code") == 200:
                data = response.get("Data", {})
                user_info = data.get("userInfo", {})
                user_info_ext = data.get("userInfoExt", {})

                # 解析嵌套的用户信息结构
                parsed_user_data = {
                    "wxid": user_info.get("userName", {}).get("str", ""),
                    "nickname": user_info.get("nickName", {}).get("str", ""),
                    "sex": user_info.get("sex", 0),
                    "province": user_info.get("province", ""),
                    "city": user_info.get("city", ""),
                    "country": user_info.get("country", ""),
                    "signature": user_info.get("signature", ""),
                    "alias": user_info.get("alias", ""),
                    "avatar": user_info_ext.get("bigHeadImgUrl", ""),
                    "small_avatar": user_info_ext.get("smallHeadImgUrl", ""),
                    "level": user_info.get("level", 0),
                    "experience": user_info.get("experience", 0),
                    "point": user_info.get("point", 0)
                }

                logger.debug(f"[WX8059] 获取用户信息成功: {parsed_user_data}")
                return parsed_user_data
            else:
                error_msg = response.get("Text", "获取用户信息失败") if response else "无响应"
                logger.error(f"[WX8059] 获取用户信息失败: {error_msg}")
                raise UserError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取用户信息异常: {e}")
            raise UserError(f"获取用户信息失败: {e}")

    async def update_nickname(self, nickname: str, scene: int = 0) -> bool:
        """修改昵称

        Args:
            nickname (str): 新昵称
            scene (int): 场景值

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "Scene": scene,
                "Val": nickname
            }

            response = await self._call_api("/user/UpdateNickName", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 修改昵称成功: {nickname}")
                self.nickname = nickname
                return True
            else:
                error_msg = response.get("Text", "修改昵称失败")
                logger.error(f"[WX8059] 修改昵称失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改昵称异常: {e}")
            return False

    async def set_signature(self, signature: str, scene: int = 0) -> bool:
        """设置个性签名

        Args:
            signature (str): 个性签名
            scene (int): 场景值

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Scene": scene,
                "Val": signature
            }

            response = await self._call_api("/user/SetSignature", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置签名成功: {signature}")
                return True
            else:
                error_msg = response.get("Text", "设置签名失败")
                logger.error(f"[WX8059] 设置签名失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置签名异常: {e}")
            return False

    async def upload_head_image(self, image_base64: str) -> bool:
        """上传头像

        Args:
            image_base64 (str): 头像图片的base64编码

        Returns:
            bool: 上传是否成功
        """
        try:
            data = {
                "Base64": image_base64
            }

            response = await self._call_api("/user/UploadHeadImage", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 上传头像成功")
                return True
            else:
                error_msg = response.get("Text", "上传头像失败")
                logger.error(f"[WX8059] 上传头像失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 上传头像异常: {e}")
            return False

    async def get_qr_code(self, style: int = 8, recover: bool = False) -> dict:
        """获取个人二维码

        Args:
            style (int): 二维码样式
            recover (bool): 是否恢复

        Returns:
            dict: 二维码信息
        """
        try:
            data = {
                "Style": style,
                "Recover": recover
            }

            response = await self._call_api("/user/GetMyQrCode", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取个人二维码成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取二维码失败")
                logger.error(f"[WX8059] 获取个人二维码失败: {error_msg}")
                raise UserError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取个人二维码异常: {e}")
            raise UserError(f"获取个人二维码失败: {e}")

    async def set_wechat_id(self, wechat_id: str) -> bool:
        """设置微信号

        Args:
            wechat_id (str): 微信号

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Alisa": wechat_id
            }

            response = await self._call_api("/user/SetWechat", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置微信号成功: {wechat_id}")
                return True
            else:
                error_msg = response.get("Text", "设置微信号失败")
                logger.error(f"[WX8059] 设置微信号失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置微信号异常: {e}")
            return False

    async def modify_sex(self, sex: int, city: str = "", country: str = "", province: str = "") -> bool:
        """修改性别

        Args:
            sex (int): 性别 (1:男, 2:女)
            city (str): 城市
            country (str): 国家
            province (str): 省份

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "City": city,
                "Country": country,
                "Province": province,
                "Sex": sex
            }

            response = await self._call_api("/user/SetSexDq", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 修改性别成功: {sex}")
                return True
            else:
                error_msg = response.get("Text", "修改性别失败")
                logger.error(f"[WX8059] 修改性别失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改性别异常: {e}")
            return False

    async def set_proxy(self, proxy: str, check: bool = False) -> bool:
        """设置代理

        Args:
            proxy (str): 代理地址
            check (bool): 是否检测代理

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Proxy": proxy,
                "Check": check
            }

            response = await self._call_api("/user/SetProxy", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置代理成功: {proxy}")
                return True
            else:
                error_msg = response.get("Text", "设置代理失败")
                logger.error(f"[WX8059] 设置代理失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置代理异常: {e}")
            return False

    async def change_password(self, old_password: str, new_password: str, op_code: int = 0) -> bool:
        """更改密码

        Args:
            old_password (str): 旧密码
            new_password (str): 新密码
            op_code (int): 操作码

        Returns:
            bool: 更改是否成功
        """
        try:
            data = {
                "NewPass": new_password,
                "OldPass": old_password,  # 修正字段名，移除逗号
                "OpCode": op_code
            }

            response = await self._call_api("/user/ChangePwd", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 更改密码成功")
                return True
            else:
                error_msg = response.get("Text", "更改密码失败")
                logger.error(f"[WX8059] 更改密码失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 更改密码异常: {e}")
            return False

    async def modify_remark(self, username: str, remark_name: str) -> bool:
        """修改备注

        Args:
            username (str): 用户名
            remark_name (str): 备注名

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "RemarkName": remark_name,
                "UserName": username
            }

            response = await self._call_api("/user/ModifyRemark", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 修改备注成功: {username} -> {remark_name}")
                return True
            else:
                error_msg = response.get("Text", "修改备注失败")
                logger.error(f"[WX8059] 修改备注失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改备注异常: {e}")
            return False

    async def modify_user_info(self, nickname: str = "", signature: str = "", sex: int = 0,
                              city: str = "", country: str = "", province: str = "", init_flag: int = 0) -> bool:
        """修改资料

        Args:
            nickname (str): 昵称
            signature (str): 签名
            sex (int): 性别
            city (str): 城市
            country (str): 国家
            province (str): 省份
            init_flag (int): 初始化标志

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "City": city,
                "Country": country,
                "InitFlag": init_flag,
                "NickName": nickname,
                "Province": province,
                "Sex": sex,
                "Signature": signature
            }

            response = await self._call_api("/user/ModifyUserInfo", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 修改资料成功")
                return True
            else:
                error_msg = response.get("Text", "修改资料失败")
                logger.error(f"[WX8059] 修改资料失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改资料异常: {e}")
            return False

    async def set_function_switch(self, function: int, value: int) -> bool:
        """设置添加我的方式

        Args:
            function (int): 功能类型
            value (int): 值

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Function": function,
                "Value": value
            }

            response = await self._call_api("/user/SetFunctionSwitch", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置添加方式成功: function={function}, value={value}")
                return True
            else:
                error_msg = response.get("Text", "设置添加方式失败")
                logger.error(f"[WX8059] 设置添加方式失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置添加方式异常: {e}")
            return False

    async def set_nickname(self, nickname: str, scene: int = 0) -> bool:
        """设置昵称

        Args:
            nickname (str): 昵称
            scene (int): 场景值

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Scene": scene,
                "Val": nickname
            }

            response = await self._call_api("/user/SetNickName", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置昵称成功: {nickname}")
                return True
            else:
                error_msg = response.get("Text", "设置昵称失败")
                logger.error(f"[WX8059] 设置昵称失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置昵称异常: {e}")
            return False

    async def set_send_pat(self, value: str) -> bool:
        """设置拍一拍名称

        Args:
            value (str): 拍一拍名称

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Value": value
            }

            response = await self._call_api("/user/SetSendPat", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置拍一拍名称成功: {value}")
                return True
            else:
                error_msg = response.get("Text", "设置拍一拍名称失败")
                logger.error(f"[WX8059] 设置拍一拍名称失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置拍一拍名称异常: {e}")
            return False

    async def update_auto_pass(self, switch_type: int) -> bool:
        """修改加好友需要验证属性

        Args:
            switch_type (int): 开关类型

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "SwitchType": switch_type
            }

            response = await self._call_api("/user/UpdateAutoPass", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 修改加好友验证属性成功: {switch_type}")
                return True
            else:
                error_msg = response.get("Text", "修改加好友验证属性失败")
                logger.error(f"[WX8059] 修改加好友验证属性失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改加好友验证属性异常: {e}")
            return False

    # 兼容性别名方法
    async def get_profile(self) -> dict:
        """获取用户资料 (get_user_info的别名方法，用于兼容wx849通道)

        Returns:
            dict: 用户信息，格式兼容wx849通道期望的结构
        """
        try:
            user_info = await self.get_user_info()

            # 转换为wx849通道期望的格式
            profile_data = {
                "userInfo": {
                    "userName": {"str": user_info.get("wxid", "")},
                    "nickName": {"str": user_info.get("nickname", "")},
                    "sex": user_info.get("sex", 0),
                    "province": user_info.get("province", ""),
                    "city": user_info.get("city", ""),
                    "country": user_info.get("country", ""),
                    "signature": user_info.get("signature", ""),
                    "alias": user_info.get("alias", ""),
                    "level": user_info.get("level", 0),
                    "experience": user_info.get("experience", 0),
                    "point": user_info.get("point", 0)
                },
                "userInfoExt": {
                    "bigHeadImgUrl": user_info.get("avatar", ""),
                    "smallHeadImgUrl": user_info.get("small_avatar", "")
                }
            }

            logger.debug(f"[WX8059] get_profile别名方法调用成功")
            return profile_data

        except Exception as e:
            logger.error(f"[WX8059] get_profile别名方法异常: {e}")
            raise UserError(f"获取用户资料失败: {e}")
