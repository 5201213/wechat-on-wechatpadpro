import aiohttp
import websockets
import json
import asyncio
from asyncio import Queue, sleep
from pathlib import Path
from .base import WechatAPIClientBase
from ..errors import MessageError
from loguru import logger

class MessageMixin(WechatAPIClientBase):
    """8059协议消息相关功能混入类"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._websocket = None
        self._ws_task = None
        self._message_queue = Queue()
        self._ws_connected = False
        self._is_processing = False

    async def _process_message_queue(self):
        """处理消息队列的异步方法"""
        if self._is_processing:
            return

        self._is_processing = True
        while True:
            if self._message_queue.empty():
                self._is_processing = False
                break

            func, args, kwargs, future = await self._message_queue.get()
            try:
                result = await func(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._message_queue.task_done()
                await sleep(1)  # 消息发送间隔1秒

    async def send_text_message(self, wxid: str, content: str, at: str = "") -> tuple:
        """发送文本消息

        Args:
            wxid (str): 接收者微信ID
            content (str): 消息内容
            at (str): @用户列表，多个用逗号分隔

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            # 构建8059协议的消息数据 - 使用正确的API格式
            data = {
                "MsgItem": [{
                    "ToUserName": wxid,
                    "MsgType": 1,  # 文本消息
                    "TextContent": content,
                    "ImageContent": "",  # 图片内容为空
                    "AtWxIDList": at.split(",") if at else []
                }]
            }

            # 使用正确的API路径
            response = await self._call_api("/message/SendTextMessage", data)

            # 处理不同的响应格式
            if isinstance(response, list):
                # 如果返回的是列表，取第一个元素
                if response and len(response) > 0:
                    response_data = response[0]
                    if isinstance(response_data, dict) and response_data.get("Code") == 200:
                        msg_data = response_data.get("Data", {})
                        client_msg_id = msg_data.get("ClientMsgId", 0)
                        create_time = msg_data.get("CreateTime", 0)
                        new_msg_id = msg_data.get("NewMsgId", "")

                        logger.debug(f"[WX8059] 发送文本消息成功: {wxid}")
                        return client_msg_id, create_time, new_msg_id
                    else:
                        if isinstance(response_data, dict):
                            error_msg = response_data.get("Text", response_data.get("Error", "发送消息失败"))
                        else:
                            error_msg = f"发送消息失败: 响应数据格式错误 {response_data}"
                        logger.error(f"[WX8059] 发送文本消息失败: {error_msg}")
                        raise MessageError(error_msg)
                else:
                    logger.error("[WX8059] 发送文本消息失败: 空响应列表")
                    raise MessageError("发送消息失败: 空响应")
            elif isinstance(response, dict):
                # 如果返回的是字典
                if response.get("Code") == 200:
                    msg_data = response.get("Data", {})

                    # 处理Data字段可能是列表的情况
                    if isinstance(msg_data, list):
                        if msg_data and len(msg_data) > 0:
                            first_data = msg_data[0]
                            if isinstance(first_data, dict):
                                client_msg_id = first_data.get("ClientMsgId", 0)
                                create_time = first_data.get("CreateTime", 0)
                                new_msg_id = first_data.get("NewMsgId", "")
                            else:
                                client_msg_id = 0
                                create_time = 0
                                new_msg_id = ""
                        else:
                            client_msg_id = 0
                            create_time = 0
                            new_msg_id = ""
                    elif isinstance(msg_data, dict):
                        client_msg_id = msg_data.get("ClientMsgId", 0)
                        create_time = msg_data.get("CreateTime", 0)
                        new_msg_id = msg_data.get("NewMsgId", "")
                    else:
                        client_msg_id = 0
                        create_time = 0
                        new_msg_id = ""

                    logger.debug(f"[WX8059] 发送文本消息成功: {wxid}")
                    return client_msg_id, create_time, new_msg_id
                else:
                    error_msg = response.get("Text", response.get("Error", "发送消息失败"))
                    logger.error(f"[WX8059] 发送文本消息失败: {error_msg}")
                    raise MessageError(error_msg)
            else:
                logger.error(f"[WX8059] 发送文本消息失败: 未知响应格式 {type(response)}")
                raise MessageError("发送消息失败: 未知响应格式")

        except Exception as e:
            logger.error(f"[WX8059] 发送文本消息异常: {e}")
            raise MessageError(f"发送文本消息失败: {e}")

    async def send_image_message(self, wxid: str, image_path: Path) -> tuple:
        """发送图片消息

        Args:
            wxid (str): 接收者微信ID
            image_path (Path): 图片文件路径

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            # 读取图片文件并转换为base64
            import base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            data = {
                "MsgItem": [{
                    "ToUserName": wxid,
                    "MsgType": 3,  # 图片消息
                    "TextContent": "",  # 文本内容为空
                    "ImageContent": image_data,
                    "AtWxIDList": []
                }]
            }

            # 使用正确的API路径
            response = await self._call_api("/message/SendImageMessage", data)

            # 记录详细的响应信息用于诊断
            logger.debug(f"[WX8059] 图片发送API响应: {response}")

            # 处理不同的响应格式（与文本消息保持一致）
            if isinstance(response, list):
                # 如果返回的是列表，取第一个元素
                if response and len(response) > 0:
                    response_data = response[0]
                    if isinstance(response_data, dict) and response_data.get("Code") == 200:
                        msg_data = response_data.get("Data", {})

                        # 处理8059协议图片发送的实际响应格式
                        if "imageId" in msg_data and "isSendSuccess" in msg_data:
                            # 8059协议图片发送的实际响应格式
                            if msg_data.get("isSendSuccess", False):
                                image_id = msg_data.get("imageId", "")
                                # 使用imageId作为消息标识
                                client_msg_id = hash(image_id) & 0x7FFFFFFF  # 生成正整数ID
                                create_time = int(__import__('time').time())  # 当前时间戳
                                new_msg_id = image_id  # 使用imageId作为NewMsgId

                                logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ImageId: {image_id}, ClientMsgId: {client_msg_id}")
                                return client_msg_id, create_time, new_msg_id
                            else:
                                logger.error(f"[WX8059] 发送图片消息失败: isSendSuccess为false, 响应数据: {msg_data}")
                                raise MessageError("发送图片失败: isSendSuccess为false")
                        else:
                            # 标准格式的响应处理
                            client_msg_id = msg_data.get("ClientMsgId", 0)
                            create_time = msg_data.get("CreateTime", 0)
                            new_msg_id = msg_data.get("NewMsgId", "")

                            # 验证是否获取到有效的消息ID
                            if client_msg_id > 0 or new_msg_id:
                                logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
                                return client_msg_id, create_time, new_msg_id
                            else:
                                logger.error(f"[WX8059] 发送图片消息失败: 获取到无效的消息ID, 响应数据: {msg_data}")
                                raise MessageError("发送图片失败: 获取到无效的消息ID")
                    else:
                        if isinstance(response_data, dict):
                            error_msg = response_data.get("Text", response_data.get("Error", "发送图片失败"))
                        else:
                            error_msg = f"发送图片失败: 响应数据格式错误 {response_data}"
                        logger.error(f"[WX8059] 发送图片消息失败: {error_msg}")
                        raise MessageError(error_msg)
                else:
                    logger.error("[WX8059] 发送图片消息失败: 空响应列表")
                    raise MessageError("发送图片失败: 空响应")
            elif isinstance(response, dict):
                # 如果返回的是字典
                if response.get("Code") == 200:
                    msg_data = response.get("Data", {})

                    # 处理Data字段可能是列表的情况
                    if isinstance(msg_data, list):
                        if msg_data and len(msg_data) > 0:
                            first_data = msg_data[0]
                            if isinstance(first_data, dict):
                                # 处理8059协议图片发送的实际响应格式
                                if "imageId" in first_data and "isSendSuccess" in first_data:
                                    if first_data.get("isSendSuccess", False):
                                        image_id = first_data.get("imageId", "")
                                        client_msg_id = hash(image_id) & 0x7FFFFFFF
                                        create_time = int(__import__('time').time())
                                        new_msg_id = image_id

                                        logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ImageId: {image_id}, ClientMsgId: {client_msg_id}")
                                        return client_msg_id, create_time, new_msg_id
                                    else:
                                        logger.error(f"[WX8059] 发送图片消息失败: isSendSuccess为false, 响应数据: {first_data}")
                                        raise MessageError("发送图片失败: isSendSuccess为false")
                                else:
                                    # 标准格式处理
                                    client_msg_id = first_data.get("ClientMsgId", 0)
                                    create_time = first_data.get("CreateTime", 0)
                                    new_msg_id = first_data.get("NewMsgId", "")

                                    if client_msg_id > 0 or new_msg_id:
                                        logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
                                        return client_msg_id, create_time, new_msg_id
                                    else:
                                        logger.error(f"[WX8059] 发送图片消息失败: 获取到无效的消息ID, 响应数据: {first_data}")
                                        raise MessageError("发送图片失败: 获取到无效的消息ID")
                            else:
                                logger.error(f"[WX8059] 发送图片消息失败: Data列表中的数据格式错误: {first_data}")
                                raise MessageError("发送图片失败: Data列表中的数据格式错误")
                        else:
                            logger.error(f"[WX8059] 发送图片消息失败: Data列表为空: {msg_data}")
                            raise MessageError("发送图片失败: Data列表为空")
                    elif isinstance(msg_data, dict):
                        # 处理8059协议图片发送的实际响应格式
                        if "imageId" in msg_data and "isSendSuccess" in msg_data:
                            if msg_data.get("isSendSuccess", False):
                                image_id = msg_data.get("imageId", "")
                                client_msg_id = hash(image_id) & 0x7FFFFFFF
                                create_time = int(__import__('time').time())
                                new_msg_id = image_id

                                logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ImageId: {image_id}, ClientMsgId: {client_msg_id}")
                                return client_msg_id, create_time, new_msg_id
                            else:
                                logger.error(f"[WX8059] 发送图片消息失败: isSendSuccess为false, 响应数据: {msg_data}")
                                raise MessageError("发送图片失败: isSendSuccess为false")
                        else:
                            # 标准格式处理
                            client_msg_id = msg_data.get("ClientMsgId", 0)
                            create_time = msg_data.get("CreateTime", 0)
                            new_msg_id = msg_data.get("NewMsgId", "")

                            if client_msg_id > 0 or new_msg_id:
                                logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
                                return client_msg_id, create_time, new_msg_id
                            else:
                                logger.error(f"[WX8059] 发送图片消息失败: 获取到无效的消息ID, 响应数据: {msg_data}")
                                raise MessageError("发送图片失败: 获取到无效的消息ID")
                    else:
                        logger.error(f"[WX8059] 发送图片消息失败: Data字段格式错误: {type(msg_data)}, 内容: {msg_data}")
                        raise MessageError("发送图片失败: Data字段格式错误")
                else:
                    error_msg = response.get("Text", response.get("Error", "发送图片失败"))
                    logger.error(f"[WX8059] 发送图片消息失败: {error_msg}")
                    raise MessageError(error_msg)
            else:
                # 处理直接返回数据的情况（没有Code和Data包装）
                if isinstance(response, dict) and "imageId" in response and "isSendSuccess" in response:
                    if response.get("isSendSuccess", False):
                        image_id = response.get("imageId", "")
                        client_msg_id = hash(image_id) & 0x7FFFFFFF
                        create_time = int(__import__('time').time())
                        new_msg_id = image_id

                        logger.debug(f"[WX8059] 发送图片消息成功: {wxid}, ImageId: {image_id}, ClientMsgId: {client_msg_id}")
                        return client_msg_id, create_time, new_msg_id
                    else:
                        logger.error(f"[WX8059] 发送图片消息失败: isSendSuccess为false, 响应数据: {response}")
                        raise MessageError("发送图片失败: isSendSuccess为false")
                else:
                    logger.error(f"[WX8059] 发送图片消息失败: 未知响应格式 {type(response)}, 内容: {response}")
                    raise MessageError("发送图片失败: 未知响应格式")

        except Exception as e:
            logger.error(f"[WX8059] 发送图片消息异常: {e}")
            raise MessageError(f"发送图片消息失败: {e}")

    async def send_voice_message(self, wxid: str, voice: Path) -> tuple:
        """发送语音消息

        Args:
            wxid (str): 接收者微信ID
            voice (Path): 语音文件路径

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            # 读取语音文件并转换为base64
            import base64
            with open(voice, 'rb') as f:
                voice_data = base64.b64encode(f.read()).decode('utf-8')

            # 微信语音条只支持SILK格式（格式4）
            # 调用此方法前应该已经转换为SILK格式
            voice_format = 4
            file_ext = voice.suffix.lower()
            if not file_ext in ['.silk', '.sil', '.slk']:
                logger.warning(f"[WX8059] 语音文件不是SILK格式 {file_ext}，但仍使用格式4发送")

            # 尝试获取语音时长
            voice_second = await self._get_audio_duration(voice)
            if voice_second <= 0:
                voice_second = 10  # 默认10秒

            data = {
                "ToUserName": wxid,
                "VoiceData": voice_data,
                "VoiceFormat": voice_format,
                "VoiceSecond": voice_second
            }

            logger.info(f"[WX8059] 发送语音: 格式={voice_format}, 时长={voice_second}秒, 文件={voice}")

            # 使用正确的API路径
            response = await self._call_api("/message/SendVoice", data)

            if response and response.get("Code") == 200:
                msg_data = response.get("Data", {})
                client_msg_id = msg_data.get("ClientMsgId", 0)
                create_time = msg_data.get("CreateTime", 0)
                new_msg_id = msg_data.get("NewMsgId", "")

                logger.info(f"[WX8059] 发送语音消息成功: {wxid}, 格式={voice_format}, 时长={voice_second}秒")
                return client_msg_id, create_time, new_msg_id
            else:
                error_msg = response.get("Text", response.get("Error", "发送语音失败"))
                logger.error(f"[WX8059] 发送语音消息失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 发送语音消息异常: {e}")
            raise MessageError(f"发送语音消息失败: {e}")

    async def send_voice_message_with_duration(self, wxid: str, voice: Path, duration_seconds: int) -> tuple:
        """发送语音消息（指定时长）

        Args:
            wxid (str): 接收者微信ID
            voice (Path): 语音文件路径（SILK格式）
            duration_seconds (int): 语音时长（秒）

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            # 读取语音文件并转换为base64
            import base64
            with open(voice, 'rb') as f:
                voice_data = base64.b64encode(f.read()).decode('utf-8')

            # 固定使用SILK格式（格式4）
            voice_format = 4

            data = {
                "ToUserName": wxid,
                "VoiceData": voice_data,
                "VoiceFormat": voice_format,
                "VoiceSecond": duration_seconds
            }

            logger.info(f"[WX8059] 发送语音: 格式={voice_format}, 时长={duration_seconds}秒, 文件={voice}")

            # 使用正确的API路径
            response = await self._call_api("/message/SendVoice", data)

            if response and response.get("Code") == 200:
                msg_data = response.get("Data", {})
                client_msg_id = msg_data.get("ClientMsgId", 0)
                create_time = msg_data.get("CreateTime", 0)
                new_msg_id = msg_data.get("NewMsgId", "")

                logger.info(f"[WX8059] 发送语音消息成功: {wxid}, 格式={voice_format}, 时长={duration_seconds}秒")
                return client_msg_id, create_time, new_msg_id
            else:
                error_msg = response.get("Text", response.get("Error", "发送语音失败"))
                logger.error(f"[WX8059] 发送语音消息失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 发送语音消息异常: {e}")
            raise MessageError(f"发送语音消息失败: {e}")

    async def _get_audio_duration(self, audio_path: Path) -> int:
        """获取音频文件时长（秒）"""
        try:
            # 对于SILK格式，尝试使用pilk获取时长
            file_ext = audio_path.suffix.lower()
            if file_ext in ['.silk', '.sil', '.slk']:
                try:
                    import pilk
                    duration_raw = pilk.get_duration(str(audio_path))
                    logger.debug(f"[WX8059] pilk.get_duration原始返回值: {duration_raw}")

                    # pilk.get_duration返回毫秒，但可能有精度问题
                    # 从日志看，60秒的文件返回了120000ms，可能是采样率问题
                    if duration_raw > 100000:  # 如果大于100秒，可能是毫秒值有问题
                        # 尝试除以2看是否更合理（可能是采样率翻倍导致）
                        duration_ms = duration_raw / 2
                        logger.debug(f"[WX8059] 检测到异常大的时长值，尝试修正: {duration_raw} -> {duration_ms}")
                    else:
                        duration_ms = duration_raw

                    duration_seconds = max(1, int(duration_ms / 1000))
                    logger.info(f"[WX8059] pilk获取SILK时长: 原始={duration_raw}, 修正后={duration_ms}ms = {duration_seconds}秒")
                    return duration_seconds
                except Exception as e:
                    logger.debug(f"[WX8059] pilk获取SILK时长失败: {e}")

            # 尝试使用ffprobe获取音频时长
            import subprocess
            import json

            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', str(audio_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                info = json.loads(result.stdout)
                duration = float(info.get('format', {}).get('duration', 0))
                return max(1, int(duration))
        except Exception as e:
            logger.debug(f"[WX8059] 无法获取音频时长: {e}")

        # 如果都失败，尝试简单的文件大小估算
        try:
            file_size = audio_path.stat().st_size
            file_ext = audio_path.suffix.lower()

            if file_ext in ['.silk', '.sil', '.slk']:
                # SILK格式估算：约8kbps，1秒约1KB
                estimated_duration = file_size / 1024
            else:
                # 其他格式估算：128kbps，1秒约16KB
                estimated_duration = file_size / (16 * 1024)

            return max(1, int(estimated_duration))
        except Exception:
            return 10  # 默认10秒

    async def forward_video_message(self, wxid: str, aes_key: str, cdn_video_url: str, length: int, play_length: int, cdn_thumb_length: int) -> tuple:
        """转发视频消息

        Args:
            wxid (str): 接收者微信ID
            aes_key (str): AES密钥
            cdn_video_url (str): CDN视频URL
            length (int): 视频长度
            play_length (int): 播放长度
            cdn_thumb_length (int): 缩略图长度

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            data = {
                "ForwardVideoList": [{
                    "ToUserName": wxid,
                    "AesKey": aes_key,
                    "CdnVideoUrl": cdn_video_url,
                    "Length": length,
                    "PlayLength": play_length,
                    "CdnThumbLength": cdn_thumb_length
                }]
            }

            response = await self._call_api("/message/ForwardVideoMessage", data)

            # 记录详细的响应信息用于诊断
            logger.info(f"[WX8059] 视频转发API响应: {response}")

            # 处理不同的响应格式（基于实际响应结构修正）
            if isinstance(response, list):
                # 如果返回的是列表，取第一个元素
                if response and len(response) > 0:
                    response_data = response[0]
                    if isinstance(response_data, dict):
                        # 检查是否发送成功
                        is_send_success = response_data.get("isSendSuccess", False)
                        ret_code = response_data.get("retCode", -1)

                        if is_send_success and ret_code == 0:
                            # 从resp字段中提取消息ID
                            resp_data = response_data.get("resp", {})
                            if isinstance(resp_data, dict):
                                client_msg_id = resp_data.get("ClientMsgId", "")
                                create_time = 0  # 转发响应中没有CreateTime
                                new_msg_id = resp_data.get("NewMsgId", 0)
                                msg_id = resp_data.get("MsgId", 0)

                                # 验证是否获取到有效的消息ID（ClientMsgId是字符串格式）
                                if client_msg_id or new_msg_id or msg_id:
                                    logger.info(f"[WX8059] 转发视频消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}, MsgId: {msg_id}")
                                    return client_msg_id, create_time, new_msg_id
                                else:
                                    logger.error(f"[WX8059] 转发视频消息失败: 获取到无效的消息ID, resp数据: {resp_data}")
                                    raise MessageError("转发视频失败: 获取到无效的消息ID")
                            else:
                                logger.error(f"[WX8059] 转发视频消息失败: resp字段格式错误, 响应数据: {response_data}")
                                raise MessageError("转发视频失败: resp字段格式错误")
                        else:
                            error_msg = response_data.get("errMsg", "转发视频失败")
                            logger.error(f"[WX8059] 转发视频消息失败: isSendSuccess={is_send_success}, retCode={ret_code}, errMsg={error_msg}")
                            raise MessageError(f"转发视频失败: {error_msg}")
                    else:
                        logger.error(f"[WX8059] 转发视频消息失败: 响应数据格式错误 {response_data}")
                        raise MessageError("转发视频失败: 响应数据格式错误")
                else:
                    logger.error("[WX8059] 转发视频消息失败: 空响应列表")
                    raise MessageError("转发视频失败: 空响应")
            elif isinstance(response, dict):
                # 如果返回的是字典（标准8059协议格式）
                if response.get("Code") == 200:
                    msg_data = response.get("Data", {})

                    # 处理Data字段可能是列表的情况（包含实际的转发响应格式）
                    if isinstance(msg_data, list):
                        if msg_data and len(msg_data) > 0:
                            first_data = msg_data[0]
                            if isinstance(first_data, dict):
                                # 检查是否是新的响应格式
                                if "isSendSuccess" in first_data and "resp" in first_data:
                                    is_send_success = first_data.get("isSendSuccess", False)
                                    ret_code = first_data.get("retCode", -1)

                                    if is_send_success and ret_code == 0:
                                        resp_data = first_data.get("resp", {})
                                        client_msg_id = resp_data.get("ClientMsgId", "")
                                        create_time = 0
                                        new_msg_id = resp_data.get("NewMsgId", 0)
                                        msg_id = resp_data.get("MsgId", 0)
                                    else:
                                        client_msg_id = ""
                                        create_time = 0
                                        new_msg_id = 0
                                else:
                                    # 旧格式
                                    client_msg_id = first_data.get("ClientMsgId", 0)
                                    create_time = first_data.get("CreateTime", 0)
                                    new_msg_id = first_data.get("NewMsgId", "")
                            else:
                                client_msg_id = ""
                                create_time = 0
                                new_msg_id = 0
                        else:
                            client_msg_id = ""
                            create_time = 0
                            new_msg_id = 0
                    elif isinstance(msg_data, dict):
                        # 检查是否是新的响应格式
                        if "isSendSuccess" in msg_data and "resp" in msg_data:
                            is_send_success = msg_data.get("isSendSuccess", False)
                            ret_code = msg_data.get("retCode", -1)

                            if is_send_success and ret_code == 0:
                                resp_data = msg_data.get("resp", {})
                                client_msg_id = resp_data.get("ClientMsgId", "")
                                create_time = 0
                                new_msg_id = resp_data.get("NewMsgId", 0)
                                msg_id = resp_data.get("MsgId", 0)
                            else:
                                client_msg_id = ""
                                create_time = 0
                                new_msg_id = 0
                        else:
                            # 旧格式
                            client_msg_id = msg_data.get("ClientMsgId", 0)
                            create_time = msg_data.get("CreateTime", 0)
                            new_msg_id = msg_data.get("NewMsgId", "")
                    else:
                        client_msg_id = ""
                        create_time = 0
                        new_msg_id = 0

                    # 验证是否获取到有效的消息ID
                    if client_msg_id or new_msg_id:
                        logger.info(f"[WX8059] 转发视频消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
                        return client_msg_id, create_time, new_msg_id
                    else:
                        logger.error(f"[WX8059] 转发视频消息失败: 获取到无效的消息ID, 响应数据: {msg_data}")
                        raise MessageError("转发视频失败: 获取到无效的消息ID")
                else:
                    error_msg = response.get("Text", response.get("Error", "转发视频失败"))
                    logger.error(f"[WX8059] 转发视频消息失败: {error_msg}")
                    raise MessageError(error_msg)
            else:
                logger.error(f"[WX8059] 转发视频消息失败: 未知响应格式 {type(response)}, 内容: {response}")
                raise MessageError("转发视频失败: 未知响应格式")

        except Exception as e:
            logger.error(f"[WX8059] 转发视频消息异常: {e}")
            raise MessageError(f"转发视频消息失败: {e}")

    async def revoke_message(self, to_user_name: str, client_msg_id: int, create_time: int, new_msg_id: str) -> bool:
        """撤回消息

        Args:
            to_user_name (str): 接收者
            client_msg_id (int): 客户端消息ID
            create_time (int): 创建时间
            new_msg_id (str): 新消息ID

        Returns:
            bool: 撤回是否成功
        """
        try:
            data = {
                "ToUserName": to_user_name,
                "ClientMsgId": client_msg_id,
                "CreateTime": create_time,
                "NewMsgId": new_msg_id
            }

            response = await self._call_api("/message/RevokeMsg", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 撤回消息成功: {new_msg_id}")
                return True
            else:
                error_msg = response.get("Text", "撤回消息失败")
                logger.error(f"[WX8059] 撤回消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 撤回消息异常: {e}")
            return False

    async def add_message_to_mgr(self, to_username: str, msg_type: int, text_content: str = "",
                                image_content: str = "", at_wxid_list: list = None) -> bool:
        """添加单条消息到管理器

        Args:
            to_username (str): 接收者用户名
            msg_type (int): 消息类型 (1=文本, 3=图片等)
            text_content (str): 文本内容
            image_content (str): 图片内容(Base64)
            at_wxid_list (list): @用户列表

        Returns:
            bool: 添加是否成功
        """
        try:
            data = {
                "MsgItem": [{
                    "ToUserName": to_username,
                    "MsgType": msg_type,
                    "TextContent": text_content,
                    "ImageContent": image_content,
                    "AtWxIDList": at_wxid_list or []
                }]
            }

            response = await self._call_api("/message/AddMessageMgr", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 添加消息到管理器成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "添加消息到管理器失败")
                logger.error(f"[WX8059] 添加消息到管理器失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 添加消息到管理器异常: {e}")
            return False

    async def add_messages_to_mgr(self, msg_items: list) -> bool:
        """批量添加消息到管理器

        Args:
            msg_items (list): 消息项列表，每个项目应包含:
                - ToUserName (str): 接收者用户名
                - MsgType (int): 消息类型
                - TextContent (str): 文本内容
                - ImageContent (str): 图片内容
                - AtWxIDList (list): @用户列表

        Returns:
            bool: 添加是否成功
        """
        try:
            # 验证参数格式
            validated_items = []
            for item in msg_items:
                if not isinstance(item, dict):
                    raise ValueError("msg_items中的每个项目必须是字典")

                required_fields = ["ToUserName", "MsgType"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"msg_items中缺少必需字段: {field}")

                validated_items.append({
                    "ToUserName": item["ToUserName"],
                    "MsgType": item["MsgType"],
                    "TextContent": item.get("TextContent", ""),
                    "ImageContent": item.get("ImageContent", ""),
                    "AtWxIDList": item.get("AtWxIDList", [])
                })

            data = {
                "MsgItem": validated_items
            }

            response = await self._call_api("/message/AddMessageMgr", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 批量添加消息到管理器成功: {len(validated_items)} 条")
                return True
            else:
                error_msg = response.get("Text", "批量添加消息到管理器失败")
                logger.error(f"[WX8059] 批量添加消息到管理器失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 批量添加消息到管理器异常: {e}")
            return False

    # 保持向后兼容性的别名方法
    async def add_message_mgr(self, msg_items: list) -> bool:
        """添加要发送的文本消息进入管理器 (向后兼容方法)

        Args:
            msg_items (list): 消息项列表

        Returns:
            bool: 添加是否成功
        """
        return await self.add_messages_to_mgr(msg_items)

    async def cdn_upload_video(self, to_username: str, video_data: bytes, thumb_data: str) -> dict:
        """上传视频

        Args:
            to_username (str): 接收者用户名
            video_data (bytes): 视频数据
            thumb_data (str): 缩略图数据

        Returns:
            dict: 上传结果，包含CDN信息
                成功: {"success": True, "aes_key": "xxx", "cdn_video_url": "xxx", "length": 123, "play_length": 10, "cdn_thumb_length": 456}
                失败: {"success": False, "error": "错误信息"}
        """
        try:
            data = {
                "ThumbData": thumb_data,
                "ToUserName": to_username,
                "VideoData": list(video_data)  # 转换为数组格式
            }

            response = await self._call_api("/message/CdnUploadVideo", data)

            # 记录详细的响应信息用于诊断
            logger.info(f"[WX8059] 视频上传API响应: {response}")

            if response and response.get("Code") == 200:
                upload_data = response.get("Data", {})

                # 提取上传后的CDN信息（基于实际响应字段）
                aes_key = upload_data.get("FileAesKey", "")
                cdn_video_url = upload_data.get("FileID", "")
                length = upload_data.get("VideoDataSize", len(video_data))
                play_length = upload_data.get("PlayLength", 10)  # 默认10秒，响应中没有此字段
                cdn_thumb_length = upload_data.get("ThumbDataSize", len(thumb_data.encode()) if thumb_data else 0)

                logger.debug(f"[WX8059] 上传视频成功: {to_username}, FileAesKey: {aes_key[:20]}..., FileID: {cdn_video_url[:50]}...")

                return {
                    "success": True,
                    "aes_key": aes_key,
                    "cdn_video_url": cdn_video_url,
                    "length": length,
                    "play_length": play_length,
                    "cdn_thumb_length": cdn_thumb_length
                }
            else:
                error_msg = response.get("Text", "上传视频失败")
                logger.error(f"[WX8059] 上传视频失败: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"[WX8059] 上传视频异常: {e}")
            return {"success": False, "error": str(e)}

    async def send_video_message(self, wxid: str, video_path: Path, thumb_path: Path = None) -> tuple:
        """发送视频消息（先上传后转发）

        Args:
            wxid (str): 接收者微信ID
            video_path (Path): 视频文件路径
            thumb_path (Path): 缩略图文件路径，可选

        Returns:
            tuple: (client_msg_id, create_time, new_msg_id)
        """
        try:
            # 1. 读取视频文件
            with open(video_path, 'rb') as f:
                video_data = f.read()

            # 2. 读取缩略图文件（如果提供）
            thumb_data = ""
            if thumb_path and thumb_path.exists():
                import base64
                with open(thumb_path, 'rb') as f:
                    thumb_bytes = f.read()
                    thumb_data = base64.b64encode(thumb_bytes).decode('utf-8')
                logger.debug(f"[WX8059] 读取缩略图: {thumb_path}, 大小: {len(thumb_bytes)} bytes")
            else:
                logger.debug(f"[WX8059] 未提供缩略图或文件不存在: {thumb_path}")

            # 3. 上传视频到CDN
            logger.info(f"[WX8059] 开始上传视频: {video_path}, 大小: {len(video_data)} bytes")
            upload_result = await self.cdn_upload_video(wxid, video_data, thumb_data)

            if not upload_result.get("success", False):
                error_msg = upload_result.get("error", "上传视频失败")
                logger.error(f"[WX8059] 视频上传失败: {error_msg}")
                raise MessageError(f"视频上传失败: {error_msg}")

            # 4. 使用上传结果转发视频
            aes_key = upload_result["aes_key"]
            cdn_video_url = upload_result["cdn_video_url"]
            length = upload_result["length"]
            play_length = upload_result["play_length"]
            cdn_thumb_length = upload_result["cdn_thumb_length"]

            logger.info(f"[WX8059] 视频上传成功，开始转发视频消息")
            client_msg_id, create_time, new_msg_id = await self.forward_video_message(
                wxid=wxid,
                aes_key=aes_key,
                cdn_video_url=cdn_video_url,
                length=length,
                play_length=play_length,
                cdn_thumb_length=cdn_thumb_length
            )

            logger.info(f"[WX8059] 发送视频消息成功: {wxid}, ClientMsgId: {client_msg_id}, NewMsgId: {new_msg_id}")
            return client_msg_id, create_time, new_msg_id

        except Exception as e:
            logger.error(f"[WX8059] 发送视频消息异常: {e}")
            raise MessageError(f"发送视频消息失败: {e}")

    async def forward_single_emoji(self, to_username: str, emoji_md5: str, emoji_size: int) -> bool:
        """转发单个表情，包含动图

        Args:
            to_username (str): 接收者用户名
            emoji_md5 (str): 表情MD5值
            emoji_size (int): 表情大小

        Returns:
            bool: 转发是否成功
        """
        try:
            data = {
                "EmojiList": [{
                    "ToUserName": to_username,
                    "EmojiMd5": emoji_md5,
                    "EmojiSize": emoji_size
                }]
            }

            response = await self._call_api("/message/ForwardEmoji", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 转发表情成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "转发表情失败")
                logger.error(f"[WX8059] 转发表情失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 转发表情异常: {e}")
            return False

    async def forward_emojis(self, emoji_items: list) -> bool:
        """批量转发表情，包含动图

        Args:
            emoji_items (list): 表情项列表，每个项目应包含:
                - ToUserName (str): 接收者用户名
                - EmojiMd5 (str): 表情MD5值
                - EmojiSize (int): 表情大小

        Returns:
            bool: 转发是否成功
        """
        try:
            # 验证参数格式
            validated_items = []
            for item in emoji_items:
                if not isinstance(item, dict):
                    raise ValueError("emoji_items中的每个项目必须是字典")

                required_fields = ["ToUserName", "EmojiMd5", "EmojiSize"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"emoji_items中缺少必需字段: {field}")

                validated_items.append({
                    "ToUserName": item["ToUserName"],
                    "EmojiMd5": item["EmojiMd5"],
                    "EmojiSize": item["EmojiSize"]
                })

            data = {
                "EmojiList": validated_items
            }

            response = await self._call_api("/message/ForwardEmoji", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 批量转发表情成功: {len(validated_items)} 个")
                return True
            else:
                error_msg = response.get("Text", "批量转发表情失败")
                logger.error(f"[WX8059] 批量转发表情失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 批量转发表情异常: {e}")
            return False

    # 保持向后兼容性的别名方法
    async def forward_emoji(self, emoji_list: list) -> bool:
        """转发表情，包含动图 (向后兼容方法)

        Args:
            emoji_list (list): 表情列表

        Returns:
            bool: 转发是否成功
        """
        return await self.forward_emojis(emoji_list)

    async def forward_image_message(self, forward_image_list: list = None, forward_video_list: list = None) -> bool:
        """转发图片

        Args:
            forward_image_list (list): 转发图片列表
            forward_video_list (list): 转发视频列表

        Returns:
            bool: 转发是否成功
        """
        try:
            data = {
                "ForwardImageList": forward_image_list or [],
                "ForwardVideoList": forward_video_list or []
            }

            response = await self._call_api("/message/ForwardImageMessage", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 转发图片消息成功")
                return True
            else:
                error_msg = response.get("Text", "转发图片消息失败")
                logger.error(f"[WX8059] 转发图片消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 转发图片消息异常: {e}")
            return False

    async def get_msg_big_img(self, from_username: str, to_username: str, msg_id: int, total_len: int,
                             start_pos: int = 0, data_len: int = 61440, compress_type: int = 0) -> dict:
        """获取图片(高清图片下载)

        Args:
            from_username (str): 发送者用户名
            to_username (str): 接收者用户名
            msg_id (int): 消息ID
            total_len (int): 总长度
            start_pos (int): 开始位置
            data_len (int): 数据长度
            compress_type (int): 压缩类型

        Returns:
            dict: 图片数据
        """
        try:
            data = {
                "CompressType": compress_type,
                "FromUserName": from_username,
                "MsgId": msg_id,
                "Section": {
                    "DataLen": data_len,
                    "StartPos": start_pos
                },
                "ToUserName": to_username,
                "TotalLen": total_len
            }

            response = await self._call_api("/message/GetMsgBigImg", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取高清图片成功: {msg_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取高清图片失败")
                logger.error(f"[WX8059] 获取高清图片失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取高清图片异常: {e}")
            raise MessageError(f"获取高清图片失败: {e}")

    async def get_msg_video(self, from_username: str, to_username: str, msg_id: int, total_len: int,
                           start_pos: int = 0, data_len: int = 61440, compress_type: int = 0) -> dict:
        """获取视频(视频数据下载)

        Args:
            from_username (str): 发送者用户名
            to_username (str): 接收者用户名
            msg_id (int): 消息ID
            total_len (int): 总长度
            start_pos (int): 开始位置
            data_len (int): 数据长度
            compress_type (int): 压缩类型

        Returns:
            dict: 视频数据
        """
        try:
            data = {
                "CompressType": compress_type,
                "FromUserName": from_username,
                "MsgId": msg_id,
                "Section": {
                    "DataLen": data_len,
                    "StartPos": start_pos
                },
                "ToUserName": to_username,
                "TotalLen": total_len
            }

            response = await self._call_api("/message/GetMsgVideo", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 获取视频数据成功: {msg_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "获取视频数据失败")
                logger.error(f"[WX8059] 获取视频数据失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 获取视频数据异常: {e}")
            raise MessageError(f"获取视频数据失败: {e}")

    async def get_msg_voice(self, to_username: str, bufid: str, length: int, new_msg_id: str) -> dict:
        """下载语音消息

        Args:
            to_username (str): 接收者用户名
            bufid (str): 缓冲区ID
            length (int): 长度
            new_msg_id (str): 新消息ID

        Returns:
            dict: 语音数据
        """
        try:
            data = {
                "Bufid": bufid,
                "Length": length,
                "NewMsgId": new_msg_id,
                "ToUserName": to_username
            }

            response = await self._call_api("/message/GetMsgVoice", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 下载语音消息成功: {new_msg_id}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "下载语音消息失败")
                logger.error(f"[WX8059] 下载语音消息失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 下载语音消息异常: {e}")
            raise MessageError(f"下载语音消息失败: {e}")

    async def group_mass_msg_image(self, to_usernames: list, image_base64: str) -> bool:
        """群发图片

        Args:
            to_usernames (list): 接收者用户名列表
            image_base64 (str): 图片Base64数据

        Returns:
            bool: 群发是否成功
        """
        try:
            data = {
                "ImageBase64": image_base64,
                "ToUserName": to_usernames
            }

            response = await self._call_api("/message/GroupMassMsgImage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 群发图片成功: {len(to_usernames)} 个用户")
                return True
            else:
                error_msg = response.get("Text", "群发图片失败")
                logger.error(f"[WX8059] 群发图片失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 群发图片异常: {e}")
            return False

    async def group_mass_msg_text(self, to_usernames: list, content: str) -> bool:
        """群发接口

        Args:
            to_usernames (list): 接收者用户名列表
            content (str): 消息内容

        Returns:
            bool: 群发是否成功
        """
        try:
            data = {
                "Content": content,
                "ToUserName": to_usernames
            }

            response = await self._call_api("/message/GroupMassMsgText", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 群发文本成功: {len(to_usernames)} 个用户")
                return True
            else:
                error_msg = response.get("Text", "群发文本失败")
                logger.error(f"[WX8059] 群发文本失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 群发文本异常: {e}")
            return False

    async def http_sync_msg(self, count: int = 0) -> dict:
        """同步消息, HTTP-轮询方式

        Args:
            count (int): 消息数量

        Returns:
            dict: 同步消息数据
        """
        try:
            data = {
                "Count": count
            }

            response = await self._call_api("/message/HttpSyncMsg", data)

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] HTTP同步消息成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "HTTP同步消息失败")
                logger.error(f"[WX8059] HTTP同步消息失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] HTTP同步消息异常: {e}")
            raise MessageError(f"HTTP同步消息失败: {e}")

    async def new_sync_history_message(self) -> dict:
        """同步历史消息

        Returns:
            dict: 历史消息数据
        """
        try:
            response = await self._call_api("/message/NewSyncHistoryMessage", method="POST")

            if response and response.get("Code") == 200:
                logger.debug("[WX8059] 同步历史消息成功")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "同步历史消息失败")
                logger.error(f"[WX8059] 同步历史消息失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] 同步历史消息异常: {e}")
            raise MessageError(f"同步历史消息失败: {e}")

    async def revoke_msg_new(self, to_username: str, client_msg_id: int, create_time: int, new_msg_id: str) -> bool:
        """撤回消息（New）

        Args:
            to_username (str): 接收者用户名
            client_msg_id (int): 客户端消息ID
            create_time (int): 创建时间
            new_msg_id (str): 新消息ID

        Returns:
            bool: 撤回是否成功
        """
        try:
            data = {
                "ClientMsgId": client_msg_id,
                "CreateTime": create_time,
                "NewMsgId": new_msg_id,
                "ToUserName": to_username
            }

            response = await self._call_api("/message/RevokeMsgNew", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 撤回消息（New）成功: {new_msg_id}")
                return True
            else:
                error_msg = response.get("Text", "撤回消息（New）失败")
                logger.error(f"[WX8059] 撤回消息（New）失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 撤回消息（New）异常: {e}")
            return False

    async def send_app_message(self, to_username: str, content_type: int, content_xml: str) -> bool:
        """发送App消息

        Args:
            to_username (str): 接收者用户名
            content_type (int): 内容类型
            content_xml (str): 内容XML

        Returns:
            bool: 发送是否成功
        """
        try:
            data = {
                "AppList": [{
                    "ContentType": content_type,
                    "ContentXML": content_xml,
                    "ToUserName": to_username
                }]
            }

            response = await self._call_api("/message/SendAppMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 发送App消息成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "发送App消息失败")
                logger.error(f"[WX8059] 发送App消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 发送App消息异常: {e}")
            return False

    async def send_app_messages(self, app_items: list) -> bool:
        """批量发送App消息

        Args:
            app_items (list): App消息项列表，每个项目应包含:
                - ToUserName (str): 接收者用户名
                - ContentType (int): 内容类型
                - ContentXML (str): 内容XML

        Returns:
            bool: 发送是否成功
        """
        try:
            # 验证参数格式
            validated_items = []
            for item in app_items:
                if not isinstance(item, dict):
                    raise ValueError("app_items中的每个项目必须是字典")

                required_fields = ["ToUserName", "ContentType", "ContentXML"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"app_items中缺少必需字段: {field}")

                validated_items.append({
                    "ContentType": item["ContentType"],
                    "ContentXML": item["ContentXML"],
                    "ToUserName": item["ToUserName"]
                })

            data = {
                "AppList": validated_items
            }

            response = await self._call_api("/message/SendAppMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 批量发送App消息成功: {len(validated_items)} 条")
                return True
            else:
                error_msg = response.get("Text", "批量发送App消息失败")
                logger.error(f"[WX8059] 批量发送App消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 批量发送App消息异常: {e}")
            return False

    async def send_cdn_download(self, aes_key: str, file_type: int, file_url: str) -> dict:
        """下载请求

        Args:
            aes_key (str): AES密钥
            file_type (int): 文件类型
            file_url (str): 文件URL

        Returns:
            dict: 下载结果
        """
        try:
            data = {
                "AesKey": aes_key,
                "FileType": file_type,
                "FileURL": file_url
            }

            response = await self._call_api("/message/SendCdnDownload", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] CDN下载请求成功: {file_url}")
                return response.get("Data", {})
            else:
                error_msg = response.get("Text", "CDN下载请求失败")
                logger.error(f"[WX8059] CDN下载请求失败: {error_msg}")
                raise MessageError(error_msg)

        except Exception as e:
            logger.error(f"[WX8059] CDN下载请求异常: {e}")
            raise MessageError(f"CDN下载请求失败: {e}")

    async def send_single_emoji_message(self, to_username: str, emoji_md5: str, emoji_size: int) -> bool:
        """发送单个表情消息

        Args:
            to_username (str): 接收者用户名
            emoji_md5 (str): 表情MD5值
            emoji_size (int): 表情大小

        Returns:
            bool: 发送是否成功
        """
        try:
            data = {
                "EmojiList": [{
                    "ToUserName": to_username,
                    "EmojiMd5": emoji_md5,
                    "EmojiSize": emoji_size
                }]
            }

            response = await self._call_api("/message/SendEmojiMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 发送表情消息成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "发送表情消息失败")
                logger.error(f"[WX8059] 发送表情消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 发送表情消息异常: {e}")
            return False

    async def send_emoji_messages(self, emoji_items: list) -> bool:
        """批量发送表情消息

        Args:
            emoji_items (list): 表情项列表，每个项目应包含:
                - ToUserName (str): 接收者用户名
                - EmojiMd5 (str): 表情MD5值
                - EmojiSize (int): 表情大小

        Returns:
            bool: 发送是否成功
        """
        try:
            # 验证参数格式
            validated_items = []
            for item in emoji_items:
                if not isinstance(item, dict):
                    raise ValueError("emoji_items中的每个项目必须是字典")

                required_fields = ["ToUserName", "EmojiMd5", "EmojiSize"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"emoji_items中缺少必需字段: {field}")

                validated_items.append({
                    "ToUserName": item["ToUserName"],
                    "EmojiMd5": item["EmojiMd5"],
                    "EmojiSize": item["EmojiSize"]
                })

            data = {
                "EmojiList": validated_items
            }

            response = await self._call_api("/message/SendEmojiMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 批量发送表情消息成功: {len(validated_items)} 个")
                return True
            else:
                error_msg = response.get("Text", "批量发送表情消息失败")
                logger.error(f"[WX8059] 批量发送表情消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 批量发送表情消息异常: {e}")
            return False

    # 保持向后兼容性的别名方法
    async def send_emoji_message(self, emoji_list: list) -> bool:
        """发送表情 (向后兼容方法)

        Args:
            emoji_list (list): 表情列表

        Returns:
            bool: 发送是否成功
        """
        return await self.send_emoji_messages(emoji_list)

    async def send_single_image_new_message(self, to_username: str, image_content: str,
                                           text_content: str = "", at_wxid_list: list = None) -> bool:
        """发送单条图片消息（New）

        Args:
            to_username (str): 接收者用户名
            image_content (str): 图片内容(Base64)
            text_content (str): 文本内容
            at_wxid_list (list): @用户列表

        Returns:
            bool: 发送是否成功
        """
        try:
            data = {
                "MsgItem": [{
                    "ToUserName": to_username,
                    "MsgType": 3,  # 图片消息类型
                    "TextContent": text_content,
                    "ImageContent": image_content,
                    "AtWxIDList": at_wxid_list or []
                }]
            }

            response = await self._call_api("/message/SendImageNewMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 发送图片消息（New）成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "发送图片消息（New）失败")
                logger.error(f"[WX8059] 发送图片消息（New）失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 发送图片消息（New）异常: {e}")
            return False

    async def send_image_new_messages(self, msg_items: list) -> bool:
        """批量发送图片消息（New）

        Args:
            msg_items (list): 消息项列表，每个项目应包含:
                - ToUserName (str): 接收者用户名
                - MsgType (int): 消息类型
                - TextContent (str): 文本内容
                - ImageContent (str): 图片内容
                - AtWxIDList (list): @用户列表

        Returns:
            bool: 发送是否成功
        """
        try:
            # 验证参数格式
            validated_items = []
            for item in msg_items:
                if not isinstance(item, dict):
                    raise ValueError("msg_items中的每个项目必须是字典")

                required_fields = ["ToUserName", "MsgType"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"msg_items中缺少必需字段: {field}")

                validated_items.append({
                    "ToUserName": item["ToUserName"],
                    "MsgType": item["MsgType"],
                    "TextContent": item.get("TextContent", ""),
                    "ImageContent": item.get("ImageContent", ""),
                    "AtWxIDList": item.get("AtWxIDList", [])
                })

            data = {
                "MsgItem": validated_items
            }

            response = await self._call_api("/message/SendImageNewMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 批量发送图片消息（New）成功: {len(validated_items)} 条")
                return True
            else:
                error_msg = response.get("Text", "批量发送图片消息（New）失败")
                logger.error(f"[WX8059] 批量发送图片消息（New）失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 批量发送图片消息（New）异常: {e}")
            return False

    # 保持向后兼容性的别名方法
    async def send_image_new_message(self, msg_items: list) -> bool:
        """发送图片消息（New） (向后兼容方法)

        Args:
            msg_items (list): 消息项列表

        Returns:
            bool: 发送是否成功
        """
        return await self.send_image_new_messages(msg_items)

    async def share_card_message(self, to_username: str, card_wxid: str, card_nickname: str,
                                card_alias: str = "", card_flag: int = 0) -> bool:
        """分享名片消息

        Args:
            to_username (str): 接收者用户名
            card_wxid (str): 名片微信ID
            card_nickname (str): 名片昵称
            card_alias (str): 名片别名
            card_flag (int): 名片标志

        Returns:
            bool: 分享是否成功
        """
        try:
            data = {
                "CardAlias": card_alias,
                "CardFlag": card_flag,
                "CardNickName": card_nickname,
                "CardWxId": card_wxid,
                "ToUserName": to_username
            }

            response = await self._call_api("/message/ShareCardMessage", data)

            if response and response.get("Code") == 200:
                logger.debug(f"[WX8059] 分享名片消息成功: {to_username}")
                return True
            else:
                error_msg = response.get("Text", "分享名片消息失败")
                logger.error(f"[WX8059] 分享名片消息失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"[WX8059] 分享名片消息异常: {e}")
            return False



    async def start_websocket_listener(self):
        """启动WebSocket监听器"""
        if self._ws_task and not self._ws_task.done():
            logger.debug("[WX8059] WebSocket监听器已在运行")
            return

        self._ws_task = asyncio.create_task(self._websocket_listener())
        logger.info("[WX8059] WebSocket监听器已启动")

    async def stop_websocket_listener(self):
        """停止WebSocket监听器"""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._ws_connected = False
        logger.info("[WX8059] WebSocket监听器已停止")

    async def _websocket_listener(self):
        """WebSocket监听器主循环"""
        while True:
            try:
                await self._connect_websocket()
                await self._listen_messages()
            except Exception as e:
                logger.error(f"[WX8059] WebSocket监听器异常: {e}")
                await asyncio.sleep(5)  # 等待5秒后重连

    async def _connect_websocket(self):
        """连接WebSocket"""
        if self._ws_connected and self._websocket:
            return

        try:
            ws_url = f"ws://{self.ip}:{self.port}/ws/GetSyncMsg?key={self.key}"
            logger.debug(f"[WX8059] 连接WebSocket: {ws_url}")

            self._websocket = await websockets.connect(ws_url)
            self._ws_connected = True
            logger.info("[WX8059] WebSocket连接成功")

        except Exception as e:
            logger.error(f"[WX8059] WebSocket连接失败: {e}")
            self._ws_connected = False
            raise

    async def _listen_messages(self):
        """监听WebSocket消息"""
        try:
            while self._ws_connected and self._websocket:
                message = await self._websocket.recv()
                logger.debug(f"[WX8059] 收到WebSocket消息: {message}")

                try:
                    data = json.loads(message)

                    # 检查是否是消息数据
                    if isinstance(data, dict):
                        # 如果是单条消息，放入队列
                        if 'msg_id' in data:
                            await self._message_queue.put([data])
                            logger.debug("[WX8059] 单条消息已放入队列")
                        # 如果是消息列表
                        elif data.get("Code") == 200:
                            msg_list = data.get("Data", {}).get("MsgList", [])
                            if msg_list:
                                await self._message_queue.put(msg_list)
                                logger.debug(f"[WX8059] {len(msg_list)} 条消息已放入队列")
                        else:
                            logger.debug(f"[WX8059] 收到非消息数据: {data}")

                except json.JSONDecodeError as e:
                    logger.error(f"[WX8059] WebSocket消息JSON解析失败: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("[WX8059] WebSocket连接已关闭")
            self._ws_connected = False
        except Exception as e:
            logger.error(f"[WX8059] WebSocket监听异常: {e}")
            self._ws_connected = False
            raise

    async def get_sync_msg(self) -> list:
        """从消息队列获取同步消息"""
        try:
            # 确保WebSocket监听器正在运行
            if not self._ws_task or self._ws_task.done():
                await self.start_websocket_listener()

            # 从队列中获取消息（非阻塞）
            try:
                messages = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                return messages
            except asyncio.TimeoutError:
                return []

        except Exception as e:
            logger.error(f"[WX8059] 获取同步消息异常: {e}")
            return []
