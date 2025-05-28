from bot.session_manager import Session

class SiliconFlowSession(Session):
    """
    SiliconFlow会话类
    继承自基础Session类，负责管理与SiliconFlow API的会话状态
    """
    def __init__(self, session_id, system_prompt=None, model=None):
        """
        初始化SiliconFlow会话
        :param session_id: 会话ID
        :param system_prompt: 系统提示词
        :param model: 使用的模型名称
        """
        super().__init__(session_id, system_prompt)
        self.model = model

    def build_messages(self):
        """
        构造messages，供发送给SiliconFlow接口
        将会话历史记录转换为API所需的格式
        :return: messages列表，包含角色和内容信息
        """
        messages = []
        # 添加系统提示词（如果存在）
        if self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
        # 添加历史消息记录
        for item in self.messages:
            messages.append({
                "role": item["role"],
                "content": item["content"]
            })
        return messages
