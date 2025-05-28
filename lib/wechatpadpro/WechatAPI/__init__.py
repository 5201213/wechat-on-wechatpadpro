# 直接导入8059协议客户端，移除Server模块依赖
from WechatAPI.errors import *
from WechatAPI.Client8059 import WechatAPIClient8059

# 为了兼容性，将WechatAPIClient8059也导出为WechatAPIClient
WechatAPIClient = WechatAPIClient8059

# 导出主要类和函数
__all__ = [
    'WechatAPIClient8059',
    'WechatAPIClient',
    # 从errors模块导出的异常类会自动包含
]

__name__ = "WechatAPI"
__version__ = "1.0.0"
__description__ = "Wechat API for XYBot - 8059 Protocol Only"
__author__ = "HenryXiaoYang"