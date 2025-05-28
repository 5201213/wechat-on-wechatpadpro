import asyncio
import os
import re
import json
import time
import threading
import io
import sys
import traceback
import xml.etree.ElementTree as ET
import cv2
import aiohttp
import uuid
from typing import Union, BinaryIO, Optional, Tuple, List, Dict
import urllib.parse
import requests
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.chat_message import ChatMessage
from channel.wechatpadpro.wechatpadpro_message import WechatPadProMessage
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from common.utils import remove_markdown_symbol, split_string_by_utf8_length
from config import conf, get_appdata_dir
from voice.audio_convert import split_audio # Added for voice splitting
from common.tmp_dir import TmpDir # Added for temporary file management
from plugins import PluginManager, EventContext, Event
# 新增HTTP服务器相关导入
from aiohttp import web
from pathlib import Path
import base64
import subprocess
import math
import time  # 添加time导入用于SILK文件命名
import functools

# 8059协议专用版本，不再需要pysilk

# 增大日志行长度限制，以便完整显示XML内容
try:
    import logging
    # 尝试设置日志格式化器的最大长度限制
    for handler in logging.getLogger().handlers:
        if hasattr(handler, 'formatter'):
            handler.formatter._fmt = handler.formatter._fmt.replace('%(message)s', '%(message).10000s')
    logger.info("[WechatPadPro] 已增大日志输出长度限制")
except Exception as e:
    logger.warning(f"[WechatPadPro] 设置日志长度限制失败: {e}")

# 添加 wechatpadpro 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# 修改路径查找逻辑，确保能找到正确的 lib/wechatpadpro 目录
# 尝试多种可能的路径
possible_lib_dirs = [
    # 尝试相对项目根目录路径
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), "lib", "wechatpadpro"),
    # 尝试当前目录的上一级
    os.path.join(os.path.dirname(os.path.dirname(current_dir)), "lib", "wechatpadpro"),
    # 尝试当前目录的上上级
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))), "lib", "wechatpadpro"),
    # 尝试绝对路径（Windows兼容写法）
    os.path.join(os.path.abspath(os.sep), "root", "dow-849", "lib", "wechatpadpro")
]

# 尝试所有可能的路径
lib_dir = None
for possible_dir in possible_lib_dirs:
    if os.path.exists(possible_dir):
        lib_dir = possible_dir
        break

# 打印路径信息以便调试
logger.info(f"WechatAPI 模块搜索路径尝试列表: {possible_lib_dirs}")
logger.info(f"最终选择的WechatAPI模块路径: {lib_dir}")

if lib_dir and os.path.exists(lib_dir):
    if lib_dir not in sys.path:
        sys.path.append(lib_dir)
    # 直接添加 WechatAPI 目录到路径
    wechat_api_dir = os.path.join(lib_dir, "WechatAPI")
    if os.path.exists(wechat_api_dir) and wechat_api_dir not in sys.path:
        sys.path.append(wechat_api_dir)
    logger.info(f"已添加 WechatAPI 模块路径: {lib_dir}")
    logger.info(f"Python 搜索路径: {sys.path}")
else:
    logger.error(f"WechatAPI 模块路径不存在，尝试的所有路径均不可用")

# 导入 WechatAPI 客户端 - 简化版，只支持8059协议
try:
    # 确保 lib_dir 路径已添加到 sys.path
    if lib_dir and os.path.exists(lib_dir) and lib_dir not in sys.path:
        sys.path.append(lib_dir)
        logger.info(f"[WechatPadPro] 已添加 WechatAPI 模块路径: {lib_dir}")

    # 直接导入 WechatAPI 模块和8059协议客户端
    import WechatAPI
    from WechatAPI import WechatAPIClient8059
    logger.info("[WechatPadPro] 成功导入 WechatAPI 模块和8059协议客户端")

    # 设置 WechatAPI 的 loguru 日志级别
    try:
        from loguru import logger as api_logger
        import logging

        # 移除所有现有处理器
        api_logger.remove()

        # 获取配置的日志级别，默认为 ERROR 以减少输出
        log_level = conf().get("log_level", "ERROR")

        # 添加新的处理器，仅输出 ERROR 级别以上的日志
        api_logger.add(sys.stderr, level=log_level)
        logger.info(f"[WechatPadPro] 已设置 WechatAPI 日志级别为: {log_level}")
    except Exception as e:
        logger.error(f"[WechatPadPro] 设置 WechatAPI 日志级别时出错: {e}")

except Exception as e:
    logger.error(f"[WechatPadPro] 导入 WechatAPI 模块失败: {e}")

    # 打印调试信息
    logger.error(f"[WechatPadPro] 当前Python路径: {sys.path}")
    if lib_dir and os.path.exists(lib_dir):
        logger.info(f"[WechatPadPro] lib_dir 目录内容: {os.listdir(lib_dir)}")
        wechat_api_dir = os.path.join(lib_dir, "WechatAPI")
        if os.path.exists(wechat_api_dir):
            logger.info(f"[WechatPadPro] WechatAPI 目录内容: {os.listdir(wechat_api_dir)}")

    # 打印堆栈信息
    import traceback
    logger.error(f"[WechatPadPro] 详细错误信息: {traceback.format_exc()}")

    raise ImportError(f"[WechatPadPro] 无法导入 WechatAPI 模块，请确保 wechatpadpro 目录已正确配置: {e}")

# 添加 ContextType.PAT 类型（如果不存在）
if not hasattr(ContextType, 'PAT'):
    setattr(ContextType, 'PAT', 'PAT')
if not hasattr(ContextType, 'QUOTE'):
    setattr(ContextType, 'QUOTE', 'QUOTE')
# 添加 ContextType.UNKNOWN 类型（如果不存在）
if not hasattr(ContextType, 'UNKNOWN'):
    setattr(ContextType, 'UNKNOWN', 'UNKNOWN')
# 添加 ContextType.XML 类型（如果不存在）
if not hasattr(ContextType, 'XML'):
    setattr(ContextType, 'XML', 'XML')
    logger.info("[WechatPadPro] 已添加 ContextType.XML 类型")
# 添加其他可能使用的ContextType类型
if not hasattr(ContextType, 'LINK'):
    setattr(ContextType, 'LINK', 'LINK')
    logger.info("[WechatPadPro] 已添加 ContextType.LINK 类型")
if not hasattr(ContextType, 'FILE'):
    setattr(ContextType, 'FILE', 'FILE')
    logger.info("[WechatPadPro] 已添加 ContextType.FILE 类型")
if not hasattr(ContextType, 'MINIAPP'):
    setattr(ContextType, 'MINIAPP', 'MINIAPP')
    logger.info("[WechatPadPro] 已添加 ContextType.MINIAPP 类型")
if not hasattr(ContextType, 'SYSTEM'):
    setattr(ContextType, 'SYSTEM', 'SYSTEM')
    logger.info("[WechatPadPro] 已添加 ContextType.SYSTEM 类型")
if not hasattr(ContextType, 'VIDEO'):
    setattr(ContextType, 'VIDEO', 'VIDEO')
    logger.info("[WechatPadPro] 已添加 ContextType.VIDEO 类型")

# 导入cv2（OpenCV）用于处理视频
try:
    import cv2
    logger.info("[WechatPadPro] 成功导入OpenCV(cv2)模块")
except ImportError:
    logger.warning("[WechatPadPro] 未安装OpenCV(cv2)模块，视频处理功能将受限")
    cv2 = None

def _find_ffmpeg_path():
    """Finds the ffmpeg executable path."""
    ffmpeg_cmd = "ffmpeg" # Default command
    if os.name == 'nt': # Windows
        possible_paths = [
            r"D:\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            * [os.path.join(p, "ffmpeg.exe") for p in os.environ.get("PATH", "").split(os.pathsep) if p]
        ]
        for path in possible_paths:
            if os.path.exists(path):
                ffmpeg_cmd = path
                logger.debug(f"[WechatPadPro] Found ffmpeg at: {ffmpeg_cmd}")
                return ffmpeg_cmd
        logger.warning("[WechatPadPro] ffmpeg not found in common Windows paths or PATH, will try system PATH with 'ffmpeg'.")
        return "ffmpeg"
    else: # Linux/macOS
        import shutil
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            logger.debug(f"[WechatPadPro] Found ffmpeg at: {ffmpeg_path}")
            return ffmpeg_path
        else:
            logger.warning("[WechatPadPro] ffmpeg not found using shutil.which. Will try system PATH with 'ffmpeg'.")
            return "ffmpeg"

def _check(func):
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(self, cmsg: ChatMessage):
            msgId = cmsg.msg_id
            if not msgId:
                msgId = f"msg_{int(time.time())}_{hash(str(cmsg.msg))}"
                logger.debug(f"[WechatPadPro] _check: 为空消息ID生成唯一ID: {msgId}")

            if msgId in self.received_msgs:
                logger.debug(f"[WechatPadPro] 消息 {msgId} 已处理过，忽略")
                return

            self.received_msgs[msgId] = True

            create_time = cmsg.create_time
            current_time = int(time.time())
            timeout = 60
            if int(create_time) < current_time - timeout:
                logger.debug(f"[WechatPadPro] 历史消息 {msgId} 已跳过，时间差: {current_time - int(create_time)}秒")
                return
            return await func(self, cmsg)
        return wrapper
    else:
        @functools.wraps(func)
        def wrapper(self, cmsg: ChatMessage):
            msgId = cmsg.msg_id
            if not msgId:
                msgId = f"msg_{int(time.time())}_{hash(str(cmsg.msg))}"
                logger.debug(f"[WechatPadPro] _check: 为空消息ID生成唯一ID: {msgId}")

            if msgId in self.received_msgs:
                logger.debug(f"[WechatPadPro] 消息 {msgId} 已处理过，忽略")
                return

            self.received_msgs[msgId] = True

            create_time = cmsg.create_time
            current_time = int(time.time())
            timeout = 60
            if int(create_time) < current_time - timeout:
                logger.debug(f"[WechatPadPro] 历史消息 {msgId} 已跳过，时间差: {current_time - int(create_time)}秒")
                return
            return func(self, cmsg)
        return wrapper

@singleton
class WechatPadProChannel(ChatChannel):
    """
    WechatPadPro channel - 微信iPad协议通道实现
    """
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.received_msgs = ExpiredDict(conf().get("expires_in_seconds", 3600))
        self.recent_image_msgs = ExpiredDict(conf().get("image_expires_in_seconds", 7200)) # Added initialization
        self.bot = None
        self.user_id = None
        self.name = None
        self.wxid = None
        self.is_running = False
        self.is_logged_in = False
        self.group_name_cache = {}
        self.image_cache_dir = os.path.join(os.getcwd(), "tmp", "wechatpadpro_img_cache")
        try:
            if not os.path.exists(self.image_cache_dir):
                os.makedirs(self.image_cache_dir, exist_ok=True)
                logger.info(f"[{self.name}] Created image cache directory: {self.image_cache_dir}")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to create image cache directory {self.image_cache_dir}: {e}")

    def _cleanup_cached_images(self):
        """Cleans up expired image files from the cache directory."""
        import glob
        if not hasattr(self, 'image_cache_dir') or not self.image_cache_dir:
            logger.debug(f"[{self.name}] Image cache directory not configured. Skipping cleanup.")
            return

        logger.info(f"[{self.name}] Starting image cache cleanup in {self.image_cache_dir}...")
        try:
            # 检查目录是否存在
            if not os.path.exists(self.image_cache_dir):
                logger.info(f"[{self.name}] Image cache directory does not exist, creating: {self.image_cache_dir}")
                os.makedirs(self.image_cache_dir, exist_ok=True)
                logger.info(f"[{self.name}] Image cache cleanup finished (directory was empty).")
                return

            current_time = time.time()
            max_age_seconds = 7 * 24 * 60 * 60  # Cache images for 7 days
            total_cleaned_count = 0
            total_size_cleaned = 0

            # Iterate over common image extensions used for caching
            # Ensure this matches extensions used during caching (see phase A3)
            for ext_pattern in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
                pattern = os.path.join(self.image_cache_dir, ext_pattern)
                cleaned_count = 0
                pattern_size_cleaned = 0

                try:
                    files = glob.glob(pattern)
                    for fpath in files:
                        try:
                            if os.path.isfile(fpath): # Ensure it's a file
                                mtime = os.path.getmtime(fpath)
                                if current_time - mtime > max_age_seconds:
                                    file_size = os.path.getsize(fpath)
                                    os.remove(fpath)
                                    cleaned_count += 1
                                    pattern_size_cleaned += file_size
                                    logger.debug(f"[{self.name}] Cleaned up expired cached image: {fpath} (Age: {(current_time - mtime)/3600/24:.1f} days)")
                        except Exception as e:
                            logger.warning(f"[{self.name}] Failed to process/delete cached image {fpath}: {e}")

                    if cleaned_count > 0:
                        logger.info(f"[{self.name}] Cleaned up {cleaned_count} '{ext_pattern}' images, freed {pattern_size_cleaned/1024/1024:.2f} MB.")

                    total_cleaned_count += cleaned_count
                    total_size_cleaned += pattern_size_cleaned

                except Exception as e:
                    logger.warning(f"[{self.name}] Failed to process pattern {ext_pattern}: {e}")

            if total_cleaned_count > 0:
                logger.info(f"[{self.name}] Image cache cleanup finished. Total: {total_cleaned_count} files, {total_size_cleaned/1024/1024:.2f} MB freed.")
            else:
                logger.info(f"[{self.name}] Image cache cleanup finished. No expired files found.")
        except Exception as e:
            logger.error(f"[{self.name}] Image cache cleanup task encountered an error: {e}")
            import traceback
            logger.debug(f"[{self.name}] Cleanup error details: {traceback.format_exc()}")

    def _start_image_cache_cleanup_task(self):
        """Starts the periodic image cache cleanup task."""
        if not hasattr(self, 'image_cache_dir'): # Don't start if cache isn't configured
            return

        def _cleanup_loop():
            logger.info(f"[{self.name}] Image cache cleanup thread started.")
            try:
                # 立即执行一次清理，不要延迟
                logger.info(f"[{self.name}] 执行初始图片缓存清理...")
                self._cleanup_cached_images()
                logger.info(f"[{self.name}] 初始图片缓存清理完成，开始定期清理循环")

                while True:
                    try:
                        # Sleep for a longer interval, e.g., 6 hours or 24 hours
                        cleanup_interval_hours = 24
                        logger.debug(f"[{self.name}] Image cache cleanup task sleeping for {cleanup_interval_hours} hours.")
                        time.sleep(cleanup_interval_hours * 60 * 60)

                        # 执行定期清理
                        self._cleanup_cached_images()
                    except Exception as e:
                        logger.error(f"[{self.name}] Image cache cleanup loop error: {e}. Retrying in 1 hour.")
                        time.sleep(60 * 60) # Wait an hour before retrying the loop on major error
            except Exception as e:
                logger.error(f"[{self.name}] Image cache cleanup thread failed to start: {e}")

        cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
        cleanup_thread.name = "WechatPadProImageCacheCleanupThread"
        cleanup_thread.start()
        logger.info(f"[{self.name}] Image cache cleanup task scheduled.")

    async def _initialize_bot(self):
        """初始化 bot"""
        logger.info("[WechatPadPro] 正在初始化 bot...")

        # 配置验证：确保使用8059协议
        protocol_version = conf().get("wechatpadpro_protocol_version", "8059")
        if protocol_version != "8059":
            logger.warning(f"[WechatPadPro] 配置验证失败：不支持的协议版本 '{protocol_version}'")
            logger.warning(f"[WechatPadPro] 此版本仅支持8059协议，已自动切换到8059协议")
            logger.warning(f"[WechatPadPro] 请在配置文件中设置 'wechatpadpro_protocol_version': '8059'")
            protocol_version = "8059"

        logger.info(f"[WechatPadPro] 使用协议版本: {protocol_version}")

        # 验证配置完整性
        api_host = conf().get("wechatpadpro_api_host", "127.0.0.1")
        api_port = conf().get("wechatpadpro_api_port", 8059)  # 8059协议默认端口
        api_key = conf().get("wechatpadpro_api_key", "")  # TOKEN_KEY - 普通API调用
        admin_key = conf().get("wechatpadpro_admin_key", "")  # ADMIN_KEY - 管理功能

        logger.info(f"[WechatPadPro] 配置检查完成:")
        logger.info(f"[WechatPadPro] - API服务器: {api_host}:{api_port}")
        logger.info(f"[WechatPadPro] - TOKEN_KEY: {'已配置' if api_key else '未配置'}")
        logger.info(f"[WechatPadPro] - ADMIN_KEY: {'已配置' if admin_key else '未配置'}")

        # 初始化WechatAPI客户端 - 只支持8059协议
        try:
            # 8059协议客户端
            self.bot = WechatAPIClient8059(api_host, api_port, api_key, admin_key)
            logger.info(f"[WechatPadPro] 成功创建8059协议客户端: {api_host}:{api_port}")
            logger.info("成功加载8059协议客户端")

            # 设置8059协议特有属性
            self.bot.ignore_protect = True
            logger.info("[WechatPadPro] 已设置8059客户端忽略风控保护")

            # 验证配置
            if not api_key:
                logger.warning("[WechatPadPro8059] 未设置wechatpadpro_api_key (TOKEN_KEY)，部分功能可能无法使用")
            if not admin_key:
                logger.warning("[WechatPadPro8059] 未设置wechatpadpro_admin_key (ADMIN_KEY)，管理功能将无法使用")

        except Exception as e:
            logger.error(f"[WechatPadPro] 初始化WechatAPI客户端失败: {e}")
            return False

        # 添加客户端状态检查
        logger.info(f"[WechatPadPro] 客户端初始化完成:")
        logger.info(f"[WechatPadPro] - 客户端类型: {type(self.bot).__name__}")
        logger.info(f"[WechatPadPro] - 客户端wxid: {getattr(self.bot, 'wxid', 'N/A')}")
        logger.info(f"[WechatPadPro] - 可用方法: {[method for method in dir(self.bot) if 'message' in method.lower() or 'sync' in method.lower()]}")
        logger.info(f"[WechatPadPro] - API路径前缀: {getattr(self.bot, 'api_path_prefix', 'N/A')}")
        logger.info(f"[WechatPadPro] - ignore_protect: {getattr(self.bot, 'ignore_protect', 'N/A')}")
        logger.info(f"[WechatPadPro] - ignore_protection: {getattr(self.bot, 'ignore_protection', 'N/A')}")

        # 等待 WechatAPI 服务启动
        service_ok = await self._check_api_service(api_host, api_port)
        if not service_ok:
            logger.error("[WechatPadPro] WechatAPI 服务连接失败")
            return False

        # 开始登录流程
        logger.info("[WechatPadPro] 开始登录流程")

        # 获取配置的key
        api_key = conf().get("wechatpadpro_api_key", "")  # 普通key
        admin_key = conf().get("wechatpadpro_admin_key", "")  # 管理key

        logger.info(f"[WechatPadPro] 登录配置检查: 普通key={'已配置' if api_key else '未配置'}, 管理key={'已配置' if admin_key else '未配置'}")

        # 场景1: 有普通key
        if api_key:
            logger.info("[WechatPadPro] 场景1: 检测到普通key，检查在线状态")

            # 1.1 检查是否在线
            try:
                # 使用GetLoginStatus接口检查在线状态
                response = await self._call_api("/login/GetLoginStatus", {}, method="GET")
                if response and response.get("Code") == 200:
                    login_data = response.get("Data", {})
                    login_state = login_data.get("loginState", 0)
                    if login_state == 1:  # 1表示在线
                        # 尝试从多个可能的字段获取wxid
                        current_wxid = (login_data.get("wxid", "") or
                                      login_data.get("userName", "") or
                                      login_data.get("userInfo", {}).get("userName", {}).get("str", ""))

                        if current_wxid:
                            logger.info(f"[WechatPadPro] 用户已在线: {current_wxid}")
                            self._set_logged_in_state(current_wxid)
                            return True
                        else:
                            # 用户在线但没有wxid，尝试通过bot对象的get_user_info方法获取用户信息
                            logger.info(f"[WechatPadPro] 用户在线但响应中无wxid，尝试获取用户信息")
                            try:
                                # 使用bot对象的get_user_info方法
                                user_info = await self.bot.get_user_info()
                                if user_info and isinstance(user_info, dict):
                                    current_wxid = user_info.get("wxid", "")
                                    if current_wxid:
                                        logger.info(f"[WechatPadPro] 通过用户信息接口获取到wxid: {current_wxid}")
                                        self._set_logged_in_state(current_wxid)
                                        return True
                                    else:
                                        logger.warning(f"[WechatPadPro] 用户信息中也无法获取wxid，响应: {user_info}")
                                else:
                                    logger.warning(f"[WechatPadPro] 获取用户信息失败，响应: {user_info}")
                            except Exception as user_info_e:
                                logger.error(f"[WechatPadPro] 获取用户信息异常: {user_info_e}")

                            # 如果用户在线但无法获取wxid，这可能是API的问题，但不应该阻止登录
                            # 我们可以使用一个临时的标识符
                            logger.warning(f"[WechatPadPro] 用户在线但无法获取wxid，使用临时标识符")
                            temp_wxid = f"temp_user_{int(time.time())}"
                            logger.info(f"[WechatPadPro] 使用临时wxid: {temp_wxid}")
                            self._set_logged_in_state(temp_wxid)
                            return True
                    else:
                        logger.info(f"[WechatPadPro] 用户不在线，登录状态: {login_state}，尝试唤醒登录")
                else:
                    logger.warning(f"[WechatPadPro] 无法获取登录状态，响应: {response}，尝试唤醒登录")
            except Exception as e:
                logger.error(f"[WechatPadPro] 检查在线状态失败: {e}，尝试唤醒登录")

            # 1.2 尝试唤醒登录
            try:
                logger.info("[WechatPadPro] 尝试唤醒登录")
                # 调用WakeUpLogin接口
                response = await self._call_api("/login/WakeUpLogin", {"Check": False, "Proxy": ""})
                if response and response.get("Code") == 200:
                    uuid = response.get("Data", {}).get("UUID", "")
                    if uuid:
                        logger.info(f"[WechatPadPro] 唤醒登录成功，UUID: {uuid}")
                        # 等待用户在手机上确认
                        confirmation_success = await self._wait_for_login_confirmation(uuid, "")
                        if confirmation_success:
                            # 再次检查登录状态获取wxid
                            try:
                                response = await self._call_api("/login/GetLoginStatus", {}, method="GET")
                                if response and response.get("Code") == 200:
                                    login_data = response.get("Data", {})
                                    current_wxid = (login_data.get("wxid", "") or
                                                  login_data.get("userName", "") or
                                                  login_data.get("userInfo", {}).get("userName", {}).get("str", ""))
                                    if current_wxid:
                                        logger.info(f"[WechatPadPro] 唤醒登录完成: {current_wxid}")
                                        self._set_logged_in_state(current_wxid)
                                        return True
                                    else:
                                        logger.warning(f"[WechatPadPro] 登录状态响应中没有wxid字段，响应数据: {login_data}")
                                else:
                                    logger.warning(f"[WechatPadPro] 获取登录状态失败，响应: {response}")
                            except Exception as status_e:
                                logger.error(f"[WechatPadPro] 获取登录状态异常: {status_e}")

                            logger.error("[WechatPadPro] 唤醒登录确认成功但无法获取用户信息")
                        else:
                            logger.warning("[WechatPadPro] 唤醒登录确认失败")
                    else:
                        logger.warning("[WechatPadPro] 唤醒登录响应中没有UUID")
                else:
                    error_msg = response.get("Text", "唤醒登录失败") if response else "无响应"
                    logger.warning(f"[WechatPadPro] 唤醒登录失败: {error_msg}")
            except Exception as e:
                logger.error(f"[WechatPadPro] 唤醒登录异常: {e}")

            # 1.3 唤醒登录失败，进入二维码登录
            logger.info("[WechatPadPro] 唤醒登录失败，使用二维码登录")

        # 场景2: 没有普通key，有管理key
        elif admin_key:
            logger.info("[WechatPadPro] 场景2: 检测到管理key，获取普通key")
            try:
                # 使用管理key获取普通key
                result = await self.bot.generate_auth_key_simple()
                if result and result.get("Success"):
                    new_token = result.get("Data", {}).get("Key", "")
                    if new_token:
                        logger.info(f"[WechatPadPro] 成功获取普通key: {new_token[:10]}...")

                        # 更新配置
                        conf().set("wechatpadpro_api_key", new_token)
                        try:
                            from config import save_config
                            save_config()
                            logger.info(f"[WechatPadPro] 已保存新的普通key到配置文件")
                        except Exception as e:
                            logger.warning(f"[WechatPadPro] 保存配置文件失败: {e}")

                        # 更新bot对象的key
                        if hasattr(self.bot, 'key'):
                            self.bot.key = new_token
                            logger.info(f"[WechatPadPro] 已更新bot.key")

                        # 使用新获取的普通key进行二维码登录
                        logger.info("[WechatPadPro] 使用新获取的普通key进行二维码登录")
                    else:
                        logger.error("[WechatPadPro] 管理key获取的普通key为空")
                        return False
                else:
                    error_msg = result.get("Error", "未知错误") if result else "无响应"
                    logger.error(f"[WechatPadPro] 使用管理key获取普通key失败: {error_msg}")
                    return False
            except Exception as e:
                logger.error(f"[WechatPadPro] 使用管理key获取普通key异常: {e}")
                return False

        # 场景3: 都没有配置
        else:
            logger.error("[WechatPadPro] 未配置普通key或管理key，无法进行登录")
            return False

        # 进行二维码登录
        return await self._qr_code_login()

    async def _qr_code_login(self):
        """二维码登录流程"""
        logger.info("[WechatPadPro] 开始二维码登录")

        # 生成device_name和device_id
        device_name = "WechatPadPro机器人"
        device_id = ""

        if hasattr(self.bot, "create_device_name"):
            device_name = self.bot.create_device_name()

        if hasattr(self.bot, "create_device_id"):
            device_id = self.bot.create_device_id()

        # 获取登录二维码
        try:
            session_key, qr_url = await self.bot.get_qr_code(device_name=device_name, device_id=device_id, print_qr=True)
            if qr_url:
                logger.info(f"[WechatPadPro] 请使用微信扫描以上二维码或以下链接登录:")
                logger.info(f"[WechatPadPro] {qr_url}")
            else:
                logger.error(f"[WechatPadPro] 未能获取到二维码链接")
                return False
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[WechatPadPro] 获取登录二维码失败: {e}")

            # 检查是否是"该链接已绑定微信号"错误
            if "该链接已绑定微信号" in error_msg or "Code: -3" in error_msg:
                logger.info("[WechatPadPro] 检测到链接已绑定微信号，尝试检查在线状态")
                try:
                    response = await self._call_api("/login/GetLoginStatus", {}, method="GET")
                    if response and response.get("Code") == 200:
                        login_data = response.get("Data", {})
                        login_state = login_data.get("loginState", 0)
                        if login_state == 1:  # 1表示在线
                            current_wxid = login_data.get("wxid", "") or login_data.get("userName", "")
                            if current_wxid:
                                logger.info(f"[WechatPadPro] 检测到已登录用户: {current_wxid}")
                                self._set_logged_in_state(current_wxid)
                                return True
                except Exception as check_e:
                    logger.error(f"[WechatPadPro] 检查在线状态失败: {check_e}")

                logger.error("[WechatPadPro] 链接已绑定但无法确认在线状态，请手动检查微信登录状态")
                return False

            # 其他错误直接返回失败
            return False

        # 等待扫码并登录
        login_success, new_wxid = await self._wait_for_qr_login(session_key, device_id, device_name)
        return login_success

    async def _check_api_service(self, api_host, api_port):
        """检查API服务是否可用"""
        logger.info(f"尝试连接到 WechatAPI 服务 (地址: {api_host}:{api_port})")

        time_out = 30
        is_connected = False

        while not is_connected and time_out > 0:
            try:
                # 尝试使用bot对象的is_running方法
                if hasattr(self.bot, "is_running") and await self.bot.is_running():
                    is_connected = True
                    logger.info("[WechatPadPro] API服务已通过is_running方法确认可用")
                    break

                # 如果bot对象的方法失败，尝试直接发送HTTP请求检查服务是否可用
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    try:
                        # 尝试访问根路径，不使用API路径前缀
                        url = f"http://{api_host}:{api_port}/"
                        logger.debug(f"尝试连接根路径: {url}")
                        async with session.get(url, timeout=5) as response:
                            if response.status in [200, 401, 403, 404]:  # 任何HTTP响应都表示服务在运行
                                is_connected = True
                                logger.info("[WechatPadPro] 通过根路径确认服务可用")
                                break
                    except Exception as e:
                        logger.debug(f"根路径请求失败: {e}")

                        # 如果根路径失败，尝试访问常见的API路径
                        for test_path in ["/api", "/VXAPI"]:
                            try:
                                url = f"http://{api_host}:{api_port}{test_path}/"
                                logger.debug(f"尝试连接API路径: {url}")
                                async with session.get(url, timeout=5) as response:
                                    if response.status in [200, 401, 403, 404]:
                                        is_connected = True
                                        logger.info(f"[WechatPadPro] 通过API路径{test_path}确认服务可用")
                                        break
                            except Exception as e2:
                                logger.debug(f"API路径{test_path}请求失败: {e2}")

                        if is_connected:
                            break
            except Exception as e:
                logger.debug(f"连接尝试失败: {e}")

            logger.info("等待 WechatAPI 启动中")
            await asyncio.sleep(2)
            time_out -= 2

        return is_connected

    async def _wait_for_qr_login(self, uuid, device_id, device_name):
        """等待扫码登录完成"""
        login_timeout = 120
        logger.info(f"[WechatPadPro] 开始等待用户扫码登录，超时时间: {login_timeout}秒")
        logger.info(f"[WechatPadPro] 请使用微信扫描上方二维码完成登录")

        check_interval = 3  # 每3秒检查一次
        while login_timeout > 0:
            try:
                logger.debug(f"[WechatPadPro] 检查登录状态，剩余 {login_timeout} 秒...")

                # 直接检查登录状态，而不是检查二维码状态
                response = await self._call_api("/login/GetLoginStatus", {}, method="GET")

                if response and response.get("Code") == 200:
                    login_data = response.get("Data", {})
                    login_state = login_data.get("loginState", 0)

                    if login_state == 1:  # 1表示在线，说明用户已经扫码登录成功
                        logger.info("[WechatPadPro] 检测到用户已扫码登录成功！")

                        # 尝试获取用户信息
                        try:
                            user_info = await self.bot.get_user_info()
                            if user_info and isinstance(user_info, dict):
                                new_wxid = user_info.get("wxid", "")
                                new_name = user_info.get("nickname", "")

                                if new_wxid:
                                    logger.info(f"[WechatPadPro] 扫码登录成功，获取到用户信息: wxid={new_wxid}, 昵称={new_name}")

                                    # 设置登录状态
                                    self._set_logged_in_state(new_wxid)

                                    # 设置昵称（如果有的话）
                                    if new_name:
                                        self.name = new_name
                                        logger.info(f"[WechatPadPro] 二维码登录获取到昵称: {new_name}")

                                    logger.info(f"[WechatPadPro] 二维码登录完成: user_id={self.user_id}, nickname={self.name}")
                                    return True, new_wxid
                                else:
                                    logger.warning("[WechatPadPro] 登录成功但无法获取wxid，使用临时标识符")
                                    temp_wxid = f"temp_user_{int(time.time())}"
                                    self._set_logged_in_state(temp_wxid)
                                    return True, temp_wxid
                            else:
                                logger.warning("[WechatPadPro] 登录成功但无法获取用户信息")
                                temp_wxid = f"temp_user_{int(time.time())}"
                                self._set_logged_in_state(temp_wxid)
                                return True, temp_wxid
                        except Exception as user_e:
                            logger.error(f"[WechatPadPro] 获取用户信息失败: {user_e}")
                            temp_wxid = f"temp_user_{int(time.time())}"
                            self._set_logged_in_state(temp_wxid)
                            return True, temp_wxid
                    else:
                        # 用户还没有扫码登录，继续等待
                        login_msg = login_data.get("loginErrMsg", "等待扫码登录")
                        logger.debug(f"[WechatPadPro] 登录状态: {login_msg}")
                else:
                    logger.debug(f"[WechatPadPro] 获取登录状态失败，响应: {response}")

            except Exception as e:
                logger.error(f"[WechatPadPro] 检查扫码登录状态出错: {e}")

            # 等待指定间隔后再次检查
            await asyncio.sleep(check_interval)
            login_timeout -= check_interval

        logger.error("[WechatPadPro] 扫码登录超时，用户可能未完成扫码")
        return False, ""

    async def _check_login_status(self, wxid):
        """检查是否已经登录"""
        try:
            logger.info(f"[WechatPadPro] 正在检查用户 {wxid} 的登录状态")

            # 使用8059协议的登录状态检查
            params = {
                "wxid": wxid,  # 参数名应该为小写的wxid
                "Wxid": wxid   # 同时提供大写参数，增加兼容性
            }

            logger.debug(f"[WechatPadPro] 心跳接口参数: {params}")

            # 调用心跳接口 - 8059协议使用登录状态检查 (GET请求)
            response = await self._call_api("/login/GetLoginStatus", {}, method="GET")

            # 打印响应内容以便调试
            logger.debug(f"[WechatPadPro] 心跳接口响应: {response}")

            # 检查响应 - 8059协议格式
            if response and response.get("Code") == 200:
                login_data = response.get("Data", {})
                login_state = login_data.get("loginState", 0)
                if login_state == 1:  # 1表示在线
                    logger.info(f"[WechatPadPro] 心跳检测成功: {wxid} 在线")
                    return True
                else:
                    login_msg = login_data.get("loginErrMsg", "账号不在线")
                    logger.warning(f"[WechatPadPro] 心跳检测失败: {login_msg}")
                    logger.warning(f"[WechatPadPro] 心跳检测失败，{wxid}不在登录状态")
                    return False
            else:
                error_code = response.get("Code", 0) if response else 0
                error_msg = response.get("Text", "未知错误") if response else "无响应"
                logger.warning(f"[WechatPadPro] 心跳检测失败，错误码: {error_code}, 错误信息: {error_msg}")
                logger.warning(f"[WechatPadPro] 心跳检测失败，{wxid}不在登录状态")
                return False
        except Exception as e:
            logger.error(f"[WechatPadPro] 检查登录状态失败: {e}")
            import traceback
            logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
            return False

    async def _awaken_login(self, key):
        """尝试唤醒登录 - 8059协议只需要传递key"""
        try:
            logger.info(f"[WechatPadPro] 尝试唤醒登录，使用key: {key[:10]}...")

            # 8059协议的唤醒登录只需要key参数
            response = await self.bot.awaken_login(key)

            if response:
                logger.info(f"[WechatPadPro] 唤醒登录成功，获取到UUID: {response}")
                return response
            else:
                logger.warning(f"[WechatPadPro] 唤醒登录失败，未获取到UUID")
                return None
        except Exception as e:
            logger.error(f"[WechatPadPro] 唤醒登录失败: {e}")
            return None

    async def _auto_login(self, saved_wxid, saved_device_id, saved_device_name):
        """8059协议自动登录流程"""
        if not saved_wxid:
            logger.info("[WechatPadPro] 无保存的微信ID，无法执行自动登录")
            return False

        logger.info(f"[WechatPadPro] 开始8059协议自动登录流程: wxid={saved_wxid}")

        # 获取配置的key
        api_key = conf().get("wechatpadpro_api_key", "")  # 普通key (TOKEN_KEY)
        admin_key = conf().get("wechatpadpro_admin_key", "")  # 管理key (ADMIN_KEY)

        logger.info(f"[WechatPadPro] 登录配置检查: 普通key={'已配置' if api_key else '未配置'}, 管理key={'已配置' if admin_key else '未配置'}")

        # 场景1: 有普通key
        if api_key:
            logger.info("[WechatPadPro] 场景1: 检测到普通key，检查在线状态")

            # 1.1 检查是否在线
            is_online = await self._check_login_status(saved_wxid)
            if is_online:
                logger.info(f"[WechatPadPro] 用户已在线: {saved_wxid}")
                self._set_logged_in_state(saved_wxid)
                return True

            # 1.2 不在线，直接转为二维码登录
            logger.info("[WechatPadPro] 用户不在线，转为二维码登录")
            return False

        # 场景2: 没有普通key，有管理key
        elif admin_key:
            logger.info("[WechatPadPro] 场景2: 检测到管理key，获取普通key进行二维码登录")
            try:
                # 2.1 使用管理key获取普通key
                result = await self.bot.generate_auth_key_simple()
                if result and result.get("Success"):
                    new_token = result.get("Data", {}).get("Key", "")
                    if new_token:
                        logger.info(f"[WechatPadPro] 成功获取普通key: {new_token[:10]}...")

                        # 立即更新配置和bot对象
                        conf().set("wechatpadpro_api_key", new_token)

                        # 保存配置到文件
                        try:
                            from config import save_config
                            save_config()
                            logger.info(f"[WechatPadPro] 已保存新的普通key到配置文件")
                        except Exception as e:
                            logger.warning(f"[WechatPadPro] 保存配置文件失败: {e}")

                        if hasattr(self.bot, 'key'):
                            self.bot.key = new_token
                            logger.info(f"[WechatPadPro] 已更新bot.key为新获取的普通key")

                        # 2.2 使用新获取的普通key进行二维码登录
                        logger.info("[WechatPadPro] 使用新获取的普通key进行二维码登录")
                        return False  # 返回False，让主流程继续二维码登录
                    else:
                        logger.error("[WechatPadPro] 管理key获取的普通key为空")
                        return False
                else:
                    error_msg = result.get("Error", "未知错误") if result else "无响应"
                    logger.error(f"[WechatPadPro] 使用管理key获取普通key失败: {error_msg}")
                    return False
            except Exception as e:
                logger.error(f"[WechatPadPro] 使用管理key获取普通key异常: {e}")
                return False

        # 场景3: 都没有配置
        else:
            logger.error("[WechatPadPro] 未配置普通key或管理key，无法进行登录")
            return False

        # 自动登录失败，转为二维码登录
        logger.info("[WechatPadPro] 自动登录失败，将进行二维码登录")
        return False

    async def _wait_for_login_confirmation(self, uuid, device_id):
        """等待唤醒登录确认 - 8059协议专用"""
        timeout = 120  # 120秒超时，给用户足够时间
        logger.info(f"[WechatPadPro] 等待唤醒登录确认，UUID: {uuid}, 设备ID: {device_id}")
        logger.info(f"[WechatPadPro] 请在手机上确认登录，等待时间: {timeout}秒")

        # 首先等待一段时间让用户有时间在手机上操作
        initial_wait = 10
        logger.info(f"[WechatPadPro] 等待 {initial_wait} 秒后开始检查登录状态...")
        await asyncio.sleep(initial_wait)
        timeout -= initial_wait

        check_interval = 5  # 每5秒检查一次，减少频率
        while timeout > 0:
            try:
                logger.info(f"[WechatPadPro] 检查唤醒登录状态，剩余 {timeout} 秒...")

                # 直接检查登录状态，不使用心跳检测
                response = await self._call_api("/login/GetLoginStatus", {}, method="GET")
                if response and response.get("Code") == 200:
                    login_data = response.get("Data", {})
                    login_state = login_data.get("loginState", 0)
                    if login_state == 1:  # 1表示在线
                        logger.info("[WechatPadPro] 唤醒登录确认成功！用户已在手机上确认登录")
                        return True
                    else:
                        logger.debug(f"[WechatPadPro] 登录状态: {login_state}，继续等待...")
                else:
                    logger.debug(f"[WechatPadPro] 获取登录状态失败，响应: {response}")

            except Exception as e:
                logger.warning(f"[WechatPadPro] 检查登录状态时出现异常: {e}")
                # 不要因为单次检查失败就退出，继续等待

            # 等待指定间隔后再次检查
            await asyncio.sleep(check_interval)
            timeout -= check_interval

        logger.warning("[WechatPadPro] 等待登录确认超时，用户可能未在手机上确认")
        return False

    def _set_logged_in_state(self, wxid):
        """设置登录成功状态"""
        logger.info(f"[WechatPadPro] 设置登录状态: wxid={wxid}")

        # 设置通道状态
        self.wxid = wxid
        self.user_id = wxid
        self.is_logged_in = True

        # 同步设置bot的wxid属性，确保消息获取正常
        if hasattr(self.bot, 'wxid'):
            self.bot.wxid = wxid
            logger.info(f"[WechatPadPro] 已同步设置bot.wxid = {wxid}")
        else:
            logger.warning(f"[WechatPadPro] bot对象没有wxid属性")

        # 异步获取用户资料
        threading.Thread(target=lambda: asyncio.run(self._get_user_profile())).start()

        logger.info(f"[WechatPadPro] 登录状态设置完成: {wxid}")

    async def _get_user_profile(self):
        """获取用户资料"""
        try:
            profile = await self.bot.get_profile()
            if profile and isinstance(profile, dict):
                userinfo = profile.get("userInfo", {})
                if isinstance(userinfo, dict):
                    if "NickName" in userinfo and isinstance(userinfo["NickName"], dict) and "string" in userinfo["NickName"]:
                        self.name = userinfo["NickName"]["string"]
                    elif "nickname" in userinfo:
                        self.name = userinfo["nickname"]
                    elif "nickName" in userinfo:
                        self.name = userinfo["nickName"]
                    else:
                        self.name = self.wxid
                    logger.info(f"[WechatPadPro] 获取到用户昵称: {self.name}")
                    return

            self.name = self.wxid
            logger.warning(f"[WechatPadPro] 无法解析用户资料，使用wxid作为昵称: {self.wxid}")
        except Exception as e:
            self.name = self.wxid
            logger.error(f"[WechatPadPro] 获取用户资料失败: {e}")

    async def _message_listener(self):
        """消息监听器"""
        logger.info("[WechatPadPro] 开始监听消息...")
        error_count = 0
        login_error_count = 0  # 跟踪登录错误计数

        while self.is_running:
            try:
                # 获取新消息
                messages = await self._get_messages_simple()

                # 重置错误计数
                error_count = 0
                login_error_count = 0  # 重置登录错误计数

                # 如果获取到消息，则处理
                if messages:
                    for idx, msg in enumerate(messages):
                        try:
                            logger.debug(f"[WechatPadPro] 处理第 {idx+1}/{len(messages)} 条消息")
                            # 判断是否是群消息
                            is_group = False
                            # 检查多种可能的群聊标识字段
                            if "roomId" in msg and msg["roomId"]:
                                is_group = True
                            # 8059协议：检查from_user_name字段（群聊消息的发送方是群聊ID）
                            elif "from_user_name" in msg:
                                from_user_name = msg["from_user_name"]
                                # 处理字符串字段可能被包装在字典中的情况
                                if isinstance(from_user_name, dict) and "str" in from_user_name:
                                    from_user_name = from_user_name["str"]
                                if from_user_name and isinstance(from_user_name, str) and from_user_name.endswith("@chatroom"):
                                    is_group = True
                            elif "toUserName" in msg:
                                to_user_name = msg["toUserName"]
                                # 处理字符串字段可能被包装在字典中的情况
                                if isinstance(to_user_name, dict) and "string" in to_user_name:
                                    to_user_name = to_user_name["string"]
                                if to_user_name and isinstance(to_user_name, str) and to_user_name.endswith("@chatroom"):
                                    is_group = True
                            elif "ToUserName" in msg:
                                to_user_name = msg["ToUserName"]
                                # 处理字符串字段可能被包装在字典中的情况
                                if isinstance(to_user_name, dict) and "string" in to_user_name:
                                    to_user_name = to_user_name["string"]
                                if to_user_name and isinstance(to_user_name, str) and to_user_name.endswith("@chatroom"):
                                    is_group = True

                            if is_group:
                                logger.debug(f"[WechatPadPro] 识别为群聊消息")
                            else:
                                logger.debug(f"[WechatPadPro] 识别为私聊消息")

                            # 创建消息对象
                            cmsg = WechatPadProMessage(msg, is_group)

                            # ADDED: Call the new filter method
                            if self._should_filter_this_message(cmsg): # 调用新的过滤方法
                                logger.debug(f"[WechatPadPro] Message from {getattr(cmsg, 'sender_wxid', 'UnknownSender')} was filtered out by _should_filter_this_message.")
                                continue # 如果消息被过滤，则跳过后续处理，处理下一条消息

                            # 处理消息
                            if is_group:
                                await self.handle_group(cmsg)
                            else:
                                await self.handle_single(cmsg)
                        except Exception as e:
                            logger.error(f"[WechatPadPro] 处理消息出错: {e}")
                            # 打印完整的异常堆栈
                            import traceback
                            logger.error(f"[WechatPadPro] 异常堆栈: {traceback.format_exc()}")

                # 休眠一段时间
                await asyncio.sleep(1)
            except Exception as e:
                error_count += 1
                error_msg = str(e)

                # 检查是否是登录相关错误
                if "请先登录" in error_msg or "您已退出微信" in error_msg or "登录已失效" in error_msg or "Please login first" in error_msg:
                    login_error_count += 1
                    # 记录更详细的日志信息
                    logger.error(f"[WechatPadPro] 获取消息出错，登录已失效: {e}")

                    # 添加客户端状态信息
                    logger.error(f"[WechatPadPro] 客户端状态 - wxid: {getattr(self.bot, 'wxid', '未知')}")
                    logger.error(f"[WechatPadPro] 客户端状态 - 本地wxid: {self.wxid}")
                    logger.error(f"[WechatPadPro] 客户端状态 - API路径前缀: {getattr(self.bot, 'api_path_prefix', '未知')}")
                    logger.error(f"[WechatPadPro] 客户端状态 - 服务器: {getattr(self.bot, 'ip', '未知')}:{getattr(self.bot, 'port', '未知')}")

                    # 获取API客户端类型
                    client_type = self.bot.__class__.__name__
                    client_module = self.bot.__class__.__module__
                    logger.error(f"[WechatPadPro] 客户端类型: {client_module}.{client_type}")

                    # 尝试自动修复wxid不一致问题
                    if hasattr(self.bot, 'wxid') and self.wxid and (not self.bot.wxid or self.bot.wxid != self.wxid):
                        logger.warning(f"[WechatPadPro] 检测到wxid不一致，尝试修复: self.wxid={self.wxid}, bot.wxid={self.bot.wxid}")
                        self.bot.wxid = self.wxid
                        logger.info(f"[WechatPadPro] 已同步设置bot.wxid = {self.wxid}")
                        # 延迟执行下次重试，避免立即失败
                        await asyncio.sleep(2)
                        continue

                    # 获取异常详细信息
                    import traceback
                    logger.error(f"[WechatPadPro] 异常详细堆栈:\n{traceback.format_exc()}")

                    # 检查客户端的get_new_message方法
                    import inspect
                    if hasattr(self.bot, 'get_new_message') and callable(getattr(self.bot, 'get_new_message')):
                        try:
                            source = inspect.getsource(self.bot.get_new_message)
                            logger.debug(f"[WechatPadPro] get_new_message方法实现:\n{source}")
                        except Exception as source_err:
                            logger.debug(f"[WechatPadPro] 无法获取get_new_message源码: {source_err}")
                else:
                    # 其他错误正常记录
                    logger.error(f"[WechatPadPro] 获取消息出错: {e}")
                    # 记录异常堆栈
                    import traceback
                    logger.error(f"[WechatPadPro] 异常堆栈: {traceback.format_exc()}")

                await asyncio.sleep(5)  # 出错后等待一段时间再重试
                continue

            except Exception as e:
                logger.error(f"[WechatPadPro] 消息监听器出错: {e}")
                # 打印完整的异常堆栈
                import traceback
                logger.error(f"[WechatPadPro] 异常堆栈: {traceback.format_exc()}")
                await asyncio.sleep(5)  # 出错后等待一段时间再重试

            # 休眠一段时间
            await asyncio.sleep(1)

    def startup(self):
        """启动函数"""
        logger.info("[WechatPadPro] 正在启动...")

        # 创建事件循环
        loop = asyncio.new_event_loop()
        self.loop = loop
        self._start_image_cache_cleanup_task()
        # 定义启动任务
        async def startup_task():
            # 初始化机器人（登录）
            login_success = await self._initialize_bot()
            if login_success:
                logger.info("[WechatPadPro] 登录成功，准备启动消息监听...")
                self.is_running = True
                # 启动消息监听
                await self._message_listener()
            else:
                logger.error("[WechatPadPro] 初始化失败")

        # 在新线程中运行事件循环
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(startup_task())

        thread = threading.Thread(target=run_loop)
        thread.daemon = True
        thread.start()

    # MODIFIED: New filter method with corrected sender ID logic for gh_ check
    def _should_filter_this_message(self, wx_msg: 'WechatPadProMessage') -> bool:
        # 过滤非用户消息
        # import time
        # from bridge.context import ContextType
        # from config import conf
        # from .wechatpadpro_message import WechatPadProMessage # Assuming WechatPadProMessage is in wechatpadpro_message.py
        # logger should be defined (e.g., import logging; logger = logging.getLogger(__name__))

        if not wx_msg:
            logger.debug("[WechatPadPro] Filter: Received an empty message object, ignoring.")
            return True

        # Get primary identifiers from wx_msg
        # actual_from_user_id is the direct sender (e.g., a user in private chat, a group ID, or a gh_ ID)
        actual_from_user_id = getattr(wx_msg, 'from_user_id', '')
        # actual_sender_wxid is specifically for the user who sent the message within a group
        actual_sender_wxid = getattr(wx_msg, 'sender_wxid', '')

        # Determine the most relevant sender ID for general filtering/logging after the gh_ check.
        # If actual_sender_wxid is populated (usually in groups for a specific user), it's preferred.
        # Otherwise (e.g., private chat, or if sender_wxid wasn't parsed from group msg), use actual_from_user_id.
        effective_sender_id = actual_sender_wxid if actual_sender_wxid else actual_from_user_id

        _content_value = getattr(wx_msg, 'content', '')
        _message_content_preview = f"(content type: {type(_content_value)}, first 50 chars: {str(_content_value)[:50]})"
        _message_type = getattr(wx_msg, 'type', None) # wx_msg.type should be ContextType
        _message_create_time = getattr(wx_msg, 'create_time', None)

        # 1. Ignore specific WeChat official accounts
        #    微信官方账号黑名单
        wechat_official_accounts = [
            "weixin",                # 微信团队
            "gh_6e99ff560306",      # 微信安全中心
            "gh_3dfda90e39d6",      # 微信支付
            "gh_25d9ac85a4bc"       # 微信游戏
        ]

        if isinstance(actual_from_user_id, str) and actual_from_user_id in wechat_official_accounts:
            logger.debug(f"[WechatPadPro] Filter: Ignored WeChat official account message from {actual_from_user_id}: {_message_content_preview}")
            return True

        # 2. 只过滤特定的官方账号，不过滤所有gh_开头的消息
        #    允许公众号等正常消息通过
        if isinstance(actual_from_user_id, str):
            # 定义需要过滤的特定官方账号列表
            filtered_official_accounts = [
                "weixin",                    # 微信团队
                "gh_6e99ff560306",          # 微信安全中心
                "gh_3dfda90e39d6",          # 微信支付
                "gh_25d9ac85a4bc",          # 微信游戏
                # 可以根据需要添加其他需要过滤的特定账号
                # 注意：不过滤系统消息，允许系统消息通过
            ]

            # 只过滤特定的官方账号
            if actual_from_user_id in filtered_official_accounts:
                logger.debug(f"[WechatPadPro] Filter: Ignored specific official account message from {actual_from_user_id}: {_message_content_preview}")
                return True

            # 对于其他gh_开头的账号（如公众号），允许通过并记录日志
            if actual_from_user_id.startswith("gh_"):
                logger.info(f"[WechatPadPro] Filter: Allowing message from gh_ account {actual_from_user_id}: {_message_content_preview}")
                return False  # 不过滤，允许通过

        # 3. Ignore voice messages if speech recognition is off
        if _message_type == ContextType.VOICE:
            if conf().get("speech_recognition") != True:
                logger.debug(f"[WechatPadPro] Filter: Ignored voice message (speech recognition off): from {effective_sender_id}")
                return True

        # 4. Ignore messages from self (self.user_id should be the bot's own WXID)
        if self.user_id and effective_sender_id == self.user_id:
            logger.debug(f"[WechatPadPro] Filter: Ignored message from myself ({self.user_id}): {_message_content_preview}")
            return True

        # 5. Ignore expired messages (e.g., older than 5 minutes)
        if _message_create_time:
            try:
                msg_ts = float(_message_create_time)
                current_ts = time.time()
                if msg_ts < (current_ts - 300):  # 300 seconds = 5 minutes
                    logger.debug(f"[WechatPadPro] Filter: Ignored expired message (timestamp: {msg_ts}) from {effective_sender_id}: {_message_content_preview}")
                    return True
            except (ValueError, TypeError):
                logger.warning(f"[WechatPadPro] Filter: Could not parse create_time '{_message_create_time}' for sender {effective_sender_id}.")
            except Exception as e:
                logger.warning(f"[WechatPadPro] Filter: Error checking expired message for sender {effective_sender_id}: {e}")

        # 5. Ignore status sync messages
        if hasattr(ContextType, 'STATUS_SYNC') and _message_type == ContextType.STATUS_SYNC:
            logger.debug(f"[WechatPadPro] Filter: Ignored status sync message from {effective_sender_id}: {_message_content_preview}")
            return True

        # Duplicate message check
        # Use effective_sender_id for the duplicate key to ensure uniqueness.
        if wx_msg and hasattr(wx_msg, 'msg_id') and wx_msg.msg_id:
            # Ensure received_msgs is initialized in WX849Channel.__init__
            # e.g., self.received_msgs = ExpiredDict(conf().get("expires_in_seconds", 3600))
            if not hasattr(self, 'received_msgs'):
                 logger.error("[WechatPadPro] Filter: self.received_msgs is not initialized. Cannot check for duplicates.")
            else:
                wx_msg_key = f"{wx_msg.msg_id}_{effective_sender_id}_{wx_msg.create_time}"
                if wx_msg_key in self.received_msgs:
                    logger.debug(f"[WechatPadPro] Filter: Ignored duplicate message: {wx_msg_key}")
                    return True
                self.received_msgs[wx_msg_key] = wx_msg
        else:
            logger.debug("[WechatPadPro] Filter: Message lacks unique msg_id for duplicate check, proceeding with caution.")

        return False # Message passed all filters


    @_check
    async def handle_single(self, cmsg: ChatMessage):
        """处理私聊消息"""
        try:
            # 处理消息内容和类型
            await self._process_message(cmsg)

            # 只记录关键消息信息，减少日志输出
            if conf().get("log_level", "INFO") != "ERROR":
                logger.debug(f"[WechatPadPro] 私聊消息 - 类型: {cmsg.ctype}, ID: {cmsg.msg_id}, 内容: {cmsg.content[:20]}...")

            # 根据消息类型处理
            if cmsg.ctype == ContextType.VOICE and conf().get("speech_recognition") != True:
                logger.debug("[WechatPadPro] 语音识别功能未启用，跳过处理")
                return

            # 检查前缀匹配
            if cmsg.ctype == ContextType.TEXT:
                single_chat_prefix = conf().get("single_chat_prefix", [""])
                # 日志记录前缀配置，方便调试
                logger.debug(f"[WechatPadPro] 单聊前缀配置: {single_chat_prefix}")
                match_prefix = None
                for prefix in single_chat_prefix:
                    if prefix and cmsg.content.startswith(prefix):
                        logger.debug(f"[WechatPadPro] 匹配到前缀: {prefix}")
                        match_prefix = prefix
                        # 去除前缀
                        cmsg.content = cmsg.content[len(prefix):].strip()
                        logger.debug(f"[WechatPadPro] 去除前缀后的内容: {cmsg.content}")
                        break

                # 记录是否匹配
                if not match_prefix and single_chat_prefix and "" not in single_chat_prefix:
                    logger.debug(f"[WechatPadPro] 未匹配到前缀，消息被过滤: {cmsg.content}")
                    # 如果没有匹配到前缀且配置中没有空前缀，则直接返回，不处理该消息
                    return

            # 生成上下文
            context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=False, msg=cmsg)
            if context:
                self.produce(context)
            else:
                logger.debug(f"[WechatPadPro] 生成上下文失败，跳过处理")
        except Exception as e:
            logger.error(f"[WechatPadPro] 处理私聊消息异常: {e}")
            if conf().get("log_level", "INFO") == "DEBUG":
                import traceback
                logger.debug(f"[WechatPadPro] 异常堆栈: {traceback.format_exc()}")

    @_check
    async def handle_group(self, cmsg: ChatMessage):
        """处理群聊消息"""
        try:
            # 添加日志，记录处理前的消息基本信息
            logger.debug(f"[WechatPadPro] 开始处理群聊消息 - ID:{cmsg.msg_id} 类型:{cmsg.msg_type} 从:{cmsg.from_user_id}")

            # 处理消息内容和类型
            await self._process_message(cmsg)

            # 只记录关键消息信息，减少日志输出
            if conf().get("log_level", "INFO") != "ERROR":
                logger.debug(f"[WechatPadPro] 群聊消息 - 类型: {cmsg.ctype}, 群ID: {cmsg.other_user_id}")

            # 根据消息类型处理
            if cmsg.ctype == ContextType.VOICE and conf().get("group_speech_recognition") != True:
                logger.debug("[WechatPadPro] 群聊语音识别功能未启用，跳过处理")
                return

            # 检查白名单
            if cmsg.from_user_id and hasattr(cmsg, 'from_user_id'):
                group_white_list = conf().get("group_name_white_list", ["ALL_GROUP"])
                # 检查是否启用了白名单
                if "ALL_GROUP" not in group_white_list:
                    # 获取群名
                    group_name = None
                    try:
                        # 使用同步方式获取群名，避免事件循环嵌套
                        chatrooms_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp", 'wechatpadpro_rooms.json')

                        if os.path.exists(chatrooms_file):
                            try:
                                with open(chatrooms_file, 'r', encoding='utf-8') as f:
                                    chatrooms_info = json.load(f)

                                if cmsg.from_user_id in chatrooms_info:
                                    group_name = chatrooms_info[cmsg.from_user_id].get("nickName")
                                    if group_name:
                                        logger.debug(f"[WechatPadPro] 从缓存获取到群名: {group_name}")
                            except Exception as e:
                                logger.error(f"[WechatPadPro] 读取群聊缓存失败: {e}")

                        # 如果没有从缓存获取到群名，使用群ID作为备用
                        if not group_name:
                            group_name = cmsg.from_user_id
                            logger.debug(f"[WechatPadPro] 没有找到群名，使用群ID: {group_name}")

                        logger.debug(f"[WechatPadPro] 群聊白名单检查 - 群名: {group_name}")
                    except Exception as e:
                        logger.error(f"[WechatPadPro] 获取群名称失败: {e}")
                        group_name = cmsg.from_user_id

                    # 检查群名是否在白名单中
                    if group_name and group_name not in group_white_list:
                        # 使用群ID再次检查
                        if cmsg.from_user_id not in group_white_list:
                            logger.info(f"[WechatPadPro] 群聊不在白名单中，跳过处理: {group_name}")
                            return

                    logger.debug(f"[WechatPadPro] 群聊通过白名单检查: {group_name or cmsg.from_user_id}")

            # 检查前缀匹配
            trigger_proceed = False
            if cmsg.ctype == ContextType.TEXT:
                group_chat_prefix = conf().get("group_chat_prefix", [])
                group_chat_keyword = conf().get("group_chat_keyword", [])

                # 日志记录前缀配置，方便调试
                logger.debug(f"[WechatPadPro] 群聊前缀配置: {group_chat_prefix}")
                logger.debug(f"[WechatPadPro] 群聊关键词配置: {group_chat_keyword}")

                # MODIFIED: Enhanced prefix checking for normal and quote messages
                text_to_check_for_prefix = cmsg.content
                is_quote_with_extracted_question = False
                guide_prefix = ""
                original_user_question_in_quote = ""
                guide_suffix = "" # This will capture the quote marks and newlines after the user question

                if hasattr(cmsg, 'is_processed_text_quote') and cmsg.is_processed_text_quote:
                    # 确保 re 模块在这里是可用的
                    import re # <--- 在这里显式导入一次
                    match = re.match(r'(用户针对以下(?:消息|聊天记录)提问：")(.*?)("\n\n)', cmsg.content, re.DOTALL)
                    if match:
                        guide_prefix = match.group(1)  # "用户针对以下消息提问：""
                        original_user_question_in_quote = match.group(2) # "xy他说什么"
                        guide_suffix = match.group(3)    # "”\n\n"
                        text_to_check_for_prefix = original_user_question_in_quote
                        is_quote_with_extracted_question = True
                        logger.debug(f"[WechatPadPro] Quote message: Extracted text for prefix check: '{text_to_check_for_prefix}'")
                    else:
                        logger.debug(f"[WechatPadPro] Quote message format did not match extraction pattern: {cmsg.content[:100]}...")

                # Loop through configured prefixes
                for prefix in group_chat_prefix:
                    if prefix and text_to_check_for_prefix.startswith(prefix):
                        logger.debug(f"[WechatPadPro] Group chat matched prefix: '{prefix}' (on text: '{text_to_check_for_prefix[:50]}...')")
                        cleaned_question_content = text_to_check_for_prefix[len(prefix):].strip()

                        if is_quote_with_extracted_question:
                            # Reconstruct cmsg.content with the cleaned question part, preserving the rest of the quote structure
                            # The rest of the message starts after the original full guide + question + suffix part
                            full_original_question_segment = guide_prefix + original_user_question_in_quote + guide_suffix
                            if cmsg.content.startswith(full_original_question_segment):
                                rest_of_message_after_quote_question = cmsg.content[len(full_original_question_segment):]
                                cmsg.content = guide_prefix + cleaned_question_content + guide_suffix + rest_of_message_after_quote_question
                                logger.debug(f"[WechatPadPro] Quote message, prefix removed. New content: {cmsg.content[:150]}...")
                            else:
                                # This fallback is less ideal as it might indicate an issue with segment identification
                                logger.warning(f"[WechatPadPro] Quote message content did not start as expected with extracted segments. Attempting direct replacement of user question part.")
                                # Attempt to replace only the original_user_question_in_quote part within the larger cmsg.content
                                # This is safer if the rest_of_message_after_quote_question logic is not robust enough for all cases
                                cmsg.content = cmsg.content.replace(original_user_question_in_quote, cleaned_question_content, 1)
                                logger.debug(f"[WechatPadPro] Quote message, prefix removed via replace. New content: {cmsg.content[:150]}...")
                        else:
                            # For non-quote messages, the behavior is as before
                            cmsg.content = cleaned_question_content
                            logger.debug(f"[WechatPadPro] Non-quote message, prefix removed. New content: {cmsg.content}")

                        trigger_proceed = True
                        break

                # 检查关键词匹配
                if not trigger_proceed and group_chat_keyword:
                    for keyword in group_chat_keyword:
                        if keyword and keyword in cmsg.content:
                            logger.debug(f"[WechatPadPro] 群聊匹配到关键词: {keyword}")
                            trigger_proceed = True
                            break

                # 检查是否@了机器人（增强版）
                if not trigger_proceed and (cmsg.at_list or cmsg.content.find("@") >= 0):
                    logger.debug(f"[WechatPadPro] @列表: {cmsg.at_list}, 机器人wxid: {self.wxid}")

                    # 检查at_list中是否包含机器人wxid
                    at_matched = False
                    if cmsg.at_list and self.wxid in cmsg.at_list:
                        at_matched = True
                        logger.debug(f"[WechatPadPro] 在at_list中匹配到机器人wxid: {self.wxid}")

                    # 如果at_list为空，或者at_list中没有找到机器人wxid，则检查消息内容中是否直接包含@机器人的文本
                    if not at_matched and cmsg.content:
                        # 获取可能的机器人名称
                        robot_names = []
                        if self.name:
                            robot_names.append(self.name)
                        if hasattr(cmsg, 'self_display_name') and cmsg.self_display_name:
                            robot_names.append(cmsg.self_display_name)

                        # 检查消息中是否包含@机器人名称
                        for name in robot_names:
                            at_text = f"@{name}"
                            if at_text in cmsg.content:
                                at_matched = True
                                logger.debug(f"[WechatPadPro] 在消息内容中直接匹配到@机器人: {at_text}")
                                break

                    # 处理多种可能的@格式
                    if at_matched:
                        # 尝试移除不同格式的@文本
                        original_content = cmsg.content
                        at_patterns = []

                        # 添加可能的@格式
                        if self.name:
                            at_patterns.extend([
                                f"@{self.name} ",  # 带空格
                                f"@{self.name}\u2005",  # 带特殊空格
                                f"@{self.name}",  # 不带空格
                            ])

                        # 检查是否存在自定义的群内昵称
                        if hasattr(cmsg, 'self_display_name') and cmsg.self_display_name:
                            at_patterns.extend([
                                f"@{cmsg.self_display_name} ",  # 带空格
                                f"@{cmsg.self_display_name}\u2005",  # 带特殊空格
                                f"@{cmsg.self_display_name}",  # 不带空格
                            ])

                        # 按照优先级尝试移除@文本
                        for pattern in at_patterns:
                            if pattern in cmsg.content:
                                cmsg.content = cmsg.content.replace(pattern, "", 1).strip()
                                logger.debug(f"[WechatPadPro] 匹配到@模式: {pattern}")
                                logger.debug(f"[WechatPadPro] 去除@后的内容: {cmsg.content}")
                                break

                        # 如果没有匹配到任何@模式，但确实在at_list中找到了机器人或内容中包含@
                        # 尝试使用正则表达式移除通用@格式
                        if cmsg.content == original_content and at_matched:
                            import re
                            # 匹配形如"@任何内容 "的模式
                            at_pattern = re.compile(r'@[^\s]+[\s\u2005]+')
                            cmsg.content = at_pattern.sub("", cmsg.content, 1).strip()
                            logger.debug(f"[WechatPadPro] 使用正则表达式去除@后的内容: {cmsg.content}")

                        trigger_proceed = True

                # 记录是否需要处理
                if not trigger_proceed:
                    logger.debug(f"[WechatPadPro] 群聊消息未匹配触发条件，跳过处理: {cmsg.content}")
                    return

            # 生成上下文
            context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=True, msg=cmsg)
            if context:
                self.produce(context)
            else:
                logger.debug(f"[WechatPadPro] 生成群聊上下文失败，跳过处理")
        except Exception as e:
            error_msg = str(e)
            # 添加更详细的错误日志信息
            logger.error(f"[WechatPadPro] 处理群聊消息异常: {error_msg}")
            logger.error(f"[WechatPadPro] 消息内容: {getattr(cmsg, 'content', '未知')[:100]}")
            logger.error(f"[WechatPadPro] 消息类型: {getattr(cmsg, 'msg_type', '未知')}")
            logger.error(f"[WechatPadPro] 上下文类型: {getattr(cmsg, 'ctype', '未知')}")

            # 记录完整的异常堆栈
            import traceback
            logger.error(f"[WechatPadPro] 异常堆栈: {traceback.format_exc()}")

    async def _process_message(self, cmsg):
        """处理消息内容和类型"""
        # 处理消息类型
        msg_type = cmsg.msg_type
        if not msg_type and "Type" in cmsg.msg:
            msg_type = cmsg.msg["Type"]

        # 尝试获取机器人在群内的昵称
        if cmsg.is_group and not cmsg.self_display_name:
            try:
                # 从缓存中查询群成员详情
                tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
                chatrooms_file = os.path.join(tmp_dir, 'wechatpadpro_rooms.json')

                if os.path.exists(chatrooms_file):
                    try:
                        with open(chatrooms_file, 'r', encoding='utf-8') as f:
                            chatrooms_info = json.load(f)

                        if cmsg.from_user_id in chatrooms_info:
                            room_info = chatrooms_info[cmsg.from_user_id]

                            # 在成员中查找机器人的信息
                            if "members" in room_info and isinstance(room_info["members"], list):
                                for member in room_info["members"]:
                                    if member.get("UserName") == self.wxid:
                                        # 优先使用群内显示名称
                                        if member.get("DisplayName"):
                                            cmsg.self_display_name = member.get("DisplayName")
                                            logger.debug(f"[WechatPadPro] 从群成员缓存中获取到机器人群内昵称: {cmsg.self_display_name}")
                                            break
                                        # 其次使用昵称
                                        elif member.get("NickName"):
                                            cmsg.self_display_name = member.get("NickName")
                                            logger.debug(f"[WechatPadPro] 从群成员缓存中获取到机器人昵称: {cmsg.self_display_name}")
                                            break
                    except Exception as e:
                        logger.error(f"[WechatPadPro] 读取群成员缓存失败: {e}")

                # 如果缓存中没有找到，使用机器人名称
                if not cmsg.self_display_name:
                    cmsg.self_display_name = self.name
                    logger.debug(f"[WechatPadPro] 使用机器人名称作为群内昵称: {cmsg.self_display_name}")
            except Exception as e:
                logger.error(f"[WechatPadPro] 获取机器人群内昵称失败: {e}")

        # 8059协议消息类型映射调试
        logger.debug(f"[WechatPadPro8059] 消息类型调试 - msg_type: {msg_type} (类型: {type(msg_type)})")
        logger.debug(f"[WechatPadPro8059] 消息内容调试 - content: {cmsg.content[:200]}")
        logger.debug(f"[WechatPadPro8059] 原始消息调试 - msg: {cmsg.msg}")

        # 根据消息类型进行处理 - 8059协议类型映射
        if msg_type in [0, "0"]:  # 8059协议中0可能是文本消息
            self._process_text_message(cmsg)
        elif msg_type in [1, "1", "Text"]:
            self._process_text_message(cmsg)
        elif msg_type in [3, "3", "Image"]:
            await self._process_image_message(cmsg)
        elif msg_type in [34, "34", "Voice"]:
            self._process_voice_message(cmsg)
        elif msg_type in [43, "43", "Video"]:
            self._process_video_message(cmsg)
        elif msg_type in [47, "47", "Emoji"]:
            self._process_emoji_message(cmsg)
        elif msg_type in [49, "49", "App"]:
            self._process_xml_message(cmsg)
        elif msg_type in [10000, "10000", "System"]:
            self._process_system_message(cmsg)
        else:
            # 默认类型处理
            cmsg.ctype = ContextType.UNKNOWN
            logger.warning(f"[WechatPadPro] 未知消息类型: {msg_type}, 内容: {cmsg.content[:100]}")

        # 检查消息是否来自群聊
        if cmsg.is_group or cmsg.from_user_id.endswith("@chatroom"):
            # 增强的群消息发送者提取逻辑
            # 尝试多种可能的格式解析发送者信息
            sender_extracted = False

            # 检查是否已经有正确的发送者信息（由特定消息类型处理器设置）
            if hasattr(cmsg, 'sender_wxid') and cmsg.sender_wxid and not cmsg.sender_wxid.startswith("未知用户_"):
                sender_extracted = True
                logger.debug(f"[WechatPadPro] 发送者信息已由消息处理器设置: {cmsg.sender_wxid}")
            else:
                # 方法1: 尝试解析完整的格式 "wxid:\n消息内容"
                # 但要排除XML内容（图片、视频等消息）
                if not cmsg.content.startswith("<"):
                    split_content = cmsg.content.split(":\n", 1)
                    if len(split_content) > 1 and split_content[0] and not split_content[0].startswith("<"):
                        cmsg.sender_wxid = split_content[0]
                        cmsg.content = split_content[1]
                        sender_extracted = True
                        logger.debug(f"[WechatPadPro] 群聊发送者提取(方法1): {cmsg.sender_wxid}")

            # 方法2: 尝试解析简单的格式 "wxid:消息内容"
            #if not sender_extracted:
            #    split_content = cmsg.content.split(":", 1)
            #    if len(split_content) > 1 and split_content[0] and not split_content[0].startswith("<"):
            #        cmsg.sender_wxid = split_content[0]
            #        cmsg.content = split_content[1]
            #        sender_extracted = True
            #        logger.debug(f"[WechatPadPro] 群聊发送者提取(方法2): {cmsg.sender_wxid}")

            # 方法3: 尝试从XML中提取发送者信息
            if not sender_extracted and cmsg.content and cmsg.content.startswith("<"):
                try:
                    # 解析XML内容
                    root = ET.fromstring(cmsg.content)

                    # 查找不同类型的XML中可能存在的发送者信息
                    if root.tag == "msg":
                        # 首先检查根元素的fromusername属性（最常见）
                        fromusername = root.get('fromusername')
                        if fromusername:
                            cmsg.sender_wxid = fromusername
                            sender_extracted = True
                            logger.debug(f"[WechatPadPro] 群聊发送者从XML根属性提取: {cmsg.sender_wxid}")

                        # 如果没有找到，再查找子元素
                        if not sender_extracted:
                            # 常见的XML消息格式
                            sender_node = root.find(".//username")
                            if sender_node is not None and sender_node.text:
                                cmsg.sender_wxid = sender_node.text
                                sender_extracted = True
                                logger.debug(f"[WechatPadPro] 群聊发送者从XML元素提取: {cmsg.sender_wxid}")

                            # 尝试其他可能的标签
                            if not sender_extracted:
                                for tag in ["fromusername", "sender", "from"]:
                                    sender_node = root.find(f".//{tag}")
                                    if sender_node is not None and sender_node.text:
                                        cmsg.sender_wxid = sender_node.text
                                        sender_extracted = True
                                        logger.debug(f"[WechatPadPro] 群聊发送者从XML({tag})提取: {cmsg.sender_wxid}")
                                        break
                except Exception as e:
                    logger.error(f"[WechatPadPro] 从XML提取群聊发送者失败: {e}")

            # 方法4: 尝试从其它字段提取
            if not sender_extracted:
                for key in ["SenderUserName", "sender", "senderId", "fromUser"]:
                    if key in cmsg.msg and cmsg.msg[key]:
                        cmsg.sender_wxid = str(cmsg.msg[key])
                        sender_extracted = True
                        logger.debug(f"[WechatPadPro] 群聊发送者从字段提取({key}): {cmsg.sender_wxid}")
                        break

            # 如果仍然无法提取，设置为默认值但不要留空
            if not sender_extracted or not cmsg.sender_wxid:
                cmsg.sender_wxid = f"未知用户_{cmsg.from_user_id}"
                logger.debug(f"[WechatPadPro] 无法提取群聊发送者，使用默认值: {cmsg.sender_wxid}")

            # 设置other_user_id为群ID，确保它不为None
            cmsg.other_user_id = cmsg.from_user_id

            # 设置actual_user_id为发送者wxid（如果尚未设置）
            if not hasattr(cmsg, 'actual_user_id') or not cmsg.actual_user_id:
                cmsg.actual_user_id = cmsg.sender_wxid

            # 异步获取发送者昵称并设置actual_user_nickname（如果尚未设置）
            # 但现在我们无法在同步方法中直接调用异步方法，所以先使用wxid
            if not hasattr(cmsg, 'actual_user_nickname') or not cmsg.actual_user_nickname:
                cmsg.actual_user_nickname = cmsg.sender_wxid

            # 启动异步任务获取昵称并更新actual_user_nickname
            threading.Thread(target=lambda: asyncio.run(self._update_nickname_async(cmsg))).start()

            logger.debug(f"[WechatPadPro] 设置实际发送者信息: actual_user_id={cmsg.actual_user_id}, actual_user_nickname={cmsg.actual_user_nickname}")
        else:
            # 私聊消息
            cmsg.sender_wxid = cmsg.from_user_id
            cmsg.is_group = False

            # 私聊消息也设置actual_user_id和actual_user_nickname
            cmsg.actual_user_id = cmsg.from_user_id
            cmsg.actual_user_nickname = cmsg.from_user_id
            logger.debug(f"[WechatPadPro] 设置私聊发送者信息: actual_user_id={cmsg.actual_user_id}, actual_user_nickname={cmsg.actual_user_nickname}")

    async def _update_nickname_async(self, cmsg):
        """异步更新消息中的昵称信息"""
        if cmsg.is_group and cmsg.from_user_id.endswith("@chatroom"):
            # 确保有正确的发送者ID
            sender_id = getattr(cmsg, 'sender_wxid', None) or getattr(cmsg, 'actual_user_id', None)
            if sender_id and sender_id != f"未知用户_{cmsg.from_user_id}":
                nickname = await self._get_chatroom_member_nickname(cmsg.from_user_id, sender_id)
                if nickname and nickname != sender_id and nickname != cmsg.actual_user_nickname:
                    cmsg.actual_user_nickname = nickname
                    logger.debug(f"[WechatPadPro] 异步更新了发送者昵称: {sender_id} -> {nickname}")
                else:
                    logger.debug(f"[WechatPadPro] 未能获取到发送者 {sender_id} 的昵称，保持原值")

    def _process_text_message(self, cmsg):
        """处理文本消息"""
        import xml.etree.ElementTree as ET

        cmsg.ctype = ContextType.TEXT

        # 处理群聊/私聊消息发送者 - 只处理消息内容，不重复设置发送者信息
        if cmsg.is_group or cmsg.from_user_id.endswith("@chatroom"):
            cmsg.is_group = True

            # 只处理消息内容的提取，发送者信息已在_process_message中设置
            # 检查是否需要从消息内容中提取真实内容（去除发送者前缀）
            if hasattr(cmsg, 'sender_wxid') and cmsg.sender_wxid and ":" in cmsg.content:
                # 尝试去除发送者前缀
                if cmsg.content.startswith(f"{cmsg.sender_wxid}:\n"):
                    cmsg.content = cmsg.content[len(f"{cmsg.sender_wxid}:\n"):]
                    logger.debug(f"[WechatPadPro] 已去除消息内容中的发送者前缀")
                elif cmsg.content.startswith(f"{cmsg.sender_wxid}:"):
                    cmsg.content = cmsg.content[len(f"{cmsg.sender_wxid}:"):]
                    logger.debug(f"[WechatPadPro] 已去除消息内容中的发送者前缀(无换行)")

            # 确保other_user_id为群ID
            cmsg.other_user_id = cmsg.from_user_id

            # 异步获取发送者昵称（如果尚未获取）
            if hasattr(cmsg, 'actual_user_nickname') and cmsg.actual_user_nickname == cmsg.actual_user_id:
                # 启动异步任务获取真实昵称
                threading.Thread(target=lambda: asyncio.run(self._update_nickname_async(cmsg))).start()
        else:
            # 私聊消息
            cmsg.is_group = False
            # 私聊消息的发送者信息已在_process_message中设置，这里不需要重复设置

        # 解析@信息 - 多种方式解析
        try:
            # 方法1: 从MsgSource解析
            msg_source = cmsg.msg.get("MsgSource", "")
            if msg_source:
                try:
                    if "<msgsource>" not in msg_source.lower():
                        msg_source = f"<msgsource>{msg_source}</msgsource>"
                    root = ET.fromstring(msg_source)
                    ats_elem = root.find(".//atuserlist")
                    if ats_elem is not None and ats_elem.text:
                        cmsg.at_list = [x for x in ats_elem.text.strip(",").split(",") if x]
                        logger.debug(f"[WechatPadPro] 从MsgSource解析到@列表: {cmsg.at_list}")
                except Exception as e:
                    logger.debug(f"[WechatPadPro] 从MsgSource解析@列表失败: {e}")

            # 方法2: 从其他字段解析
            if not cmsg.at_list:
                for key in ["AtUserList", "at_list", "atlist"]:
                    if key in cmsg.msg:
                        at_value = cmsg.msg[key]
                        if isinstance(at_value, list):
                            cmsg.at_list = [str(x) for x in at_value if x]
                        elif isinstance(at_value, str):
                            cmsg.at_list = [x for x in at_value.strip(",").split(",") if x]

                        if cmsg.at_list:
                            logger.debug(f"[WechatPadPro] 从字段{key}解析到@列表: {cmsg.at_list}")
                            break

            # 方法3: 从消息内容中检测@机器人
            if cmsg.is_group and not cmsg.at_list and "@" in cmsg.content:
                # 如果机器人有名称或群内昵称，检查是否被@
                if self.name and f"@{self.name}" in cmsg.content:
                    # 模拟添加自己到at_list
                    cmsg.at_list.append(self.wxid)
                    logger.debug(f"[WechatPadPro] 从消息内容检测到@机器人名称: {self.name}")
                elif hasattr(cmsg, 'self_display_name') and cmsg.self_display_name and f"@{cmsg.self_display_name}" in cmsg.content:
                    # 模拟添加自己到at_list
                    cmsg.at_list.append(self.wxid)
                    logger.debug(f"[WechatPadPro] 从消息内容检测到@机器人群内昵称: {cmsg.self_display_name}")
        except Exception as e:
            logger.debug(f"[WechatPadPro] 解析@列表失败: {e}")
            cmsg.at_list = []

        # 确保at_list不为空列表
        if not cmsg.at_list or (len(cmsg.at_list) == 1 and cmsg.at_list[0] == ""):
            cmsg.at_list = []

        # 输出日志
        logger.info(f"收到文本消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid} @:{cmsg.at_list} 内容:{cmsg.content}")

    async def _process_image_message(self, cmsg: WechatPadProMessage): # Added WechatPadProMessage type hint
        """处理图片消息"""
        import xml.etree.ElementTree as ET
        import os

        import time
        # import threading # Not used directly in this snippet
        import traceback # Added for logging
        from bridge.context import ContextType # Added for ContextType

        # 在这里不检查和标记图片消息，而是在图片下载完成后再标记
        # 这样可以确保图片消息被正确处理为IMAGE类型，而不是UNKNOWN类型

        cmsg.ctype = ContextType.IMAGE

        # 处理群聊图片消息的发送者信息和XML内容分离
        original_content = cmsg.content

        logger.debug(f"[WechatPadPro] 处理图片消息: msg_id={cmsg.msg_id}, is_group={cmsg.is_group}")

        if cmsg.is_group or (hasattr(cmsg, 'from_user_id') and cmsg.from_user_id and cmsg.from_user_id.endswith("@chatroom")):
            cmsg.is_group = True

            # 对于群聊图片消息，内容格式通常是 "wxid:\n<?xml...>"
            if isinstance(cmsg.content, str) and ":\n" in cmsg.content and not cmsg.content.startswith("<?xml"):
                split_content = cmsg.content.split(":\n", 1)
                if len(split_content) == 2 and split_content[1].startswith("<?xml"):
                    # 提取发送者ID
                    cmsg.sender_wxid = split_content[0]
                    # 更新内容为纯XML
                    cmsg.content = split_content[1]
                    logger.info(f"[WechatPadPro] 群聊图片消息发送者提取成功: {cmsg.sender_wxid}")
                else:
                    # 如果格式不匹配，使用已设置的发送者信息或默认值
                    if not hasattr(cmsg, 'sender_wxid') or not cmsg.sender_wxid:
                        cmsg.sender_wxid = f"未知用户_{cmsg.from_user_id}"
                    logger.warning(f"[WechatPadPro] 群聊图片消息格式不匹配，使用默认发送者: {cmsg.sender_wxid}")
            else:
                # 如果没有发送者前缀，使用已设置的发送者信息或默认值
                if not hasattr(cmsg, 'sender_wxid') or not cmsg.sender_wxid:
                    cmsg.sender_wxid = f"未知用户_{cmsg.from_user_id}"
                logger.warning(f"[WechatPadPro] 群聊图片消息无发送者前缀，使用默认发送者: {cmsg.sender_wxid}")
        else:
            # 私聊消息：使用from_user_id作为发送者ID
            cmsg.sender_wxid = cmsg.from_user_id
            cmsg.is_group = False
            logger.debug(f"[WechatPadPro] 私聊图片消息发送者: {cmsg.sender_wxid}")

        # 确保actual_user_id和actual_user_nickname已设置
        cmsg.actual_user_id = cmsg.sender_wxid
        cmsg.actual_user_nickname = cmsg.sender_wxid

        logger.info(f"[WechatPadPro] 图片消息发送者信息设置完成: sender_wxid={cmsg.sender_wxid}, actual_user_id={cmsg.actual_user_id}")

        # 解析图片信息
        try:
            xml_content_to_parse = ""
            # 现在cmsg.content应该已经是纯XML内容了
            if isinstance(cmsg.content, str) and (cmsg.content.startswith('<?xml') or cmsg.content.startswith("<msg>")):
                xml_content_to_parse = cmsg.content
                logger.debug(f"[WechatPadPro] 图片消息XML内容长度: {len(xml_content_to_parse)}")
            # Add handling if cmsg.content might be bytes that need decoding
            elif isinstance(cmsg.content, bytes):
                try:
                    xml_content_to_parse = cmsg.content.decode('utf-8')
                    if not (xml_content_to_parse.startswith('<?xml') or xml_content_to_parse.startswith("<msg>")):
                        xml_content_to_parse = "" # Not valid XML
                except UnicodeDecodeError:
                    logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Image content is bytes but failed to decode as UTF-8.")
                    xml_content_to_parse = ""
            else:
                # 如果内容仍然不是XML格式，记录详细信息
                logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Image content is not XML after processing. Content type: {type(cmsg.content)}, starts with: {str(cmsg.content)[:50] if cmsg.content else 'None'}")

            if xml_content_to_parse:
                try:
                    root = ET.fromstring(xml_content_to_parse)
                    img_element = root.find('img')
                    if img_element is not None:
                        # MODIFICATION START: Store aeskey and other info on cmsg directly
                        cmsg.img_aeskey = img_element.get('aeskey')
                        cmsg.img_cdnthumbaeskey = img_element.get('cdnthumbaeskey') # Optional
                        cmsg.img_md5 = img_element.get('md5') # Optional
                        cmsg.img_length = img_element.get('length', '0')
                        cmsg.img_cdnmidimgurl = img_element.get('cdnmidimgurl', '')
                        # MODIFICATION END

                        # Use a combined dictionary for logging for clarity
                        cmsg.image_info = {
                            'aeskey': cmsg.img_aeskey,
                            'cdnmidimgurl': cmsg.img_cdnmidimgurl,
                            'length': cmsg.img_length,
                            'md5': cmsg.img_md5
                        }
                        logger.debug(f"[{self.name}] Msg {cmsg.msg_id}: Parsed image XML: aeskey={cmsg.img_aeskey}, length={cmsg.img_length}, md5={cmsg.img_md5}")

                        if not cmsg.img_aeskey:
                             logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Image XML 'aeskey' is missing. Caching by aeskey will not be possible.")
                    else:
                        logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: XML in content but no <img> tag found. Content (first 100): {xml_content_to_parse[:100]}")
                        # Initialize attributes on cmsg to prevent AttributeError later
                        cmsg.img_aeskey = None
                        cmsg.img_length = '0'
                        # Create a default image_info for compatibility if other parts expect it
                        cmsg.image_info = {'aeskey': '', 'cdnmidimgurl': '', 'length': '0', 'md5': ''}
                except ET.ParseError as xml_err:
                    logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Failed to parse image XML: {xml_err}. Content (first 100): {xml_content_to_parse[:100]}")
                    cmsg.img_aeskey = None
                    cmsg.img_length = '0'
                    cmsg.image_info = {'aeskey': '', 'cdnmidimgurl': '', 'length': '0', 'md5': ''}
            else:
                # Content is not XML (could be a path if already processed by another layer, or unexpected format)
                logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Image content is not XML. Content (first 100): {str(cmsg.content)[:100]}")
                cmsg.img_aeskey = None # Ensure it's defined
                cmsg.img_length = '0'
                cmsg.image_info = {'aeskey': '', 'cdnmidimgurl': '', 'length': '0', 'md5': ''} # Default

            # Download logic (largely from your snippet)
            # Check if image_path is already set and valid
            if hasattr(cmsg, 'image_path') and cmsg.image_path and os.path.exists(cmsg.image_path):
                logger.info(f"[{self.name}] Msg {cmsg.msg_id}: Image already exists at path: {cmsg.image_path}")
            else:

                locks_tmp_dir = os.path.join(os.path.dirname(self.image_cache_dir) if hasattr(self, 'image_cache_dir') else os.path.join(os.getcwd(), "tmp"), "img_locks")

                try:
                    os.makedirs(locks_tmp_dir, exist_ok=True)
                except Exception as e_mkdir:
                     logger.error(f"[{self.name}] Failed to create lock directory {locks_tmp_dir}: {e_mkdir}")
                     # Potentially skip download if lock dir cannot be made, or try without lock

                lock_file = os.path.join(locks_tmp_dir, f"img_{cmsg.msg_id}.lock")

                if os.path.exists(lock_file):
                    # Check lock file age, could be stale
                    try:
                        lock_time = os.path.getmtime(lock_file)
                        if (time.time() - lock_time) < 300: # 5-minute timeout for stale lock
                            logger.info(f"[{self.name}] Image {cmsg.msg_id} is likely being downloaded by another thread (lock active). Skipping.")
                            return # Skip if lock is recent
                        else:
                            logger.warning(f"[{self.name}] Image {cmsg.msg_id} lock file is stale. Removing and attempting download.")
                            os.remove(lock_file)
                    except Exception as e_lock_check:
                        logger.warning(f"[{self.name}] Error checking stale lock for {cmsg.msg_id}: {e_lock_check}. Proceeding with caution.")

                download_attempted = False
                try:
                    # Create lock file
                    with open(lock_file, "w") as f:
                        f.write(str(time.time()))

                    download_attempted = True
                    logger.info(f"[{self.name}] Msg {cmsg.msg_id}: Attempting to download image.")
                    # Asynchronously download the image
                    # _download_image should set cmsg.image_path upon success
                    await self._download_image(cmsg)

                except Exception as e:
                    logger.error(f"[{self.name}] Msg {cmsg.msg_id}: Failed to download image: {e}")
                    logger.error(traceback.format_exc())
                finally:
                    if download_attempted: # Only remove lock if we attempted to create it
                        try:
                            if os.path.exists(lock_file):
                                os.remove(lock_file)
                        except Exception as e:
                            logger.error(f"[{self.name}] Msg {cmsg.msg_id}: Failed to remove lock file {lock_file}: {e}")

        except Exception as e_outer: # Catch errors in the outer XML parsing/setup
            logger.error(f"[{self.name}] Msg {cmsg.msg_id}: Major error in _process_image_message: {e_outer}")
            logger.error(traceback.format_exc())
            # Ensure default attributes if parsing failed badly
            if not hasattr(cmsg, 'img_aeskey'): cmsg.img_aeskey = None
            if not hasattr(cmsg, 'image_info'):
                cmsg.image_info = {'aeskey': '', 'cdnmidimgurl': '', 'length': '0', 'md5': ''}


        # This logging and recent_image_msgs update should happen regardless of download success
        # as the message itself was an image message.
        logger.info(f"[{self.name}] Processed image message (ID:{cmsg.msg_id} From:{cmsg.from_user_id} Sender:{cmsg.sender_wxid} ActualUser:{cmsg.actual_user_id})")

        # Record recently received image messages
        # Ensure actual_user_id is set for session_id
        session_user_id = cmsg.actual_user_id if hasattr(cmsg, 'actual_user_id') and cmsg.actual_user_id else cmsg.from_user_id

        # Use self.received_msgs or a dedicated dict for image contexts for plugins
        # self.recent_image_msgs was initialized in __init__
        if hasattr(self, 'recent_image_msgs') and session_user_id:
            self.recent_image_msgs[session_user_id] = cmsg # Store the WX849Message object
            logger.info(f"[{self.name}] Recorded image message context for session {session_user_id} (MsgID: {cmsg.msg_id}).")


        # Final check and update of cmsg properties if image was successfully downloaded and path is set
        if hasattr(cmsg, 'image_path') and cmsg.image_path and os.path.exists(cmsg.image_path):
            cmsg.content = cmsg.image_path # Update content to be the path
            cmsg.ctype = ContextType.IMAGE # Ensure ctype is IMAGE
            logger.info(f"[{self.name}] Msg {cmsg.msg_id}: Final image path set to: {cmsg.image_path}")
        else:
            logger.warning(f"[{self.name}] Msg {cmsg.msg_id}: Image path not available after processing. Image download might have failed or was skipped.")


    async def _download_image(self, cmsg):
        """下载图片并设置本地路径"""
        try:
            # 检查是否已经有图片路径
            if hasattr(cmsg, 'image_path') and cmsg.image_path and os.path.exists(cmsg.image_path):
                logger.info(f"[WechatPadPro] 图片已存在，路径: {cmsg.image_path}")
                return True

            # 创建临时目录
            tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp", "wechatpadpro_img_cache")
            os.makedirs(tmp_dir, exist_ok=True)

            # 检查是否已经存在相同的图片文件
            msg_id = cmsg.msg_id
            existing_files = [f for f in os.listdir(tmp_dir) if f.startswith(f"img_{msg_id}_")]

            if existing_files:
                # 找到最新的文件
                latest_file = sorted(existing_files, key=lambda x: os.path.getmtime(os.path.join(tmp_dir, x)), reverse=True)[0]
                existing_path = os.path.join(tmp_dir, latest_file)

                # 检查文件是否有效
                if os.path.exists(existing_path) and os.path.getsize(existing_path) > 0:
                    try:
                        from PIL import Image
                        try:
                            # 尝试打开图片文件
                            with Image.open(existing_path) as img:
                                # 获取图片格式和大小
                                img_format = img.format
                                img_size = img.size
                                logger.info(f"[WechatPadPro] 图片已存在且有效: 格式={img_format}, 大小={img_size}")

                                # 设置图片本地路径
                                cmsg.image_path = existing_path
                                cmsg.content = existing_path
                                cmsg.ctype = ContextType.IMAGE
                                cmsg._prepared = True

                                logger.info(f"[WechatPadPro] 使用已存在的图片文件: {existing_path}")
                                return True
                        except Exception as img_err:
                            logger.warning(f"[WechatPadPro] 已存在的图片文件无效，重新下载: {img_err}")
                    except ImportError:
                        # 如果PIL库未安装，假设文件有效
                        if os.path.getsize(existing_path) > 10000:  # 至少10KB
                            cmsg.image_path = existing_path
                            cmsg.content = existing_path
                            cmsg.ctype = ContextType.IMAGE
                            cmsg._prepared = True

                            logger.info(f"[WechatPadPro] 使用已存在的图片文件: {existing_path}")
                            return True

            # 生成图片文件名
            image_filename = f"img_{cmsg.msg_id}_{int(time.time())}.jpg"
            image_path = os.path.join(tmp_dir, image_filename)

            # 使用CDN下载图片
            logger.info(f"[WechatPadPro8059] 使用CDN下载图片")

            # 从XML中提取CDN信息
            cdn_info = self._extract_cdn_info_from_xml(cmsg.content)
            if cdn_info and cdn_info.get('cdn_url') and cdn_info.get('aes_key'):
                logger.info(f"[WechatPadPro8059] 使用CDN下载: URL={cdn_info['cdn_url'][:50]}..., AesKey={cdn_info['aes_key'][:20]}...")
                result = await self._download_image_by_cdn(cmsg, image_path, cdn_info)
                return result
            else:
                logger.error(f"[WechatPadPro8059] 无法从XML中提取CDN信息，图片下载失败")
                return False

        except Exception as e:
            logger.error(f"[WechatPadPro] 下载图片过程中出错: {e}")
            logger.error(traceback.format_exc())
            return False

    def _extract_cdn_info_from_xml(self, xml_content: str) -> dict:
        """从XML内容中提取CDN信息

        Args:
            xml_content (str): 图片消息的XML内容

        Returns:
            dict: CDN信息，包含cdn_url, aes_key等
        """
        try:
            import xml.etree.ElementTree as ET

            # 解析XML
            root = ET.fromstring(xml_content)
            img_element = root.find('img')

            if img_element is None:
                logger.warning(f"[WechatPadPro8059] XML中未找到img元素")
                return {}

            cdn_info = {}

            # 提取AES密钥
            aes_key = img_element.get('aeskey')
            if aes_key:
                cdn_info['aes_key'] = aes_key

            # 提取CDN URL - 优先使用中等尺寸图片，回退到缩略图
            cdn_mid_url = img_element.get('cdnmidimgurl')
            cdn_thumb_url = img_element.get('cdnthumburl')

            if cdn_mid_url:
                cdn_info['cdn_url'] = cdn_mid_url
                cdn_info['url_type'] = 'mid'
                logger.debug(f"[WechatPadPro8059] 使用中等尺寸CDN URL")
            elif cdn_thumb_url:
                cdn_info['cdn_url'] = cdn_thumb_url
                cdn_info['url_type'] = 'thumb'
                logger.debug(f"[WechatPadPro8059] 使用缩略图CDN URL")

            # 提取其他有用信息
            length = img_element.get('length')
            if length:
                try:
                    cdn_info['length'] = int(length)
                except ValueError:
                    pass

            md5 = img_element.get('md5')
            if md5:
                cdn_info['md5'] = md5

            logger.debug(f"[WechatPadPro8059] 提取到CDN信息: {cdn_info}")
            return cdn_info

        except Exception as e:
            logger.error(f"[WechatPadPro8059] 解析XML提取CDN信息失败: {e}")
            return {}

    async def _download_image_by_cdn(self, cmsg: WechatPadProMessage, image_path: str, cdn_info: dict) -> bool:
        """使用CDN接口下载图片

        Args:
            cmsg: 消息对象
            image_path: 保存路径
            cdn_info: CDN信息

        Returns:
            bool: 下载是否成功
        """
        try:
            import os
            import base64
            from io import BytesIO
            from PIL import Image, UnidentifiedImageError

            # 确保目标目录存在
            target_dir = os.path.dirname(image_path)
            os.makedirs(target_dir, exist_ok=True)

            cdn_url = cdn_info['cdn_url']
            aes_key = cdn_info['aes_key']

            logger.info(f"[WechatPadPro8059] 开始CDN下载图片: msg_id={cmsg.msg_id}")

            # 使用8059协议的CDN下载方法
            if hasattr(self, 'bot') and self.bot:
                # 尝试使用send_cdn_download方法
                try:
                    # 确定文件类型：0=默认, 1=缩略图, 2=正常图, 3=高清图, 4=视频, 5=其他文件
                    # 根据CDN URL类型选择合适的文件类型
                    url_type = cdn_info.get('url_type', 'mid')
                    if url_type == 'thumb':
                        file_type = 1  # 缩略图
                    elif url_type == 'mid':
                        file_type = 2  # 正常图
                    else:
                        file_type = 2  # 默认使用正常图

                    logger.info(f"[WechatPadPro8059] CDN下载参数: aes_key={aes_key[:20]}..., file_type={file_type}, file_url={cdn_url[:50]}...")
                    result = await self.bot.send_cdn_download(aes_key, file_type, cdn_url)

                    if result:
                        # 处理下载结果
                        image_data = None

                        # 8059协议库的send_cdn_download方法在成功时直接返回Data部分
                        if isinstance(result, dict):
                            # 直接从result中获取FileData
                            image_data = result.get("FileData")
                            if image_data:
                                logger.info(f"[WechatPadPro8059] 获取到图片数据，长度: {len(image_data)}")
                            else:
                                logger.error(f"[WechatPadPro8059] FileData字段为空")
                                return False
                        else:
                            logger.error(f"[WechatPadPro8059] CDN响应格式错误: {type(result)}")
                            return False

                        if image_data:
                            if isinstance(image_data, str):
                                # Base64解码
                                try:
                                    # 清理可能的前缀（如 "data:image/jpeg;base64,"）
                                    if ',' in image_data and 'base64' in image_data:
                                        image_data = image_data.split(',', 1)[1]

                                    # 清理空白字符
                                    image_data = image_data.strip()

                                    logger.info(f"[WechatPadPro8059] 开始Base64解码，数据长度: {len(image_data)}")
                                    image_bytes = base64.b64decode(image_data)
                                    logger.info(f"[WechatPadPro8059] Base64解码成功，图片字节长度: {len(image_bytes)}")
                                except Exception as decode_err:
                                    logger.error(f"[WechatPadPro8059] CDN图片Base64解码失败: {decode_err}")
                                    logger.error(f"[WechatPadPro8059] Base64数据前100字符: {image_data[:100]}")
                                    return False
                            elif isinstance(image_data, bytes):
                                image_bytes = image_data
                                logger.info(f"[WechatPadPro8059] 直接使用字节数据，长度: {len(image_bytes)}")
                            else:
                                logger.error(f"[WechatPadPro8059] CDN返回的图片数据格式未知: {type(image_data)}")
                                return False

                            # 验证图片数据
                            if not image_bytes:
                                logger.error(f"[WechatPadPro8059] CDN返回的图片数据为空")
                                return False

                            # 验证并确定图片格式
                            try:
                                with Image.open(BytesIO(image_bytes)) as img:
                                    img_format = img.format
                                    img_size = img.size

                                    # 确定正确的文件扩展名
                                    if img_format in ['JPEG', 'JPG']:
                                        correct_ext = '.jpg'
                                    elif img_format == 'PNG':
                                        correct_ext = '.png'
                                    elif img_format == 'GIF':
                                        correct_ext = '.gif'
                                    elif img_format == 'WEBP':
                                        correct_ext = '.webp'
                                    else:
                                        # 默认保存为JPG
                                        correct_ext = '.jpg'
                                        logger.info(f"[WechatPadPro8059] 未知图片格式 {img_format}，默认保存为JPG")

                                    # 检查并修正文件路径扩展名
                                    current_ext = os.path.splitext(image_path)[1].lower()
                                    if current_ext != correct_ext:
                                        # 修正文件路径
                                        base_path = os.path.splitext(image_path)[0]
                                        image_path = base_path + correct_ext
                                        logger.info(f"[WechatPadPro8059] 修正文件扩展名为: {correct_ext}")

                                    logger.info(f"[WechatPadPro8059] 图片格式验证成功: 格式={img_format}, 大小={img_size}")

                            except UnidentifiedImageError as img_err:
                                logger.error(f"[WechatPadPro8059] CDN下载的图片无法识别: {img_err}")
                                return False

                            # 写入文件
                            try:
                                with open(image_path, 'wb') as f:
                                    f.write(image_bytes)
                                logger.info(f"[WechatPadPro8059] 图片文件写入成功: {image_path}")
                            except Exception as write_err:
                                logger.error(f"[WechatPadPro8059] 图片文件写入失败: {write_err}")
                                return False

                            # 最终验证保存的文件
                            try:
                                with Image.open(image_path) as img:
                                    img_format = img.format
                                    img_size = img.size
                                logger.info(f"[WechatPadPro8059] CDN图片下载成功: 格式={img_format}, 大小={img_size}, 路径={image_path}")

                                # 设置消息属性
                                cmsg.image_path = image_path
                                cmsg.content = image_path
                                cmsg.ctype = ContextType.IMAGE
                                cmsg._prepared = True

                                return True

                            except Exception as final_err:
                                logger.error(f"[WechatPadPro8059] 保存的图片文件验证失败: {final_err}")
                                if os.path.exists(image_path):
                                    os.remove(image_path)
                                return False
                        else:
                            logger.error(f"[WechatPadPro8059] CDN下载结果中未找到图片数据")
                            return False
                    else:
                        logger.error(f"[WechatPadPro8059] CDN下载返回空结果")
                        return False

                except Exception as cdn_err:
                    logger.error(f"[WechatPadPro8059] CDN下载异常: {cdn_err}")
                    return False
            else:
                logger.error(f"[WechatPadPro8059] 8059协议客户端(self.bot)未初始化，无法使用CDN下载")
                return False

        except Exception as e:
            logger.error(f"[WechatPadPro8059] CDN图片下载过程中出错: {e}")
            return False

    async def _download_image_with_details(self, image_meta: dict, target_path: str) -> bool:
        """
        Downloads an image using detailed metadata, typically for referenced images.
        Uses chunked download.

        :param image_meta: Dict containing keys like 'msg_id_for_download', 'data_len',
                           'aeskey', 'downloader_wxid', 'original_sender_wxid'.
        :param target_path: Full path where the image should be saved.
        :return: True if download and verification are successful, False otherwise.
        """
        import traceback
        import asyncio
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError

        logger.info(f"[{self.name}] Attempting download with details: {image_meta} to {target_path}")

        try:
            # 1. Pre-check: Validate target_path and create directory
            tmp_dir = os.path.dirname(target_path)
            os.makedirs(tmp_dir, exist_ok=True)

            # 2. Get API config and calculate chunk info
            api_host = conf().get("wechatpadpro_api_host", "127.0.0.1")
            # For image downloads, often a specific media port is used, check if it's configured
            api_port = conf().get("wechatpadpro_api_port", conf().get("wechatpadpro_api_port", 8059))
            protocol_version = conf().get("wechatpadpro_protocol_version", "8059")
            api_path_prefix = "/api" if protocol_version in ["855", "ipad"] else "/VXAPI"

            data_len_str = image_meta.get('data_len', '0')
            try:
                data_len = int(data_len_str)
            except ValueError:
                logger.error(f"[{self.name}] Invalid data_len '{data_len_str}' in image_meta. Using default 0.")
                data_len = 0

            if data_len <= 0: # If data_len is 0 or invalid, try a default or log an error
                logger.warning(f"[{self.name}] data_len is {data_len}. Download might be problematic or rely on API to handle it.")
                # Fallback or error handling for zero data_len might be needed depending on API behavior

            chunk_size = 65536  # 64KB
            num_chunks = (data_len + chunk_size - 1) // chunk_size if data_len > 0 else 1
            if data_len == 0 and num_chunks == 1: # Special case for potentially unknown length but expecting at least one chunk
                 logger.info(f"[{self.name}] data_len is 0, attempting to download as a single chunk of default size or as determined by API.")


            logger.info(f"[{self.name}] Downloading referenced image to: {target_path}, Total Size: {data_len} B, Chunks: {num_chunks}")

            # 3. Chunked download logic
            all_chunks_data_list = []
            download_stream_successful = True
            actual_downloaded_size = 0

            for i in range(num_chunks):
                start_pos = i * chunk_size
                current_chunk_size = min(chunk_size, data_len - start_pos) if data_len > 0 else chunk_size # Default to chunk_size if data_len is unknown

                if data_len > 0 and current_chunk_size <= 0: # Ensure we don't try to download 0 bytes if data_len was positive
                    logger.debug(f"[{self.name}] Calculated current_chunk_size <=0 with positive data_len. Breaking chunk loop. StartPos: {start_pos}, DataLen: {data_len}")
                    break

                # Ensure msg_id_for_download is an integer for the API call
                msg_id_for_api = None
                try:
                    msg_id_for_api = int(image_meta['msg_id_for_download'])
                except (ValueError, TypeError) as e:
                    logger.error(f"[{self.name}] RefDownload Chunk {i+1} Error: 'msg_id_for_download' ({image_meta.get('msg_id_for_download')}) is not a valid integer: {e}")
                    download_stream_successful = False
                    break

                params = {
                    "MsgId": msg_id_for_api, # MODIFIED: Use the integer version
                    "ToWxid": image_meta.get('original_sender_wxid'), # The user who originally sent the image
                    "Wxid": image_meta.get('downloader_wxid', self.wxid), # The WXID doing the download (our bot)
                    "DataLen": data_len,
                    "CompressType": 0,
                    "Section": {"StartPos": start_pos, "DataLen": current_chunk_size}
                }
                # Add aeskey if present and non-empty
                if image_meta.get('aeskey'):
                    params["Aeskey"] = image_meta['aeskey']

                api_url = f"http://{api_host}:{api_port}{api_path_prefix}/Tools/DownloadImg"
                logger.debug(f"[{self.name}] RefDownload Chunk {i+1}/{num_chunks}: URL={api_url}, Params={params}")

                try:
                    async with aiohttp.ClientSession() as session:
                        # Increased timeout for potentially slow media downloads
                        async with session.post(api_url, json=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                            if response.status != 200:
                                full_error_text = await response.text()
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1} HTTP Error: {response.status}, Response: {full_error_text[:500]}")
                                download_stream_successful = False
                                break

                            try:
                                result = await response.json()
                            except aiohttp.ContentTypeError:
                                raw_response_text = await response.text()
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1} API Error: Non-JSON response. Status: {response.status}. Response text (first 500 chars): {raw_response_text[:500]}")
                                download_stream_successful = False
                                break

                            if not result or not isinstance(result, dict):
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1} API Error: Invalid or empty JSON response. FullResult: {result}")
                                download_stream_successful = False
                                break

                            if not result.get("Success", False):
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1} API Error: {result.get('Message', 'Unknown API error')}, FullResult: {result}")
                                download_stream_successful = False
                                break

                            data_payload = result.get("Data", {})
                            chunk_base64 = None
                            if isinstance(data_payload, dict):
                                if "buffer" in data_payload: chunk_base64 = data_payload["buffer"]
                                elif "data" in data_payload and isinstance(data_payload.get("data"), dict) and "buffer" in data_payload["data"]: chunk_base64 = data_payload["data"]["buffer"]
                                else:
                                    for field in ["Chunk", "Image", "Data", "FileData"]: # Common field names
                                        if field in data_payload: chunk_base64 = data_payload.get(field); break
                            elif isinstance(data_payload, str): # Direct base64 string
                                chunk_base64 = data_payload

                            if not chunk_base64 and isinstance(result, dict): # Fallback to check root result
                                 for field in ["data", "Data", "FileData", "Image"]:
                                     if field in result and result.get(field): chunk_base64 = result.get(field); break

                            if not chunk_base64:
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1} Error: No image data found in API response. Response: {str(result)[:200]}")
                                download_stream_successful = False
                                break

                            try:
                                if not isinstance(chunk_base64, str):
                                    if isinstance(chunk_base64, bytes):
                                        try: chunk_base64 = chunk_base64.decode('utf-8')
                                        except UnicodeDecodeError: raise ValueError("chunk_base64 is bytes but cannot be utf-8 decoded.")
                                    else: raise ValueError(f"chunk_base64 is not str or bytes: {type(chunk_base64)}")

                                clean_base64 = chunk_base64.strip()
                                padding = (4 - len(clean_base64) % 4) % 4
                                clean_base64 += '=' * padding
                                chunk_data_bytes = base64.b64decode(clean_base64)
                                all_chunks_data_list.append(chunk_data_bytes)
                                actual_downloaded_size += len(chunk_data_bytes)
                                logger.debug(f"[{self.name}] RefDownload Chunk {i+1}/{num_chunks} decoded, size: {len(chunk_data_bytes)} B. Total so far: {actual_downloaded_size} B")
                            except Exception as decode_err:
                                logger.error(f"[{self.name}] RefDownload Chunk {i+1}/{num_chunks} Base64 decode error: {decode_err}. Data (first 100): {str(chunk_base64)[:100]}")
                                download_stream_successful = False
                                break
                except asyncio.TimeoutError:
                    logger.error(f"[{self.name}] RefDownload Chunk {i+1} timed out.")
                    download_stream_successful = False
                    break
                except Exception as api_call_err:
                    logger.error(f"[{self.name}] RefDownload Chunk {i+1} API call error: {api_call_err}\n{traceback.format_exc()}")
                    download_stream_successful = False
                    break

            # 4. Data writing, flushing, and syncing
            file_written_successfully = False
            if download_stream_successful and all_chunks_data_list:
                try:
                    with open(target_path, "wb") as f_write:
                        for chunk_piece in all_chunks_data_list:
                            f_write.write(chunk_piece)
                        f_write.flush()
                        if hasattr(os, 'fsync'): # fsync might not be available on all OS (e.g. some Windows setups)
                            try:
                                os.fsync(f_write.fileno())
                            except OSError as e_fsync:
                                logger.warning(f"[{self.name}] os.fsync failed for {target_path}: {e_fsync}. Continuing without fsync.")
                        else:
                            logger.debug(f"[{self.name}] os.fsync not available on this system.")

                    final_file_size = os.path.getsize(target_path)
                    logger.info(f"[{self.name}] RefDownload: All chunks written to disk: {target_path}, Actual Final Size: {final_file_size} B (Expected: {data_len} B, Downloaded: {actual_downloaded_size} B)")
                    if final_file_size == 0 and actual_downloaded_size > 0:
                        logger.error(f"[{self.name}] RefDownload WARNING: Data downloaded ({actual_downloaded_size}B) but written file size is 0! Path: {target_path}")
                    else:
                        file_written_successfully = True
                except IOError as io_err_write_final:
                    logger.error(f"[{self.name}] RefDownload: Failed to write or flush image file: {io_err_write_final}, Path: {target_path}")
                except Exception as e_write_final:
                    logger.error(f"[{self.name}] RefDownload: Unknown error during file write: {e_write_final}, Path: {target_path}\n{traceback.format_exc()}")
            elif not all_chunks_data_list and download_stream_successful:
                logger.warning(f"[{self.name}] RefDownload: API calls successful, but no data chunks collected for {target_path}.")

            # 5. Image Verification Stage
            if file_written_successfully:
                await asyncio.sleep(0.1) # Brief pause to ensure file system operations complete
                try:
                    with open(target_path, "rb") as f_read_verify_final:
                        image_bytes_for_verify_final = f_read_verify_final.read()

                    if not image_bytes_for_verify_final:
                        logger.error(f"[{self.name}] RefDownload: Image file empty after download and read for verification: {target_path}")
                        raise UnidentifiedImageError("Downloaded image file is empty for verification.")

                    with Image.open(BytesIO(image_bytes_for_verify_final)) as img_final:
                        img_format_final = img_final.format
                        img_size_final = img_final.size
                        logger.info(f"[{self.name}] RefDownload: Image verification successful (PIL): Format={img_format_final}, Size={img_size_final}, Path={target_path}")
                        return True
                except UnidentifiedImageError as unident_err_final:
                    logger.error(f"[{self.name}] RefDownload: Image verification failed (PIL UnidentifiedImageError): {unident_err_final}, File: {target_path}")
                    if os.path.exists(target_path): os.remove(target_path)
                    return False
                except ImportError: # Should have been caught earlier, but as a safeguard
                    logger.warning("[WechatPadPro] RefDownload: PIL (Pillow) library not installed, cannot perform strict image verification.")
                    fsize_final_no_pil = os.path.getsize(target_path) if os.path.exists(target_path) else 0
                    if fsize_final_no_pil > 1000: # Heuristic: >1KB might be a valid small image
                        logger.info(f"[{self.name}] RefDownload: Image download likely complete (No PIL verification, size: {fsize_final_no_pil}B), Path: {target_path}")
                        return True
                    else:
                        logger.warning(f"[{self.name}] RefDownload: PIL not installed AND file size ({fsize_final_no_pil}B) is too small. Invalid: {target_path}")
                        if os.path.exists(target_path): os.remove(target_path)
                        return False
                except Exception as pil_verify_err_final:
                    logger.error(f"[{self.name}] RefDownload: Unknown PIL verification error: {pil_verify_err_final}, File: {target_path}\n{traceback.format_exc()}")
                    if os.path.exists(target_path): os.remove(target_path)
                    return False

            # 6. Final Failure Path (if not returned True already)
            logger.error(f"[{self.name}] RefDownload: Image download or verification failed. StreamOK={download_stream_successful}, WrittenOK={file_written_successfully}, DataCollected={bool(all_chunks_data_list)}. Path: {target_path}")
            if os.path.exists(target_path): # Cleanup if file exists but process failed
                try:
                    os.remove(target_path)
                    logger.info(f"[{self.name}] RefDownload: Deleted failed/unverified image file: {target_path}")
                except Exception as e_remove_cleanup:
                    logger.error(f"[{self.name}] RefDownload: Error deleting failed image file: {e_remove_cleanup}, Path: {target_path}")
            return False

        except Exception as outer_e_details:
            logger.critical(f"[{self.name}] _download_image_with_details: Critical unexpected error: {outer_e_details}\n{traceback.format_exc()}")
            path_to_cleanup_outer = target_path
            if path_to_cleanup_outer and os.path.exists(path_to_cleanup_outer):
                try: os.remove(path_to_cleanup_outer)
                except Exception as e_remove_critical: logger.error(f"[{self.name}] Critical error: Failed to cleanup {path_to_cleanup_outer}: {e_remove_critical}")
            return False

    def _get_image(self, msg_id):
        """获取图片数据"""
        # 查找图片文件
        tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp", "wechatpadpro_img_cache")

        # 查找匹配的图片文件
        if os.path.exists(tmp_dir):
            for filename in os.listdir(tmp_dir):
                if filename.startswith(f"img_{msg_id}_"):
                    image_path = os.path.join(tmp_dir, filename)
                    try:
                        # 验证图片文件是否为有效的图片格式
                        try:
                            from PIL import Image
                            try:
                                # 尝试打开图片文件
                                with Image.open(image_path) as img:
                                    # 获取图片格式和大小
                                    img_format = img.format
                                    img_size = img.size
                                    logger.info(f"[WechatPadPro] 图片验证成功: 格式={img_format}, 大小={img_size}")
                            except Exception as img_err:
                                logger.error(f"[WechatPadPro] 图片验证失败，可能不是有效的图片文件: {img_err}")
                                # 尝试修复图片文件
                                try:
                                    # 读取文件内容
                                    with open(image_path, "rb") as f:
                                        img_data = f.read()

                                    # 尝试查找JPEG文件头和尾部标记
                                    jpg_header = b'\xff\xd8'
                                    jpg_footer = b'\xff\xd9'

                                    if img_data.startswith(jpg_header) and img_data.endswith(jpg_footer):
                                        logger.info(f"[WechatPadPro] 图片文件有效的JPEG头尾标记，但内部可能有损坏")
                                    else:
                                        # 查找JPEG头部标记的位置
                                        header_pos = img_data.find(jpg_header)
                                        if header_pos >= 0:
                                            # 查找JPEG尾部标记的位置
                                            footer_pos = img_data.rfind(jpg_footer)
                                            if footer_pos > header_pos:
                                                # 提取有效的JPEG数据
                                                valid_data = img_data[header_pos:footer_pos+2]
                                                # 重写文件
                                                with open(image_path, "wb") as f:
                                                    f.write(valid_data)
                                                logger.info(f"[WechatPadPro] 尝试修复图片文件，提取了 {len(valid_data)} 字节的有效JPEG数据")
                                                # 返回修复后的数据
                                                return valid_data
                                except Exception as fix_err:
                                    logger.error(f"[WechatPadPro] 尝试修复图片文件失败: {fix_err}")
                        except ImportError:
                            logger.warning(f"[WechatPadPro] PIL库未安装，无法验证图片有效性")

                        # 读取图片文件
                        with open(image_path, "rb") as f:
                            image_data = f.read()
                            logger.info(f"[WechatPadPro] 成功读取图片文件: {image_path}, 大小: {len(image_data)} 字节")
                            return image_data
                    except Exception as e:
                        logger.error(f"[WechatPadPro] 读取图片文件失败: {e}")
                        return None

        logger.error(f"[WechatPadPro] 未找到图片文件: msg_id={msg_id}")
        return None

    def _process_voice_message(self, cmsg):
        """处理语音消息"""
        import xml.etree.ElementTree as ET
        import re

        cmsg.ctype = ContextType.VOICE

        # 保存原始内容，避免修改
        original_content = cmsg.content

        # 检查内容是否为XML格式
        is_xml_content = original_content.strip().startswith("<?xml") or original_content.strip().startswith("<msg")

        # 首先尝试从XML中提取发送者信息
        if is_xml_content:
            logger.debug(f"[WechatPadPro] 语音消息：尝试从XML提取发送者")
            try:
                # 使用正则表达式从XML字符串中提取fromusername属性或元素
                match = re.search(r'fromusername\s*=\s*["\'](.*?)["\']', original_content)
                if match:
                    cmsg.sender_wxid = match.group(1)
                    logger.debug(f"[WechatPadPro] 语音消息：从XML属性提取的发送者ID: {cmsg.sender_wxid}")
                else:
                    # 尝试从元素中提取
                    match = re.search(r'<fromusername>(.*?)</fromusername>', original_content)
                    if match:
                        cmsg.sender_wxid = match.group(1)
                        logger.debug(f"[WechatPadPro] 语音消息：从XML元素提取的发送者ID: {cmsg.sender_wxid}")
                    else:
                        logger.debug("[WechatPadPro] 语音消息：未找到fromusername")

                        # 尝试使用ElementTree解析
                        try:
                            root = ET.fromstring(original_content)
                            # 尝试查找语音元素的fromusername属性
                            voice_element = root.find('voicemsg')
                            if voice_element is not None and 'fromusername' in voice_element.attrib:
                                cmsg.sender_wxid = voice_element.attrib['fromusername']
                                logger.debug(f"[WechatPadPro] 语音消息：使用ElementTree提取的发送者ID: {cmsg.sender_wxid}")
                        except Exception as e:
                            logger.debug(f"[WechatPadPro] 语音消息：使用ElementTree解析失败: {e}")
            except Exception as e:
                logger.debug(f"[WechatPadPro] 语音消息：提取发送者失败: {e}")

        # 如果无法从XML提取，再尝试传统的分割方法
        if not cmsg.sender_wxid and (cmsg.is_group or cmsg.from_user_id.endswith("@chatroom")):
            cmsg.is_group = True
            split_content = original_content.split(":\n", 1)
            if len(split_content) > 1:
                cmsg.sender_wxid = split_content[0]
                logger.debug(f"[WechatPadPro] 语音消息：使用分割方法提取的发送者ID: {cmsg.sender_wxid}")
            else:
                # 处理没有换行的情况
                split_content = original_content.split(":", 1)
                if len(split_content) > 1:
                    cmsg.sender_wxid = split_content[0]
                    logger.debug(f"[WechatPadPro] 语音消息：使用冒号分割提取的发送者ID: {cmsg.sender_wxid}")

        # 对于私聊消息，使用from_user_id作为发送者ID
        if not cmsg.sender_wxid and not cmsg.is_group:
            cmsg.sender_wxid = cmsg.from_user_id
            cmsg.is_group = False

        # 设置actual_user_id和actual_user_nickname
        cmsg.actual_user_id = cmsg.sender_wxid or cmsg.from_user_id
        cmsg.actual_user_nickname = cmsg.sender_wxid or cmsg.from_user_id

        # 解析语音信息 (保留此功能以获取语音URL等信息)
        try:
            root = ET.fromstring(original_content)
            voice_element = root.find('voicemsg')
            if voice_element is not None:
                cmsg.voice_info = {
                    'voiceurl': voice_element.get('voiceurl'),
                    'length': voice_element.get('length')
                }
                logger.debug(f"解析语音XML成功: voiceurl={cmsg.voice_info['voiceurl']}, length={cmsg.voice_info['length']}")
        except Exception as e:
            logger.debug(f"解析语音消息失败: {e}, 内容: {original_content[:100]}")
            cmsg.voice_info = {}

        # 确保保留原始XML内容
        cmsg.content = original_content

        # 最终检查，确保发送者不是XML内容
        if not cmsg.sender_wxid or "<" in cmsg.sender_wxid:
            cmsg.sender_wxid = "未知发送者"
            cmsg.actual_user_id = cmsg.sender_wxid
            cmsg.actual_user_nickname = cmsg.sender_wxid

        # 输出日志，显示完整XML内容
        logger.info(f"收到语音消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid}\nXML内容: {cmsg.content}")

    def _process_video_message(self, cmsg):
        """处理视频消息"""
        import xml.etree.ElementTree as ET
        import re

        cmsg.ctype = ContextType.VIDEO

        # 保存原始内容，避免修改
        original_content = cmsg.content

        # 检查内容是否为XML格式
        is_xml_content = original_content.strip().startswith("<?xml") or original_content.strip().startswith("<msg")

        # 首先尝试从XML中提取发送者信息
        if is_xml_content:
            logger.debug(f"[WechatPadPro] 视频消息：尝试从XML提取发送者")
            try:
                # 使用正则表达式从XML字符串中提取fromusername属性或元素
                match = re.search(r'fromusername\s*=\s*["\'](.*?)["\']', original_content)
                if match:
                    cmsg.sender_wxid = match.group(1)
                    logger.debug(f"[WechatPadPro] 视频消息：从XML属性提取的发送者ID: {cmsg.sender_wxid}")
                else:
                    # 尝试从元素中提取
                    match = re.search(r'<fromusername>(.*?)</fromusername>', original_content)
                    if match:
                        cmsg.sender_wxid = match.group(1)
                        logger.debug(f"[WechatPadPro] 视频消息：从XML元素提取的发送者ID: {cmsg.sender_wxid}")
                    else:
                        logger.debug("[WechatPadPro] 视频消息：未找到fromusername")

                        # 尝试使用ElementTree解析
                        try:
                            root = ET.fromstring(original_content)
                            # 尝试查找video元素的fromusername属性
                            video_element = root.find('videomsg')
                            if video_element is not None and 'fromusername' in video_element.attrib:
                                cmsg.sender_wxid = video_element.attrib['fromusername']
                                logger.debug(f"[WechatPadPro] 视频消息：使用ElementTree提取的发送者ID: {cmsg.sender_wxid}")
                        except Exception as e:
                            logger.debug(f"[WechatPadPro] 视频消息：使用ElementTree解析失败: {e}")
            except Exception as e:
                logger.debug(f"[WechatPadPro] 视频消息：提取发送者失败: {e}")

        # 如果无法从XML提取，再尝试传统的分割方法
        if not cmsg.sender_wxid and (cmsg.is_group or cmsg.from_user_id.endswith("@chatroom")):
            cmsg.is_group = True
            split_content = original_content.split(":\n", 1)
            if len(split_content) > 1:
                cmsg.sender_wxid = split_content[0]
                logger.debug(f"[WechatPadPro] 视频消息：使用分割方法提取的发送者ID: {cmsg.sender_wxid}")
            else:
                # 处理没有换行的情况
                split_content = original_content.split(":", 1)
                if len(split_content) > 1:
                    cmsg.sender_wxid = split_content[0]
                    logger.debug(f"[WechatPadPro] 视频消息：使用冒号分割提取的发送者ID: {cmsg.sender_wxid}")

        # 对于私聊消息，使用from_user_id作为发送者ID
        if not cmsg.sender_wxid and not cmsg.is_group:
            cmsg.sender_wxid = cmsg.from_user_id
            cmsg.is_group = False

        # 设置actual_user_id和actual_user_nickname
        cmsg.actual_user_id = cmsg.sender_wxid or cmsg.from_user_id
        cmsg.actual_user_nickname = cmsg.sender_wxid or cmsg.from_user_id

        # 确保保留原始XML内容
        cmsg.content = original_content

        # 最终检查，确保发送者不是XML内容
        if not cmsg.sender_wxid or "<" in cmsg.sender_wxid:
            cmsg.sender_wxid = "未知发送者"
            cmsg.actual_user_id = cmsg.sender_wxid
            cmsg.actual_user_nickname = cmsg.sender_wxid

        # 输出日志，显示完整XML内容
        logger.info(f"收到视频消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid}\nXML内容: {cmsg.content}")

    def _process_emoji_message(self, cmsg):
        """处理表情消息"""
        import xml.etree.ElementTree as ET
        import re

        cmsg.ctype = ContextType.TEXT  # 表情消息通常也用TEXT类型

        # 保存原始内容，避免修改
        original_content = cmsg.content

        # 检查内容是否为XML格式
        is_xml_content = original_content.strip().startswith("<?xml") or original_content.strip().startswith("<msg")

        # 首先尝试从XML中提取发送者信息
        if is_xml_content:
            logger.debug(f"[WechatPadPro] 表情消息：尝试从XML提取发送者")
            try:
                # 使用正则表达式从XML中提取fromusername属性
                match = re.search(r'fromusername\s*=\s*["\'](.*?)["\']', original_content)
                if match:
                    cmsg.sender_wxid = match.group(1)
                    logger.debug(f"[WechatPadPro] 表情消息：从XML提取的发送者ID: {cmsg.sender_wxid}")
                else:
                    logger.debug("[WechatPadPro] 表情消息：未找到fromusername属性")

                    # 尝试使用ElementTree解析
                    try:
                        root = ET.fromstring(original_content)
                        emoji_element = root.find('emoji')
                        if emoji_element is not None and 'fromusername' in emoji_element.attrib:
                            cmsg.sender_wxid = emoji_element.attrib['fromusername']
                            logger.debug(f"[WechatPadPro] 表情消息：使用ElementTree提取的发送者ID: {cmsg.sender_wxid}")
                    except Exception as e:
                        logger.debug(f"[WechatPadPro] 表情消息：使用ElementTree解析失败: {e}")
            except Exception as e:
                logger.debug(f"[WechatPadPro] 表情消息：提取发送者失败: {e}")

        # 如果无法从XML提取，再尝试传统的分割方法
        if not cmsg.sender_wxid and (cmsg.is_group or cmsg.from_user_id.endswith("@chatroom")):
            cmsg.is_group = True
            split_content = original_content.split(":\n", 1)
            if len(split_content) > 1:
                cmsg.sender_wxid = split_content[0]
                logger.debug(f"[WechatPadPro] 表情消息：使用分割方法提取的发送者ID: {cmsg.sender_wxid}")
            else:
                # 处理没有换行的情况
                split_content = original_content.split(":", 1)
                if len(split_content) > 1:
                    cmsg.sender_wxid = split_content[0]
                    logger.debug(f"[WechatPadPro] 表情消息：使用冒号分割提取的发送者ID: {cmsg.sender_wxid}")

        # 对于私聊消息，使用from_user_id作为发送者ID
        if not cmsg.sender_wxid and not cmsg.is_group:
            cmsg.sender_wxid = cmsg.from_user_id
            cmsg.is_group = False

        # 设置actual_user_id和actual_user_nickname
        cmsg.actual_user_id = cmsg.sender_wxid or cmsg.from_user_id
        cmsg.actual_user_nickname = cmsg.sender_wxid or cmsg.from_user_id

        # 确保保留原始XML内容
        cmsg.content = original_content

        # 最终检查，确保发送者不是XML内容
        if not cmsg.sender_wxid or "<" in cmsg.sender_wxid:
            cmsg.sender_wxid = "未知发送者"
            cmsg.actual_user_id = cmsg.sender_wxid
            cmsg.actual_user_nickname = cmsg.sender_wxid

        # 输出日志，显示完整XML内容
        logger.info(f"收到表情消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid} \nXML内容: {cmsg.content}")

    def _process_xml_message(self, cmsg: WechatPadProMessage):
        """
        处理 XML 类型的消息，主要是 Type 57 引用和 Type 5 分享链接。
        会修改 cmsg 的 ctype 和 content 属性。
        """
        import xml.etree.ElementTree as ET
        import re
        import asyncio
        import os
        import time
        import traceback
        import tempfile
        import threading
        from bridge.context import ContextType

        # 初始化msg_xml变量，确保在所有代码路径中都有定义
        msg_xml = None

        try:
            msg_xml = ET.fromstring(cmsg.content)
            appmsg = msg_xml.find("appmsg")

            # 1. 处理引用消息 (Type 57)
            if appmsg is not None and appmsg.findtext("type") == "57":
                refermsg = appmsg.find("refermsg")
                if refermsg is not None:
                    refer_type = refermsg.findtext("type")
                    title = appmsg.findtext("title") # User's question part / command
                    displayname = refermsg.findtext("displayname") # Quoter's display name

                    # 1.1 处理文本引用 (refermsg type=1)
                    if refer_type == "1":
                        quoted_text = refermsg.findtext("content")
                        if title and displayname and quoted_text:
                            # 清理群聊消息可能的前缀（如"x "、"小艾 "等）
                            # 群聊消息的content可能包含额外的前缀标记或@提及
                            import re
                            cleaned_quoted_text = quoted_text

                            # 1. 移除开头的单个字符+空格的模式（如"x "、"a "等）
                            cleaned_quoted_text = re.sub(r'^[a-zA-Z0-9]\s+', '', cleaned_quoted_text).strip()

                            # 2. 移除@提及前缀（如"小艾 "、"@小艾 "等）
                            # 匹配@符号（可选）+ 中文/英文名称 + 空格
                            cleaned_quoted_text = re.sub(r'^@?[\u4e00-\u9fff\w]+\s+', '', cleaned_quoted_text).strip()

                            # 如果清理后为空，使用原始内容
                            if not cleaned_quoted_text:
                                cleaned_quoted_text = quoted_text

                            logger.debug(f"[{self.name}] Quote content cleaning: original='{quoted_text}' -> cleaned='{cleaned_quoted_text}'")

                            prompt = (
                                f"用户针对以下消息提问：\"{title}\"\n\n"
                                f"被引用的消息来自\"{displayname}\"：\n\"{cleaned_quoted_text}\"\n\n"
                                f"请基于被引用的消息回答用户的问题。"
                            )
                            cmsg.content = prompt
                            cmsg.is_processed_text_quote = True
                            cmsg.ctype = ContextType.TEXT
                            logger.info(f"[{self.name}] Processed text quote msg {cmsg.msg_id}. Set type to TEXT.")
                            return

                    # 1.2 处理聊天记录引用 (refermsg type=49 -> inner appmsg type=19)
                    elif refer_type == "49":
                        quoted_content_raw = refermsg.findtext("content")
                        if quoted_content_raw:
                            try:
                                inner_xml_root = ET.fromstring(quoted_content_raw)
                                inner_appmsg = inner_xml_root.find("appmsg")
                                if inner_appmsg is not None and inner_appmsg.findtext("type") == "19":
                                    chat_record_desc = inner_appmsg.findtext("des")
                                    if title and displayname and chat_record_desc:
                                        prompt = (
                                            f"用户针对以下聊天记录提问：\"{title}\"\n\n"
                                            f"被引用的聊天记录来自\"{displayname}\"：\n（摘要：{chat_record_desc}）\n\n"
                                            f"请基于被引用的聊天记录内容回答用户的问题（注意：聊天记录可能包含多条消息）。"
                                        )
                                        cmsg.content = prompt
                                        cmsg.is_processed_text_quote = True
                                        cmsg.ctype = ContextType.TEXT
                                        logger.info(f"[{self.name}] Processed chat record quote msg {cmsg.msg_id}. Set type to TEXT.")
                                        return
                            except ET.ParseError:
                                logger.debug(f"[{self.name}] Inner XML parsing failed for type 49 refermsg content in msg {cmsg.msg_id}")
                            except Exception as e_inner:
                                logger.warning(f"[{self.name}] Error processing inner XML for type 49 refermsg in msg {cmsg.msg_id}: {e_inner}")

                    # MODIFICATION START: Handling for referenced image (refer_type == '3' implied by finding 'img' node)
                    elif refer_type == "3" and (quoted_content_raw := refermsg.findtext("content")):
                        # This 'elif' specifically targets Type 3 (image) references if an explicit check for refer_type is desired.
                        # The original code relied on finding an 'img' node within the quoted_content_raw.

                        original_image_svrid = refermsg.findtext("svrid") # Still useful for logging/context

                        try:
                            inner_xml_root = ET.fromstring(quoted_content_raw)
                            img_node = inner_xml_root.find("img")

                            if img_node is not None:
                                extracted_refer_aeskey = img_node.get("aeskey")
                                # title and displayname are already defined above for Type 57

                                if extracted_refer_aeskey and hasattr(self, 'image_cache_dir') and self.image_cache_dir:
                                    logger.debug(f"[{self.name}] Msg {cmsg.msg_id} (Type 57 quote) references image with aeskey: {extracted_refer_aeskey}. User command: '{title}'. Original svrid: {original_image_svrid}")

                                    found_cached_path = None
                                    # Try common extensions or the extension determined during caching
                                    # Assuming caching logic (Phase A3) saves with original extension or defaults to .jpg
                                    # Let's try common ones, prioritising .jpg
                                    possible_extensions = ['.jpg', '.jpeg', '.png', '.gif']
                                    # A more robust way would be to store file extension along with aeskey if it can vary
                                    # or ensure a consistent extension like .jpg during caching.

                                    for ext in possible_extensions:
                                        # Ensure consistent naming with caching logic (Phase A3)
                                        # Example: cached_file_name = f"{cmsg.img_aeskey}{file_extension}"
                                        potential_path = os.path.join(self.image_cache_dir, f"{extracted_refer_aeskey}{ext}")
                                        if os.path.exists(potential_path):
                                            found_cached_path = potential_path
                                            break

                                    if found_cached_path:
                                        logger.info(f"[{self.name}] Found cached image for aeskey {extracted_refer_aeskey} at {found_cached_path} for msg {cmsg.msg_id}")

                                        cmsg.content = title if title else ""
                                        cmsg.ctype = ContextType.TEXT
                                        cmsg.original_user_question = title if title else ""
                                        cmsg.referenced_image_path = found_cached_path
                                        cmsg.is_processed_image_quote = True

                                        if displayname:
                                            cmsg.quoter_display_name = displayname
                                        cmsg.quoted_image_id = extracted_refer_aeskey # Using aeskey as a quoted image identifier

                                        logger.info(f"[{self.name}] Successfully processed referenced image (from cache) for msg {cmsg.msg_id}. Set ctype=TEXT. Path: {cmsg.referenced_image_path}")
                                        return # Crucial: stop further processing of this XML
                                    else:
                                        logger.warning(f"[{self.name}] Referenced image with aeskey {extracted_refer_aeskey} not found in cache ({self.image_cache_dir}) for msg {cmsg.msg_id}. Fallback: No API download configured for this path.")
                                        # If you had a working API download as fallback, it would go here.
                                        # For now, if not in cache, it will be treated as an unhandled Type 57 quote.

                                else: # extracted_refer_aeskey is None or image_cache_dir not set
                                    if not extracted_refer_aeskey:
                                        logger.warning(f"[{self.name}] Referenced image in msg {cmsg.msg_id} has no aeskey in its XML, cannot look up in cache.")
                                    if not (hasattr(self, 'image_cache_dir') and self.image_cache_dir):
                                         logger.error(f"[{self.name}] Image cache directory not configured. Cannot look up referenced image for msg {cmsg.msg_id}")

                            # else: img_node was None (not an image reference within the content)
                            # This case would also fall through.

                        except ET.ParseError as e_parse_inner:
                            logger.debug(f"[{self.name}] Failed to parse inner XML for referenced msg content in msg {cmsg.msg_id}: {e_parse_inner}. Content: {quoted_content_raw[:100] if quoted_content_raw else 'None'}")
                        except Exception as e_proc_ref_img:
                            logger.error(f"[{self.name}] Error processing potential image reference in msg {cmsg.msg_id}: {e_proc_ref_img}\n{traceback.format_exc()}")
                    # MODIFICATION END

                    # Fallback for unhandled Type 57 messages (if not text, chat record, or successfully processed image quote from cache)
                    if not (hasattr(cmsg, 'is_processed_text_quote') and cmsg.is_processed_text_quote or \
                            hasattr(cmsg, 'is_processed_image_quote') and cmsg.is_processed_image_quote):
                        logger.debug(f"[{self.name}] Unhandled Type 57 refermsg (type='{refer_type}') in msg {cmsg.msg_id}. Title: '{title}'. Will be treated as generic XML.")
                        if title:
                             cmsg.content = f"用户引用了一个消息并提问：\"{title}\" (类型：{refer_type}，未特殊处理)"
                        else:
                             cmsg.content = f"用户引用了一个未处理类型的消息 (类型：{refer_type})"
                        cmsg.ctype = ContextType.XML

            elif appmsg is not None and appmsg.findtext("type") == "5":
                url = appmsg.findtext("url")
                link_title = appmsg.findtext("title")
                if url:
                    if not url.startswith("http"):
                        url = "http:" + url if url.startswith("//") else "http://" + url
                    if "." in url and " " not in url: # Basic URL validation
                        cmsg.content = url
                        cmsg.ctype = ContextType.SHARING
                        logger.info(f"[{self.name}] Processed sharing link msg {cmsg.msg_id}. URL: {url}, Title: {link_title}")
                        return
                    else:
                         logger.warning(f"[{self.name}] Invalid URL extracted from sharing link msg {cmsg.msg_id}: {url}")
                else:
                    logger.warning(f"[{self.name}] Sharing link msg {cmsg.msg_id} has no URL.")

            # Check if any processing flag was set or if it's a sharing link
            processed_flags_true = (hasattr(cmsg, 'is_processed_text_quote') and cmsg.is_processed_text_quote) or \
                                   (hasattr(cmsg, 'is_processed_image_quote') and cmsg.is_processed_image_quote)
            is_sharing_link = hasattr(cmsg, 'ctype') and cmsg.ctype == ContextType.SHARING

            if not (processed_flags_true or is_sharing_link):

                if appmsg is not None: # Only default to XML if it was an appmsg
                    cmsg.ctype = ContextType.XML
                    logger.debug(f"[{self.name}] XML message {cmsg.msg_id} (appmsg type: {appmsg.findtext('type') if appmsg is not None else 'N/A'}) not specifically processed. Final ctype={cmsg.ctype}.")
                # else: If not an appmsg, its ctype should have been determined earlier or it's not XML.

        except ET.ParseError: # Error parsing the main cmsg.content
            logger.debug(f"[{self.name}] Failed to parse content as XML for msg {cmsg.msg_id}. Content: {str(cmsg.content)[:200]}... Assuming not XML or malformed.")
            # Do not return here, let it fall through. If ctype not set, it might be handled by caller.
            # Or, if it's guaranteed to be XML if this method is called, then this is an error state.
            pass


        except Exception as e:
            logger.error(f"[{self.name}] Unexpected error processing XML message {cmsg.msg_id}: {e}\n{traceback.format_exc()}")
            # Fallback ctype if an unexpected error occurs
            if not hasattr(cmsg, 'ctype') or cmsg.ctype == ContextType.XML: # Avoid overriding if already set to TEXT etc.
                 cmsg.ctype = ContextType.TEXT # Default to TEXT to show error to user potentially
                 cmsg.content = "[XML消息处理时发生内部错误]"
            return # Return on unhandled exception to prevent further issues

        # Group message sender processing - this seems out of place if msg_xml parsing failed.
        # This should ideally be higher up or only if msg_xml was successfully parsed.
        # However, to match the original structure provided:
        if msg_xml is not None and cmsg.is_group and not (hasattr(cmsg, 'actual_user_id') and cmsg.actual_user_id):
            try:
                 # 'fromusername' is usually on the root <msg> for group messages if it's the raw XML
                 sender_id_xml = msg_xml.get('fromusername')
                 if sender_id_xml:
                     cmsg.sender_wxid = sender_id_xml # This might be the group ID itself
                     cmsg.actual_user_id = sender_id_xml # This needs to be the actual sender in group
                     logger.debug(f"[{self.name}] Attempted to extract sender_wxid '{sender_id_xml}' from group XML msg {cmsg.msg_id}")
                     # This logic for group sender needs careful review based on actual XML structure for group messages.
                     # Often, for group messages, the sender is in a different field or part of a CDATA section.
            except Exception as e_sender:
                logger.error(f"[{self.name}] Error extracting sender from group XML msg {cmsg.msg_id}: {e_sender}")

        processed_text_quote_status = getattr(cmsg, 'is_processed_text_quote', False)
        processed_image_quote_status = getattr(cmsg, 'is_processed_image_quote', False)
        current_ctype = getattr(cmsg, 'ctype', 'Unknown') # Default to 'Unknown' if not set
        logger.debug(f"[{self.name}] Finished _process_xml_message for {cmsg.msg_id}. Final ctype={current_ctype}, is_text_quote={processed_text_quote_status}, is_image_quote={processed_image_quote_status}")

    def _process_system_message(self, cmsg):
        """处理系统消息"""
        # 移除重复导入的ET

        # 检查是否是拍一拍消息
        if "<pat" in cmsg.content:
            try:
                root = ET.fromstring(cmsg.content)
                pat = root.find("pat")
                if pat is not None:
                    cmsg.ctype = ContextType.PAT  # 使用自定义类型
                    patter = pat.find("fromusername").text if pat.find("fromusername") is not None else ""
                    patted = pat.find("pattedusername").text if pat.find("pattedusername") is not None else ""
                    pat_suffix = pat.find("patsuffix").text if pat.find("patsuffix") is not None else ""
                    cmsg.pat_info = {
                        "patter": patter,
                        "patted": patted,
                        "suffix": pat_suffix
                    }

                    # 设置actual_user_id和actual_user_nickname
                    cmsg.sender_wxid = patter
                    cmsg.actual_user_id = patter
                    cmsg.actual_user_nickname = patter

                    # 日志输出
                    logger.info(f"收到拍一拍消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid} 拍者:{patter} 被拍:{patted} 后缀:{pat_suffix}")
                    return
            except Exception as e:
                logger.debug(f"[WechatPadPro] 解析拍一拍消息失败: {e}")

        # 如果不是特殊系统消息，按普通系统消息处理
        cmsg.ctype = ContextType.SYSTEM

        # 设置系统消息的actual_user_id和actual_user_nickname为系统
        cmsg.sender_wxid = "系统消息"
        cmsg.actual_user_id = "系统消息"
        cmsg.actual_user_nickname = "系统消息"

        logger.info(f"收到系统消息: ID:{cmsg.msg_id} 来自:{cmsg.from_user_id} 发送人:{cmsg.sender_wxid} 内容:{cmsg.content}")

    def _is_likely_base64_for_log(self, s: str) -> bool:
        """
        判断字符串是否可能是base64编码 (用于日志记录目的)。
        直接改编自 gemini_image.py 中的 _is_likely_base64。
        """
        if not isinstance(s, str): # 确保是字符串
            return False
        # base64编码通常只包含A-Z, a-z, 0-9, +, /, =
        if not s or len(s) < 50:  # 太短的字符串不太可能是需要截断的base64
            return False

        # 检查字符是否符合base64编码
        base64_chars_set = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
        non_base64_count = 0
        for char_value in s: # s 是字符串，char_value 是字符
            if char_value not in base64_chars_set and char_value != '=': # '=' 是填充字符
                non_base64_count += 1

        if non_base64_count < len(s) * 0.05 and len(s) > 100:
            return True
        return False

    def _create_loggable_params(self, data: any) -> any:
        """
        创建参数的安全版本，用于日志记录。
        将可能的base64数据替换为长度和预览指示器。
        此函数通过构建新的字典/列表来确保原始数据不被修改。
        """
        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                new_dict[key] = self._create_loggable_params(value) # 递归调用
            return new_dict
        elif isinstance(data, list):
            new_list = []
            for item in data:
                new_list.append(self._create_loggable_params(item)) # 递归调用
            return new_list
        elif isinstance(data, bytes): # <--- 新增对 bytes 类型的处理
            return f"<binary_bytes_data len={len(data)} bytes>"
        elif isinstance(data, str):
            if self._is_likely_base64_for_log(data):
                # 截断并添加长度指示器，类似 gemini_image.py 的做法
                return f"{data[:20]}... [base64_len:{len(data)} chars]"
            else:
                return data # 如果不是base64或太短，返回原字符串
        else:
            # 对于其他数据类型 (如 int, float, bool, None 等) 返回原样
            return data

    async def _call_api(self, endpoint, params, retry_count=0, max_retries=2, method="POST"):
        """调用API接口

        Args:
            endpoint (str): API端点，如 "/Login/GetQR"
            params (dict): API参数字典
            retry_count (int, optional): 当前重试次数. Defaults to 0.
            max_retries (int, optional): 最大重试次数. Defaults to 2.
            method (str, optional): HTTP方法. Defaults to "POST".

        Returns:
            dict: API响应结果，包含Success字段和相关数据
        """
        try:
            import aiohttp

            # 获取API配置
            api_host = conf().get("wechatpadpro_api_host", "127.0.0.1")
            api_port = conf().get("wechatpadpro_api_port", 8059)
            api_key = conf().get("wechatpadpro_api_key", "")

            # 确保endpoint格式正确
            if endpoint and not endpoint.startswith('/'):
                endpoint = '/' + endpoint

            # 构建完整的API URL，直接添加key参数
            url = f"http://{api_host}:{api_port}{endpoint}"
            if api_key:
                if "?" in url:
                    url += f"&key={api_key}"
                else:
                    url += f"?key={api_key}"
            else:
                logger.warning(f"[WechatPadPro] 未设置wechatpadpro_api_key，API调用可能失败")

            # 记录API调用信息
            logger.debug(f"[WechatPadPro] API调用: {url}")
            if params:
                loggable_params = self._create_loggable_params(params)
                logger.debug(f"[WechatPadPro] 请求参数: {json.dumps(loggable_params, ensure_ascii=False)}")

            # 简化数据处理，默认使用JSON格式
            content_type = "application/json"
            data = params or {}

            # 发送请求，设置超时时间
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": content_type} if method.upper() != "GET" else {}
                try:
                    # 根据HTTP方法选择不同的请求方式
                    if method.upper() == "GET":
                        logger.debug(f"[WechatPadPro] 发送GET请求: {url}")
                        async with session.get(url, headers=headers, timeout=60) as response:
                            if response.status == 200:
                                try:
                                    result = await response.json(content_type=None)
                                    logger.debug(f"[WechatPadPro] 收到响应: {json.dumps(result, ensure_ascii=False)}")
                                    return result
                                except Exception as json_err:
                                    text = await response.text()
                                    logger.error(f"[WechatPadPro] JSON解析失败: {json_err}, 原始内容: {text}")
                                    return {"Success": False, "Message": f"JSON解析错误: {str(json_err)}", "RawResponse": text}
                            else:
                                error_text = await response.text()
                                logger.error(f"[WechatPadPro] API请求失败: {response.status} - {error_text[:200]}")
                                return {"Success": False, "Message": f"HTTP错误 {response.status}", "ErrorDetail": error_text[:500]}
                    else:  # POST请求，使用JSON格式
                        logger.debug(f"[WechatPadPro] 发送POST请求: {url}")
                        async with session.post(url, json=data, headers=headers, timeout=60) as response:
                            if response.status == 200:
                                try:
                                    result = await response.json(content_type=None)
                                    logger.debug(f"[WechatPadPro] 收到响应: {json.dumps(result, ensure_ascii=False)}")
                                    return result
                                except Exception as json_err:
                                    text = await response.text()
                                    logger.error(f"[WechatPadPro] JSON解析失败: {json_err}, 原始内容: {text}")
                                    return {"Success": False, "Message": f"JSON解析错误: {str(json_err)}", "RawResponse": text}
                            else:
                                error_text = await response.text()
                                logger.error(f"[WechatPadPro] API请求失败: {response.status} - {error_text[:200]}")
                                return {"Success": False, "Message": f"HTTP错误 {response.status}", "ErrorDetail": error_text[:500]}
                except aiohttp.ClientError as client_err:
                    # 客户端连接错误
                    logger.error(f"[WechatPadPro] HTTP请求错误: {client_err}")
                    return {"Success": False, "Message": f"HTTP请求错误: {str(client_err)}"}

        except aiohttp.ClientError as e:
            # 处理连接错误
            logger.error(f"[WechatPadPro] API连接错误: {str(e)}")
            return {"Success": False, "Message": f"API连接错误: {str(e)}"}
        except asyncio.TimeoutError:
            # 处理超时错误
            logger.error(f"[WechatPadPro] API请求超时")
            return {"Success": False, "Message": "API请求超时"}
        except Exception as e:
            # 处理其他错误
            logger.error(f"[WechatPadPro] 调用API时出错: {str(e)}")
            import traceback
            logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")

            # 检查是否是网络相关错误
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['connection', 'timeout', 'network']):
                logger.warning(f"[WechatPadPro] 检测到网络相关错误，可能需要重试")
                return {"Success": False, "Message": f"网络错误: {str(e)}", "ErrorType": "NetworkError"}

            return {"Success": False, "Message": f"API调用错误: {str(e)}"}



    async def _send_message(self, to_user_id, content, msg_type=1):
        """发送消息的异步方法 - 只支持8059协议"""
        try:
            if not to_user_id:
                logger.error("[WechatPadPro8059] 发送消息失败: 接收者ID为空")
                return None

            # 8059协议发送文本消息
            try:
                client_msg_id, create_time, new_msg_id = await self.bot.send_text_message(
                    wxid=to_user_id,
                    content=content,
                    at=""
                )
                logger.debug(f"[WechatPadPro8059] 发送文本消息成功: 接收者: {to_user_id}")
                return {
                    "Success": True,
                    "Data": {
                        "ClientMsgId": client_msg_id,
                        "CreateTime": create_time,
                        "NewMsgId": new_msg_id
                    }
                }
            except Exception as e:
                logger.error(f"[WechatPadPro8059] 发送文本消息失败: {e}")
                return {"Success": False, "Error": str(e)}

        except Exception as e:
            logger.error(f"[WechatPadPro8059] 发送消息失败: {e}")
            return None

    async def _send_image(self, to_user_id, image_source, context=None):
        """发送图片的异步方法 - 只支持8059协议"""
        try:
            # 8059协议图片发送
            if isinstance(image_source, str):
                # 处理文件路径
                image_path = image_source
                if not os.path.exists(image_path):
                    logger.error(f"[WechatPadPro8059] 发送图片失败: 文件不存在 {image_path}")
                    return None

                from pathlib import Path
                image_path_obj = Path(image_path)
                client_msg_id, create_time, new_msg_id = await self.bot.send_image_message(
                    wxid=to_user_id,
                    image_path=image_path_obj
                )
                logger.info(f"[WechatPadPro8059] 发送图片消息成功: 接收者: {to_user_id}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
                return {
                    "Success": True,
                    "Data": {
                        "ClientMsgId": client_msg_id,
                        "CreateTime": create_time,
                        "NewMsgId": new_msg_id
                    }
                }
            elif isinstance(image_source, io.BytesIO):
                # 对于BytesIO对象，需要先保存为临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    tmp_file.write(image_source.getvalue())
                    tmp_path = tmp_file.name

                try:
                    from pathlib import Path
                    image_path_obj = Path(tmp_path)
                    client_msg_id, create_time, new_msg_id = await self.bot.send_image_message(
                        wxid=to_user_id,
                        image_path=image_path_obj
                    )
                    logger.debug(f"[WechatPadPro8059] 发送图片消息成功: 接收者: {to_user_id}")
                    return {
                        "Success": True,
                        "Data": {
                            "ClientMsgId": client_msg_id,
                            "CreateTime": create_time,
                            "NewMsgId": new_msg_id
                        }
                    }
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            elif isinstance(image_source, bytes):
                # 处理bytes对象
                logger.debug("[WechatPadPro8059] 处理 bytes 类型的图片源")
                if not image_source:
                    logger.error("[WechatPadPro8059] 发送图片失败: bytes 对象为空")
                    return {"Success": False, "Error": "bytes 对象为空"}

                # 将bytes保存为临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    tmp_file.write(image_source)
                    tmp_path = tmp_file.name

                try:
                    from pathlib import Path
                    image_path_obj = Path(tmp_path)
                    client_msg_id, create_time, new_msg_id = await self.bot.send_image_message(
                        wxid=to_user_id,
                        image_path=image_path_obj
                    )
                    logger.debug(f"[WechatPadPro8059] 发送图片消息成功: 接收者: {to_user_id}")
                    return {
                        "Success": True,
                        "Data": {
                            "ClientMsgId": client_msg_id,
                            "CreateTime": create_time,
                            "NewMsgId": new_msg_id
                        }
                    }
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            elif isinstance(image_source, io.BufferedReader):
                # 处理BufferedReader对象 - 获取路径并重新读取
                try:
                    image_path = getattr(image_source, 'name', None)
                    if not image_path:
                        logger.error("[WechatPadPro8059] 发送图片失败: BufferedReader对象没有name属性")
                        return {"Success": False, "Error": "BufferedReader对象没有name属性"}

                    # 确保文件仍然存在
                    if not os.path.exists(image_path):
                        logger.error(f"[WechatPadPro8059] 发送图片失败: 文件已被删除或不存在于路径 {image_path}")
                        return {"Success": False, "Error": f"文件不存在: {image_path}"}

                    # 直接使用文件路径
                    from pathlib import Path
                    image_path_obj = Path(image_path)
                    client_msg_id, create_time, new_msg_id = await self.bot.send_image_message(
                        wxid=to_user_id,
                        image_path=image_path_obj
                    )
                    logger.debug(f"[WechatPadPro8059] 发送图片消息成功: 接收者: {to_user_id}")
                    return {
                        "Success": True,
                        "Data": {
                            "ClientMsgId": client_msg_id,
                            "CreateTime": create_time,
                            "NewMsgId": new_msg_id
                        }
                    }
                except AttributeError:
                    logger.error("[WechatPadPro8059] 发送图片失败: 无法从BufferedReader对象获取name属性")
                    return {"Success": False, "Error": "无法从BufferedReader对象获取name属性"}
                except Exception as e:
                    logger.error(f"[WechatPadPro8059] 处理BufferedReader时失败: {e}")
                    return {"Success": False, "Error": str(e)}
            else:
                logger.error(f"[WechatPadPro8059] 不支持的图片源类型: {type(image_source)}")
                return {"Success": False, "Error": f"不支持的图片源类型: {type(image_source)}"}

        except Exception as e:
            logger.error(f"[WechatPadPro8059] 发送图片失败: {e}")
            return {"Success": False, "Error": str(e)}

    async def _prepare_video_and_thumb(self, video_url: str, session_id: str) -> dict:
        """
        异步下载视频，提取缩略图和时长。
        返回包含 video_path, thumb_path, duration 的字典，失败则返回 None。
        """
        tmp_dir = TmpDir().path()
        # 使用 uuid 生成更独特的文件名，避免仅依赖 session_id 和时间戳可能产生的冲突
        unique_id = str(uuid.uuid4())
        video_file_name = f"tmp_video_{session_id}_{unique_id}.mp4" # 假设是mp4
        video_file_path = os.path.join(tmp_dir, video_file_name)
        thumb_file_name = f"tmp_thumb_{session_id}_{unique_id}.jpg"
        thumb_file_path = os.path.join(tmp_dir, thumb_file_name)

        video_downloaded = False
        try:
            # 1. 异步下载视频
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=60)) as resp: # 60秒超时
                    if resp.status == 200:
                        with open(video_file_path, 'wb') as f:
                            while True:
                                chunk = await resp.content.read(1024) # 读取块
                                if not chunk:
                                    break
                                f.write(chunk)
                        video_downloaded = True
                        logger.debug(f"[WechatPadPro] Video downloaded to {video_file_path} from {video_url}")
                    else:
                        logger.error(f"[WechatPadPro] Failed to download video from {video_url}. Status: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"[WechatPadPro] Exception during video download from {video_url}: {e}", exc_info=True)
            if os.path.exists(video_file_path): # 如果下载部分成功但后续出错，清理掉
                os.remove(video_file_path)
            return None

        if not video_downloaded:
            return None

        # 2. 使用 OpenCV 处理视频，提取缩略图和时长
        duration = 0
        thumb_generated = False
        cap = None # 初始化 cap
        try:
            cap = cv2.VideoCapture(video_file_path)
            if not cap.isOpened():
                logger.error(f"[WechatPadPro] OpenCV could not open video file: {video_file_path}")
                # 不需要在这里删除 video_file_path，send_video 的 finally 会处理
                return {"video_path": video_file_path, "thumb_path": None, "duration": 0} # 返回部分信息

            # 获取时长
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if fps > 0 and frame_count > 0:
                duration = int(frame_count / fps)
            else:
                logger.warning(f"[WechatPadPro] Could not get valid fps ({fps}) or frame_count ({frame_count}) for {video_file_path}. Duration set to 0.")
                duration = 0 # 或设置为一个默认值，或标记为未知

            # 提取第一帧作为缩略图
            ret, frame = cap.read()
            if ret:
                # 改进缩略图生成：调整大小和质量
                try:
                    # 调整缩略图大小到合适的尺寸（最大320x240）
                    height, width = frame.shape[:2]
                    max_width, max_height = 320, 240

                    # 计算缩放比例
                    scale = min(max_width/width, max_height/height)
                    if scale < 1:
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

                    # 确保使用JPEG格式，Client2库要求"data:image/jpeg;base64,"格式
                    if not thumb_file_path.lower().endswith('.jpg') and not thumb_file_path.lower().endswith('.jpeg'):
                        thumb_file_path = thumb_file_path.rsplit('.', 1)[0] + '.jpg'

                    # 使用JPEG格式保存
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]  # 85%质量
                    success = cv2.imwrite(thumb_file_path, frame, encode_params)

                    if success and os.path.exists(thumb_file_path):
                        logger.debug(f"[WechatPadPro] 缩略图生成成功: {thumb_file_path}")

                        thumb_generated = True
                        final_size = os.path.getsize(thumb_file_path)
                        logger.debug(f"[WechatPadPro] Thumbnail generated: {thumb_file_path}, size: {final_size} bytes, duration: {duration}s")
                    else:
                        logger.error(f"[WechatPadPro] Failed to save thumbnail to {thumb_file_path}")
                except Exception as thumb_error:
                    logger.error(f"[WechatPadPro] Error processing thumbnail: {thumb_error}")
            else:
                logger.warning(f"[WechatPadPro] Could not read frame from video {video_file_path} to generate thumbnail.")

        except Exception as e:
            logger.error(f"[WechatPadPro] Exception during OpenCV video processing for {video_file_path}: {e}", exc_info=True)
            # 即使处理失败，视频已下载，返回视频路径和获取到的时长（可能为0）
            # thumb_path 将为 None（如果之前未成功生成）
            # 不需要在这里删除 video_file_path，send_video 的 finally 会处理
            return {"video_path": video_file_path, "thumb_path": None, "duration": duration}
        finally:
            if cap:
                cap.release()

        return {
            "video_path": video_file_path,
            "thumb_path": thumb_file_path if thumb_generated else None,
            "duration": duration
        }

    async def send_video(self, to_wxid: str, video_url: str, session_id: str):
        """
        下载视频URL，准备视频路径、缩略图路径和时长，
        然后使用8059协议的先上传后转发流程发送。
        """
        logger.info(f"[WechatPadPro8059] 准备视频发送: {video_url} -> {to_wxid} (session: {session_id})")
        prepared_video_info = await self._prepare_video_and_thumb(video_url, session_id)

        if not prepared_video_info or not prepared_video_info.get("video_path"):
            logger.error(f"[WechatPadPro8059] 视频准备失败: {video_url}")
            return None

        video_path = prepared_video_info["video_path"]
        thumb_path = prepared_video_info.get("thumb_path")

        if not os.path.exists(video_path):
            logger.error(f"[WechatPadPro8059] 视频文件不存在: {video_path}")
            return None

        # 直接使用原始视频，不进行压缩
        logger.info(f"[WechatPadPro8059] 使用原始视频: {video_path}")

        try:
            # 使用8059协议的send_video_message方法（先上传后转发）
            from pathlib import Path
            video_path_obj = Path(video_path)
            thumb_path_obj = Path(thumb_path) if thumb_path and os.path.exists(thumb_path) else None

            logger.info(f"[WechatPadPro8059] 开始发送视频消息: 视频={video_path_obj}, 缩略图={thumb_path_obj}")

            client_msg_id, create_time, new_msg_id = await self.bot.send_video_message(
                wxid=to_wxid,
                video_path=video_path_obj,
                thumb_path=thumb_path_obj
            )

            logger.info(f"[WechatPadPro8059] 视频发送成功: 接收者={to_wxid}, ClientMsgId={client_msg_id}, NewMsgId={new_msg_id}")
            return {
                "Success": True,
                "Data": {
                    "ClientMsgId": client_msg_id,
                    "CreateTime": create_time,
                    "NewMsgId": new_msg_id
                },
                "Message": "视频发送成功"
            }

        except Exception as e:
            logger.error(f"[WechatPadPro8059] 视频发送异常: {e}")
            return {"Success": False, "Error": str(e)}
        finally:
            # 清理临时文件
            # 清理视频文件
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    logger.debug(f"[WechatPadPro8059] 清理视频文件: {video_path}")
                except Exception as e_clean:
                    logger.warning(f"[WechatPadPro8059] 清理视频文件失败: {video_path}, {e_clean}")

            # 清理缩略图文件
            if thumb_path and os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                    logger.debug(f"[WechatPadPro8059] 清理缩略图文件: {thumb_path}")
                except Exception as e_clean:
                    logger.warning(f"[WechatPadPro8059] 清理缩略图文件失败: {thumb_path}, {e_clean}")

    def send(self, reply: Reply, context: Context):
        """发送消息"""
        # 获取接收者ID
        receiver = context.get("receiver")
        if not receiver:
            # 如果context中没有接收者，尝试从消息对象中获取
            msg = context.get("msg")
            if msg and hasattr(msg, "from_user_id"):
                receiver = msg.from_user_id

        if not receiver:
            logger.error("[WechatPadPro] 发送消息失败: 无法确定接收者ID")
            return

        # 安全的异步调用方法
        def run_async_safely(coro, timeout=60, operation_name="未知操作"):
            """安全地运行异步协程"""
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果循环正在运行，使用asyncio.run_coroutine_threadsafe
                    import concurrent.futures
                    logger.debug(f"[WechatPadPro8059] 开始执行异步操作: {operation_name}, 超时时间: {timeout}秒")
                    future = asyncio.run_coroutine_threadsafe(coro, loop)
                    try:
                        result = future.result(timeout=timeout)
                        logger.debug(f"[WechatPadPro8059] 异步操作完成: {operation_name}")
                        return result
                    except concurrent.futures.TimeoutError:
                        logger.error(f"[WechatPadPro8059] 异步操作超时: {operation_name}, 超时时间: {timeout}秒")
                        raise TimeoutError(f"操作超时: {operation_name}")
                else:
                    # 如果循环没有运行，直接运行
                    logger.debug(f"[WechatPadPro8059] 直接运行异步操作: {operation_name}")
                    return loop.run_until_complete(coro)
            except RuntimeError:
                # 如果没有事件循环或有其他问题，使用asyncio.run
                logger.debug(f"[WechatPadPro8059] 使用asyncio.run执行: {operation_name}")
                return asyncio.run(coro)

        if reply.type == ReplyType.TEXT:
            reply.content = remove_markdown_symbol(reply.content)
            result = run_async_safely(self._send_message(receiver, reply.content), timeout=30, operation_name="发送文本消息")
            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送文本消息成功: 接收者: {receiver}")
                if conf().get("log_level", "INFO") == "DEBUG":
                    logger.debug(f"[WechatPadPro] 消息内容: {reply.content[:50]}...")
            else:
                logger.warning(f"[WechatPadPro] 发送文本消息可能失败: 接收者: {receiver}, 结果: {result}")

        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
            reply.content = remove_markdown_symbol(reply.content)
            result = run_async_safely(self._send_message(receiver, reply.content), timeout=30, operation_name="发送错误/信息消息")
            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送消息成功: 接收者: {receiver}")
                if conf().get("log_level", "INFO") == "DEBUG":
                    logger.debug(f"[WechatPadPro] 消息内容: {reply.content[:50]}...")
            else:
                logger.warning(f"[WechatPadPro] 发送消息可能失败: 接收者: {receiver}, 结果: {result}")

        elif reply.type == ReplyType.IMAGE_URL:
            # 从网络下载图片并发送
            img_url = reply.content
            logger.debug(f"[WechatPadPro] 开始下载图片, url={img_url}")
            try:
                pic_res = requests.get(img_url, stream=True)
                # 使用临时文件保存图片
                tmp_path = os.path.join(get_appdata_dir(), f"tmp_img_{int(time.time())}.png")
                with open(tmp_path, 'wb') as f:
                    for block in pic_res.iter_content(1024):
                        f.write(block)

                # 使用我们的自定义方法发送图片
                result = run_async_safely(self._send_image(receiver, tmp_path), timeout=90, operation_name="发送网络图片")

                if result and isinstance(result, dict) and result.get("Success", False):
                    logger.info(f"[WechatPadPro] 发送图片成功: 接收者: {receiver}")
                else:
                    logger.warning(f"[WechatPadPro] 发送图片可能失败: 接收者: {receiver}, 结果: {result}")

                # 删除临时文件
                try:
                    os.remove(tmp_path)
                except Exception as e:
                    logger.debug(f"[WechatPadPro] 删除临时图片文件失败: {e}")
            except Exception as e:
                logger.error(f"[WechatPadPro] 发送图片失败: {e}")

        elif reply.type == ReplyType.IMAGE: # 添加处理 ReplyType.IMAGE
            image_input = reply.content
            # 移除 os.path.exists 检查，交由 _send_image 处理
            # 使用我们的自定义方法发送本地图片或BytesIO
            result = run_async_safely(self._send_image(receiver, image_input), timeout=90, operation_name="发送本地图片")

            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送图片成功: 接收者: {receiver}")
            else:
                logger.warning(f"[WechatPadPro] 发送图片可能失败: 接收者: {receiver}, 结果: {result}")

        elif reply.type == ReplyType.APP:
            xml_content = reply.content
            logger.info(f"[WechatPadPro] APP message raw content type: {type(xml_content)}, content length: {len(xml_content)}")
            if conf().get("log_level", "INFO") == "DEBUG":
                 logger.debug(f"[WechatPadPro] APP XML Content: {xml_content[:500]}") # Log more content for debugging

            if not isinstance(xml_content, str):
                logger.error(f"[WechatPadPro] send app message failed: content must be XML string, got type={type(xml_content)}")
                return
            if not xml_content.strip():
                logger.error("[WechatPadPro] send app message failed: content is empty string")
                return

            # Extract app_type from XML content
            app_type = 3 # Default to 3 (music type from log example) if not found
            try:
                # Using regex to find <type>integer_value</type>
                match = re.search(r"<type>\s*(\d+)\s*</type>", xml_content, re.IGNORECASE)
                if match:
                    app_type = int(match.group(1))
                    logger.info(f"[WechatPadPro] Extracted app_type from XML: {app_type}")
                else:
                    logger.warning(f"[WechatPadPro] Could not find <type> tag in XML, using default app_type: {app_type}. XML: {xml_content[:300]}...")
            except Exception as e_parse_type:
                logger.error(f"[WechatPadPro] Error parsing app_type from XML: {e_parse_type}, using default: {app_type}. XML: {xml_content[:300]}...")

            result = run_async_safely(self._send_app_xml(receiver, xml_content, app_type), timeout=60, operation_name="发送APP XML消息")
            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送App XML消息成功: 接收者: {receiver}, Type: {app_type}")
            else:
                logger.warning(f"[WechatPadPro] 发送App XML消息可能失败: 接收者: {receiver}, Type: {app_type}, 结果: {result}")

        elif reply.type == ReplyType.MINIAPP:
            app_input = reply.content
            # 移除 os.path.exists 检查，交由 _send_app 处理
            # 使用我们的自定义方法发送小程序
            result = run_async_safely(self._send_app(receiver, app_input), timeout=60, operation_name="发送小程序")

            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送小程序成功: 接收者: {receiver}")
            else:
                logger.warning(f"[WechatPadPro] 发送小程序可能失败: 接收者: {receiver}, 结果: {result}")

        # 移除不存在的ReplyType.System类型，使用ReplyType.INFO或忽略
        elif reply.type == ReplyType.INFO:
            system_input = reply.content
            # 移除 os.path.exists 检查，交由 _send_system 处理
            # 使用我们的自定义方法发送系统消息
            result = run_async_safely(self._send_message(receiver, system_input), timeout=30, operation_name="发送系统消息")

            if result and isinstance(result, dict) and result.get("Success", False):
                logger.info(f"[WechatPadPro] 发送系统消息成功: 接收者: {receiver}")
            else:
                logger.warning(f"[WechatPadPro] 发送系统消息可能失败: 接收者: {receiver}, 结果: {result}")

        elif reply.type == ReplyType.VIDEO_URL:
            logger.info(f"[WechatPadPro8059] 收到视频URL请求: {reply.content}")
            to_wxid = context.get("receiver")
            if not to_wxid:
                logger.error("[WechatPadPro8059] 无法发送视频: 接收者ID未定义")
                return

            session_id = context.get("session_id") or context.get("msg", {}).get("msg_id") or self.get_random_session()
            if not session_id:
                session_id = self.get_random_session()
                logger.warning(f"[WechatPadPro8059] session_id为空，使用随机ID: {session_id}")

            # 使用8059协议的视频发送方法（先上传后转发）
            logger.info("[WechatPadPro8059] 使用8059协议视频发送方案（先上传后转发）")

            try:
                # 调用我们新创建的send_video方法，视频操作需要更长时间
                result = run_async_safely(self.send_video(to_wxid, reply.content, session_id), timeout=300, operation_name="发送视频")

                if result and isinstance(result, dict) and result.get("Success", False):
                    logger.info(f"[WechatPadPro8059] 视频发送成功: 接收者: {to_wxid}")
                    return
                else:
                    logger.warning(f"[WechatPadPro8059] 视频发送失败: {result}")
                    # 回退到文本消息
                    fallback_message = f"🎬 视频分享：{reply.content}"
                    result = run_async_safely(self._send_message(to_wxid, fallback_message), timeout=30, operation_name="发送视频回退文本")
                    if result and isinstance(result, dict) and result.get("Success", False):
                        logger.info(f"[WechatPadPro8059] 发送视频链接文本成功: 接收者: {to_wxid}")
                    else:
                        logger.warning(f"[WechatPadPro8059] 发送视频链接文本失败: 接收者: {to_wxid}")

            except Exception as e:
                logger.error(f"[WechatPadPro8059] 视频发送异常: {e}")
                # 异常时发送文本消息
                fallback_message = f"🎬 视频分享：{reply.content}"
                result = run_async_safely(self._send_message(to_wxid, fallback_message), timeout=30, operation_name="发送视频异常回退文本")

            return

        elif reply.type == ReplyType.VOICE:
            original_voice_file_path = reply.content
            if not original_voice_file_path or not os.path.exists(original_voice_file_path):
                logger.error(f"[WechatPadPro] Send voice failed: Original voice file not found or path is empty: {original_voice_file_path}")
                return

            if not original_voice_file_path.lower().endswith('.mp3'):
                logger.error(f"[WechatPadPro] Send voice failed: Only .mp3 voice files are supported, got {original_voice_file_path}")
                return

            # FFmpeg preprocessing
            ffmpeg_path = _find_ffmpeg_path()

            # Correctly create temporary directory for ffmpeg output
            base_tmp_root = TmpDir().path() # e.g., ./tmp/
            voice_subdir_name = "wechatpadpro_voice"
            voice_tmp_dir = os.path.join(base_tmp_root, voice_subdir_name) # e.g., ./tmp/wechatpadpro_voice
            os.makedirs(voice_tmp_dir, exist_ok=True)
            processed_voice_path = os.path.join(voice_tmp_dir, f"ffmpeg_processed_{os.path.basename(original_voice_file_path)}")

            effective_voice_path = original_voice_file_path # Default to original if ffmpeg fails
            ffmpeg_success = False

            try:
                # 优化FFmpeg参数以提高音质，为SILK转换做准备
                cmd = [
                    ffmpeg_path, "-y", "-i", original_voice_file_path,
                    "-acodec", "libmp3lame",  # 使用高质量MP3编码器
                    "-ar", "48000",           # 48000Hz采样率（SILK最高支持）
                    "-ab", "320k",            # 320kbps高比特率
                    "-ac", "1",               # 单声道（微信语音要求）
                    "-af", "volume=1.2",      # 轻微增强音量
                    processed_voice_path
                ]
                logger.info(f"[WechatPadPro] Attempting to preprocess voice file with ffmpeg: {' '.join(cmd)}")
                process_result = subprocess.run(cmd, capture_output=True, text=True, check=False) # check=False to inspect manually
                if process_result.returncode == 0 and os.path.exists(processed_voice_path):
                    logger.info(f"[WechatPadPro] ffmpeg preprocessing successful. Using processed file: {processed_voice_path}")
                    effective_voice_path = processed_voice_path
                    ffmpeg_success = True
                else:
                    logger.warning(f"[WechatPadPro] ffmpeg preprocessing failed. Return code: {process_result.returncode}. Error: {process_result.stderr}. Will use original file.")
            except Exception as e_ffmpeg:
                logger.error(f"[WechatPadPro] Exception during ffmpeg preprocessing: {e_ffmpeg}. Will use original file.")

            temp_files_to_clean = []
            # 添加原始下载的语音文件到清理列表
            temp_files_to_clean.append(original_voice_file_path)
            if ffmpeg_success and effective_voice_path != original_voice_file_path:
                temp_files_to_clean.append(effective_voice_path) # Add ffmpeg processed file for cleanup

            try:
                # 微信语音条支持最长60秒，按60秒分割
                _total_duration_ms, segment_paths = split_audio(effective_voice_path, 60 * 1000)
                temp_files_to_clean.extend(segment_paths) # Add segment paths from split_audio for cleanup

                if not segment_paths:
                    logger.error(f"[WechatPadPro] Voice splitting failed for {effective_voice_path}. No segments created.")
                    logger.info(f"[WechatPadPro] Attempting to send {effective_voice_path} as fallback.")
                    # Duration calculation for fallback is now inside _send_voice, so just pass path
                    fallback_result = run_async_safely(self._send_voice(receiver, effective_voice_path), timeout=120, operation_name="发送语音回退")
                    if fallback_result and isinstance(fallback_result, dict) and fallback_result.get("Success", False):
                        logger.info(f"[WechatPadPro] Fallback: Sent voice file successfully: {effective_voice_path}")
                    else:
                        logger.warning(f"[WechatPadPro] Fallback: Sending voice file failed: {effective_voice_path}, Result: {fallback_result}")
                    return

                logger.info(f"[WechatPadPro] Voice file {effective_voice_path} split into {len(segment_paths)} segments.")

                for i, segment_path in enumerate(segment_paths):
                    # Duration calculation and SILK conversion are now inside _send_voice
                    segment_result = run_async_safely(self._send_voice(receiver, segment_path), timeout=120, operation_name=f"发送语音片段{i+1}/{len(segment_paths)}")
                    if segment_result and isinstance(segment_result, dict) and segment_result.get("Success", False):
                        logger.info(f"[WechatPadPro] Sent voice segment {i+1}/{len(segment_paths)} successfully: {segment_path}")
                    else:
                        logger.warning(f"[WechatPadPro] Sending voice segment {i+1}/{len(segment_paths)} failed: {segment_path}, Result: {segment_result}")
                        # If a segment fails, we might decide to stop or continue. For now, continue.

                    if i < len(segment_paths) - 1:
                        time.sleep(0.5)

            except Exception as e_split_send:
                logger.error(f"[WechatPadPro] Error during voice splitting or segmented sending for {effective_voice_path}: {e_split_send}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                logger.info(f"[WechatPadPro] 开始清理 {len(temp_files_to_clean)} 个语音相关文件...")
                for temp_file_path in temp_files_to_clean:
                    try:
                        if os.path.exists(temp_file_path):
                            file_size = os.path.getsize(temp_file_path)
                            os.remove(temp_file_path)
                            if temp_file_path == original_voice_file_path:
                                logger.info(f"[WechatPadPro] 已清理原始下载语音文件: {os.path.basename(temp_file_path)} ({file_size} bytes)")
                            else:
                                logger.debug(f"[WechatPadPro] 已清理临时语音文件: {os.path.basename(temp_file_path)} ({file_size} bytes)")
                        else:
                            logger.debug(f"[WechatPadPro] 文件不存在，跳过清理: {temp_file_path}")
                    except Exception as e_cleanup:
                        logger.warning(f"[WechatPadPro] 清理语音文件失败 {temp_file_path}: {e_cleanup}")
                logger.info(f"[WechatPadPro] 语音文件清理完成")

        else:
            logger.warning(f"[WechatPadPro] 不支持的回复类型: {reply.type}")

    async def _get_group_member_details(self, group_id):
        """获取群成员详情"""
        try:
            logger.debug(f"[WechatPadPro] 尝试获取群 {group_id} 的成员详情")

            # 检查是否已存在群成员信息，并检查是否需要更新
            # 定义群聊信息文件路径
            tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            chatrooms_file = os.path.join(tmp_dir, 'wechatpadpro_rooms.json')

            # 读取现有的群聊信息（如果存在）
            chatrooms_info = {}
            if os.path.exists(chatrooms_file):
                try:
                    with open(chatrooms_file, 'r', encoding='utf-8') as f:
                        chatrooms_info = json.load(f)
                    logger.debug(f"[WechatPadPro] 已加载 {len(chatrooms_info)} 个现有群聊信息")
                except Exception as e:
                    logger.error(f"[WechatPadPro] 加载现有群聊信息失败: {str(e)}")

            # 检查该群聊是否已存在且成员信息是否已更新
            # 设定缓存有效期为24小时(86400秒)
            cache_expiry = 86400
            current_time = int(time.time())

            if (group_id in chatrooms_info and
                "members" in chatrooms_info[group_id] and
                len(chatrooms_info[group_id]["members"]) > 0 and
                "last_update" in chatrooms_info[group_id] and
                current_time - chatrooms_info[group_id]["last_update"] < cache_expiry):
                logger.debug(f"[WechatPadPro] 群 {group_id} 成员信息已存在且未过期，跳过更新")
                return chatrooms_info[group_id]

            logger.debug(f"[WechatPadPro] 群 {group_id} 成员信息不存在或已过期，开始更新")

            # ============== 新增：首先调用GetChatRoomInfo获取群名称 ==============
            # 调用API获取群详情 - 8059协议格式
            info_params = {
                "ChatRoomWxIdList": [group_id]  # 8059协议使用ChatRoomWxIdList参数
            }

            # 获取API配置
            api_host = conf().get("wechatpadpro_api_host", "127.0.0.1")
            api_port = conf().get("wechatpadpro_api_port", 8059)  # 8059协议端口
            protocol_version = conf().get("wechatpadpro_protocol_version", "8059")

            # 8059协议不使用路径前缀
            api_path_prefix = ""

            logger.info(f"[WechatPadPro] 正在请求群详情API: http://{api_host}:{api_port}/group/GetChatRoomInfo")
            logger.info(f"[WechatPadPro] 群详情请求参数: {json.dumps(info_params, ensure_ascii=False)}")

            # 调用GetChatRoomInfo API - 8059协议路径
            group_info_response = await self._call_api("/group/GetChatRoomInfo", info_params)

            # 解析群名称 - 8059协议响应格式
            group_name = None
            if group_info_response and isinstance(group_info_response, dict) and group_info_response.get("Code") == 200:
                data = group_info_response.get("Data", {})

                # 递归函数用于查找特定key的值
                def find_value(obj, key):
                    # 如果是字典
                    if isinstance(obj, dict):
                        # 直接检查当前字典
                        if key in obj:
                            return obj[key]
                        # 检查带有"string"嵌套的字典
                        if key in obj and isinstance(obj[key], dict) and "string" in obj[key]:
                            return obj[key]["string"]
                        # 递归检查字典的所有值
                        for k, v in obj.items():
                            result = find_value(v, key)
                            if result is not None:
                                return result
                    # 如果是列表
                    elif isinstance(obj, list):
                        # 递归检查列表的所有项
                        for item in obj:
                            result = find_value(item, key)
                            if result is not None:
                                return result
                    return None

                # 8059协议特定的数据结构解析
                contact_list = data.get("contactList", [])
                if contact_list and len(contact_list) > 0:
                    contact = contact_list[0]
                    # 从nickName.str字段提取群名称
                    nick_name_obj = contact.get("nickName", {})
                    if isinstance(nick_name_obj, dict) and "str" in nick_name_obj:
                        group_name = nick_name_obj["str"]
                        logger.info(f"[WechatPadPro] 成功获取到群名称: {group_name}")
                    else:
                        logger.warning(f"[WechatPadPro] nickName字段格式异常: {nick_name_obj}")
                else:
                    # 如果contactList为空，尝试使用递归查找
                    for name_key in ["NickName", "ChatRoomName", "nickname", "chatroomname", "DisplayName", "displayname"]:
                        name_value = find_value(data, name_key)
                        if name_value:
                            if isinstance(name_value, dict) and "string" in name_value:
                                group_name = name_value["string"]
                            elif isinstance(name_value, dict) and "str" in name_value:
                                group_name = name_value["str"]
                            elif isinstance(name_value, str):
                                group_name = name_value
                            if group_name:
                                logger.info(f"[WechatPadPro] 成功获取到群名称: {group_name} (字段: {name_key})")
                                break

                # 如果找不到，记录整个响应以便调试
                if not group_name:
                    logger.warning(f"[WechatPadPro] 无法从API响应中提取群名称，响应内容: {json.dumps(data, ensure_ascii=False)[:500]}...")
            else:
                logger.warning(f"[WechatPadPro] 获取群详情失败: Code={group_info_response.get('Code') if group_info_response else 'None'}")

            # 确保在chatrooms_info中创建该群的条目
            if group_id not in chatrooms_info:
                chatrooms_info[group_id] = {
                    "chatroomId": group_id,
                    "nickName": group_name or group_id,  # 如果获取到群名则使用，否则使用群ID
                    "chatRoomOwner": "",
                    "members": [],
                    "last_update": int(time.time())
                }
            else:
                # 更新现有条目的群名称
                if group_name:
                    chatrooms_info[group_id]["nickName"] = group_name

            # 立即保存群名称信息
            with open(chatrooms_file, 'w', encoding='utf-8') as f:
                json.dump(chatrooms_info, f, ensure_ascii=False, indent=2)

            logger.info(f"[WechatPadPro] 已更新群 {group_id} 的名称: {group_name or '未获取到'}")

            # 更新群名缓存
            if group_name:
                if not hasattr(self, "group_name_cache"):
                    self.group_name_cache = {}
                self.group_name_cache[f"group_name_{group_id}"] = group_name
            # ============== 群名称获取完毕 ==============

            # 接下来继续获取群成员详情
            # 调用API获取群成员详情 - 8059协议格式
            params = {
                "ChatRoomName": group_id  # 8059协议使用ChatRoomName参数
            }

            try:
                # 构建完整的API URL用于日志
                api_url = f"http://{api_host}:{api_port}/group/GetChatroomMemberDetail"
                logger.debug(f"[WechatPadPro] 正在请求群成员详情API: {api_url}")
                logger.debug(f"[WechatPadPro] 请求参数: {json.dumps(params, ensure_ascii=False)}")

                # 调用API获取群成员详情 - 8059协议路径
                response = await self._call_api("/group/GetChatroomMemberDetail", params)

                if not response or not isinstance(response, dict):
                    logger.error(f"[WechatPadPro] 获取群成员详情失败: 无效响应")
                    return None

                # 检查响应是否成功 - 8059协议使用Code字段
                if response.get("Code") != 200:
                    logger.error(f"[WechatPadPro] 获取群成员详情失败: {response.get('Text', '未知错误')}")
                    return None

                # 提取member_data - 8059协议数据结构
                data = response.get("Data", {})
                member_data = data.get("member_data", {})

                if not member_data:
                    logger.error(f"[WechatPadPro] 获取群成员详情失败: 响应中无member_data")
                    return None

                # 提取成员信息 - 8059协议字段名
                member_count = member_data.get("member_count", 0)
                chat_room_members = member_data.get("chatroom_member_list", [])

                # 确保是有效的成员列表
                if not isinstance(chat_room_members, list):
                    logger.error(f"[WechatPadPro] 获取群成员详情失败: chatroom_member_list不是有效的列表")
                    return None

                # 更新群聊成员信息 - 映射8059协议字段名
                members = []
                for member in chat_room_members:
                    if not isinstance(member, dict):
                        continue

                    # 提取成员必要信息 - 8059协议字段映射
                    member_info = {
                        "UserName": member.get("user_name", ""),
                        "NickName": member.get("nick_name", ""),
                        "DisplayName": member.get("display_name", ""),  # 8059协议可能没有此字段
                        "ChatroomMemberFlag": member.get("chatroom_member_flag", 0),
                        "InviterUserName": member.get("unknow", ""),  # 8059协议使用unknow字段
                        "BigHeadImgUrl": member.get("big_head_img_url", ""),
                        "SmallHeadImgUrl": member.get("small_head_img_url", "")
                    }

                    members.append(member_info)

                # 更新群聊信息
                chatrooms_info[group_id]["members"] = members
                chatrooms_info[group_id]["last_update"] = int(time.time())
                chatrooms_info[group_id]["memberCount"] = member_count

                # 同时更新群主信息
                for member in members:
                    if member.get("ChatroomMemberFlag") == 2049:  # 群主标志
                        chatrooms_info[group_id]["chatRoomOwner"] = member.get("UserName", "")
                        break

                # 保存到文件
                with open(chatrooms_file, 'w', encoding='utf-8') as f:
                    json.dump(chatrooms_info, f, ensure_ascii=False, indent=2)

                logger.info(f"[WechatPadPro] 已更新群聊 {group_id} 成员信息，成员数: {len(members)}")

                # 返回成员信息 - 8059协议数据结构
                return member_data
            except Exception as e:
                logger.error(f"[WechatPadPro] 获取群成员详情失败: {e}")
                logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
                return None
        except Exception as e:
            logger.error(f"[WechatPadPro] 获取群成员详情过程中出错: {e}")
            logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
            return None

    async def _get_group_name(self, group_id):
        """获取群名称"""
        try:
            logger.debug(f"[WechatPadPro] 尝试获取群 {group_id} 的名称")

            # 检查缓存中是否有群名
            cache_key = f"group_name_{group_id}"
            if hasattr(self, "group_name_cache") and cache_key in self.group_name_cache:
                cached_name = self.group_name_cache[cache_key]
                logger.debug(f"[WechatPadPro] 从缓存中获取群名: {cached_name}")

                # 检查是否需要更新群成员详情
                tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
                chatrooms_file = os.path.join(tmp_dir, 'wechatpadpro_rooms.json')

                need_update = True
                # 设定缓存有效期为24小时(86400秒)
                cache_expiry = 86400
                current_time = int(time.time())

                if os.path.exists(chatrooms_file):
                    try:
                        with open(chatrooms_file, 'r', encoding='utf-8') as f:
                            chatrooms_info = json.load(f)

                        # 检查群信息是否存在且未过期
                        if (group_id in chatrooms_info and
                            "last_update" in chatrooms_info[group_id] and
                            current_time - chatrooms_info[group_id]["last_update"] < cache_expiry and
                            "members" in chatrooms_info[group_id] and
                            len(chatrooms_info[group_id]["members"]) > 0):
                            logger.debug(f"[WechatPadPro] 群 {group_id} 信息已存在且未过期，跳过更新")
                            need_update = False
                    except Exception as e:
                        logger.error(f"[WechatPadPro] 检查群信息缓存时出错: {e}")

                # 只有需要更新时才启动线程获取群成员详情
                if need_update:
                    logger.debug(f"[WechatPadPro] 群 {group_id} 信息需要更新，启动更新线程")
                    threading.Thread(target=lambda: asyncio.run(self._get_group_member_details(group_id))).start()

                return cached_name

            # 检查文件中是否已经有群信息，且未过期
            tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)

            chatrooms_file = os.path.join(tmp_dir, 'wechatpadpro_rooms.json')

            # 设定缓存有效期为24小时(86400秒)
            cache_expiry = 86400
            current_time = int(time.time())

            if os.path.exists(chatrooms_file):
                try:
                    with open(chatrooms_file, 'r', encoding='utf-8') as f:
                        chatrooms_info = json.load(f)

                    # 检查群信息是否存在且未过期
                    if (group_id in chatrooms_info and
                        "nickName" in chatrooms_info[group_id] and
                        chatrooms_info[group_id]["nickName"] and
                        chatrooms_info[group_id]["nickName"] != group_id and
                        "last_update" in chatrooms_info[group_id] and
                        current_time - chatrooms_info[group_id]["last_update"] < cache_expiry):

                        # 从文件中获取群名
                        group_name = chatrooms_info[group_id]["nickName"]
                        logger.debug(f"[WechatPadPro] 从文件缓存中获取群名: {group_name}")

                        # 缓存群名
                        if not hasattr(self, "group_name_cache"):
                            self.group_name_cache = {}
                        self.group_name_cache[cache_key] = group_name

                        # 检查是否需要更新群成员详情
                        need_update_members = not ("members" in chatrooms_info[group_id] and
                                                len(chatrooms_info[group_id]["members"]) > 0)

                        if need_update_members:
                            logger.debug(f"[WechatPadPro] 群 {group_id} 名称已缓存，但需要更新成员信息")
                            threading.Thread(target=lambda: asyncio.run(self._get_group_member_details(group_id))).start()
                        else:
                            logger.debug(f"[WechatPadPro] 群 {group_id} 信息已完整且未过期，无需更新")

                        return group_name
                except Exception as e:
                    logger.error(f"[WechatPadPro] 从文件获取群名出错: {e}")

            logger.debug(f"[WechatPadPro] 群 {group_id} 信息不存在或已过期，需要从API获取")

            # 调用API获取群信息 - 8059协议格式
            params = {
                "ChatRoomWxIdList": [group_id]  # 8059协议使用ChatRoomWxIdList参数
            }

            try:
                # 获取API配置
                api_host = conf().get("wechatpadpro_api_host", "127.0.0.1")
                api_port = conf().get("wechatpadpro_api_port", 8059)  # 8059协议端口
                protocol_version = conf().get("wechatpadpro_protocol_version", "8059")

                # 构建完整的API URL用于日志
                api_url = f"http://{api_host}:{api_port}/group/GetChatRoomInfo"
                logger.debug(f"[WechatPadPro] 正在请求群信息API: {api_url}")
                logger.debug(f"[WechatPadPro] 请求参数: {json.dumps(params, ensure_ascii=False)}")  # 记录请求参数

                # 尝试使用群聊专用API - 8059协议路径
                group_info = await self._call_api("/group/GetChatRoomInfo", params)

                # 保存群聊详情到统一的JSON文件
                try:
                    # 读取现有的群聊信息（如果存在）
                    chatrooms_info = {}
                    if os.path.exists(chatrooms_file):
                        try:
                            with open(chatrooms_file, 'r', encoding='utf-8') as f:
                                chatrooms_info = json.load(f)
                            logger.debug(f"[WechatPadPro] 已加载 {len(chatrooms_info)} 个现有群聊信息")
                        except Exception as e:
                            logger.error(f"[WechatPadPro] 加载现有群聊信息失败: {str(e)}")

                    # 提取必要的群聊信息
                    if group_info and isinstance(group_info, dict):
                        # 递归函数用于查找特定key的值
                        def find_value(obj, key):
                            # 如果是字典
                            if isinstance(obj, dict):
                                # 直接检查当前字典
                                if key in obj:
                                    return obj[key]
                                # 检查带有"string"嵌套的字典
                                if key in obj and isinstance(obj[key], dict) and "string" in obj[key]:
                                    return obj[key]["string"]
                                # 递归检查字典的所有值
                                for k, v in obj.items():
                                    result = find_value(v, key)
                                    if result is not None:
                                        return result
                            # 如果是列表
                            elif isinstance(obj, list):
                                # 递归检查列表的所有项
                                for item in obj:
                                    result = find_value(item, key)
                                    if result is not None:
                                        return result
                            return None

                        # 尝试提取群名称及其他信息
                        group_name = None

                        # 首先尝试从NickName中获取
                        nickname_obj = find_value(group_info, "NickName")
                        if isinstance(nickname_obj, dict) and "string" in nickname_obj:
                            group_name = nickname_obj["string"]
                        elif isinstance(nickname_obj, str):
                            group_name = nickname_obj

                        # 如果没找到，尝试其他可能的字段
                        if not group_name:
                            for name_key in ["ChatRoomName", "nickname", "name", "DisplayName"]:
                                name_value = find_value(group_info, name_key)
                                if name_value:
                                    if isinstance(name_value, dict) and "string" in name_value:
                                        group_name = name_value["string"]
                                    elif isinstance(name_value, str):
                                        group_name = name_value
                                    if group_name:
                                        break

                        # 提取群主ID
                        owner_id = None
                        for owner_key in ["ChatRoomOwner", "chatroomowner", "Owner"]:
                            owner_value = find_value(group_info, owner_key)
                            if owner_value:
                                if isinstance(owner_value, dict) and "string" in owner_value:
                                    owner_id = owner_value["string"]
                                elif isinstance(owner_value, str):
                                    owner_id = owner_value
                                if owner_id:
                                    break

                        # 检查群聊信息是否已存在
                        if group_id in chatrooms_info:
                            # 更新已有群聊信息
                            if group_name:
                                chatrooms_info[group_id]["nickName"] = group_name
                            if owner_id:
                                chatrooms_info[group_id]["chatRoomOwner"] = owner_id
                            chatrooms_info[group_id]["last_update"] = int(time.time())
                        else:
                            # 创建新群聊信息
                            chatrooms_info[group_id] = {
                                "chatroomId": group_id,
                                "nickName": group_name or group_id,
                                "chatRoomOwner": owner_id or "",
                                "members": [],
                                "last_update": int(time.time())
                            }

                        # 保存到文件
                        with open(chatrooms_file, 'w', encoding='utf-8') as f:
                            json.dump(chatrooms_info, f, ensure_ascii=False, indent=2)

                        logger.info(f"[WechatPadPro] 已更新群聊 {group_id} 基础信息")

                        # 缓存群名
                        if group_name:
                            if not hasattr(self, "group_name_cache"):
                                self.group_name_cache = {}
                            self.group_name_cache[cache_key] = group_name

                            # 异步获取群成员详情（不阻塞当前方法）
                            threading.Thread(target=lambda: asyncio.run(self._get_group_member_details(group_id))).start()

                            return group_name

                except Exception as save_err:
                    logger.error(f"[WechatPadPro] 保存群聊信息到文件失败: {save_err}")
                    import traceback
                    logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")

                # 如果上面的处理没有返回群名称，再次尝试从原始数据中提取
                if group_info and isinstance(group_info, dict):
                    # 尝试从API返回中获取群名称
                    group_name = None

                    # 尝试多种可能的字段名
                    possible_fields = ["NickName", "nickname", "ChatRoomName", "chatroomname", "DisplayName", "displayname"]
                    for field in possible_fields:
                        if field in group_info and group_info[field]:
                            group_name = group_info[field]
                            if isinstance(group_name, dict) and "string" in group_name:
                                group_name = group_name["string"]
                            break

                    if group_name:
                        logger.debug(f"[WechatPadPro] 获取到群名称: {group_name}")

                        # 缓存群名
                        if not hasattr(self, "group_name_cache"):
                            self.group_name_cache = {}
                        self.group_name_cache[cache_key] = group_name

                        # 异步获取群成员详情
                        threading.Thread(target=lambda: asyncio.run(self._get_group_member_details(group_id))).start()

                        return group_name
                    else:
                        logger.warning(f"[WechatPadPro] API返回成功但未找到群名称字段: {json.dumps(group_info, ensure_ascii=False)}")
                else:
                    logger.warning(f"[WechatPadPro] API返回无效数据: {group_info}")
            except Exception as e:
                # 详细记录API请求失败的错误信息
                logger.error(f"[WechatPadPro] 使用群聊API获取群名称失败: {e}")
                logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
                logger.error(f"[WechatPadPro] 请求参数: {json.dumps(params, ensure_ascii=False)}")

            # 如果无法获取群名，使用群ID作为名称
            logger.debug(f"[WechatPadPro] 无法获取群名称，使用群ID代替: {group_id}")
            # 缓存结果
            if not hasattr(self, "group_name_cache"):
                self.group_name_cache = {}
            self.group_name_cache[cache_key] = group_id

            # 尽管获取群名失败，仍然尝试获取群成员详情
            threading.Thread(target=lambda: asyncio.run(self._get_group_member_details(group_id))).start()

            return group_id
        except Exception as e:
            logger.error(f"[WechatPadPro] 获取群名称失败: {e}")
            logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
            return group_id

    async def _get_chatroom_member_nickname(self, group_id, member_wxid):
        """获取群成员的昵称"""
        if not group_id or not member_wxid:
            return member_wxid

        try:
            # 优先从缓存获取群成员信息
            tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")
            chatrooms_file = os.path.join(tmp_dir, 'wechatpadpro_rooms.json')

            if os.path.exists(chatrooms_file):
                with open(chatrooms_file, 'r', encoding='utf-8') as f:
                    chatrooms_info = json.load(f)

                if group_id in chatrooms_info and "members" in chatrooms_info[group_id]:
                    for member in chatrooms_info[group_id]["members"]:
                        if member.get("UserName") == member_wxid:
                            # 优先使用群内显示名称(群昵称)
                            if member.get("DisplayName"):
                                logger.debug(f"[WechatPadPro] 获取到成员 {member_wxid} 的群昵称: {member.get('DisplayName')}")
                                return member.get("DisplayName")
                            # 其次使用成员昵称
                            elif member.get("NickName"):
                                logger.debug(f"[WechatPadPro] 获取到成员 {member_wxid} 的昵称: {member.get('NickName')}")
                                return member.get("NickName")

            # 如果缓存中没有，尝试更新群成员信息
            await self._get_group_member_details(group_id)

            # 再次尝试从更新后的缓存中获取
            if os.path.exists(chatrooms_file):
                with open(chatrooms_file, 'r', encoding='utf-8') as f:
                    chatrooms_info = json.load(f)

                if group_id in chatrooms_info and "members" in chatrooms_info[group_id]:
                    for member in chatrooms_info[group_id]["members"]:
                        if member.get("UserName") == member_wxid:
                            # 优先使用群内显示名称
                            if member.get("DisplayName"):
                                logger.debug(f"[WechatPadPro] 更新后获取到成员 {member_wxid} 的群昵称: {member.get('DisplayName')}")
                                return member.get("DisplayName")
                            # 其次使用成员昵称
                            elif member.get("NickName"):
                                logger.debug(f"[WechatPadPro] 更新后获取到成员 {member_wxid} 的昵称: {member.get('NickName')}")
                                return member.get("NickName")
        except Exception as e:
            logger.error(f"[WechatPadPro] 获取群成员昵称出错: {e}")

        # 默认返回wxid
        return member_wxid

    async def _get_current_login_wxid(self):
        """获取当前API服务器登录的微信账号"""
        try:
            # 尝试通过profile接口获取当前登录账号
            response = await self._call_api("/User/Profile", {"Wxid": ""})

            if response and isinstance(response, dict) and response.get("Success", False):
                data = response.get("Data", {})
                userinfo = data.get("userInfo", {})
                # 尝试获取userName，这通常是wxid
                if "userName" in userinfo:
                    return userinfo["userName"]
                # 尝试获取UserName，有些版本可能是大写
                elif "UserName" in userinfo:
                    return userinfo["UserName"]
                # 尝试获取string结构中的wxid
                elif isinstance(userinfo, dict):
                    for key in ["userName", "UserName"]:
                        if key in userinfo and isinstance(userinfo[key], dict) and "string" in userinfo[key]:
                            return userinfo[key]["string"]

            # 如果以上方法都失败，尝试通过其他接口
            response = await self._call_api("/User/GetSelfInfo", {})
            if response and isinstance(response, dict) and response.get("Success", False):
                data = response.get("Data", {})
                return data.get("Wxid", "")

            return ""
        except Exception as e:
            logger.error(f"[WechatPadPro] 获取当前登录账号失败: {e}")
            return ""

    async def _check_api_login_consistency(self, saved_wxid):
        """检查API服务器登录的账号是否与保存的一致"""
        try:
            # 尝试获取当前登录的用户信息
            profile = await self.bot.get_profile()

            if not profile or not isinstance(profile, dict):
                logger.warning("[WechatPadPro] 获取用户资料失败，无法确认登录一致性")
                return False

            # 提取当前登录用户的wxid
            current_wxid = None
            userinfo = profile.get("userInfo", {})

            if isinstance(userinfo, dict):
                if "wxid" in userinfo:
                    current_wxid = userinfo["wxid"]
                elif "userName" in userinfo:
                    current_wxid = userinfo["userName"]
                elif "UserName" in userinfo:
                    current_wxid = userinfo["UserName"]

            # 如果没有获取到当前wxid，返回False
            if not current_wxid:
                logger.warning("[WechatPadPro] 无法从用户资料中获取wxid，无法确认登录一致性")
                return False

            # 比较当前wxid与保存的wxid是否一致
            is_consistent = (current_wxid == saved_wxid)

            if is_consistent:
                logger.info(f"[WechatPadPro] API服务器登录用户与本地保存一致: {saved_wxid}")
            else:
                logger.warning(f"[WechatPadPro] API服务器登录用户 ({current_wxid}) 与本地保存 ({saved_wxid}) 不一致")

            return is_consistent
        except Exception as e:
            logger.error(f"[WechatPadPro] 检查登录一致性失败: {e}")
            return False

    async def _get_messages_simple(self):
        """获取新消息 - 带超时控制的版本，支持8059协议"""
        import time
        start_time = time.time()

        try:
            # 检查协议版本，使用不同的消息获取方式
            protocol_version = conf().get("wechatpadpro_protocol_version", "8059")

            if protocol_version == "8059":
                # 8059协议使用WebSocket实时消息推送
                logger.debug("[WechatPadPro8059] 使用WebSocket获取消息")

                try:
                    # 直接从WebSocket消息队列获取消息
                    sync_data = await self.bot.get_sync_msg()

                    elapsed = time.time() - start_time

                    if not sync_data:
                        return []

                    # 8059协议的消息格式处理
                    messages = []
                    if isinstance(sync_data, list):
                        messages = sync_data
                    elif isinstance(sync_data, dict):
                        if 'MsgList' in sync_data:
                            messages = sync_data['MsgList']
                        elif 'Messages' in sync_data:
                            messages = sync_data['Messages']

                    if messages:
                        logger.info(f"[WechatPadPro8059] 获取到 {len(messages)} 条新消息 (耗时{elapsed:.2f}s)")
                        return messages
                    else:
                        return []

                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.error(f"[WechatPadPro8059] WebSocket获取消息失败 (耗时{elapsed:.2f}s): {e}")
                    return []

            else:
                # 其他协议使用原有的sync_message方式
                timeout = 20  # 20秒超时，允许协议容器的最大延迟
                try:
                    success, data = await asyncio.wait_for(
                        self.bot.sync_message(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    logger.warning(f"[WechatPadPro] sync_message超时 ({elapsed:.2f}s)，跳过本次同步")
                    return []

                elapsed = time.time() - start_time
                logger.debug(f"[WechatPadPro] sync_message完成: success={success}, 耗时={elapsed:.2f}s")

                if not success:
                    logger.debug(f"[WechatPadPro] sync_message失败")
                    return []

                if not data:
                    logger.debug(f"[WechatPadPro] sync_message返回空数据")
                    return []

                if not isinstance(data, dict):
                    logger.debug(f"[WechatPadPro] sync_message返回数据不是字典: {type(data)}")
                    return []

                # 显示数据结构（仅在有消息时）
                if 'AddMsgs' in data and isinstance(data['AddMsgs'], list) and data['AddMsgs']:
                    logger.debug(f"[WechatPadPro] sync_message数据键: {list(data.keys())}")

                # 检查AddMsgs字段（主要的消息存储位置）
                if 'AddMsgs' in data:
                    add_msgs = data['AddMsgs']

                    if isinstance(add_msgs, list) and add_msgs:
                        logger.info(f"[WechatPadPro] 获取到 {len(add_msgs)} 条新消息 (耗时{elapsed:.2f}s)")
                        return add_msgs

                # 没有新消息（不输出调试日志，减少噪音）
                return []

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[WechatPadPro] 获取消息失败 (耗时{elapsed:.2f}s): {e}")
            return []

    async def _send_app_xml(self, to_user_id, xml_content, app_type: int):
        """发送App XML消息的异步方法 - 8059协议专用"""
        try:
            if not to_user_id:
                logger.error("[WechatPadPro8059] Send App XML failed: receiver ID is empty")
                return None
            if not xml_content or not isinstance(xml_content, str):
                logger.error("[WechatPadPro8059] Send App XML failed: XML content is invalid or not a string")
                return None
            if not xml_content.strip():
                logger.error("[WechatPadPro8059] Send App XML failed: XML content is empty string")
                return None

            # 8059协议使用send_app_message方法
            try:
                success = await self.bot.send_app_message(
                    to_username=to_user_id,
                    content_type=app_type,
                    content_xml=xml_content
                )

                if success:
                    logger.info(f"[WechatPadPro8059] 发送App消息成功: 接收者: {to_user_id}, Type: {app_type}")
                    return {
                        "Success": True,
                        "Message": "App消息发送成功"
                    }
                else:
                    logger.error(f"[WechatPadPro8059] 发送App消息失败: 接收者: {to_user_id}, Type: {app_type}")
                    return {
                        "Success": False,
                        "Message": "App消息发送失败"
                    }
            except Exception as e:
                logger.error(f"[WechatPadPro8059] 发送App消息异常: {e}")
                return {"Success": False, "Message": f"App消息发送异常: {e}"}

        except Exception as e:
            logger.error(f"[WechatPadPro8059] Send App XML failed (General Exception in _send_app_xml): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"Success": False, "Message": f"Exception in _send_app_xml: {e}"}

    async def _send_app(self, to_user_id, app_content):
        """发送小程序消息的异步方法 - 8059协议专用"""
        try:
            if not to_user_id:
                logger.error("[WechatPadPro8059] Send App failed: receiver ID is empty")
                return None
            if not app_content or not isinstance(app_content, str):
                logger.error("[WechatPadPro8059] Send App failed: App content is invalid or not a string")
                return None
            if not app_content.strip():
                logger.error("[WechatPadPro8059] Send App failed: App content is empty string")
                return None

            # 小程序消息通常使用content_type=33
            app_type = 33

            # 8059协议使用send_app_message方法发送小程序
            try:
                success = await self.bot.send_app_message(
                    to_username=to_user_id,
                    content_type=app_type,
                    content_xml=app_content
                )

                if success:
                    logger.info(f"[WechatPadPro8059] 发送小程序消息成功: 接收者: {to_user_id}")
                    return {
                        "Success": True,
                        "Message": "小程序消息发送成功"
                    }
                else:
                    logger.error(f"[WechatPadPro8059] 发送小程序消息失败: 接收者: {to_user_id}")
                    return {
                        "Success": False,
                        "Message": "小程序消息发送失败"
                    }
            except Exception as e:
                logger.error(f"[WechatPadPro8059] 发送小程序消息异常: {e}")
                return {"Success": False, "Message": f"小程序消息发送异常: {e}"}

        except Exception as e:
            logger.error(f"[WechatPadPro8059] Send App failed (General Exception in _send_app): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"Success": False, "Message": f"Exception in _send_app: {e}"}

    async def _send_voice(self, to_user_id, voice_file_path_segment):
        """发送语音消息的异步方法 - 8059协议专用，支持SILK转换"""
        try:
            if not to_user_id:
                logger.error("[WechatPadPro8059] Send voice failed: receiver ID is empty")
                return {"Success": False, "Message": "Receiver ID empty"}
            if not os.path.exists(voice_file_path_segment):
                logger.error(f"[WechatPadPro8059] Send voice failed: voice segment file not found at {voice_file_path_segment}")
                return {"Success": False, "Message": f"Voice segment not found: {voice_file_path_segment}"}

            # 微信语音条只支持SILK格式，需要转换
            silk_file_path = None
            temp_files_to_clean = []

            try:
                # 检查是否已经是SILK格式
                if voice_file_path_segment.lower().endswith(('.silk', '.sil', '.slk')):
                    silk_file_path = voice_file_path_segment
                    # 对于已有的SILK文件，尝试获取时长
                    try:
                        import pilk
                        duration_ms = pilk.get_duration(silk_file_path)
                        duration_seconds = max(1, int(duration_ms / 1000))
                        logger.debug(f"[WechatPadPro8059] 文件已是SILK格式: {voice_file_path_segment}, 时长={duration_seconds}秒")
                    except Exception as e:
                        duration_seconds = 10  # 默认10秒
                        logger.warning(f"[WechatPadPro8059] 无法获取SILK文件时长，使用默认值: {e}")
                else:
                    # 转换为SILK格式
                    from voice.audio_convert import any_to_sil
                    import tempfile

                    # 创建临时SILK文件
                    temp_dir = TmpDir().path()
                    silk_filename = f"voice_{int(time.time())}_{os.path.basename(voice_file_path_segment)}.silk"
                    silk_file_path = os.path.join(temp_dir, silk_filename)
                    temp_files_to_clean.append(silk_file_path)

                    logger.info(f"[WechatPadPro8059] 转换语音为SILK格式: {voice_file_path_segment} -> {silk_file_path}")

                    # 执行转换
                    duration_ms = any_to_sil(voice_file_path_segment, silk_file_path)
                    duration_seconds = max(1, int(duration_ms / 1000))
                    logger.info(f"[WechatPadPro8059] SILK转换成功: 时长={duration_ms}ms ({duration_seconds}秒)")

                # 使用8059协议发送SILK文件（传递正确的时长）
                from pathlib import Path
                silk_path_obj = Path(silk_file_path)
                client_msg_id, create_time, new_msg_id = await self.bot.send_voice_message_with_duration(
                    wxid=to_user_id,
                    voice=silk_path_obj,
                    duration_seconds=duration_seconds
                )
                logger.info(f"[WechatPadPro8059] 发送SILK语音消息成功: 接收者: {to_user_id}")

                return {
                    "Success": True,
                    "Data": {
                        "ClientMsgId": client_msg_id,
                        "CreateTime": create_time,
                        "NewMsgId": new_msg_id
                    }
                }

            except Exception as e:
                logger.error(f"[WechatPadPro8059] 发送语音消息失败: {e}")
                return {"Success": False, "Error": str(e)}

            finally:
                # 清理临时文件
                for temp_file in temp_files_to_clean:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            logger.debug(f"[WechatPadPro8059] 清理临时SILK文件: {temp_file}")
                    except Exception as cleanup_e:
                        logger.warning(f"[WechatPadPro8059] 清理临时文件失败: {temp_file}, 错误: {cleanup_e}")

        except Exception as e:
            logger.error(f"[WechatPadPro8059] Exception in _send_voice for {voice_file_path_segment} to {to_user_id}: {e}")
            logger.error(traceback.format_exc())
            return {"Success": False, "Message": f"General exception in _send_voice: {e}"}

    def _compose_context(self, ctype: ContextType, content, **kwargs):
        """重写父类方法，构建消息上下文"""
        try:
            # 直接创建Context对象，确保结构正确
            context = Context()
            context.type = ctype
            context.content = content

            # 获取消息对象
            msg = kwargs.get('msg')

            # 检查是否是群聊消息
            isgroup = kwargs.get('isgroup', False)
            if isgroup and msg and hasattr(msg, 'from_user_id'):
                # 设置群组相关信息
                context["isgroup"] = True

                # 优先使用actual_user_nickname，如果没有则使用sender_wxid
                actual_nickname = getattr(msg, 'actual_user_nickname', None)
                if actual_nickname and actual_nickname != getattr(msg, 'sender_wxid', ''):
                    context["from_user_nickname"] = actual_nickname
                else:
                    # 尝试同步获取昵称
                    sender_id = getattr(msg, 'sender_wxid', '')
                    if sender_id and msg.from_user_id.endswith("@chatroom"):
                        try:
                            # 同步获取昵称
                            import asyncio
                            nickname = asyncio.run(self._get_chatroom_member_nickname(msg.from_user_id, sender_id))
                            if nickname and nickname != sender_id:
                                context["from_user_nickname"] = nickname
                                # 同时更新msg对象
                                msg.actual_user_nickname = nickname
                            else:
                                context["from_user_nickname"] = sender_id
                        except Exception as e:
                            logger.debug(f"[WechatPadPro] 同步获取昵称失败: {e}")
                            context["from_user_nickname"] = sender_id
                    else:
                        context["from_user_nickname"] = sender_id

                context["from_user_id"] = msg.sender_wxid  # 发送者ID
                context["to_user_id"] = msg.to_user_id  # 接收者ID
                context["other_user_id"] = msg.other_user_id or msg.from_user_id  # 群ID
                context["group_name"] = msg.from_user_id  # 临时使用群ID作为群名
                context["group_id"] = msg.from_user_id  # 群ID
                context["msg"] = msg  # 消息对象

                # 设置session_id为群ID
                context["session_id"] = msg.other_user_id or msg.from_user_id

            else:
                # 私聊消息
                context["isgroup"] = False
                context["from_user_nickname"] = msg.sender_wxid if msg and hasattr(msg, 'sender_wxid') else ""
                context["from_user_id"] = msg.sender_wxid if msg and hasattr(msg, 'sender_wxid') else ""
                context["to_user_id"] = msg.to_user_id if msg and hasattr(msg, 'to_user_id') else ""
                context["other_user_id"] = None
                context["msg"] = msg

                # 设置session_id为发送者ID
                context["session_id"] = msg.sender_wxid if msg and hasattr(msg, 'sender_wxid') else ""

            # 添加接收者信息
            context["receiver"] = msg.from_user_id if isgroup else msg.sender_wxid

            # 记录原始消息类型
            context["origin_ctype"] = ctype

            # 添加调试日志
            logger.debug(f"[WechatPadPro] 生成Context对象: type={context.type}, content={context.content}, isgroup={context['isgroup']}, session_id={context.get('session_id', 'None')}")

            try:
                # 手动触发 ON_RECEIVE_MESSAGE 事件
                e_context = EventContext(Event.ON_RECEIVE_MESSAGE, {"channel": self, "context": context})
                PluginManager().emit_event(e_context)
                context = e_context["context"] # 获取可能被修改的 context

                # 检查插件是否阻止了消息 或 清空了 context
                if e_context.is_pass() or context is None:
                    logger.info(f"[WechatPadPro] Event ON_RECEIVE_MESSAGE breaked or context is None by plugin {e_context.get('breaked_by', 'N/A')}. Returning early.")
                    return context # 返回 None 或被插件修改的 context
            except Exception as plugin_e:
                logger.error(f"[WechatPadPro] Error during ON_RECEIVE_MESSAGE event processing: {plugin_e}", exc_info=True)
                # 根据需要决定是否继续，这里选择继续返回原始 context
            # --- 结束插入修改 ---

            return context # 返回（可能被插件修改过的）context
        except Exception as e:
            # ... (原有的错误处理 L4875-L4878) ...
            logger.error(f"[WechatPadPro] 构建上下文失败: {e}")
            logger.error(f"[WechatPadPro] 详细错误: {traceback.format_exc()}")
            return None
