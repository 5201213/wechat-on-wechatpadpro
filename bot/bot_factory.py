"""
channel factory
"""
from common import const
from config import conf


def create_bot(bot_type):
    """
    create a bot_type instance
    :param bot_type: bot type code
    :return: bot instance
    """
    # 获取当前配置的模型
    model = conf().get("model")
    
    # 如果模型是 SiliconFlow 系列模型，使用 SiliconFlowBot
    if model in [
        const.DEEPSEEK_V3,
        const.DEEPSEEK_R1,
        const.GLM_4_9B,
        const.GLM_Z1_9B,
        const.GLM_Z1_R_32B,
        const.QWEN_2_7B
    ]:
        from bot.siliconflow.siliconflow_bot import SiliconFlowBot
        return SiliconFlowBot()
    
    # 如果模型是 DeepSeek 系列模型，使用 DeepSeekBot
    if model in [
        const.DEEPSEEK_CHAT,
        const.DEEPSEEK_REASONER
    ]:
        from bot.deepseek.deepseek_bot import DeepSeekBot
        return DeepSeekBot()
        
    # 如果模型是 ZhipuAI 系列模型，使用 ZhipuAIBot
    if model in [
        const.GLM_4_FLASH,
        const.GLM_4_PLUS,
        const.GLM_Z1_FLASH
    ]:
        from bot.zhipuai.zhipuai_bot import ZhipuAIBot
        return ZhipuAIBot()

    # 如果模型是 Dashscope 系列模型，使用 DashscopeBot
    if model in [
        const.QWEN_PLUS,
        const.QWEN_MAX,
        const.QWEN_TURBO,
        const.QWEN3_235B,
        const.QWEN3_32B,
        const.QWEN3_14B,
        const.QWQ_PLUS,
        const.QWEN_CHAT,
        const.QWEN_R1
    ]:
        from bot.dashscope.dashscope_bot import DashscopeBot
        return DashscopeBot()

    # 如果模型是 Dify 系列模型，或者 bot_type 是 dify，使用 DifyBot
    if model in [
        const.DIFY_CHATBOT,
        const.DIFY_AGENT,
        const.DIFY_CHATFLOW,
        const.DIFY_WORKFLOW
    ] or bot_type == const.DIFY:
        from bot.dify.dify_bot import DifyBot
        return DifyBot()

    # 如果模型是 OpenAI 系列模型，使用 OpenAIBot
    if model in [
        const.O1_MINI,
        const.GPT_41,
        const.GPT_41_MINI,
        const.GPT_41_NANO,
        const.GPT_4O_MINI,
        const.GPT_4O_MINI_SEARCH        
    ]:
        from bot.openai.open_ai_bot import OpenAIBot
        return OpenAIBot()

    # 其他模型的处理逻辑
    if bot_type == const.BAIDU:
        from bot.baidu.baidu_wenxin import BaiduWenxinBot
        return BaiduWenxinBot()

    elif bot_type == const.CHATGPT:
        # ChatGPT 网页端web接口
        from bot.chatgpt.chat_gpt_bot import ChatGPTBot
        return ChatGPTBot()

    elif bot_type == const.CHATGPTONAZURE:
        # Azure chatgpt service
        from bot.chatgpt.chat_gpt_bot import AzureChatGPTBot
        return AzureChatGPTBot()

    elif bot_type == const.XUNFEI:
        from bot.xunfei.xunfei_spark_bot import XunFeiBot
        return XunFeiBot()

    elif bot_type == const.LINKAI:
        from bot.linkai.link_ai_bot import LinkAIBot
        return LinkAIBot()

    elif bot_type == const.CLAUDEAI:
        from bot.claude.claude_ai_bot import ClaudeAIBot
        return ClaudeAIBot()

    elif bot_type == const.CLAUDEAPI:
        from bot.claude.claude_ai_bot import ClaudeAPIBot
        return ClaudeAPIBot()

    elif bot_type == const.QWEN:
        from bot.ali.ali_qwen_bot import AliQwenBot
        return AliQwenBot()
        
    elif bot_type == const.MOONSHOT:
        from bot.moonshot.moonshot_bot import MoonshotBot
        return MoonshotBot()

    elif bot_type == const.GEMINI:
        from bot.gemini.google_gemini_bot import GoogleGeminiBot
        return GoogleGeminiBot()        

    elif bot_type == const.COZE:
        from bot.bytedance.bytedance_coze_bot import ByteDanceCozeBot
        return ByteDanceCozeBot()

    raise RuntimeError
