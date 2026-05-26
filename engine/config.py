"""
Conversation Engine · 配置
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EngineConfig:
    """Conversation Engine 配置。"""

    # 数据库路径
    db_path: str = field(default_factory=lambda: os.environ.get(
        "ENGINE_DB_PATH",
        str(Path.home() / ".convey" / "engine" / "convey_engine.db"),
    ))

    # 系统提示（可选）
    system_prompt: str = "你是一个技术助手。"

    # Session 过期天数 (0 = 不过期)
    session_expire_days: int = 30

    # 消息历史最大加载条数
    max_history_messages: int = 200

    # Portal 公网 URL（用于附件链接等需要绝对路径的场景）
    portal_url: str = field(default_factory=lambda: os.environ.get(
        "CONVEY_PUBLIC_URL", "http://localhost:3000"
    ))
