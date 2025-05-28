# WeChatPadPro 通道

这是一个基于WeChatPadPro协议的微信机器人通道实现，用于对接Dify平台。

## 文件结构

- `wechatpadpro_channel.py`: 通道主文件，负责通道的初始化、消息收发、会话管理等
- `wechatpadpro_message.py`: 消息处理文件，处理各类微信消息的解析和格式化

## 功能特点

- 支持私聊和群聊消息
- 支持文本、图片、语音等多种消息类型
- 自动处理群系统消息（如入群、退群通知）
- 基于WeChatPadPro 8059协议，稳定可靠
- 健壮的错误处理和重连机制
- 详细的日志记录
- 自动二维码显示和登录
- 智能key管理（管理key自动生成普通key）

## 配置说明

在`config.json`中可以配置以下参数：

```json
{
  "channel_type": "wechatpadpro",             // 通道类型
  "wechatpadpro_api_host": "127.0.0.1",      // WeChatPadPro服务器地址
  "wechatpadpro_api_port": 8059,             // WeChatPadPro服务器端口（默认8059）
  "wechatpadpro_protocol_version": "8059",   // 协议版本（固定8059）
  "wechatpadpro_api_key": "",                // TOKEN_KEY（普通key，可自动生成）
  "wechatpadpro_admin_key": "your_admin_key", // ADMIN_KEY（管理key，必须配置）
  "expires_in_seconds": 3600                 // 消息过期时间
}
```

## 使用方法

1. 确保WeChatPadPro协议服务已启动（默认端口8059）
2. 在配置文件中设置`channel_type`为`wechatpadpro`
3. 配置有效的`wechatpadpro_admin_key`（管理密钥）
4. 启动程序：`python app.py`
5. 程序会自动显示二维码，使用微信扫码登录

## 代码说明

- `WechatPadProChannel`: 通道主类，处理消息收发和登录管理
- `WechatPadProMessage`: 消息处理类，负责消息的解析和格式化
- `_check`: 装饰器函数，用于过滤重复消息和过期消息

## 登录流程

1. **自动登录检查**: 检查是否有保存的登录信息
2. **Key管理**: 使用管理key自动生成普通key
3. **二维码登录**: 自动显示ASCII二维码和原始链接
4. **状态保存**: 自动保存登录状态，支持下次自动登录

## 常见问题

1. **连接问题**: 检查WeChatPadPro协议服务是否在8059端口正常运行
2. **登录失败**: 验证ADMIN_KEY是否正确有效
3. **二维码问题**: 程序会同时显示ASCII二维码和原始链接
4. **消息解析错误**: 确保使用的是8059协议版本