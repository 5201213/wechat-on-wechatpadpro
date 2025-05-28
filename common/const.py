# bot_type
ZHIPU_AI = "zhipuai"
OPEN_AI = "openAI"
CHATGPT = "chatGPT"
BAIDU = "baidu"
XUNFEI = "xunfei"
CHATGPTONAZURE = "chatGPTOnAzure"
LINKAI = "linkai"
CLAUDEAI = "claude" # 使用cookie的历史模型
CLAUDEAPI= "claudeAPI" # 通过Claude api调用模型
QWEN = "qwen"  # 旧版通义模型
QWEN_DASHSCOPE = "dashscope"   # 通义新版sdk和api key
GEMINI = "gemini"
MOONSHOT = "moonshot"
MiniMax = "minimax"
COZE = "coze"
DIFY = "dify"
SILICONFLOW = "siliconflow"  # 确保这个值与 config.json 中的 bot_type 一致
DEEPSEEK = "deepseek"  # 添加DeepSeek类型
MODELSCOPE = "modelscope"  # 添加ModelScope类型

# openAI models
O1_MINI = "o1-mini"
GPT_41 = "gpt-4.1"
GPT_41_MINI = "gpt-4.1-mini"
GPT_41_NANO = "gpt-4.1-nano"
GPT_4O_MINI = "gpt-4o-mini"
GPT_4O_MINI_SEARCH = "gpt-4o-mini-search-preview"

WHISPER_1 = "whisper-1"
TTS_1 = "tts-1"
TTS_1_HD = "tts-1-hd"

# dashscope models
QWEN_PLUS = "qwen-plus"
QWEN_MAX = "qwen-max"
QWEN_TURBO = "qwen-turbo-2025-04-28"
QWEN3_235B = "qwen3-235b-a22b"
QWEN3_32B = "qwen3-32b"
QWEN3_14B = "qwen3-14b"
QWQ_PLUS = "qwq-plus"
QWEN_CHAT = "deepseek-v3"
QWEN_R1 = "deepseek-r1"

# zhipuai models
GLM_4_PLUS = "glm-4-plus"
GLM_4_FLASH = "glm-4-flash-250414"
GLM_Z1_FLASH = "glm-z1-flash"

# siliconflow models
DEEPSEEK_V3 = "deepseek-ai/DeepSeek-V3"
DEEPSEEK_R1 = "deepseek-ai/DeepSeek-R1"
GLM_4_9B = "THUDM/GLM-4-9B-0414"
GLM_Z1_9B = "THUDM/GLM-Z1-9B-0414"
GLM_Z1_R_32B = "THUDM/GLM-Z1-Rumination-32B-0414"
QWEN_2_7B = "Qwen/Qwen2.5-7B-Instruct"

# deepseek models
DEEPSEEK_CHAT = "deepseek-chat"
DEEPSEEK_REASONER = "deepseek-reasoner"

# gemini models
GEMINI_15_FLASH = "gemini-1.5-flash"
GEMINI_15_PRO = "gemini-1.5-pro"
GEMINI_20_FLASH_EXP = "gemini-2.0-flash-exp"

# dify models
DIFY_CHATFLOW = "chatflow"
DIFY_CHATBOT = "chatbot"
DIFY_AGENT = "agent"
DIFY_WORKFLOW = "workflow"

MODEL_LIST = [OPEN_AI, O1_MINI, GPT_41, GPT_41_MINI, GPT_41_NANO, GPT_4O_MINI, GPT_4O_MINI_SEARCH,
              QWEN_DASHSCOPE, QWEN_PLUS, QWEN_MAX, QWEN_TURBO, QWEN3_235B, QWEN3_32B, QWEN3_14B, QWQ_PLUS, QWEN_CHAT, QWEN_R1,
              ZHIPU_AI, GLM_4_PLUS, GLM_4_FLASH, GLM_Z1_FLASH, 
              SILICONFLOW, DEEPSEEK_V3, DEEPSEEK_R1, QWEN_2_7B, GLM_4_9B, GLM_Z1_9B, GLM_Z1_R_32B,
              COZE, 
              DIFY, DIFY_CHATFLOW, DIFY_CHATBOT, DIFY_AGENT, DIFY_WORKFLOW,
              GEMINI, GEMINI_15_FLASH, GEMINI_15_PRO, GEMINI_20_FLASH_EXP,
              DEEPSEEK, DEEPSEEK_CHAT, DEEPSEEK_REASONER]

# channel
FEISHU = "feishu"
DINGTALK = "dingtalk"
