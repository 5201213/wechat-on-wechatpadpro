from .base import WechatAPIClientBase
from ..errors import *
from loguru import logger

class HongBaoMixin(WechatAPIClientBase):
    """8059协议红包相关功能混入类"""
    
    async def send_red_packet(self, username: str, amount: int, count: int = 1, 
                             content: str = "恭喜发财", red_type: int = 0, from_type: int = 1) -> dict:
        """发送红包
        
        Args:
            username (str): 接收者微信ID或群ID
            amount (int): 每个红包金额(单位为分)
            count (int): 红包个数
            content (str): 红包祝福语
            red_type (int): 红包类型 (0:普通红包 1:拼手气红包)
            from_type (int): 红包来源 (0:群红包 1:个人红包)
            
        Returns:
            dict: 发送结果
        """
        try:
            data = {
                "Username": username,
                "Amount": amount,
                "Count": count,
                "Content": content,
                "RedType": red_type,
                "From": from_type
            }
            
            response = await self._call_api("/pay/SendRedPacket", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 发送红包成功: {username}, 金额: {amount}分")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "发送红包失败")
                logger.error(f"[WX8059] 发送红包失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 发送红包异常: {e}")
            raise PaymentError(f"发送红包失败: {e}")
    
    async def open_red_packet(self, native_url: str) -> dict:
        """打开红包
        
        Args:
            native_url (str): 红包原生URL
            
        Returns:
            dict: 打开结果
        """
        try:
            data = {
                "NativeUrl": native_url
            }
            
            response = await self._call_api("/pay/OpenRedEnvelopes", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 打开红包成功: {native_url}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "打开红包失败")
                logger.error(f"[WX8059] 打开红包失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 打开红包异常: {e}")
            raise PaymentError(f"打开红包失败: {e}")
    
    async def get_red_packet_list(self, limit: int = 10, offset: int = 0, native_url: str = "") -> dict:
        """获取红包列表
        
        Args:
            limit (int): 限制数量
            offset (int): 偏移量
            native_url (str): 原生URL
            
        Returns:
            dict: 红包列表
        """
        try:
            data = {
                "Limit": limit,
                "Offset": offset,
                "NativeURL": native_url,
                "HongBaoItem": {}
            }
            
            response = await self._call_api("/pay/GetRedPacketList", data)
            
            if response and response.get("Success"):
                logger.debug("[WX8059] 获取红包列表成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "获取红包列表失败")
                logger.error(f"[WX8059] 获取红包列表失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 获取红包列表异常: {e}")
            raise PaymentError(f"获取红包列表失败: {e}")
    
    async def create_transfer(self, to_user_name: str, fee: int, description: str = "") -> dict:
        """创建转账
        
        Args:
            to_user_name (str): 接收者微信ID
            fee (int): 转账金额(单位为分)
            description (str): 转账备注
            
        Returns:
            dict: 创建结果，包含ReqKey
        """
        try:
            data = {
                "ToUserName": to_user_name,
                "Fee": fee,
                "Description": description
            }
            
            response = await self._call_api("/pay/CreatePreTransfer", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 创建转账成功: {to_user_name}, 金额: {fee}分")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "创建转账失败")
                logger.error(f"[WX8059] 创建转账失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 创建转账异常: {e}")
            raise PaymentError(f"创建转账失败: {e}")
    
    async def confirm_transfer(self, req_key: str, pay_password: str, bank_type: str = "", bank_serial: str = "") -> dict:
        """确认转账
        
        Args:
            req_key (str): 创建转账返回的ReqKey
            pay_password (str): 支付密码
            bank_type (str): 付款方式类型
            bank_serial (str): 付款方式序列号
            
        Returns:
            dict: 确认结果
        """
        try:
            data = {
                "ReqKey": req_key,
                "PayPassword": pay_password,
                "BankType": bank_type,
                "BankSerial": bank_serial
            }
            
            response = await self._call_api("/pay/ConfirmPreTransfer", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 确认转账成功: {req_key}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "确认转账失败")
                logger.error(f"[WX8059] 确认转账失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 确认转账异常: {e}")
            raise PaymentError(f"确认转账失败: {e}")
    
    async def generate_pay_qr_code(self, money: str, name: str = "") -> dict:
        """生成收款二维码
        
        Args:
            money (str): 金额(单位为分)，如"999"表示9.99元
            name (str): 收款备注
            
        Returns:
            dict: 二维码信息
        """
        try:
            data = {
                "Money": money,
                "Name": name
            }
            
            response = await self._call_api("/pay/GeneratePayQCode", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 生成收款码成功: {money}分")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "生成收款码失败")
                logger.error(f"[WX8059] 生成收款码失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 生成收款码异常: {e}")
            raise PaymentError(f"生成收款码失败: {e}")
    
    async def collect_money(self, to_user_name: str, transfer_id: str, transaction_id: str, invalid_time: str = "") -> dict:
        """收款
        
        Args:
            to_user_name (str): 付款方微信ID
            transfer_id (str): 转账ID
            transaction_id (str): 交易ID
            invalid_time (str): 失效时间
            
        Returns:
            dict: 收款结果
        """
        try:
            data = {
                "ToUserName": to_user_name,
                "TransFerId": transfer_id,
                "TransactionId": transaction_id,
                "InvalidTime": invalid_time
            }
            
            response = await self._call_api("/pay/CollectMoney", data)
            
            if response and response.get("Success"):
                logger.debug(f"[WX8059] 收款成功: {transfer_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Error", "收款失败")
                logger.error(f"[WX8059] 收款失败: {error_msg}")
                raise PaymentError(error_msg)
                
        except Exception as e:
            logger.error(f"[WX8059] 收款异常: {e}")
            raise PaymentError(f"收款失败: {e}")
