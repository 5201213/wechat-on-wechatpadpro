# encoding:utf-8

import time
import requests
from bot.bot import Bot
from bot.siliconflow.siliconflow_session import SiliconFlowSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from common import const

class SiliconFlowBot(Bot):
    """
    SiliconFlow API 接口实现类
    支持多个开源模型的统一接口
    """
    def __init__(self):
        """
        初始化SiliconFlowBot
        设置API密钥、基础URL和模型参数
        """
        super().__init__()
        # 初始化会话管理器
        self.sessions = SessionManager(SiliconFlowSession, model=conf().get("model") or "siliconflow")
        # 设置API密钥和基础URL
        self.api_key = conf().get("siliconflow_api_key")
        self.api_base = conf().get("siliconflow_api_base")
        
        # 获取当前选择的模型
        model = conf().get("model")
        # 设置默认模型
        if not model or model not in [
            const.DEEPSEEK_V3,
            const.DEEPSEEK_R1,
            const.GLM_4_9B,
            const.GLM_Z1_9B,
            const.GLM_Z1_R_32B,
            const.QWEN_2_7B
        ]:
            model = const.QWEN_2_7B
        
        # 设置模型参数
        self.args = {
            "model": model,
            "temperature": conf().get("temperature", 0.7),
            "top_p": conf().get("top_p", 0.7),
            "stream": False
        }

    def _make_api_request(self, messages):
        """
        发送请求到 SiliconFlow API
        :param messages: 消息列表
        :return: API 响应
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            **self.args,
            "messages": messages
        }
        
        response = requests.post(
            self.api_base,
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
            
        return response.json()

    def reply(self, query, context=None):
        """
        处理用户查询并返回回复
        :param query: 用户输入的查询文本
        :param context: 上下文信息
        :return: Reply对象，包含回复内容和类型
        """
        if context.type == ContextType.TEXT:
            logger.info("[SILICONFLOW] query={}".format(query))

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
            elif query.startswith("#model "):
                # 处理模型切换命令
                model = query[7:].strip()
                if model in [
                    const.DEEPSEEK_V3,
                    const.DEEPSEEK_R1,
                    const.GLM_4_9B,
                    const.GLM_Z1_9B,
                    const.GLM_Z1_R_32B,
                    const.QWEN_2_7
                ]:
                    self.args["model"] = model
                    reply = Reply(ReplyType.INFO, f"模型已切换为 {model}")
                else:
                    reply = Reply(ReplyType.ERROR, f"不支持的模型: {model}")
            if reply:
                return reply

            session = self.sessions.session_query(query, session_id)
            logger.debug("[SILICONFLOW] session query={}".format(session.messages))

            # 调用 SiliconFlow API
            try:
                response = self._make_api_request(session.build_messages())
                reply_content = response["choices"][0]["message"]["content"]
                logger.debug("[SILICONFLOW] reply={}".format(reply_content))
                return Reply(ReplyType.TEXT, reply_content)
            except Exception as e:
                logger.error("[SILICONFLOW] Exception: {}".format(e))
                return Reply(ReplyType.ERROR, f"SiliconFlow API 调用失败: {str(e)}")
        else:
            return Reply(ReplyType.ERROR, "暂不支持其他类型的查询")
