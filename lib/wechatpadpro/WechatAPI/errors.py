class MarshallingError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UnmarshallingError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MMTLSError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PacketError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class ParsePacketError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class DatabaseError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class LoginError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UserLoggedOut(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BanProtection(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# 8059协议专用异常类
class APIError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AuthenticationError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PermissionError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class NotFoundError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class RateLimitError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MessageError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class FriendError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class ChatroomError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UserError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class ToolError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PaymentError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SnsError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
