from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class PyqMixin(WechatAPIClientBase):
    """8059协议朋友圈相关功能混入类"""
    
    async def get_pyq_list(self, wxid: str = None, max_id: int = 0) -> dict:
        """获取朋友圈首页列表
        
        Args:
            wxid (str, optional): 用户wxid
            max_id (int, optional): 朋友圈ID，用于分页获取
            
        Returns:
            dict: 朋友圈列表数据
        """
        if not self.wxid and not wxid:
            raise UserLoggedOut("请先登录")
        
        if not wxid:
            wxid = self.wxid
        
        try:
            data = {
                "UserName": wxid,
                "MaxID": max_id,
                "FirstPageMD5": ""
            }
            
            response = await self._call_api("/sns/GetSnsInfo", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 获取朋友圈列表成功: {wxid}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取朋友圈列表失败")
                logger.error(f"[WX8059] 获取朋友圈列表失败: {error_msg}")
                raise SnsError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 获取朋友圈列表异常: {e}")
            raise SnsError(f"获取朋友圈列表失败: {e}")
    
    async def send_sns_comment(self, to_user_name: str, item_id: str, content: str, 
                              op_type: int = 1, reply_comment_id: int = 0, create_time: int = 0) -> bool:
        """发送朋友圈评论
        
        Args:
            to_user_name (str): 好友微信ID
            item_id (str): 朋友圈项ID
            content (str): 评论内容
            op_type (int): 操作类型 (1:评论 2:点赞)
            reply_comment_id (int): 回复的评论ID
            create_time (int): 创建时间
            
        Returns:
            bool: 发送是否成功
        """
        try:
            data = {
                "SnsCommentList": [{
                    "ToUserName": to_user_name,
                    "ItemID": item_id,
                    "Content": content,
                    "OpType": op_type,
                    "ReplyCommentID": reply_comment_id,
                    "CreateTime": create_time,
                    "ReplyItem": None
                }],
                "Tx": False
            }
            
            response = await self._call_api("/sns/SendSnsComment", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 发送朋友圈评论成功: {item_id}")
                return True
            else:
                error_msg = response.get("Error", "发送朋友圈评论失败")
                logger.error(f"[WX8059] 发送朋友圈评论失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[WX8059] 发送朋友圈评论异常: {e}")
            return False
    
    async def like_sns_object(self, to_user_name: str, item_id: str, op_type: int = 1) -> bool:
        """点赞朋友圈
        
        Args:
            to_user_name (str): 好友微信ID
            item_id (str): 朋友圈项ID
            op_type (int): 操作类型 (1:点赞 0:取消点赞)
            
        Returns:
            bool: 操作是否成功
        """
        try:
            data = {
                "SnsObjectOpList": [{
                    "ToUserName": to_user_name,
                    "ItemID": item_id,
                    "OpType": op_type
                }]
            }
            
            response = await self._call_api("/sns/SendSnsObjectOp", data)
            
            if response and response.get("Success"):
                action = "点赞" if op_type == 1 else "取消点赞"
                logger.debug(f"[WX8059] {action}朋友圈成功: {item_id}")
                return True
            else:
                error_msg = response.get("Error", "操作朋友圈失败")
                logger.error(f"[WX8059] 操作朋友圈失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[WX8059] 操作朋友圈异常: {e}")
            return False
    
    async def upload_friend_circle(self, content: str = "", image_list: list = None, 
                                  video_list: list = None, black_list: list = None,
                                  location: dict = None) -> dict:
        """发布朋友圈
        
        Args:
            content (str): 朋友圈文字内容
            image_list (list): 图片列表 (base64编码)
            video_list (list): 视频列表 (base64编码)
            black_list (list): 不可见用户列表
            location (dict): 位置信息
            
        Returns:
            dict: 发布结果
        """
        try:
            data = {
                "Content": content,
                "ImageDataList": image_list or [],
                "VideoDataList": video_list or [],
                "BlackList": black_list or [],
                "Location": location or {},
                "LocationVal": 0
            }
            
            response = await self._call_api("/sns/UploadFriendCircle", data)
            
            if response and response.get("Success"):
                logger.debug("[WX8059] 发布朋友圈成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "发布朋友圈失败")
                logger.error(f"[WX8059] 发布朋友圈失败: {error_msg}")
                raise SnsError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 发布朋友圈异常: {e}")
            raise SnsError(f"发布朋友圈失败: {e}")
    
    async def send_fav_item_circle(self, fav_item_id: int, source_id: str = "", 
                                  black_list: list = None, location: dict = None) -> dict:
        """发送收藏到朋友圈
        
        Args:
            fav_item_id (int): 收藏项ID
            source_id (str): 来源ID
            black_list (list): 不可见用户列表
            location (dict): 位置信息
            
        Returns:
            dict: 发送结果
        """
        try:
            data = {
                "FavItemID": fav_item_id,
                "SourceID": source_id,
                "BlackList": black_list or [],
                "Location": location or {},
                "LocationVal": 0
            }
            
            response = await self._call_api("/sns/SendFavItemCircle", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 发送收藏到朋友圈成功: {fav_item_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "发送收藏到朋友圈失败")
                logger.error(f"[WX8059] 发送收藏到朋友圈失败: {error_msg}")
                raise SnsError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 发送收藏到朋友圈异常: {e}")
            raise SnsError(f"发送收藏到朋友圈失败: {e}")
    
    async def set_friend_circle_days(self, function: int, value: int) -> bool:
        """设置朋友圈可见天数
        
        Args:
            function (int): 功能类型
            value (int): 天数值
            
        Returns:
            bool: 设置是否成功
        """
        try:
            data = {
                "Function": function,
                "Value": value
            }
            
            response = await self._call_api("/user/SetFriendCircleDays", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 设置朋友圈可见天数成功: {value}天")
                return True
            else:
                error_msg = response.get("Error", "设置朋友圈可见天数失败")
                logger.error(f"[WX8059] 设置朋友圈可见天数失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[WX8059] 设置朋友圈可见天数异常: {e}")
            return False
