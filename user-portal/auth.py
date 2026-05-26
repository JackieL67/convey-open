"""
Convey · Token 认证工具

最小 HMAC-SHA256 签名 token，用于 Portal 用户鉴权。

Token 格式: base64(email|expires_at).signature
签名: HMAC-SHA256(secret, f"{email}|{expires_at}")

设计原则:
  - 零外部依赖（仅 stdlib）
  - 24h 有效期
  - 不可伪造（需要 server secret）
  - 可提取 email（不需要 DB 查询）
"""

import hmac
import hashlib
import base64
import time
import os
from pathlib import Path
from typing import Optional

# Token 有效期（秒）
TOKEN_TTL = 24 * 60 * 60  # 24 hours

# Server secret — 优先读环境变量，其次读持久化文件，最后自动生成
_secret = os.environ.get("CONVEY_TOKEN_SECRET", "")
_SECRET_FILE = Path(__file__).parent / "data" / ".token_secret"


def _get_secret() -> bytes:
    """获取签名密钥（持久化，重启不变）。"""
    global _secret
    if not _secret:
        # 尝试从文件读取
        if _SECRET_FILE.exists():
            _secret = _SECRET_FILE.read_text().strip()
        if not _secret:
            # 生成新密钥并持久化
            _secret = base64.b64encode(os.urandom(32)).decode()
            _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SECRET_FILE.write_text(_secret)
    return _secret.encode()


def generate_token(email: str) -> str:
    """
    生成认证 token。

    Args:
        email: 用户邮箱

    Returns:
        token 字符串
    """
    expires_at = int(time.time()) + TOKEN_TTL
    payload = f"{email}|{expires_at}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    signature = hmac.new(
        _get_secret(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()[:32]

    return f"{payload_b64}.{signature}"


def validate_token(token: str) -> Optional[str]:
    """
    验证 token 并提取 email。

    Args:
        token: token 字符串

    Returns:
        email 字符串，无效则返回 None
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload_b64, signature = parts

        # 验证签名
        expected_sig = hmac.new(
            _get_secret(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()[:32]

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # 解码 payload
        # 补全 base64 padding
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(padded).decode()

        email, expires_str = payload.split("|", 1)
        expires_at = int(expires_str)

        # 检查过期
        if time.time() > expires_at:
            return None

        # 基本邮箱格式校验
        if "@" not in email:
            return None

        return email

    except Exception:
        return None
