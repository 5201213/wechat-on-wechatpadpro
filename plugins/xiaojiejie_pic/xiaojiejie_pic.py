from io import BytesIO
import requests
import plugins
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger

BASE_URL_365 = "https://3650000.xyz/api/" #https://3650000.xyz/
BASE_URL_QEMAOAPI = "http://api.qemao.com/api/" 


@plugins.register(name="xiaojiejie_pic",
                  desc="xiaojiejie_pic插件",
                  version="1.0",
                  author="masterke",
                  desire_priority=100)
class xiaojiejie_pic(Plugin):
    content = None
    config_data = None
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info(f"[{__class__.__name__}] inited")

    def get_help_text(self, **kwargs):
        help_text = f""
        return help_text

    def on_handle_context(self, e_context: EventContext):
        # 只处理文本消息
        if e_context['context'].type != ContextType.TEXT:
            return
        self.content = e_context["context"].content.strip()
        
        if self.content == "图片":
            logger.info(f"[{__class__.__name__}] 收到消息: {self.content}")
            # 读取配置文件
            config_path = os.path.join(os.path.dirname(__file__),"config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    self.config_data = json.load(file)
            else:
                logger.error(f"请先配置{config_path}文件")
                return
            
            reply = Reply()
            result = self.xiaojiejie_pic()
            if result != None:
                reply.type = ReplyType.IMAGE if isinstance(result,BytesIO) else ReplyType.IMAGE_URL
                reply.content = result
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                reply.type = ReplyType.ERROR
                reply.content = "获取失败,等待修复⌛️"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

    def xiaojiejie_pic(self):
        try:
            # 主接口
            url = BASE_URL_QEMAOAPI + "pic/"
            params = f"type={self.config_data['xiaojiejie_pic_size']}"
            headers = {'Content-Type': "application/x-www-form-urlencoded"}
            response = requests.get(url=url, params=params, headers=headers,timeout=2)
            if response.status_code==200:
                logger.info(f"主接口获取图片:{response.content[:10]}")
                image_bytes = response.content
                # 使用BytesIO保存到内存中
                image_in_memory = BytesIO(image_bytes)
                return image_in_memory
            else:
                logger.error(f"主接口请求失败:{response.status_code}")
                raise requests.exceptions.ConnectionError
        except Exception as e:
            try:
                # 备用接口
                logger.error(f"主接口抛出异常:{e}")
                url = BASE_URL_365
                params = f"type=json"
                headers = {'Content-Type': "application/x-www-form-urlencoded"}
                response = requests.get(url=url, params=params, headers=headers)
                if response.status_code==200:
                    json_data = response.json()
                    if json_data['code']==200 and json_data['url']:
                        img_url = json_data['url']
                        return img_url
                    else:
                        logger.error(f"备用接口返回数据异常:{json_data}")
                else:
                    logger.error(f"备用接口请求失败:{response.status_code}")
            except Exception as e:
                logger.error(f"备用接口抛出异常:{e}")

        logger.error(f"所有接口都挂了,无法获取")
        return None