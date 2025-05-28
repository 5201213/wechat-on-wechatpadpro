# encoding:utf-8

import time
import openai
from bot.bot import Bot
from bot.deepseek.deepseek_session import DeepSeekSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from common import const

class DeepSeekBot(Bot):
    def __init__(self):
        super().__init__()
        # 初始化会话管理器
        self.sessions = SessionManager(DeepSeekSession, model=conf().get("model") or "deepseek")
        self.api_key = conf().get("deepseek_api_key")
        self.api_base = conf().get("deepseek_api_base")
        # 获取当前选择的模型
        model = conf().get("model")
        # 设置默认模型
        if not model or model not in [
            const.DEEPSEEK_CHAT,
            const.DEEPSEEK_REASONER
        ]:
            model = const.DEEPSEEK_CHAT
        
        # 设置模型参数
        self.args = {
            "model": model,
            "temperature": conf().get("temperature", 1.3),
            "top_p": conf().get("top_p", 0.7),
            "stream": False
        }

    def reply(self, query, context=None):
        if context.type == ContextType.TEXT:
            logger.info("[DEEPSEEK] query={}".format(query))

            session_id = context["session_id"]
            reply = None
            
            # 处理特殊命令
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:
                return reply

            session = self.sessions.session_query(query, session_id)
            logger.debug("[DEEPSEEK] session query={}".format(session.messages))

            # 调用 DeepSeek API
            try:
                response = openai.ChatCompletion.create(
                    api_key=self.api_key,
                    api_base=self.api_base,
                    messages=session.messages,
                    **self.args
                )
                if response.choices:
                    reply_content = response.choices[0].message.content
                    self.sessions.session_reply(reply_content, session_id, response.usage.total_tokens)
                    reply = Reply(ReplyType.TEXT, reply_content)
                else:
                    reply = Reply(ReplyType.ERROR, "Sorry, I don't know what to say.")
                
            except Exception as e:
                logger.error("[DEEPSEEK] Exception: {}".format(e))
                reply = Reply(ReplyType.ERROR, "Exception: {}".format(e))
                
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "暂不支持其他类型的消息")
            return reply
