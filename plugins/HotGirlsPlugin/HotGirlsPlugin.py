import requests
import plugins
from plugins import Plugin
from bridge.reply import Reply, ReplyType
from bridge.context import ContextType
from common.log import logger

@plugins.register(
    name="HotGirlsPlugin",
    desire_priority=10,
    hidden=False,
    desc="获取美女图片或视频的插件",
    version="0.0.1",
    author="sllt",
)
class HotGirlsPlugin(Plugin):
    """
    插件功能：
    1. 当消息中包含 "美女" 或 "小姐姐" 时，返回美女图片。
    2. 当消息中包含 "比基尼" 或 "色诱" 时，返回黑丝图片。
    3. 当消息中包含 "坤坤" 或 "坤式" 时，返回相关图片。
    4. 当消息中包含 "黑丝视频" 或 "丝袜视频" 时，返回黑丝相关视频。
    5. 当消息中包含 "小瑾" 时，返回小瑾相关视频。
    6. 当消息中包含 "琳铛" 时，返回琳铛相关视频。
    7. 当消息中包含 "杂鱼川系" 时，返回杂鱼川系相关视频。
    8. 当消息中包含 "萝莉" 时，返回萝莉相关视频。
    9. 当消息中包含 "女大" 时，返回女大相关视频。
    10. 未来可扩展更多 API 和功能。
    """

    # 关键词与 API 的映射（支持模糊匹配）
    API_CONFIG = [
        {"keywords": ["比基尼", "色诱"], "url": "https://api.317ak.com/API/tp/hstp.php", "type": ReplyType.IMAGE_URL},
        {"keywords": ["小姐姐", "美女"], "url": "https://api.317ak.com/API/tp/hstp.php", "type": ReplyType.IMAGE_URL},
        {"keywords": ["坤坤", "坤式"], "url": "https://api.317ak.com/API/tp/kun.php", "type": ReplyType.IMAGE_URL},
        {"keywords": ["黑丝视频", "丝袜视频"], "url": "https://api.317ak.com/API/sp/hssp.php", "type": ReplyType.VIDEO_URL},
        {"keywords": ["奶白","小瑾"], "url": "https://api.317ak.com/API/sp/xjxl.php", "type": ReplyType.VIDEO_URL},
        {"keywords": ["琳铛"], "url": "https://api.317ak.com/API/sp/ldxl.php", "type": ReplyType.VIDEO_URL},
        {"keywords": ["杂鱼川系"], "url": "https://api.317ak.com/API/sp/zycx.php", "type": ReplyType.VIDEO_URL},
        {"keywords": ["萝莉"], "url": "https://api.317ak.com/API/sp/slxl.php", "type": ReplyType.VIDEO_URL},
        {"keywords": ["女大"], "url": "https://api.317ak.com/API/sp/ndxl.php", "type": ReplyType.VIDEO_URL},
        
    ]

    def __init__(self):
        super().__init__()
        self.handlers[plugins.Event.ON_HANDLE_CONTEXT] = self.on_handle_context

    def on_handle_context(self, e_context: plugins.EventContext):
        context = e_context["context"]

        if context.type != ContextType.TEXT:
            return

        content = context.content.strip().lower()  # 统一转换为小写，提升匹配灵活性

        # 遍历 API_CONFIG，找到匹配的关键词
        for api_info in self.API_CONFIG:
            if any(keyword in content for keyword in api_info["keywords"]):  # 只要包含关键词就触发
                api_url = api_info["url"]
                reply_type = api_info["type"]
                params = api_info.get("params", {})

                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    response = requests.get(api_url, headers=headers, params=params, timeout=10)

                    if response.status_code == 200:
                        result_url = response.url  # 获取最终的资源地址
                        reply = Reply(reply_type, result_url)
                    else:
                        logger.warning(f"[HotGirlsPlugin] API 请求失败，状态码: {response.status_code}")
                        reply = Reply(ReplyType.TEXT, "获取资源失败，请稍后再试。")
                except requests.exceptions.RequestException as e:
                    logger.error(f"[HotGirlsPlugin] 请求异常: {str(e)}")
                    reply = Reply(ReplyType.TEXT, "网络错误，请稍后再试。")

                e_context["reply"] = reply
                e_context.action = plugins.EventAction.BREAK_PASS
                return  # 处理完匹配的一个关键词后直接返回，避免多个 API 触发

    def get_help_text(self, verbose=False, **kwargs):
        return "发送包含以下关键词的消息，即可获取相关资源：\n" \
               "- **比基尼** / **色诱** - 获取黑丝图片\n" \
               "- **小姐姐** / **美女** - 获取小姐姐图片\n" \
               "- **黑丝视频** / **丝袜视频** - 获取黑丝相关视频\n" \
               "- **坤坤** / **坤式** - 获取坤坤相关图片\n" \
               "- **小瑾** - 获取小瑾相关视频\n" \
               "- **琳铛** - 获取琳铛相关视频\n" \
               "- **杂鱼川系** - 获取杂鱼川系相关视频\n" \
               "- **萝莉** - 获取萝莉相关视频\n" \
               "- **女大** - 获取女大相关视频\n" 
