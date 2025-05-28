# encoding:utf-8

from bot.bot import Bot
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from .dashscope_session import DashscopeSession
import os
import logging
import dashscope
from http import HTTPStatus


# 直接使用字符串作为模型名称
dashscope_models = {}

# 基础模型 - 尝试使用 Models 类属性
try:
    dashscope_models["qwen-plus"] = dashscope.Generation.Models.qwen_plus
except AttributeError:
    dashscope_models["qwen-plus"] = "qwen-plus"
    logger.warning("使用字符串替代 Models.qwen_plus")

try:
    dashscope_models["qwen-max"] = dashscope.Generation.Models.qwen_max
except AttributeError:
    dashscope_models["qwen-max"] = "qwen-max"
    logger.warning("使用字符串替代 Models.qwen_max")

# 新模型 - 直接使用字符串
dashscope_models["qwq-plus"] = "qwq-plus"
logger.info("已添加 qwq-plus 模型（使用字符串模型名）")

dashscope_models["qwen-turbo-2025-04-28"] = "qwen-turbo-2025-04-28"
logger.info("已添加 qwen-turbo-2025-04-28 模型（使用字符串模型名）")

dashscope_models["qwen3-235b-a22b"] = "qwen3-235b-a22b"
logger.info("已添加 qwen3-235b-a22b 模型（使用字符串模型名）")

dashscope_models["qwen3-32b"] = "qwen3-32b"
logger.info("已添加 qwen3-32b 模型（使用字符串模型名）")

dashscope_models["qwen3-14b"] = "qwen3-14b"
logger.info("已添加 qwen3-14b 模型（使用字符串模型名）")

dashscope_models["deepseek-v3"] = "deepseek-v3"
logger.info("已添加 deepseek-v3 模型（使用字符串模型名）")

dashscope_models["deepseek-r1"] = "deepseek-r1"
logger.info("已添加 deepseek-r1 模型（使用字符串模型名）")

# 定义需要使用OpenAI兼容模式的模型
openai_compatible_models = ["qwq-plus", "deepseek-r1", "qwen-turbo-2025-04-28", "qwen3-235b-a22b", "qwen3-32b", "qwen3-14b"]

# 定义需要流式模式的模型
stream_required_models = ["qwq-plus", "deepseek-r1", "qwen-turbo-2025-04-28", "qwen3-235b-a22b", "qwen3-32b", "qwen3-14b"]

# Dashscope对话模型API
class DashscopeBot(Bot):
    def __init__(self):
        super().__init__()
        self.sessions = SessionManager(DashscopeSession, model=conf().get("model") or "qwen-plus")
        self.model_name = conf().get("model") or "qwen-plus"
        self.api_key = conf().get("dashscope_api_key")
        os.environ["DASHSCOPE_API_KEY"] = self.api_key
        self.client = dashscope.Generation

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[DASHSCOPE] query={}".format(query))

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
            logger.debug("[DASHSCOPE] session query={}".format(session.messages))

            reply_content = self.reply_text(session)
            logger.debug(
                "[DASHSCOPE] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                # 将ERROR类型改为TEXT类型，避免[ERROR]标记出现在回复内容中
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                # 将ERROR类型改为TEXT类型，避免[ERROR]标记出现在回复内容中
                reply = Reply(ReplyType.TEXT, reply_content["content"])
                logger.debug("[DASHSCOPE] reply {} used 0 tokens.".format(reply_content))
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: DashscopeSession, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            dashscope.api_key = self.api_key
            
            # 检查模型是否存在
            if self.model_name not in dashscope_models:
                available_models = list(dashscope_models.keys())
                logger.warning(f"模型 {self.model_name} 不存在，可用模型: {available_models}")
                
                # 如果没有可用模型，返回错误信息
                if not available_models:
                    return {
                        "completion_tokens": 0, 
                        "content": f"抱歉，当前没有可用的模型。请联系管理员更新 dashscope 库或修改配置。"
                    }
                
                # 使用默认模型
                model_to_use = "qwen-plus" if "qwen-plus" in dashscope_models else available_models[0]
                logger.info(f"使用默认模型: {model_to_use} 替代请求的模型: {self.model_name}")
            else:
                model_to_use = self.model_name
            
            # 获取模型值
            model_value = dashscope_models[model_to_use]
            
            # 确定是否需要流式模式
            need_stream = model_to_use in stream_required_models or (isinstance(model_value, str) and model_value in stream_required_models)
            
            # 检查是否需要使用OpenAI兼容模式
            use_openai_compatible = model_to_use in openai_compatible_models
            
            # 使用OpenAI兼容模式API
            if use_openai_compatible:
                logger.info(f"使用OpenAI兼容模式调用: {model_value}")
                try:
                    import requests
                    import json
                    
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    # 转换消息格式
                    messages = []
                    for msg in session.messages:
                        if isinstance(msg, dict) and "role" in msg and "content" in msg:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                    
                    data = {
                        "model": model_value,
                        "messages": messages,
                        "stream": True  # QwQ模型必须使用流式模式
                    }
                    
                    logger.debug(f"OpenAI兼容模式请求数据: {json.dumps(data, ensure_ascii=False)}")
                    
                    try:
                        response = requests.post(
                            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                            headers=headers,
                            json=data,
                            stream=True,
                            timeout=30
                        )
                        
                        logger.debug(f"OpenAI兼容模式响应状态码: {response.status_code}")
                        
                        if response.status_code == 200:
                            full_content = ""
                            reasoning_content = ""
                            total_tokens = 0
                            completion_tokens = 0
                            
                            # 使用更安全的方式处理流式响应
                            for line in response.iter_lines():
                                if not line:
                                    continue
                                    
                                try:
                                    # 解码行内容
                                    line_str = line.decode('utf-8', errors='replace')
                                    logger.debug(f"收到行: {line_str}")
                                    
                                    # 检查是否是数据行
                                    if not line_str.startswith('data: '):
                                        logger.debug(f"跳过非数据行: {line_str}")
                                        continue
                                        
                                    # 提取数据部分
                                    data_str = line_str[6:].strip()  # 去掉 'data: ' 前缀
                                    
                                    # 检查是否是结束标记
                                    if data_str == '[DONE]':
                                        logger.debug("收到结束标记 [DONE]")
                                        continue
                                    
                                    # 尝试解析JSON
                                    try:
                                        chunk = json.loads(data_str)
                                        logger.debug(f"解析的JSON: {json.dumps(chunk, ensure_ascii=False)[:100]}...")
                                    except json.JSONDecodeError as je:
                                        logger.error(f"JSON解析错误: {je}, 数据: {data_str}")
                                        continue
                                    
                                    # 处理usage信息
                                    if chunk and isinstance(chunk, dict) and 'usage' in chunk:
                                        usage = chunk.get('usage', {})
                                        if isinstance(usage, dict):
                                            total_tokens = usage.get('total_tokens', total_tokens)
                                            completion_tokens = usage.get('completion_tokens', completion_tokens)
                                            logger.debug(f"更新token使用情况: total={total_tokens}, completion={completion_tokens}")
                                    
                                    # 处理choices信息
                                    if chunk and isinstance(chunk, dict) and 'choices' in chunk:
                                        choices = chunk.get('choices', [])
                                        if choices and isinstance(choices, list) and len(choices) > 0:
                                            choice = choices[0]
                                            if isinstance(choice, dict) and 'delta' in choice:
                                                delta = choice.get('delta', {})
                                                if isinstance(delta, dict):
                                                    # 处理思考过程
                                                    if 'reasoning_content' in delta:
                                                        rc = delta.get('reasoning_content')
                                                        if rc:
                                                            reasoning_content += rc
                                                            logger.debug(f"思考过程: {rc}")
                                                    
                                                    # 处理回复内容
                                                    if 'content' in delta:
                                                        content = delta.get('content')
                                                        if content:
                                                            full_content += content
                                                            logger.debug(f"回复内容: {content}")
                                                # 检查并移除回复内容中可能的错误标记
                                                if full_content.startswith("[ERROR]"):
                                                    full_content = full_content[7:].lstrip()
                                                    logger.info(f"已移除回复内容中的[ERROR]标记")
                                    else:
                                        logger.debug(f"收到空的delta对象: {response.output.choices[0]}")
                                except Exception as line_error:
                                    logger.error(f"处理行时出错: {line_error}")
                                    logger.debug(f"问题行内容: {line if isinstance(line, bytes) else 'non-bytes'}")
                                    # 继续处理下一行，不中断
                            
                            logger.info(f"OpenAI兼容模式调用成功，获取到回复: {len(full_content)} 字符")
                            if not full_content:
                                logger.warning("未获取到任何回复内容")
                                
                            # 检查并移除回复内容中可能的错误标记
                            if full_content.startswith("[ERROR]"):
                                full_content = full_content[7:].lstrip()
                                logger.info(f"已移除回复内容中的[ERROR]标记")
                                
                            return {
                                "total_tokens": total_tokens,
                                "completion_tokens": completion_tokens,
                                "content": full_content if full_content else "抱歉，我暂时无法回答这个问题。",
                            }
                        else:
                            error_text = "无法获取响应内容"
                            try:
                                error_text = response.text
                            except:
                                pass
                            error_message = f"OpenAI兼容模式API调用失败: 状态码 {response.status_code} - {error_text}"
                            logger.error(error_message)
                            raise Exception(error_message)
                    except requests.RequestException as req_err:
                        logger.error(f"请求异常: {req_err}")
                        raise Exception(f"API请求失败: {req_err}")
                        
                except Exception as e:
                    logger.error(f"OpenAI兼容模式调用出错: {e}")
                    if retry_count < 2:
                        logger.info(f"尝试使用标准模式重试 (重试次数: {retry_count + 1})")
                        # 尝试使用标准模式
                        use_openai_compatible = False
                        need_stream = True
                    else:
                        raise e
            
            # 根据模型值类型决定调用方式
            elif isinstance(model_value, str):
                # 如果是字符串，直接使用model参数
                logger.info(f"使用字符串模型名称调用: {model_value}" + (" (流式模式)" if need_stream else ""))
                
                # 准备调用参数
                call_params = {
                    "model": model_value,
                    "messages": session.messages,
                    "result_format": "message",
                }
                
                # 如果需要流式模式，添加stream参数
                if need_stream:
                    call_params["stream"] = True
                    
                    # 使用流式模式调用API
                    full_content = ""
                    reasoning_content = ""
                    total_tokens = 0
                    output_tokens = 0
                    
                    try:
                        for response in self.client.call(**call_params):
                            if response.status_code == HTTPStatus.OK:
                                if response.output and response.output.choices and len(response.output.choices) > 0:
                                    # 检查是否有reasoning_content字段
                                    delta = response.output.choices[0].get("delta", {})
                                    if delta is not None:
                                        if "reasoning_content" in delta:
                                            reasoning_part = delta.get("reasoning_content", "")
                                            if reasoning_part:
                                                reasoning_content += reasoning_part
                                                logger.debug(f"思考过程: {reasoning_part}")
                                        
                                        # 获取回复内容 - 检查message是否存在
                                        message = response.output.choices[0].get("message")
                                        if message is not None:
                                            chunk = message.get("content", "")
                                            if chunk:
                                                full_content += chunk
                                        # 如果没有message字段，尝试从delta中获取content
                                        elif "content" in delta and delta["content"]:
                                            full_content += delta["content"]
                                    else:
                                        logger.debug(f"收到空的delta对象: {response.output.choices[0]}")
                                elif response.output:
                                    logger.debug(f"响应output不包含有效的choices: {response.output}")
                                else:
                                    logger.debug("响应不包含output字段")
                            
                                if response.usage:
                                    total_tokens = response.usage.get("total_tokens", 0)
                                    output_tokens = response.usage.get("output_tokens", 0)
                            else:
                                logger.error('Stream request failed: %s, Status code: %s, error code: %s, error message: %s' % (
                                    response.request_id, response.status_code,
                                    response.code, response.message
                                ))
                                raise Exception(f"流式请求失败: {response.message}")
                        
                        # 返回完整内容
                        logger.info(f"流式调用成功，获取到回复: {len(full_content)} 字符")
                        return {
                            "total_tokens": total_tokens,
                            "completion_tokens": output_tokens,
                            "content": full_content,
                        }
                    except Exception as stream_error:
                        logger.error(f"流式调用出错: {stream_error}")
                        raise stream_error
                else:
                    # 非流式调用
                    response = self.client.call(**call_params)
            else:
                # 使用原来的方式调用
                logger.info(f"使用Models类属性调用模型")
                response = self.client.call(
                    model_value,
                    messages=session.messages,
                    result_format="message"
                )
            
            # 处理非流式调用的响应
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0]["message"]["content"]
                return {
                    "total_tokens": response.usage["total_tokens"],
                    "completion_tokens": response.usage["output_tokens"],
                    "content": content,
                }
            else:
                logger.error('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                    response.request_id, response.status_code,
                    response.code, response.message
                ))
                result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
                need_retry = retry_count < 2
                if need_retry:
                    return self.reply_text(session, retry_count + 1)
                else:
                    return result
        except Exception as e:
            logger.error(f"{self.model_name}")
            logger.error(e, exc_info=True)
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": f"抱歉，模型调用出错，请稍后再试或联系管理员。错误信息：{str(e)}"}
            if need_retry:
                return self.reply_text(session, retry_count + 1)
            else:
                return result
