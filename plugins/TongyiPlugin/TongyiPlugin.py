import os
import json
import time
import logging
import re
import html
import shutil
import requests
from plugins import Plugin, Event, EventContext, EventAction
from plugins import register
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from .module.video_parser import VideoParser
from .module.audio_transcriber import AudioTranscriber
from .module.video_analyzer import VideoAnalyzer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@register(
    name="TongyiPlugin",
    desc="通义视频分析插件 - 支持分析抖音等平台的短视频内容和图片识别",
    version="1.0.0",
    author="tongyi",
    desire_priority=1,
    hidden=False,
    enabled=True
)
class TongyiPlugin(Plugin):
    def __init__(self):
        super().__init__()
        try:
            # 初始化日志
            global logger
            logger = logging.getLogger(__name__)
            
            # 加载配置文件
            curdir = os.path.dirname(__file__)
            config_path = os.path.join(curdir, "config.json")
            
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                    logger.info("[TongyiPlugin] 成功加载配置文件")
            except Exception as e:
                logger.error(f"[TongyiPlugin] 加载配置文件失败: {e}")
                raise e
            
            # 初始化配置参数
            basic_config = self.config.get("basic_config", {})
            self.keyword = basic_config.get("keyword", "ty")
            self.auto_summary = basic_config.get("auto_summary", True)
            self.auto_video_summary = basic_config.get("auto_video_summary", True)
            
            # 初始化群聊和私聊配置
            self.group_config = self.config.get("group_auto_summary", {})
            self.private_config = self.config.get("private_auto_summary", {})
            self.auto_trigger_groups = set(self.group_config.get("auto_trigger_groups", []))
            
            # 获取提示词模板
            self.video_prompt = self.config.get("prompts", {}).get("video_prompt", "")
            self.image_prompt = self.config.get("prompts", {}).get("image_prompt", "")
            self.default_prompt = self.config.get("prompts", {}).get("default_prompt", "")
            
            # 获取 API 配置
            api_config = self.config.get("api_config", {})
            audio_token = api_config.get("audio_token")
            if not audio_token:
                raise ValueError("[TongyiPlugin] 配置文件中缺少 audio_token")
            
            # 初始化视频解析器
            self.video_parser = VideoParser(self.config)
            
            # 初始化视频分析器
            self.video_analyzer = VideoAnalyzer()
            
            # 初始化音频转写器
            self.audio_transcriber = AudioTranscriber(audio_token)
            
            # 设置存储目录
            self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
            self.storage_dir = os.path.join(self.plugin_dir, 'storage')
            self.temp_dir = os.path.join(self.storage_dir, 'temp')
            self.video_dir = os.path.join(self.storage_dir, 'video')
            
            # 创建所需目录
            for dir_path in [self.storage_dir, self.temp_dir, self.video_dir]:
                try:
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                        logger.info(f"[TongyiPlugin] 创建目录: {dir_path}")
                    else:
                        # 检查目录权限
                        if not os.access(dir_path, os.W_OK):
                            logger.error(f"[TongyiPlugin] 目录无写入权限: {dir_path}")
                            raise PermissionError(f"目录无写入权限: {dir_path}")
                        logger.info(f"[TongyiPlugin] 目录已存在: {dir_path}")
                except Exception as e:
                    logger.error(f"[TongyiPlugin] 目录操作失败: {dir_path}, 错误: {e}")
                    raise e
            
            # 初始化文件清理时间
            self.last_cleanup_time = time.time()
            self.cleanup_interval = 3600  # 每小时清理一次
            self.file_max_age = 7200  # 文件最大保存时间（2小时）
            
            # 初始化图片识别相关变量
            self.waiting_for_image = {}
            self.image_prompts = {}
            
            # 注册事件处理器
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message
            
            # 初始化状态管理
            self.processed_messages = set()  # 用于存储已处理的消息ID
            
            logger.info("[TongyiPlugin] 插件初始化完成")
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 初始化失败: {str(e)}", exc_info=True)
            raise e

    def on_handle_context(self, e_context: EventContext):
        try:
            context = e_context["context"]
            if not context:
                return
                
            # 获取消息内容
            content = context.content
            if not content:
                return
                
            # 获取用户信息
            msg = context.kwargs.get("msg")
            is_group = context.kwargs.get("isgroup", False)
            group_name = context.kwargs.get("group_name", "") if is_group else None
            
            # 检查是否已经处理过该消息
            msg_id = msg.msg_id if msg else None
            if msg_id in self.processed_messages:
                e_context.action = EventAction.BREAK_PASS
                return True
                
            # 生成等待ID
            if is_group:
                # 群消息处理
                group_id = msg.other_user_id if msg else None
                real_user_id = msg.actual_user_id if msg and hasattr(msg, "actual_user_id") else None
                waiting_id = f"{group_id}_{real_user_id}" if real_user_id else group_id
            else:
                real_user_id = msg.from_user_id if msg else None
                waiting_id = real_user_id
                
            # 处理群消息中的用户ID前缀
            if is_group and isinstance(content, str):
                # 移除群消息中的用户ID前缀
                user_prefix = None
                if ":\n" in content:
                    user_prefix, content = content.split(":\n", 1)
                    logger.info(f"[TongyiPlugin] 移除用户前缀: {user_prefix}")
                    
            # 检查是否是文本消息
            if context.type == ContextType.TEXT:
                # 检查是否是带关键词的命令
                if content.startswith(f"{self.keyword}"):
                    # 处理带关键词的命令
                    return self.handle_command(content, e_context)
                    
                # 检查是否需要自动处理视频分享
                if self.video_parser.is_video_share(content):
                    auto_process = False
                    
                    # 检查私聊自动处理
                    if not is_group and self.private_config.get("enabled", False):
                        auto_process = True
                        logger.info(f"[TongyiPlugin] 私聊自动处理已启用")
                        
                    # 检查群聊自动处理
                    elif is_group and self.group_config.get("enabled", False):
                        auto_trigger_groups = self.group_config.get("auto_trigger_groups", [])
                        logger.info(f"[TongyiPlugin] 群名: {group_name}, 自动触发群列表: {auto_trigger_groups}")
                        if group_name and any(group in group_name for group in auto_trigger_groups):
                            auto_process = True
                            logger.info(f"[TongyiPlugin] 群聊自动处理已启用")
                    
                    if auto_process:
                        logger.info(f"[TongyiPlugin] 自动处理视频分享: {content}")
                        result = self.handle_video_share(content, None, e_context)
                        if result and msg_id:
                            self.processed_messages.add(msg_id)
                        return result

                # 检查是否是图片识别命令
                if content.startswith(f"{self.keyword}识别"):
                    prompt = content[len(f"{self.keyword}识别"):].strip()
                    if prompt:
                        self.image_prompts[waiting_id] = prompt
                    else:
                        self.image_prompts[waiting_id] = self.default_prompt
                    self.waiting_for_image[waiting_id] = True
                    reply = Reply(ReplyType.TEXT, "请发送要识别的图片")
                    e_context["channel"].send(reply, e_context["context"])
                    if msg_id:
                        self.processed_messages.add(msg_id)
                    e_context.action = EventAction.BREAK_PASS
                    return True
            
            # 处理图片消息
            elif context.type == ContextType.IMAGE:
                # 检查是否在等待图片
                if waiting_id in self.waiting_for_image:
                    try:
                        # 获取图片数据
                        image_path = self._get_image_data(msg, content)
                        if not image_path:
                            logger.error("[TongyiPlugin] 获取图片数据失败")
                            reply = Reply(ReplyType.TEXT, "获取图片失败，请重试")
                            e_context["channel"].send(reply, e_context["context"])
                            e_context.action = EventAction.BREAK_PASS
                            return True

                        # 处理图片
                        self._process_image(image_path, msg, e_context)
                        
                    except Exception as e:
                        logger.error(f"[TongyiPlugin] 处理图片失败: {e}")
                        reply = Reply(ReplyType.TEXT, "处理图片失败，请重试")
                        e_context["channel"].send(reply, e_context["context"])
                    finally:
                        # 清理状态
                        self.waiting_for_image.pop(waiting_id, None)
                        self.image_prompts.pop(waiting_id, None)
                        
                    if msg_id:
                        self.processed_messages.add(msg_id)
                    e_context.action = EventAction.BREAK_PASS
                    return True
                    
            return None
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 处理消息失败: {e}")
            return None

    def handle_command(self, content, e_context):
        """处理命令消息"""
        try:
            # 提取命令后的内容
            msg = content[len(self.keyword):].strip()
            if not msg:
                return False
                
            logger.info(f"[TongyiPlugin] 收到命令: {msg}")
            
            # 检查是否包含视频链接
            if self.video_parser.is_video_share(msg):
                return self.handle_video_share(msg, None, e_context)
                
            return False
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 处理命令失败: {e}")
            return False

    def _ensure_directory(self, file_path):
        """确保目录存在
        Args:
            file_path (str): 文件路径
        Returns:
            bool: 是否成功创建/确认目录
        """
        try:
            directory = os.path.dirname(file_path)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"[TongyiPlugin] 创建目录: {directory}")
            return True
        except Exception as e:
            logger.error(f"[TongyiPlugin] 创建目录失败: {directory}, 错误: {e}")
            return False

    def handle_video_share(self, content, user_id, e_context):
        """处理视频分享"""
        video_path = None
        try:
            # 定期清理文件
            self._cleanup_files()
            
            # 发送处理提示
            process_reply = Reply(ReplyType.TEXT, "正在处理视频，请稍候...")
            e_context["channel"].send(process_reply, e_context["context"])
            
            # 提取视频信息
            logger.info("[TongyiPlugin] 开始解析视频链接...")
            title, share_url = self.video_parser.extract_share_info(content)
            if not share_url:
                logger.error("[TongyiPlugin] 未找到视频链接")
                error_reply = Reply(ReplyType.TEXT, "未找到有效的视频链接")
                e_context["channel"].send(error_reply, e_context["context"])
                e_context.action = EventAction.BREAK_PASS
                return True
                
            # 确保临时目录存在
            temp_video_path = os.path.join(self.temp_dir, f"video_{int(time.time())}.mp4")
            if not self._ensure_directory(temp_video_path):
                logger.error("[TongyiPlugin] 创建临时目录失败")
                error_reply = Reply(ReplyType.TEXT, "视频处理失败，请稍后重试")
                e_context["channel"].send(error_reply, e_context["context"])
                e_context.action = EventAction.BREAK_PASS
                return True
                
            # 获取视频信息
            video_info = self.video_parser.get_video_info(share_url)
            if not video_info:
                logger.error("[TongyiPlugin] 获取视频信息失败")
                error_reply = Reply(ReplyType.TEXT, "视频解析失败，请稍后重试")
                e_context["channel"].send(error_reply, e_context["context"])
                e_context.action = EventAction.BREAK_PASS
                return True
                
            # 如果需要，更新视频路径
            if "video_path" not in video_info:
                video_info["video_path"] = temp_video_path
            
            logger.info("[TongyiPlugin] 视频链接解析成功")
            
            # 构建基础信息
            title = video_info.get("title", title) or "未知标题"
            author = video_info.get("author", "未知作者")
            video_url = video_info.get("video_url", "")
            
            # 发送视频文件
            if video_url:
                logger.info("[TongyiPlugin] 发送视频文件...")
                video_reply = Reply(ReplyType.VIDEO_URL, video_url)
                e_context["channel"].send(video_reply, e_context["context"])
            
            # 构建回复内容
            formatted_content = f"🎬 视频解析结果\n\n"
            if title:
                formatted_content += f"📽️ 标题：{title}\n"
            if author:
                formatted_content += f"👤 作者：{author}\n"
            if video_url:
                formatted_content += f"🔗 无水印链接：{video_url}\n"
            
            # 发送视频信息
            info_reply = Reply(ReplyType.TEXT, formatted_content)
            e_context["channel"].send(info_reply, e_context["context"])
            
            video_path = video_info.get("video_path", "")
            
            try:
                # 提取音频并转写
                logger.info("[TongyiPlugin] 开始音频转写...")
                audio_text = self.audio_transcriber.transcribe(video_path)
                if not audio_text:
                    logger.warning("[TongyiPlugin] 音频转写结果为空")
                
                # 上传视频到通义服务器
                logger.info("[TongyiPlugin] 开始上传视频到通义服务器...")
                file_info = self.video_analyzer.upload_video(video_path)
                if not file_info:
                    logger.error("[TongyiPlugin] 上传视频失败")
                    error_reply = Reply(ReplyType.TEXT, "视频处理失败，请稍后重试")
                    e_context["channel"].send(error_reply, e_context["context"])
                    return True
                    
                logger.info("[TongyiPlugin] 视频上传成功，开始分析...")
                
                # 构建完整提示词
                prompt = self.video_prompt
                if title != "未知标题":
                    prompt = f"视频标题：{title}\n\n" + prompt
                if audio_text:
                    prompt = f"{prompt}\n\n音频内容：{audio_text}"
                
                logger.info(f"[TongyiPlugin] 使用提示词: {prompt}")
                
                # 分析视频
                result = self.video_analyzer.analyze_video(file_info, prompt)
                if not result:
                    logger.error("[TongyiPlugin] 视频分析失败: 返回结果为空")
                    error_reply = Reply(ReplyType.TEXT, "视频分析失败，请稍后重试")
                    e_context["channel"].send(error_reply, e_context["context"])
                    return True

                # 记录分析结果
                logger.info(f"[TongyiPlugin] 获取到分析结果: {result}")
                
                try:
                    # 尝试解析结果
                    if isinstance(result, dict):
                        # 如果结果是字典格式
                        formatted_result = result.get('result', '') or result.get('response', '') or str(result)
                    elif isinstance(result, str) and result != "无法获取分析结果":
                        # 如果结果是有效的字符串格式
                        formatted_result = result
                    else:
                        # 其他情况，尝试转换为字符串
                        formatted_result = str(result)
                        if formatted_result == "无法获取分析结果":
                            raise ValueError("服务器返回空结果")

                    if not formatted_result or formatted_result.strip() == '':
                        raise ValueError("分析结果为空")

                    logger.info("[TongyiPlugin] 视频分析完成")
                    
                    # 发送分析结果
                    analysis_reply = Reply(ReplyType.TEXT, f"🤖 视频内容分析\n\n{formatted_result}")
                    e_context["channel"].send(analysis_reply, e_context["context"])
                    
                except Exception as e:
                    logger.error(f"[TongyiPlugin] 处理分析结果时出错: {e}, 原始结果: {result}")
                    error_reply = Reply(ReplyType.TEXT, "处理分析结果时出错，请稍后重试")
                    e_context["channel"].send(error_reply, e_context["context"])
                
            except Exception as e:
                logger.error(f"[TongyiPlugin] 视频分析过程出错: {e}")
                error_reply = Reply(ReplyType.TEXT, "视频分析过程出错，请稍后重试")
                e_context["channel"].send(error_reply, e_context["context"])
                # 发生错误时也要清理文件
                self._cleanup_video_file(video_path)
            finally:
                # 清理当前视频文件
                self._cleanup_video_file(video_path)
            
            e_context.action = EventAction.BREAK_PASS
            return True
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 处理视频分享失败: {e}", exc_info=True)
            error_reply = Reply(ReplyType.TEXT, "处理视频失败，请稍后重试")
            e_context["channel"].send(error_reply, e_context["context"])
            # 发生错误时也要清理文件
            self._cleanup_video_file(video_path)
            e_context.action = EventAction.BREAK_PASS
            return True

    def on_receive_message(self, e_context: EventContext):
        """处理接收到的消息"""
        try:
            context = e_context['context']
            if not context:
                return
                
            # 获取消息内容
            content = context.content.strip() if context.content else ""
            if not content:
                return
                
            # 获取用户信息
            msg = context.kwargs.get('msg')
            is_group = context.kwargs.get('isgroup', False)
            
            # 检查是否已经处理过该消息
            msg_id = msg.msg_id if msg else None
            if msg_id in self.processed_messages:
                return
                
            # 检查是否是文本消息
            if context.type == ContextType.TEXT:
                # 检查是否包含视频分享链接
                if self.video_parser.is_video_share(content):
                    logger.info(f"[TongyiPlugin] 检测到视频分享: {content}")
                    result = self.handle_video_share(content, None, e_context)
                    if result and msg_id:
                        self.processed_messages.add(msg_id)
                    return result
                    
            return None
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 处理接收消息失败: {e}")
            return None

    def _cleanup_files(self, force=False):
        """清理临时文件
        Args:
            force (bool): 是否强制清理，不考虑时间间隔
        """
        current_time = time.time()
        
        # 如果不是强制清理，检查是否达到清理间隔
        if not force and (current_time - self.last_cleanup_time) < self.cleanup_interval:
            return
            
        try:
            logger.info("[TongyiPlugin] 开始清理临时文件...")
            
            # 清理临时目录
            self._cleanup_directory(self.temp_dir)
            
            # 清理视频目录
            self._cleanup_directory(self.video_dir)
            
            self.last_cleanup_time = current_time
            logger.info("[TongyiPlugin] 临时文件清理完成")
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 清理临时文件失败: {e}")

    def _cleanup_directory(self, directory):
        """清理指定目录中的过期文件"""
        current_time = time.time()
        
        try:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if not os.path.isfile(file_path):
                    continue
                    
                # 获取文件修改时间
                file_mtime = os.path.getmtime(file_path)
                
                # 如果文件超过最大保存时间，删除它
                if (current_time - file_mtime) > self.file_max_age:
                    try:
                        os.remove(file_path)
                        logger.info(f"[TongyiPlugin] 删除过期文件: {file_path}")
                    except Exception as e:
                        logger.error(f"[TongyiPlugin] 删除文件失败: {file_path}, 错误: {e}")
                        
        except Exception as e:
            logger.error(f"[TongyiPlugin] 清理目录失败: {directory}, 错误: {e}")

    def _cleanup_video_file(self, video_path):
        """清理单个视频文件"""
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                logger.info(f"[TongyiPlugin] 删除视频文件: {video_path}")
            except Exception as e:
                logger.error(f"[TongyiPlugin] 删除视频文件失败: {video_path}, 错误: {e}")

    def get_help_text(self, **kwargs):
        """获取帮助信息"""
        help_text = "通义视频分析插件使用说明：\n\n"
        help_text += f"1. 使用 {self.keyword} + 视频链接 进行视频分析\n"
        help_text += "2. 支持自动识别视频分享内容\n"
        help_text += "3. 支持抖音、快手、微博、小红书等平台的视频分享\n"
        help_text += "4. 会自动提取视频标题、音频内容和画面分析\n"
        help_text += "5. 分析结果包含内容概要、详细分析、核心要点、情感基调和创作亮点\n"
        return help_text

    def _get_image_data(self, msg, content):
        """获取图片数据
        Args:
            msg: 消息对象
            content: 消息内容
        Returns:
            str: 图片路径
        """
        try:
            # 获取当前工作目录
            cwd = os.getcwd()
            
            # 尝试的路径列表
            file_paths = [
                content,  # 原始路径
                os.path.abspath(content),  # 绝对路径
                os.path.join(cwd, content),  # 相对于当前目录的路径
                os.path.join(cwd, 'tmp', os.path.basename(content)),  # tmp目录
                os.path.join(cwd, 'plugins', 'TongyiPlugin', 'tmp', os.path.basename(content)),  # 插件tmp目录
                os.path.join(cwd, 'plugins', 'TongyiPlugin', 'storage', 'temp', os.path.basename(content))  # 插件临时目录
            ]
            
            # 检查每个可能的路径
            for path in file_paths:
                if os.path.isfile(path):
                    logger.info(f"[TongyiPlugin] 找到图片文件: {path}")
                    return path
            
            # 如果文件还未下载,尝试下载
            if hasattr(msg, '_prepare_fn') and not msg._prepared:
                logger.info("[TongyiPlugin] 准备下载图片...")
                msg._prepare_fn()
                msg._prepared = True
                time.sleep(1)  # 等待文件准备完成
                
                # 再次检查所有路径
                for path in file_paths:
                    if os.path.isfile(path):
                        logger.info(f"[TongyiPlugin] 下载后找到图片文件: {path}")
                        return path
                
                # 如果还是找不到，尝试从msg.content获取
                if hasattr(msg, 'content') and msg.content:
                    file_path = msg.content
                    if os.path.isfile(file_path):
                        logger.info(f"[TongyiPlugin] 从msg.content找到图片文件: {file_path}")
                        return file_path
            
            # 如果是URL,尝试下载
            if isinstance(content, str) and (content.startswith('http://') or content.startswith('https://')):
                temp_path = os.path.join(self.temp_dir, f"image_{int(time.time())}.jpg")
                response = requests.get(content, timeout=30)
                if response.status_code == 200:
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                    return temp_path
            
            logger.error(f"[TongyiPlugin] 未找到图片文件: {content}")
            return None
            
        except Exception as e:
            logger.error(f"[TongyiPlugin] 获取图片数据失败: {e}")
            return None

    def _process_image(self, image_path, msg, e_context):
        """处理图片
        Args:
            image_path: 图片路径
            msg: 消息对象
            e_context: 事件上下文
        """
        try:
            # 读取图片文件
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # 发送等待消息
            e_context["channel"].send(Reply(ReplyType.INFO, "正在处理图片..."), e_context["context"])

            # 上传图片到通义服务器
            logger.info("[TongyiPlugin] 开始上传图片到通义服务器...")
            file_info = self.video_analyzer.upload_video(image_path)
            if not file_info:
                logger.error("[TongyiPlugin] 上传图片失败")
                e_context["reply"] = Reply(ReplyType.ERROR, "图片处理失败，请重试")
                return

            # 构建提示词
            prompt = self.image_prompt
            logger.info(f"[TongyiPlugin] 使用提示词: {prompt}")

            # 分析图片
            result = self.video_analyzer.analyze_video(file_info, prompt)
            if not result:
                logger.error("[TongyiPlugin] 图片分析失败: 返回结果为空")
                e_context["reply"] = Reply(ReplyType.ERROR, "图片分析失败，请重试")
                return

            # 记录分析结果
            logger.info(f"[TongyiPlugin] 获取到分析结果: {result}")

            try:
                # 尝试解析结果
                if isinstance(result, dict):
                    # 如果结果是字典格式
                    formatted_result = result.get('result', '') or result.get('response', '') or str(result)
                elif isinstance(result, str) and result != "无法获取分析结果":
                    # 如果结果是有效的字符串格式
                    formatted_result = result
                else:
                    # 其他情况，尝试转换为字符串
                    formatted_result = str(result)
                    if formatted_result == "无法获取分析结果":
                        raise ValueError("服务器返回空结果")

                if not formatted_result or formatted_result.strip() == '':
                    raise ValueError("分析结果为空")

                logger.info("[TongyiPlugin] 图片分析完成")
                
                # 发送分析结果
                analysis_reply = Reply(ReplyType.TEXT, f"🤖 图片内容分析\n\n{formatted_result}")
                e_context["channel"].send(analysis_reply, e_context["context"])

            except Exception as e:
                logger.error(f"[TongyiPlugin] 处理分析结果时出错: {e}, 原始结果: {result}")
                e_context["reply"] = Reply(ReplyType.ERROR, "处理分析结果时出错，请稍后重试")

        except Exception as e:
            logger.error(f"[TongyiPlugin] 处理图片失败: {e}")
            e_context["reply"] = Reply(ReplyType.ERROR, "处理图片失败，请重试")
        finally:
            # 清理临时文件
            try:
                if os.path.exists(image_path) and self.temp_dir in image_path:
                    os.remove(image_path)
            except Exception as e:
                logger.error(f"[TongyiPlugin] 清理临时文件失败: {e}") 