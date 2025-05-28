# encoding:utf-8

import time
import pkg_resources

import openai
import openai.error

from bot.bot import Bot
from bot.openai.open_ai_image import OpenAIImage
from bot.openai.open_ai_session import OpenAISession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf

user_session = dict()


# OpenAI对话模型API (可用)
class OpenAIBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        api_key = conf().get("open_ai_api_key")
        api_base = conf().get("open_ai_api_base", "https://vip.apiyi.com/v1")
        if api_base.endswith("/"):
            api_base = api_base[:-1]
        
        # 检查 openai 包版本
        try:
            openai_version = pkg_resources.get_distribution("openai").version
            if openai_version >= "1.0.0":
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=api_key,
                    base_url=api_base
                )
            else:
                # 使用旧版本的配置方式
                openai.api_key = api_key
                openai.api_base = api_base
                self.client = None
        except Exception as e:
            logger.warn(f"Failed to check openai version: {e}")
            # 使用旧版本的配置方式
            openai.api_key = api_key
            openai.api_base = api_base
            self.client = None
        
        proxy = conf().get("proxy")
        if proxy:
            if self.client:
                self.client.proxy = proxy
            else:
                openai.proxy = proxy

        self.sessions = SessionManager(OpenAISession, model=conf().get("model") or "gpt-4o-mini-search-preview")
        self.args = {
            "model": conf().get("model") or "gpt-4o-mini-search-preview",  # 对话模型的名称
            "max_tokens": 1200,  # 回复最大的字符数
            "request_timeout": conf().get("request_timeout", None),  # 请求超时时间
        }

    def reply(self, query, context=None):
        # acquire reply content
        if context and context.type:
            if context.type == ContextType.TEXT:
                logger.info("[OPEN_AI] query={}".format(query))
                session_id = context["session_id"]
                reply = None
                if query == "#清除记忆":
                    self.sessions.clear_session(session_id)
                    reply = Reply(ReplyType.INFO, "记忆已清除")
                elif query == "#清除所有":
                    self.sessions.clear_all_session()
                    reply = Reply(ReplyType.INFO, "所有人记忆已清除")
                else:
                    session = self.sessions.session_query(query, session_id)
                    result = self.reply_text(session)
                    total_tokens, completion_tokens, reply_content = (
                        result["total_tokens"],
                        result["completion_tokens"],
                        result["content"],
                    )
                    logger.debug(
                        "[OPEN_AI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(str(session), session_id, reply_content, completion_tokens)
                    )

                    if total_tokens == 0:
                        reply = Reply(ReplyType.ERROR, reply_content)
                    else:
                        self.sessions.session_reply(reply_content, session_id, total_tokens)
                        reply = Reply(ReplyType.TEXT, reply_content)
                return reply
            elif context.type == ContextType.IMAGE_CREATE:
                ok, retstring = self.create_img(query, 0)
                reply = None
                if ok:
                    reply = Reply(ReplyType.IMAGE_URL, retstring)
                else:
                    reply = Reply(ReplyType.ERROR, retstring)
                return reply

    def reply_text(self, session: OpenAISession, retry_count=0):
        try:
            # 确保消息列表包含系统提示
            messages = session.get_messages()
            if not any(msg["role"] == "system" for msg in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": "你是一个拥有联网搜索能力的助手，能够提供最新信息。"
                })

            if self.client:
                # 使用新版本的 API 调用方式
                response = self.client.chat.completions.create(
                    model=self.args["model"],
                    messages=messages,
                    max_tokens=self.args["max_tokens"],
                    timeout=self.args["request_timeout"]
                )
                res_content = response.choices[0].message.content.strip()
                total_tokens = response.usage.total_tokens
                completion_tokens = response.usage.completion_tokens
            else:
                # 使用旧版本的 API 调用方式
                response = openai.ChatCompletion.create(
                    model=self.args["model"],
                    messages=messages,
                    max_tokens=self.args["max_tokens"],
                    timeout=self.args["request_timeout"]
                )
                res_content = response.choices[0]["message"]["content"].strip()
                total_tokens = response["usage"]["total_tokens"]
                completion_tokens = response["usage"]["completion_tokens"]
            
            logger.info("[OPEN_AI] reply={}".format(res_content))
            return {
                "total_tokens": total_tokens,
                "completion_tokens": completion_tokens,
                "content": res_content,
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {
                "total_tokens": 0,
                "completion_tokens": 0,
                "content": "我现在有点累了，等会再来吧"
            }
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[OPEN_AI] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[OPEN_AI] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[OPEN_AI] APIConnectionError: {}".format(e))
                need_retry = False
                result["content"] = "我连接不到你的网络"
            else:
                logger.warn("[OPEN_AI] Exception: {}".format(e))
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[OPEN_AI] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result
