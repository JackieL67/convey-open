"""
Convey CRM · 核心逻辑

邀请码池 + 邮箱注册绑定。
"""

import sqlite3
import time
import random
import string
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = Path(__file__).parent / "data" / "crm.db"

# 首次启动生成的邀请码数量
INITIAL_CODE_COUNT = 10

# 邀请码长度
CODE_LENGTH = 8


class CRM:
    """客户关系管理 — 邀请码 + 邮箱注册。"""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """初始化数据库 + 首次生成邀请码。"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS invitation_codes (
                    code TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'available',
                    used_by_email TEXT,
                    used_at REAL
                );

                CREATE TABLE IF NOT EXISTS registered_emails (
                    email TEXT PRIMARY KEY,
                    registered_at REAL,
                    invitation_code TEXT
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    email TEXT PRIMARY KEY,
                    system_prompt TEXT DEFAULT '你是一个技术助手。',
                    reply_rules TEXT DEFAULT '## 回复规范\\n- 用 Markdown 格式回复\\n- 代码块标注使用的编程语言\\n- 不确定时直接说明，不要编造\\n- 用中文回复',
                    last_context_snapshot TEXT DEFAULT NULL,
                    updated_at REAL
                );
            """)

            # 为已存在的表添加 reply_rules 列（如果不存在）
            try:
                conn.execute("ALTER TABLE user_settings ADD COLUMN reply_rules TEXT DEFAULT '## 回复规范\\n- 用 Markdown 格式回复\\n- 代码块标注使用的编程语言\\n- 不确定时直接说明，不要编造\\n- 用中文回复'")
            except sqlite3.OperationalError:
                # 列已存在，忽略错误
                pass
            
            # 为已存在的表添加 last_context_snapshot 列（如果不存在）
            try:
                conn.execute("ALTER TABLE user_settings ADD COLUMN last_context_snapshot TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                # 列已存在，忽略错误
                pass

            # 如果池子为空，生成初始邀请码
            count = conn.execute(
                "SELECT COUNT(*) FROM invitation_codes"
            ).fetchone()[0]

            if count == 0:
                codes = self._generate_codes(INITIAL_CODE_COUNT)
                conn.executemany(
                    "INSERT INTO invitation_codes (code) VALUES (?)",
                    [(c,) for c in codes],
                )
                logger.info("CRM: 生成 %d 个初始邀请码: %s", len(codes), codes)
                print(f"[CRM] ✅ 生成 {len(codes)} 个初始邀请码: {', '.join(codes)}")

    def _generate_codes(self, count: int) -> list[str]:
        """生成指定数量的随机邀请码。"""
        codes = []
        chars = string.ascii_uppercase + string.digits
        for _ in range(count):
            code = "".join(random.choices(chars, k=CODE_LENGTH))
            codes.append(code)
        return codes

    # ── 公开接口 ──

    def is_registered(self, email: str) -> bool:
        """
        检查邮箱是否已注册。

        Args:
            email: 用户邮箱

        Returns:
            True 如果已注册
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM registered_emails WHERE email = ?",
                (email,),
            ).fetchone()
            return row is not None

    def validate_and_register(self, email: str, code: str) -> tuple[bool, str]:
        """
        验证邀请码并注册邮箱。

        Args:
            email: 用户邮箱
            code: 邀请码

        Returns:
            (success, message) 元组
        """
        if not code or not code.strip():
            return False, "请输入邀请码"

        code = code.strip().upper()

        with self._conn() as conn:
            # 检查邮箱是否已注册
            existing = conn.execute(
                "SELECT 1 FROM registered_emails WHERE email = ?",
                (email,),
            ).fetchone()
            if existing:
                return True, "该邮箱已注册"

            # 检查邀请码
            row = conn.execute(
                "SELECT status, used_by_email FROM invitation_codes WHERE code = ?",
                (code,),
            ).fetchone()

            if not row:
                return False, "邀请码不存在"

            if row["status"] == "used":
                return False, f"邀请码已被使用"

            # 邀请码有效 → 注册
            now = time.time()
            conn.execute(
                "UPDATE invitation_codes SET status='used', used_by_email=?, used_at=? WHERE code=?",
                (email, now, code),
            )
            conn.execute(
                "INSERT OR IGNORE INTO registered_emails (email, registered_at, invitation_code) VALUES (?, ?, ?)",
                (email, now, code),
            )

            remaining = conn.execute(
                "SELECT COUNT(*) FROM invitation_codes WHERE status='available'"
            ).fetchone()[0]

            logger.info("CRM: 邮箱 %s 使用邀请码 %s 注册成功（剩余 %d）", email, code, remaining)
            print(f"[CRM] ✅ {email} 注册成功 (code={code}, 剩余={remaining})")

            return True, "注册成功"

    def get_remaining_count(self) -> int:
        """获取剩余可用邀请码数量。"""
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM invitation_codes WHERE status='available'"
            ).fetchone()[0]

    def get_all_codes(self) -> list[dict]:
        """获取所有邀请码状态（管理用）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT code, status, used_by_email, used_at FROM invitation_codes ORDER BY status, code"
            ).fetchall()
            return [dict(r) for r in rows]

    def add_codes(self, count: int = 10) -> list[str]:
        """新增邀请码到池子。"""
        codes = self._generate_codes(count)
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO invitation_codes (code) VALUES (?)",
                [(c,) for c in codes],
            )
        logger.info("CRM: 新增 %d 个邀请码: %s", len(codes), codes)
        return codes

    def get_system_prompt(self, email: str) -> str:
        """获取用户的 system_prompt，无则返回默认值 '你是一个技术助手。'"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT system_prompt FROM user_settings WHERE email = ?",
                (email,),
            ).fetchone()
            if row:
                return row["system_prompt"]
            # 自动插入默认值
            conn.execute(
                "INSERT OR IGNORE INTO user_settings (email, system_prompt, updated_at) VALUES (?, '你是一个技术助手。', ?)",
                (email, time.time()),
            )
            return '你是一个技术助手。'

    def set_system_prompt(self, email: str, prompt: str) -> None:
        """设置用户的 system_prompt"""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (email, system_prompt, updated_at) VALUES (?, ?, ?)",
                (email, prompt, time.time()),
            )

    def get_reply_rules(self, email: str) -> str:
        """获取用户的回复规范，无则返回默认值"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT reply_rules FROM user_settings WHERE email = ?",
                (email,),
            ).fetchone()
            if row and row["reply_rules"]:
                return row["reply_rules"]
            # 返回默认值
            default = "## 回复规范\n- 用 Markdown 格式回复\n- 代码块标注使用的编程语言\n- 不确定时直接说明，不要编造\n- 用中文回复"
            return default

    def set_reply_rules(self, email: str, rules: str) -> None:
        """设置用户的回复规范"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE user_settings SET reply_rules = ?, updated_at = ? WHERE email = ?",
                (rules, time.time(), email),
            )

    def save_context_snapshot(self, email: str, snapshot: dict) -> None:
        """保存最近一次发给 LLM 的上下文快照"""
        import json
        with self._conn() as conn:
            conn.execute(
                "UPDATE user_settings SET last_context_snapshot = ?, updated_at = ? WHERE email = ?",
                (json.dumps(snapshot, ensure_ascii=False), time.time(), email),
            )

    def get_context_snapshot(self, email: str) -> dict | None:
        """获取最近一次上下文快照"""
        import json
        with self._conn() as conn:
            row = conn.execute(
                "SELECT last_context_snapshot FROM user_settings WHERE email = ?",
                (email,),
            ).fetchone()
            if row and row["last_context_snapshot"]:
                return json.loads(row["last_context_snapshot"])
            return None