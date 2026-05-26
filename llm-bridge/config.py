"""LLM Bridge 配置

DeepSeek API 参数管理。
"""

from dataclasses import dataclass, field
import os


@dataclass
class LLMBridgeConfig:
    """DeepSeek API 通信配置"""
    base_url: str = "https://api.deepseek.com"
    api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    model: str = "deepseek-v4-flash"
    max_tokens: int = 8192
    stream_timeout: int = 120       # 流式超时（秒）
    reasoning_effort: str = "high"  # "high" | "max"
