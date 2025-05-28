"""
8059协议保护机制模块
"""
import time
from typing import Dict, Any
from loguru import logger

class Protector:
    """8059协议保护机制类"""
    
    def __init__(self):
        self.login_status = {}
        self.last_activity = {}
        self.protection_enabled = True
    
    def update_login_status(self, device_id: str = "", wxid: str = ""):
        """更新登录状态"""
        key = device_id or wxid or "default"
        self.login_status[key] = {
            "logged_in": True,
            "login_time": time.time(),
            "device_id": device_id,
            "wxid": wxid
        }
        logger.debug(f"[WX8059] 更新登录状态: {key}")
    
    def update_activity(self, device_id: str = "", wxid: str = ""):
        """更新活动时间"""
        key = device_id or wxid or "default"
        self.last_activity[key] = time.time()
    
    def is_logged_in(self, device_id: str = "", wxid: str = "") -> bool:
        """检查是否已登录"""
        key = device_id or wxid or "default"
        return self.login_status.get(key, {}).get("logged_in", False)
    
    def get_login_info(self, device_id: str = "", wxid: str = "") -> Dict[str, Any]:
        """获取登录信息"""
        key = device_id or wxid or "default"
        return self.login_status.get(key, {})
    
    def clear_login_status(self, device_id: str = "", wxid: str = ""):
        """清除登录状态"""
        key = device_id or wxid or "default"
        if key in self.login_status:
            del self.login_status[key]
        if key in self.last_activity:
            del self.last_activity[key]
        logger.debug(f"[WX8059] 清除登录状态: {key}")
    
    def enable_protection(self):
        """启用保护机制"""
        self.protection_enabled = True
        logger.info("[WX8059] 启用保护机制")
    
    def disable_protection(self):
        """禁用保护机制"""
        self.protection_enabled = False
        logger.info("[WX8059] 禁用保护机制")
    
    def is_protection_enabled(self) -> bool:
        """检查保护机制是否启用"""
        return self.protection_enabled

# 全局保护器实例
protector = Protector()
