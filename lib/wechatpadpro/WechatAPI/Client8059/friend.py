from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class FriendMixin(WechatAPIClientBase):
    """8059协议朋友相关功能混入类"""

    async def get_friend_list(self) -> dict:
        """获取好友列表

        Returns:
            dict: 好友列表数据
        """
        try:
            response = await self._call_api("/friend/GetFriendList", method="GET")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取好友列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取好友列表失败")
                logger.error(f"[WX8059] 获取好友列表失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取好友列表异常: {e}")
            raise FriendError(f"获取好友列表失败: {e}")

    async def get_contact_list(self, current_wxcontact_seq: int = 0, current_chatroom_contact_seq: int = 0) -> dict:
        """获取全部联系人

        Args:
            current_wxcontact_seq (int): 当前微信联系人序列号
            current_chatroom_contact_seq (int): 当前群聊联系人序列号

        Returns:
            dict: 联系人列表数据
        """
        try:
            data = {
                "CurrentWxcontactSeq": current_wxcontact_seq,
                "CurrentChatRoomContactSeq": current_chatroom_contact_seq
            }

            response = await self._call_api("/friend/GetContactList", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取联系人列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取联系人列表失败")
                logger.error(f"[WX8059] 获取联系人列表失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取联系人列表异常: {e}")
            raise FriendError(f"获取联系人列表失败: {e}")

    async def search_contact(self, username: str, from_scene: int = 3, search_scene: int = 1, op_code: int = 1) -> dict:
        """搜索联系人

        Args:
            username (str): 要搜索的用户名/手机号/微信号
            from_scene (int): 来源场景
            search_scene (int): 搜索场景
            op_code (int): 操作类型

        Returns:
            dict: 搜索结果
        """
        try:
            data = {
                "UserName": username,
                "FromScene": from_scene,
                "SearchScene": search_scene,
                "OpCode": op_code
            }

            response = await self._call_api("/friend/SearchContact", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 搜索联系人成功: {username}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "搜索联系人失败")
                logger.error(f"[WX8059] 搜索联系人失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 搜索联系人异常: {e}")
            raise FriendError(f"搜索联系人失败: {e}")

    async def add_friend(self, username: str, verify_content: str = "", scene: int = 3, v3: str = "", v4: str = "", chatroom_username: str = "") -> bool:
        """添加好友

        Args:
            username (str): 用户名
            verify_content (str): 验证信息
            scene (int): 添加来源
            v3 (str): V3用户名数据
            v4 (str): V4校验数据
            chatroom_username (str): 群聊用户名

        Returns:
            bool: 添加是否成功
        """
        try:
            data = {
                "ChatRoomUserName": chatroom_username,
                "OpCode": 2,  # 添加好友/发送验证申请
                "Scene": scene,
                "V3": v3,
                "V4": v4,
                "VerifyContent": verify_content
            }

            response = await self._call_api("/friend/VerifyUser", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 添加好友成功: {username}")
                return True
            else:
                error_msg = response.get("Text", "添加好友失败")
                logger.error(f"[WX8059] 添加好友失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 添加好友异常: {e}")
            return False

    async def agree_friend_request(self, v3: str, v4: str, scene: int, chatroom_username: str = "", verify_content: str = "") -> bool:
        """同意好友请求

        Args:
            v3 (str): V3用户名数据
            v4 (str): V4校验数据
            scene (int): 场景值
            chatroom_username (str): 群聊用户名
            verify_content (str): 验证内容

        Returns:
            bool: 同意是否成功
        """
        try:
            data = {
                "ChatRoomUserName": chatroom_username,
                "OpCode": 2,  # 根据API文档，OpCode应该是2
                "Scene": scene,
                "V3": v3,
                "V4": v4,
                "VerifyContent": verify_content
            }

            response = await self._call_api("/friend/AgreeAdd", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 同意好友请求成功")
                return True
            else:
                error_msg = response.get("Text", "同意好友请求失败")
                logger.error(f"[WX8059] 同意好友请求失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 同意好友请求异常: {e}")
            return False

    async def delete_friend(self, username: str) -> bool:
        """删除好友

        Args:
            username (str): 要删除的好友用户名

        Returns:
            bool: 删除是否成功
        """
        try:
            data = {
                "DelUserName": username
            }

            response = await self._call_api("/friend/DelContact", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 删除好友成功: {username}")
                return True
            else:
                error_msg = response.get("Text", "删除好友失败")
                logger.error(f"[WX8059] 删除好友失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 删除好友异常: {e}")
            return False

    async def modify_remark(self, username: str, remark_name: str) -> bool:
        """修改好友备注

        Args:
            username (str): 好友用户名
            remark_name (str): 新备注名

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "UserName": username,
                "RemarkName": remark_name
            }

            response = await self._call_api("/friend/ModifyRemark", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 修改好友备注成功: {username} -> {remark_name}")
                return True
            else:
                error_msg = response.get("Text", "修改备注失败")
                logger.error(f"[WX8059] 修改好友备注失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 修改好友备注异常: {e}")
            return False

    async def get_contact_details_list(self, room_wxid_list: list = None, user_names: list = None) -> dict:
        """获取联系人详情

        Args:
            room_wxid_list (list): 群聊微信ID列表
            user_names (list): 用户名列表

        Returns:
            dict: 联系人详情数据
        """
        try:
            data = {
                "RoomWxIDList": room_wxid_list or [],
                "UserNames": user_names or []
            }

            response = await self._call_api("/friend/GetContactDetailsList", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取联系人详情成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取联系人详情失败")
                logger.error(f"[WX8059] 获取联系人详情失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取联系人详情异常: {e}")
            raise FriendError(f"获取联系人详情失败: {e}")

    async def get_friend_relation(self, username: str) -> dict:
        """获取好友关系

        Args:
            username (str): 用户名

        Returns:
            dict: 好友关系数据
        """
        try:
            data = {
                "UserName": username
            }

            response = await self._call_api("/friend/GetFriendRelation", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取好友关系成功: {username}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取好友关系失败")
                logger.error(f"[WX8059] 获取好友关系失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取好友关系异常: {e}")
            raise FriendError(f"获取好友关系失败: {e}")

    async def get_gh_list(self) -> dict:
        """获取关注的公众号列表

        Returns:
            dict: 公众号列表数据
        """
        try:
            response = await self._call_api("/friend/GetGHList", method="GET")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取公众号列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取公众号列表失败")
                logger.error(f"[WX8059] 获取公众号列表失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取公众号列表异常: {e}")
            raise FriendError(f"获取公众号列表失败: {e}")

    async def get_m_friend(self) -> dict:
        """获取手机通讯录好友

        Returns:
            dict: 手机通讯录好友数据
        """
        try:
            response = await self._call_api("/friend/GetMFriend", method="GET")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取手机通讯录好友成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取手机通讯录好友失败")
                logger.error(f"[WX8059] 获取手机通讯录好友失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取手机通讯录好友异常: {e}")
            raise FriendError(f"获取手机通讯录好友失败: {e}")

    async def get_group_list(self) -> dict:
        """获取保存的群聊列表

        Returns:
            dict: 群聊列表数据
        """
        try:
            response = await self._call_api("/friend/GroupList", method="GET")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取群聊列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群聊列表失败")
                logger.error(f"[WX8059] 获取群聊列表失败: {error_msg}")
                raise FriendError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群聊列表异常: {e}")
            raise FriendError(f"获取群聊列表失败: {e}")

    async def upload_m_contact(self, mobile: str = "", mobile_list: list = None) -> bool:
        """上传手机通讯录好友

        Args:
            mobile (str): 单个手机号
            mobile_list (list): 手机号列表

        Returns:
            bool: 上传是否成功
        """
        try:
            data = {
                "Mobile": mobile,
                "MobileList": mobile_list or []
            }

            response = await self._call_api("/friend/UploadMContact", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 上传手机通讯录好友成功")
                return True
            else:
                error_msg = response.get("Text", "上传手机通讯录好友失败")
                logger.error(f"[WX8059] 上传手机通讯录好友失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 上传手机通讯录好友异常: {e}")
            return False
