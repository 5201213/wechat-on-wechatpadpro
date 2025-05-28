from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class ToolMixin(WechatAPIClientBase):
    """8059协议工具相关功能混入类"""
    
    async def download_image(self, msg_id: int, from_user_name: str, to_user_name: str, 
                           total_len: int = 0, start_pos: int = 0, data_len: int = 61440, 
                           compress_type: int = 0) -> dict:
        """下载图片
        
        Args:
            msg_id (int): 消息ID
            from_user_name (str): 发送者
            to_user_name (str): 接收者
            total_len (int): 总长度
            start_pos (int): 开始位置
            data_len (int): 数据长度
            compress_type (int): 压缩类型
            
        Returns:
            dict: 下载结果
        """
        try:
            data = {
                "MsgId": msg_id,
                "FromUserName": from_user_name,
                "ToUserName": to_user_name,
                "TotalLen": total_len,
                "Section": {
                    "StartPos": start_pos,
                    "DataLen": data_len
                },
                "CompressType": compress_type
            }
            
            response = await self._call_api("/other/DownloadImage", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 下载图片成功: msg_id={msg_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "下载图片失败")
                logger.error(f"[WX8059] 下载图片失败: {error_msg}")
                raise ToolError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 下载图片异常: {e}")
            raise ToolError(f"下载图片失败: {e}")
    
    async def download_voice(self, new_msg_id: str, to_user_name: str, bufid: str, length: int) -> dict:
        """下载语音
        
        Args:
            new_msg_id (str): 新消息ID
            to_user_name (str): 接收者
            bufid (str): 缓冲ID
            length (int): 长度
            
        Returns:
            dict: 下载结果
        """
        try:
            data = {
                "NewMsgId": new_msg_id,
                "ToUserName": to_user_name,
                "Bufid": bufid,
                "Length": length
            }
            
            response = await self._call_api("/other/DownloadVoice", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 下载语音成功: {new_msg_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "下载语音失败")
                logger.error(f"[WX8059] 下载语音失败: {error_msg}")
                raise ToolError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 下载语音异常: {e}")
            raise ToolError(f"下载语音失败: {e}")
    
    async def download_media(self, url: str, key: str) -> dict:
        """下载媒体文件
        
        Args:
            url (str): 媒体URL
            key (str): 密钥
            
        Returns:
            dict: 下载结果
        """
        try:
            data = {
                "URL": url,
                "Key": key
            }
            
            response = await self._call_api("/other/DownloadMedia", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 下载媒体成功: {url}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "下载媒体失败")
                logger.error(f"[WX8059] 下载媒体失败: {error_msg}")
                raise ToolError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 下载媒体异常: {e}")
            raise ToolError(f"下载媒体失败: {e}")
    
    async def get_a8_key(self, req_url: str, op_code: int = 1, scene: int = 1) -> dict:
        """获取A8Key
        
        Args:
            req_url (str): 请求URL
            op_code (int): 操作码
            scene (int): 场景
            
        Returns:
            dict: A8Key信息
        """
        try:
            data = {
                "ReqUrl": req_url,
                "OpCode": op_code,
                "Scene": scene
            }
            
            response = await self._call_api("/other/GetA8Key", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 获取A8Key成功: {req_url}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取A8Key失败")
                logger.error(f"[WX8059] 获取A8Key失败: {error_msg}")
                raise ToolError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 获取A8Key异常: {e}")
            raise ToolError(f"获取A8Key失败: {e}")
    
    async def share_card(self, to_user_name: str, card_wxid: str, card_nickname: str, 
                        card_alias: str = "", card_flag: int = 0) -> bool:
        """分享名片
        
        Args:
            to_user_name (str): 接收者
            card_wxid (str): 名片微信ID
            card_nickname (str): 名片昵称
            card_alias (str): 名片别名
            card_flag (int): 名片标志
            
        Returns:
            bool: 分享是否成功
        """
        try:
            data = {
                "ToUserName": to_user_name,
                "CardWxId": card_wxid,
                "CardNickName": card_nickname,
                "CardAlias": card_alias,
                "CardFlag": card_flag
            }
            
            response = await self._call_api("/message/ShareCard", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 分享名片成功: {card_wxid} -> {to_user_name}")
                return True
            else:
                error_msg = response.get("Error", "分享名片失败")
                logger.error(f"[WX8059] 分享名片失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[WX8059] 分享名片异常: {e}")
            return False
    
    async def send_pat(self, to_user_name: str, chatroom_name: str = "", scene: int = 0) -> bool:
        """发送拍一拍
        
        Args:
            to_user_name (str): 接收者
            chatroom_name (str): 群聊名称
            scene (int): 场景
            
        Returns:
            bool: 发送是否成功
        """
        try:
            data = {
                "ToUserName": to_user_name,
                "ChatRoomName": chatroom_name,
                "Scene": scene
            }
            
            response = await self._call_api("/message/SendPat", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 发送拍一拍成功: {to_user_name}")
                return True
            else:
                error_msg = response.get("Error", "发送拍一拍失败")
                logger.error(f"[WX8059] 发送拍一拍失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[WX8059] 发送拍一拍异常: {e}")
            return False
