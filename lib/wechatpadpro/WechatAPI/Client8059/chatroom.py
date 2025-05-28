from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class ChatroomMixin(WechatAPIClientBase):
    """8059协议群聊相关功能混入类"""

    async def create_chatroom(self, user_list: list, topic: str = "") -> dict:
        """创建群聊

        Args:
            user_list (list): 用户列表
            topic (str): 群聊主题

        Returns:
            dict: 创建结果
        """
        try:
            data = {
                "UserList": user_list,
                "TopIc": topic
            }

            response = await self._call_api("/group/CreateChatRoom", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 创建群聊成功: {topic}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "创建群聊失败")
                logger.error(f"[WX8059] 创建群聊失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 创建群聊异常: {e}")
            raise ChatroomError(f"创建群聊失败: {e}")

    async def get_chatroom_member_list(self, chatroom_name: str) -> dict:
        """获取群成员列表

        Args:
            chatroom_name (str): 群聊ID

        Returns:
            dict: 群成员列表
        """
        try:
            data = {
                "ChatRoomName": chatroom_name
            }

            response = await self._call_api("/group/GetChatroomMemberDetail", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取群成员列表成功: {chatroom_name}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群成员列表失败")
                logger.error(f"[WX8059] 获取群成员列表失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群成员列表异常: {e}")
            raise ChatroomError(f"获取群成员列表失败: {e}")

    async def invite_chatroom_members(self, chatroom_name: str, user_list: list) -> bool:
        """邀请群成员

        Args:
            chatroom_name (str): 群聊ID
            user_list (list): 要邀请的用户列表

        Returns:
            bool: 邀请是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "UserList": user_list
            }

            response = await self._call_api("/group/InviteChatroomMembers", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 邀请群成员成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "邀请群成员失败")
                logger.error(f"[WX8059] 邀请群成员失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 邀请群成员异常: {e}")
            return False

    async def remove_chatroom_members(self, chatroom_name: str, user_list: list) -> bool:
        """移除群成员

        Args:
            chatroom_name (str): 群聊ID
            user_list (list): 要移除的用户列表

        Returns:
            bool: 移除是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "UserList": user_list
            }

            response = await self._call_api("/group/SendDelDelChatRoomMember", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 移除群成员成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "移除群成员失败")
                logger.error(f"[WX8059] 移除群成员失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 移除群成员异常: {e}")
            return False

    async def modify_chatroom_name(self, chatroom_name: str, nickname: str) -> bool:
        """设置群昵称

        Args:
            chatroom_name (str): 群聊ID
            nickname (str): 新昵称

        Returns:
            bool: 修改是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "Nickname": nickname
            }

            response = await self._call_api("/group/SetChatroomName", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置群昵称成功: {chatroom_name} -> {nickname}")
                return True
            else:
                error_msg = response.get("Text", "设置群昵称失败")
                logger.error(f"[WX8059] 设置群昵称失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置群昵称异常: {e}")
            return False

    async def get_chatroom_qr_code(self, chatroom_name: str) -> dict:
        """获取群二维码

        Args:
            chatroom_name (str): 群聊ID

        Returns:
            dict: 二维码信息
        """
        try:
            data = {
                "ChatRoomName": chatroom_name
            }

            response = await self._call_api("/group/GetChatroomQrCode", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取群二维码成功: {chatroom_name}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群二维码失败")
                logger.error(f"[WX8059] 获取群二维码失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群二维码异常: {e}")
            raise ChatroomError(f"获取群二维码失败: {e}")

    async def set_chatroom_access_verify(self, chatroom_name: str, enable: bool) -> bool:
        """设置群聊入群验证

        Args:
            chatroom_name (str): 群聊ID
            enable (bool): 是否启用验证

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "Enable": enable
            }

            response = await self._call_api("/group/SetChatroomAccessVerify", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置群验证成功: {chatroom_name}, enable={enable}")
                return True
            else:
                error_msg = response.get("Text", "设置群验证失败")
                logger.error(f"[WX8059] 设置群验证失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置群验证异常: {e}")
            return False

    async def quit_chatroom(self, chatroom_name: str) -> bool:
        """退出群聊

        Args:
            chatroom_name (str): 群聊ID

        Returns:
            bool: 退出是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name
            }

            response = await self._call_api("/group/QuitChatroom", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 退出群聊成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "退出群聊失败")
                logger.error(f"[WX8059] 退出群聊失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 退出群聊异常: {e}")
            return False

    async def add_chatroom_members(self, chatroom_name: str, user_list: list) -> bool:
        """添加群成员

        Args:
            chatroom_name (str): 群聊ID
            user_list (list): 要添加的用户列表

        Returns:
            bool: 添加是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "UserList": user_list
            }

            response = await self._call_api("/group/AddChatRoomMembers", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 添加群成员成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "添加群成员失败")
                logger.error(f"[WX8059] 添加群成员失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 添加群成员异常: {e}")
            return False

    async def add_chatroom_admin(self, chatroom_name: str, user_list: list) -> bool:
        """添加群管理员

        Args:
            chatroom_name (str): 群聊ID
            user_list (list): 要设为管理员的用户列表

        Returns:
            bool: 添加是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "UserList": user_list
            }

            response = await self._call_api("/group/AddChatroomAdmin", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 添加群管理员成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "添加群管理员失败")
                logger.error(f"[WX8059] 添加群管理员失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 添加群管理员异常: {e}")
            return False

    async def del_chatroom_admin(self, chatroom_name: str, user_list: list) -> bool:
        """删除群管理员

        Args:
            chatroom_name (str): 群聊ID
            user_list (list): 要取消管理员的用户列表

        Returns:
            bool: 删除是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "UserList": user_list
            }

            response = await self._call_api("/group/DelChatroomAdmin", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 删除群管理员成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "删除群管理员失败")
                logger.error(f"[WX8059] 删除群管理员失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 删除群管理员异常: {e}")
            return False

    async def get_chatroom_info(self, chatroom_wxid_list: list) -> dict:
        """获取群详情

        Args:
            chatroom_wxid_list (list): 群聊微信ID列表

        Returns:
            dict: 群详情数据
        """
        try:
            data = {
                "ChatRoomWxIdList": chatroom_wxid_list
            }

            response = await self._call_api("/group/GetChatRoomInfo", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取群详情成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群详情失败")
                logger.error(f"[WX8059] 获取群详情失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群详情异常: {e}")
            raise ChatroomError(f"获取群详情失败: {e}")

    async def get_group_list(self) -> dict:
        """获取群列表

        Returns:
            dict: 群列表数据
        """
        try:
            response = await self._call_api("/group/GroupList", method="GET")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 获取群列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群列表失败")
                logger.error(f"[WX8059] 获取群列表失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群列表异常: {e}")
            raise ChatroomError(f"获取群列表失败: {e}")

    async def move_to_contract(self, chatroom_name: str, val: int) -> bool:
        """获取群聊

        Args:
            chatroom_name (str): 群聊ID
            val (int): 值

        Returns:
            bool: 操作是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "Val": val
            }

            response = await self._call_api("/group/MoveToContract", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取群聊成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "获取群聊失败")
                logger.error(f"[WX8059] 获取群聊失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 获取群聊异常: {e}")
            return False

    async def scan_into_url_group(self, url: str) -> bool:
        """扫码入群

        Args:
            url (str): 群二维码URL

        Returns:
            bool: 入群是否成功
        """
        try:
            data = {
                "Url": url
            }

            response = await self._call_api("/group/ScanIntoUrlGroup", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 扫码入群成功: {url}")
                return True
            else:
                error_msg = response.get("Text", "扫码入群失败")
                logger.error(f"[WX8059] 扫码入群失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 扫码入群异常: {e}")
            return False

    async def send_pat(self, chatroom_name: str, to_username: str, scene: int = 0) -> bool:
        """群拍一拍功能

        Args:
            chatroom_name (str): 群聊ID
            to_username (str): 目标用户名
            scene (int): 场景值

        Returns:
            bool: 拍一拍是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "Scene": scene,
                "ToUserName": to_username
            }

            response = await self._call_api("/group/SendPat", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 群拍一拍成功: {chatroom_name} -> {to_username}")
                return True
            else:
                error_msg = response.get("Text", "群拍一拍失败")
                logger.error(f"[WX8059] 群拍一拍失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 群拍一拍异常: {e}")
            return False

    async def transfer_group_owner(self, chatroom_name: str, new_owner_username: str) -> bool:
        """转让群

        Args:
            chatroom_name (str): 群聊ID
            new_owner_username (str): 新群主用户名

        Returns:
            bool: 转让是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "NewOwnerUserName": new_owner_username
            }

            response = await self._call_api("/group/SendTransferGroupOwner", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 转让群成功: {chatroom_name} -> {new_owner_username}")
                return True
            else:
                error_msg = response.get("Text", "转让群失败")
                logger.error(f"[WX8059] 转让群失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 转让群异常: {e}")
            return False

    async def set_chatroom_announcement(self, chatroom_name: str, content: str) -> bool:
        """设置群公告

        Args:
            chatroom_name (str): 群聊ID
            content (str): 公告内容

        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "ChatRoomName": chatroom_name,
                "Content": content
            }

            response = await self._call_api("/group/SetChatroomAnnouncement", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 设置群公告成功: {chatroom_name}")
                return True
            else:
                error_msg = response.get("Text", "设置群公告失败")
                logger.error(f"[WX8059] 设置群公告失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 设置群公告异常: {e}")
            return False

    async def get_chatroom_info_detail(self, chatroom_name: str) -> dict:
        """获取群公告

        Args:
            chatroom_name (str): 群聊ID

        Returns:
            dict: 群公告详情
        """
        try:
            data = {
                "ChatRoomName": chatroom_name
            }

            response = await self._call_api("/group/SetGetChatRoomInfoDetail", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取群公告成功: {chatroom_name}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取群公告失败")
                logger.error(f"[WX8059] 获取群公告失败: {error_msg}")
                raise ChatroomError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取群公告异常: {e}")
            raise ChatroomError(f"获取群公告失败: {e}")
