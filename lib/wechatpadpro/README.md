# WeChatPadPro 协议接入指南

本文档介绍如何在 Dify-on-WeChat-PadPro 项目中使用 WeChatPadPro 通道进行微信接入。

## 1. 目录结构

```
dify-on-wechat-padpro/
├── channel/                         # 通道目录
│   ├── wechatpadpro/               # WeChatPadPro 通道
│   │   ├── __init__.py             # 包初始化文件
│   │   ├── wechatpadpro_channel.py # WeChatPadPro 通道实现
│   │   └── wechatpadpro_message.py # 消息处理实现
│   └── ...
└── lib/
    └── wechatpadpro/               # WeChatPadPro 协议库
        └── WechatAPI/              # WechatAPI接口实现
            ├── Client8059/         # 8059协议客户端
            ├── core/               # 核心功能模块
            └── errors.py           # 错误处理
```

## 2. 特点与优势

作为一个独立的通道（与 wx、wxy 等并列），WeChatPadPro 通道具有以下特点：

- **基于WeChatPadPro**: 使用稳定的WeChatPadPro协议（8059端口）
- **完全独立**: 不依赖于其他通道的实现，可以单独维护和升级
- **智能登录**: 支持管理key自动生成普通key，自动二维码显示
- **自动重连**: 支持断线重连和登录状态检查
- **可扩展性**: 可以轻松添加新的特性和功能，而不影响其他通道
- **更好的代码组织**: 遵循项目的模块化架构，使代码更加清晰和易于维护

## 3. 使用方法

### 3.1 配置项目

1. 修改配置文件 `config.json`，添加以下配置项：

```json
{
  "channel_type": "wechatpadpro",
  "wechatpadpro_api_host": "127.0.0.1",
  "wechatpadpro_api_port": 8059,
  "wechatpadpro_protocol_version": "8059",
  "wechatpadpro_api_key": "",
  "wechatpadpro_admin_key": "YOUR_ADMIN_KEY"
}
```

配置说明：
- `"channel_type"`: 必须设置为 `"wechatpadpro"`
- `"wechatpadpro_protocol_version"`: 固定为 `"8059"`
- `"wechatpadpro_api_port"`: WeChatPadPro协议默认端口8059
- `"wechatpadpro_api_key"`: TOKEN_KEY，可留空自动生成
- `"wechatpadpro_admin_key"`: ADMIN_KEY，必须配置有效的管理密钥

### 3.2 启动服务

#### 前置条件

1. 确保WeChatPadPro协议服务已启动并运行在8059端口
2. 获取有效的ADMIN_KEY（管理密钥）

#### 启动步骤

1. **配置管理密钥**：在 `config.json` 中设置 `wechatpadpro_admin_key`
2. **启动主程序**：
   ```bash
   python app.py
   ```
3. **扫码登录**：程序会自动显示二维码，使用微信扫码登录
4. **开始使用**：登录成功后即可开始对话

#### 自动化流程

- 程序会自动使用管理key生成普通key
- 自动保存登录信息，下次启动时自动登录
- 支持断线重连和状态检查

## 4. 故障排除

### 4.1 WeChatPadPro协议服务问题

1. 确保WeChatPadPro协议服务正在运行
2. 检查8059端口是否被占用
3. 验证ADMIN_KEY是否有效

### 4.2 登录失败

1. 确保网络稳定
2. 检查管理密钥是否正确
3. 尝试重新启动协议服务
4. 清除保存的设备信息重新登录

### 4.3 二维码显示问题

1. 程序会自动显示ASCII二维码
2. 同时提供微信原始链接
3. 可以直接点击链接或扫描二维码

### 4.4 消息接收失败

1. 确认微信客户端保持登录状态
2. 检查网络连接是否正常
3. 检查WebSocket连接状态

## 5. 注意事项

1. WeChatPadPro协议为第三方实现，可能随微信更新而需要调整
2. 建议使用备用微信账号进行测试
3. 避免频繁登录/登出操作，防止触发风控
4. 确保WeChatPadPro协议服务稳定运行

## 6. 参考资料

- [WeChatPadPro 协议项目](https://github.com/WeChatPadPro/WeChatPadPro)
- [Dify-on-WeChat-PadPro 项目主页](https://github.com/your-username/dify-on-wechat-padpro)