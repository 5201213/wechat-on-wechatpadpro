# WeChatPadPro通道8059协议支持指南

## 概述

本指南介绍如何在WeChatPadPro通道中使用8059协议（WeChatPadPro-8059）。8059协议是一个基于HTTP的微信协议实现，提供了完整的微信功能支持。

## 主要特性

### 8059协议特点
- **双重消息获取**: 支持WebSocket实时连接和HTTP轮询两种消息获取方式
- **无API前缀**: API路径直接使用如`/login/`、`/message/`等，不需要`/api`前缀
- **双Key认证**: 使用TOKEN_KEY进行普通API调用，ADMIN_KEY进行管理功能
- **完整功能**: 支持文本、图片、语音、视频、红包等完整微信功能
- **管理功能**: 支持授权码生成、删除、延期等管理操作

### 支持的功能
- ✅ 文本消息发送/接收
- ✅ 图片消息发送/接收
- ✅ 语音消息发送/接收
- ✅ 视频消息转发
- ✅ 好友管理（添加、删除、搜索）
- ✅ 群聊管理（创建、邀请、移除成员）
- ✅ 朋友圈操作（发布、点赞、评论）
- ✅ 红包和转账功能
- ✅ 登录管理（二维码、二次登录）

## 配置说明

### 基础配置

在`config.json`中设置以下参数：

```json
{
  "channel_type": "wechatpadpro",
  "wechatpadpro_protocol_version": "8059",
  "wechatpadpro_api_host": "127.0.0.1",
  "wechatpadpro_api_port": 8059,
  "wechatpadpro_api_key": "cc824010-dbc4-40fe-a0c7-a0a09f825402",
  "wechatpadpro_admin_key": "stay33"
}
```

### 配置参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wx849_protocol_version` | string | "855" | 设置为"8059"启用8059协议 |
| `wx849_api_host` | string | "127.0.0.1" | 8059协议服务器地址 |
| `wx849_api_port` | int | 8059 | 8059协议服务器端口 |
| `wx849_api_key` | string | "" | TOKEN_KEY，用于普通API调用（必须设置） |
| `wx849_admin_key` | string | "" | ADMIN_KEY，用于管理功能（可选） |

### 可选配置

```json
{
  "wx849_8059_message_mode": "websocket",
  "wx849_8059_polling_interval": 1,
  "wx849_8059_timeout": 10,
  "wx849_8059_retry_count": 3
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wx849_8059_message_mode` | string | "websocket" | 消息获取方式："websocket"或"polling" |
| `wx849_8059_polling_interval` | int | 1 | HTTP轮询间隔（秒） |
| `wx849_8059_timeout` | int | 10 | API调用超时时间（秒） |
| `wx849_8059_retry_count` | int | 3 | 失败重试次数 |

## 使用步骤

### 1. 安装依赖

确保已安装所需的Python包：

```bash
pip install aiohttp loguru
```

### 2. 配置文件

复制`config-8059-example.json`为`config.json`并修改相关配置：

```bash
cp config-8059-example.json config.json
```

编辑`config.json`，设置：
- `wx849_api_key`: TOKEN_KEY (示例中的密钥是真实可用的)
- `wx849_admin_key`: ADMIN_KEY (可选，用于管理功能)
- `wx849_api_host`: 8059服务器地址
- `wx849_api_port`: 8059服务器端口

### 3. 启动服务

```bash
python app.py
```

### 4. 登录微信

程序启动后会自动尝试连接8059协议服务器。根据8059协议的登录流程进行微信登录。

## API接口映射

### 8059协议 vs 855协议

| 功能 | 8059协议路径 | 855协议路径 |
|------|-------------|-------------|
| 登录二维码 | `/login/GetLoginQrCode` | `/api/Login/GetQrCode` |
| 检查登录 | `/login/LoginCheckQR` | `/api/Login/CheckLogin` |
| 发送消息 | `/message/SendMessage` | `/api/Msg/SendTxt` |
| 获取消息 | `/message/GetSyncMsg` | WebSocket |
| 好友列表 | `/friend/GetFriendList` | `/api/Friend/GetFriendList` |
| 群聊管理 | `/group/CreateChatRoom` | `/api/Group/CreateGroup` |

## 消息格式差异

### 8059协议消息格式

```json
{
  "MsgItem": [{
    "ToUserName": "接收者ID",
    "MsgType": 1,
    "TextContent": "消息内容",
    "AtWxIDList": []
  }]
}
```

### 855协议消息格式

```json
{
  "ToWxid": "接收者ID",
  "Content": "消息内容",
  "Type": 1,
  "wxid": "发送者ID"
}
```

## 错误处理

### 常见错误及解决方案

1. **连接失败**
   ```
   [WX8059] API调用失败: Network error
   ```
   - 检查`wx849_api_host`和`wx849_api_port`配置
   - 确认8059协议服务器正在运行

2. **认证失败**
   ```
   [WX8059] API调用失败: Authentication error
   ```
   - 检查`wx849_api_key`配置是否正确
   - 确认key是否有效且未过期

3. **消息发送失败**
   ```
   [WX8059] 发送文本消息失败: Message send error
   ```
   - 检查接收者ID是否正确
   - 确认账号登录状态正常

## 日志说明

### 日志前缀

- `[WX8059]`: 8059协议相关日志
- `[WX849]`: 通用wx849通道日志

### 重要日志示例

```
[WX8059] 初始化8059协议客户端: 127.0.0.1:8059, key=abc123
[WX8059] 获取到 3 条新消息 (耗时1.23s)
[WX8059] 发送文本消息成功: wxid_xxx
```

## 性能优化

### 轮询优化

8059协议使用HTTP轮询，可通过以下方式优化：

1. **调整轮询间隔**
   ```json
   "wx849_8059_polling_interval": 2
   ```

2. **设置合理超时**
   ```json
   "wx849_8059_timeout": 5
   ```

3. **减少重试次数**
   ```json
   "wx849_8059_retry_count": 1
   ```

## 故障排除

### 调试模式

启用调试模式获取详细日志：

```json
{
  "log_level": "DEBUG",
  "debug": true
}
```

### 网络诊断

检查8059协议服务器连通性：

```bash
curl http://127.0.0.1:8059/login/GetLoginQrCode?key=your_key
```

### 常见问题

1. **Q: 消息接收延迟**
   A: 降低`wx849_8059_polling_interval`值

2. **Q: 频繁超时**
   A: 增加`wx849_8059_timeout`值

3. **Q: 登录失败**
   A: 检查key配置和8059服务器状态

## 更新日志

### v1.0.0 (2024-01-XX)
- 初始版本
- 支持8059协议基础功能
- 实现消息收发、好友管理、群聊管理
- 添加朋友圈和红包功能支持

## 技术支持

如遇到问题，请：

1. 检查配置文件格式和参数
2. 查看日志输出定位问题
3. 确认8059协议服务器状态
4. 提交Issue时附上相关日志

## 相关链接

- [WX849通道文档](../README.md)
- [8059协议接口文档](./8059-API-Reference.md)
- [配置示例文件](../config-8059-example.json)
