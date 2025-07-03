# LLM Bot on WeChat (WeChatPadPro Edition)

本项目基于 `chatgpt-on-wechat` 框架，并深度整合 `WeChatPadPro` 协议，旨在为个人微信账号提供一个稳定、高效、功能丰富的智能对话机器人解决方案。此版本为持续优化版，修复了登录、消息处理中的多个已知问题，并对代码结构进行了重构。
协议来源: [WeChatPadPro](https://github.com/WeChatPadPro/WeChatPadPro)
原始框架: [chatgpt-on-wechat](https://github.com/zhayujie/chatgpt-on-wechat)
请自行查看WeChatPadPro协议的部署方法，不再赘述。


## 功能特点

- **WeChatPadPro协议**: 对接WeChatPadPro协议
- **高稳定性**: 连接稳定，功能丰富，支持多种消息类型
- **多样化交互**: 支持文本、图片、语音、卡片等多种消息类型
- **智能对话**: 对接Dify API，提供智能对话服务
- **灵活配置**: 支持白名单、黑名单等多样化配置

## 环境要求

- Python 3.11+
- Redis
- Windows 10/11、Linux或macOS

## 安装步骤

### 1. 下载源码

```bash
git clone https://github.com/5201213/wechat-on-wechatpadpro.git
cd wechat-on-wechatpadpro
```

### 2. 安装依赖

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装可选依赖（语音识别等）
pip install -r requirements-optional.txt
```

### 3. 配置文件

复制 `config-template.json` 为 `config.json`，并根据你的实际情况修改关键配置：

```json
{

  "channel_type": "wxpad",
   # WeChatPadPro协议版本配置
  "wechatpadpro_base_url": "http://127.0.0.1:1239", #修改为你的服务器IP跟部署的端口
  "wechatpadpro_admin_key": "YOUR_ADMIN_KEY_HERE", # ADMIN_KEY（管理key，用于生成普通key）
  "wechatpadpro_user_key": null # TOKEN_KEY（普通key，可由管理key自动生成
  "wechatpadpro_ws_url": "ws://IP:1239/ws/GetSyncMsg",#修改为你的服务器IP跟部署的端口
  "log_level": "INFO",
  
}
```

## 使用方法

### 前置条件

1. 确保已安装并启动WeChatPadPro协议服务


### 启动步骤

1. **配置管理密钥**：在 `config.json` 中设置 `wechatpadpro_admin_key`
2. **启动主程序**：
   ```bash
   python app.py
   ```
3. **扫码登录**：程序会自动显示二维码，使用微信扫码登录
4. **开始使用**：登录成功后即可开始对话

### 自动化流程

- 程序会自动使用管理key生成普通key
- 自动保存登录信息，下次启动时自动登录
- 支持断线重连和状态检查

## 消息交互

### 私聊交互
直接向机器人发送消息即可获得回复

### 群聊交互
默认使用`@bot`前缀，例如：`@bot 今天天气怎么样？`

## 常见问题

### WeChatPadPro协议服务问题
- 确保WeChatPadPro协议服务正在运行
- 检查1239端口是否被占用
- 验证ADMIN_KEY是否有效

### 登录问题
- 确保网络稳定
- 检查管理密钥是否正确
- 尝试重新启动协议服务
- 清除保存的设备信息重新登录

### 二维码显示问题
- 程序会自动显示ASCII二维码
- 同时提供微信原始链接
- 可以直接点击链接或扫描二维码


## 注意事项

1. WeChatPadPro协议为第三方实现，可能随微信更新而需要调整
2. 建议使用备用微信账号进行测试
3. 避免频繁登录/登出操作，防止触发风控
4. 定期更新代码以获取最新功能和修复
5. 确保WeChatPadPro协议服务稳定运行

## 目录结构

```
wechat-on-wechatpadpro/
├── channel/                         # 通道目录
│   ├── wxpad/                      # WeChatPadPro通道实现
│   │   ├── wxpad_channel.py        # 通道主文件
│   │   └── wxpad_message.py        # 消息处理
│   └── ...
├── lib/
│   └── wxpad/                       # WeChatPadPro协议库
│       └── client.py               # 协议API客户端
├── config-template.json            # 配置模板
├── config.json                     # 你的配置文件
└── app.py                          # 主程序
```

## 更新与维护

1. 定期拉取最新代码：
   ```bash
   git pull
   ```

2. 更新依赖：
   ```bash
   pip install -r requirements.txt --upgrade
   ```

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 贡献与感谢

### 通道实现
- **[WeChatPadPro](https://github.com/WeChatPadPro/WeChatPadPro)**: 提供稳定可靠的微信iPad协议实现

### 基础架构
- **[CoW(chatgpt-on-wechat)](https://github.com/zhayujie/chatgpt-on-wechat)**: 提供微信机器人的基础架构
- **[DoW(dify-on-wechat)](https://github.com/hanfangyuan4396/dify-on-wechat)**: 提供Dify集成的核心功能

### 参考项目
- **[chatgpt-on-wechat](https://github.com/zhayujie/chatgpt-on-wechat)**: 原版项目基础
- **[xxxbot-pad](https://github.com/NanSsye/xxxbot-pad)**: iPad协议接入参考

由于本人不会代码，此项目全由ai写作不好的地方欢迎提交Pull Request或Issue来帮助改进本项目！

---

## 交流器
![b5f35b0052209b43c52f8274c904fc9](https://github.com/user-attachments/assets/eeb0c535-7e1e-493b-b219-08e8e26d8c30)


**免责声明**：本项目仅供学习和研究使用，请勿用于商业或违法用途。使用本项目产生的任何后果由用户自行承担。
