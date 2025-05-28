from bot.session_manager import Session
from common.log import logger
import tiktoken
import json


class OpenAISession(Session):
    def __init__(self, session_id, system_prompt=None, model="text-davinci-003"):
        super().__init__(session_id, system_prompt)
        self.model = model
        self.reset()

    def __str__(self):
        """返回格式化的对话历史字符串，用于日志记录"""
        formatted_messages = []
        for msg in self.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted_messages.append(f"{role}: {content}")
        return "\n".join(formatted_messages)

    def get_messages(self):
        """返回原始消息列表，用于 API 调用"""
        return self.messages

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True
        try:
            cur_tokens = self.calc_tokens()
        except Exception as e:
            precise = False
            if cur_tokens is None:
                raise e
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))
        while cur_tokens > max_tokens:
            if len(self.messages) > 1:
                self.messages.pop(0)
            elif len(self.messages) == 1 and self.messages[0]["role"] == "assistant":
                self.messages.pop(0)
                if precise:
                    cur_tokens = self.calc_tokens()
                else:
                    cur_tokens = len(str(self))
                break
            elif len(self.messages) == 1 and self.messages[0]["role"] == "user":
                logger.warn("user question exceed max_tokens. total_tokens={}".format(cur_tokens))
                break
            else:
                logger.debug("max_tokens={}, total_tokens={}, len(conversation)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break
            if precise:
                cur_tokens = self.calc_tokens()
            else:
                cur_tokens = len(str(self))
        return cur_tokens

    def calc_tokens(self):
        return num_tokens_from_messages(self.messages, self.model)


def num_tokens_from_messages(messages, model: str) -> int:
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # 使用通用的编码器
    except Exception as e:
        logger.warn(f"Failed to get encoding: {e}")
        return len(str(messages))  # 如果获取编码器失败，返回字符串长度作为估计

    num_tokens = 0
    for message in messages:
        num_tokens += 4  # 每条消息的额外标记
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # 如果有名字字段，额外加1
                num_tokens += 1
    num_tokens += 2  # 回复以 assistant 开头
    return num_tokens
