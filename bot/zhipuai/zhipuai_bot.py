# encoding:utf-8

import time
import openai
from openai import OpenAIError
from bot.bot import Bot
from bot.zhipuai.zhipu_ai_session import ZhipuAISession
from bot.zhipuai.zhipu_ai_image import ZhipuAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from zhipuai import ZhipuAI


# ZhipuAI对话模型API
class ZhipuAIBot(Bot, ZhipuAIImage):
    def __init__(self):
        super().__init__()
        # 初始化会话管理器
        self.sessions = SessionManager(ZhipuAISession, model=conf().get("model") or "glm-4-flash")
        # 设置API密钥和基础URL
        self.client = ZhipuAI(api_key=conf().get("zhipu_ai_api_key"))
        # 设置模型参数
        self.args = {
            "model": conf().get("model") or "glm-4-flash",  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在(0,1)之间(智谱AI 的温度不能取 0 或者 1)
            "top_p": conf().get("top_p", 0.7),  # 值在(0,1)之间(智谱AI 的 top_p 不能取 0 或者 1)
        }

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[ZHIPU_AI] query={}".format(query))

            session_id = context["session_id"]
            reply = None
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
            logger.debug("[ZHIPU_AI] session query={}".format(session.messages))

            try:
                response = self.client.chat.completions.create(messages=session.messages, **self.args)
                if response.choices:
                    reply_content = response.choices[0].message.content
                    self.sessions.session_reply(reply_content, session_id, response.usage.total_tokens)
                    reply = Reply(ReplyType.TEXT, reply_content)
                else:
                    reply = Reply(ReplyType.ERROR, "Sorry, I don't know what to say.")
                
            except Exception as e:
                logger.error("[ZHIPU_AI] Exception: {}".format(e))
                reply = Reply(ReplyType.ERROR, "Exception: {}".format(e))
                
            return reply
        elif context.type == ContextType.IMAGE_CREATE:
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply
