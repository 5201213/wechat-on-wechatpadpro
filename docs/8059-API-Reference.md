# 8059协议API参考文档

## 概述

本文档描述了WX849通道中8059协议（WeChatPadPro-8059）的API接口实现。

## 基础信息

- **协议版本**: 8059
- **通信方式**: HTTP/HTTPS
- **认证方式**: URL参数中的key
- **消息获取**: HTTP轮询
- **API前缀**: 无（直接使用路径如`/login/`、`/message/`）

## 认证

所有API请求都需要在URL参数中包含`key`参数：

```
GET /login/GetLoginQrCode?key=your_api_key
POST /message/SendMessage?key=your_api_key
```

## 登录相关API

### 获取登录二维码

**接口**: `GET /login/GetLoginQrCode`

**参数**:
- `key` (string): 账号唯一标识

**请求体**:
```json
{
  "Proxy": "",
  "Check": false
}
```

**响应**:
```json
{
  "Success": true,
  "Data": {
    "uuid": "登录UUID",
    "qrUrl": "二维码URL"
  }
}
```

### 检查登录状态

**接口**: `POST /login/LoginCheckQR`

**参数**:
- `key` (string): 账号唯一标识

**请求体**:
```json
{
  "uuid": "登录UUID"
}
```

**响应**:
```json
{
  "Success": true,
  "Data": {
    "acctSectResp": {
      "userName": "用户微信ID",
      "nickName": "用户昵称"
    }
  }
}
```

### 二次登录

**接口**: `POST /login/LoginTwiceAutoAuth`

**请求体**:
```json
{
  "wxid": "微信ID"
}
```

## 消息相关API

### 发送消息

**接口**: `POST /message/SendMessage`

**请求体**:
```json
{
  "MsgItem": [{
    "ToUserName": "接收者微信ID",
    "MsgType": 1,
    "TextContent": "消息内容",
    "AtWxIDList": []
  }]
}
```

**消息类型**:
- `1`: 文本消息
- `2`: 图片消息
- `3`: 语音消息
- `43`: 视频消息

### 获取同步消息

**接口**: `GET /message/GetSyncMsg`

**参数**:
- `key` (string): 账号唯一标识

**响应**:
```json
{
  "Success": true,
  "Data": {
    "MsgList": [
      {
        "MsgId": "消息ID",
        "FromUserName": "发送者",
        "ToUserName": "接收者", 
        "MsgType": 1,
        "Content": "消息内容",
        "CreateTime": 1234567890
      }
    ]
  }
}
```

### 撤回消息

**接口**: `POST /message/RevokeMsg`

**请求体**:
```json
{
  "ToUserName": "接收者",
  "ClientMsgId": 123456,
  "CreateTime": 1234567890,
  "NewMsgId": "消息ID"
}
```

## 好友相关API

### 获取好友列表

**接口**: `GET /friend/GetFriendList`

**响应**:
```json
{
  "Success": true,
  "Data": {
    "FriendList": [
      {
        "UserName": "好友微信ID",
        "NickName": "好友昵称",
        "RemarkName": "备注名"
      }
    ]
  }
}
```

### 搜索联系人

**接口**: `POST /friend/SearchContact`

**请求体**:
```json
{
  "UserName": "搜索关键词",
  "FromScene": 3,
  "SearchScene": 1,
  "OpCode": 1
}
```

### 添加好友

**接口**: `POST /friend/VerifyUser`

**请求体**:
```json
{
  "OpCode": 2,
  "Scene": 3,
  "VerifyContent": "验证信息",
  "V3": "V3数据",
  "V4": "V4数据"
}
```

## 群聊相关API

### 创建群聊

**接口**: `POST /group/CreateChatRoom`

**请求体**:
```json
{
  "UserList": ["用户1", "用户2"],
  "TopIc": "群聊主题"
}
```

### 获取群成员

**接口**: `POST /group/GetChatroomMemberDetail`

**请求体**:
```json
{
  "ChatRoomName": "群聊ID"
}
```

### 邀请群成员

**接口**: `POST /group/InviteChatroomMembers`

**请求体**:
```json
{
  "ChatRoomName": "群聊ID",
  "UserList": ["用户1", "用户2"]
}
```

## 用户相关API

### 获取用户信息

**接口**: `GET /user/GetUserInfo`

**响应**:
```json
{
  "Success": true,
  "Data": {
    "UserName": "用户微信ID",
    "NickName": "用户昵称",
    "Signature": "个性签名"
  }
}
```

### 修改昵称

**接口**: `POST /user/UpdateNickName`

**请求体**:
```json
{
  "NickName": "新昵称"
}
```

### 设置个性签名

**接口**: `POST /user/SetSignature`

**请求体**:
```json
{
  "Signature": "个性签名"
}
```

## 朋友圈相关API

### 获取朋友圈

**接口**: `POST /sns/GetSnsInfo`

**请求体**:
```json
{
  "UserName": "用户微信ID",
  "MaxID": 0,
  "FirstPageMD5": ""
}
```

### 发布朋友圈

**接口**: `POST /sns/UploadFriendCircle`

**请求体**:
```json
{
  "Content": "朋友圈内容",
  "ImageDataList": [],
  "VideoDataList": [],
  "BlackList": [],
  "Location": {},
  "LocationVal": 0
}
```

### 点赞朋友圈

**接口**: `POST /sns/SendSnsObjectOp`

**请求体**:
```json
{
  "SnsObjectOpList": [{
    "ToUserName": "好友微信ID",
    "ItemID": "朋友圈ID",
    "OpType": 1
  }]
}
```

## 红包相关API

### 发送红包

**接口**: `POST /pay/SendRedPacket`

**请求体**:
```json
{
  "Username": "接收者",
  "Amount": 100,
  "Count": 1,
  "Content": "恭喜发财",
  "RedType": 0,
  "From": 1
}
```

### 打开红包

**接口**: `POST /pay/OpenRedEnvelopes`

**请求体**:
```json
{
  "NativeUrl": "红包原生URL"
}
```

## 错误处理

### 标准错误响应

```json
{
  "Success": false,
  "Error": "错误描述",
  "ErrorCode": 错误码
}
```

### 常见错误码

| 错误码 | 说明 |
|--------|------|
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 接口不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

## 注意事项

1. **频率限制**: 建议消息发送间隔不少于1秒
2. **超时设置**: API调用建议设置10秒超时
3. **重试机制**: 失败时可重试，建议最多3次
4. **日志记录**: 建议记录所有API调用日志便于调试
5. **错误处理**: 必须处理所有可能的错误情况

## 示例代码

### Python示例

```python
import aiohttp
import asyncio

async def call_8059_api(endpoint, data=None, key="your_key"):
    url = f"http://127.0.0.1:8059{endpoint}"
    params = {"key": key}
    
    async with aiohttp.ClientSession() as session:
        if data:
            async with session.post(url, params=params, json=data) as response:
                return await response.json()
        else:
            async with session.get(url, params=params) as response:
                return await response.json()

# 发送文本消息
async def send_text_message(to_user, content, key):
    data = {
        "MsgItem": [{
            "ToUserName": to_user,
            "MsgType": 1,
            "TextContent": content,
            "AtWxIDList": []
        }]
    }
    return await call_8059_api("/message/SendMessage", data, key)
```
