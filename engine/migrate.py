"""
Conversation Engine · 数据迁移脚本

从 User Portal 的 JSON 文件迁移到 Engine SQLite。

迁移内容:
  - users.json → users + devices 表
  - conversations/{email}/{session_id}.json → sessions + messages 表
"""

import json
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def migrate_portal_data(
    portal_data_dir: str,
    engine_db_path: str,
    dry_run: bool = False,
) -> dict:
    """
    从 Portal JSON 文件迁移数据到 Engine SQLite。

    Args:
        portal_data_dir: Portal data 目录路径 (含 users.json 和 conversations/)
        engine_db_path: Engine DB 路径
        dry_run: 仅统计，不写入

    Returns:
        {
            "users_migrated": int,
            "sessions_migrated": int,
            "messages_migrated": int,
            "errors": list[str],
        }
    """
    from engine.db import EngineDB

    data_dir = Path(portal_data_dir)
    users_file = data_dir / "users.json"
    conv_dir = data_dir / "conversations"

    stats = {
        "users_migrated": 0,
        "sessions_migrated": 0,
        "messages_migrated": 0,
        "errors": [],
    }

    if not users_file.exists():
        stats["errors"].append(f"users.json not found at {users_file}")
        return stats

    # 读取 users.json
    users_data = json.loads(users_file.read_text())
    logger.info("Found %d users in Portal", len(users_data))

    if dry_run:
        # Dry run: 只统计
        for email, user_info in users_data.items():
            stats["users_migrated"] += 1
            session_ids = user_info.get("session_ids", [])
            stats["sessions_migrated"] += len(session_ids)
            for sid in session_ids:
                conv_file = conv_dir / _email_to_dirname(email) / f"{sid}.json"
                if conv_file.exists():
                    messages = json.loads(conv_file.read_text())
                    stats["messages_migrated"] += len(messages)
        return stats

    # 实际迁移
    db = EngineDB(engine_db_path)

    for email, user_info in users_data.items():
        try:
            _migrate_user(db, email, user_info, conv_dir, stats)
            stats["users_migrated"] += 1
        except Exception as e:
            error_msg = f"Error migrating user {email}: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)

    return stats


def _migrate_user(
    db,
    email: str,
    user_info: dict,
    conv_dir: Path,
    stats: dict,
):
    """迁移单个用户。"""
    now = time.time()
    created_at = user_info.get("created_at", now)
    last_active = user_info.get("last_active", now)
    display_name = user_info.get("display_name", "")

    # 插入用户
    with db._conn() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (email, display_name, created_at, last_active) VALUES (?, ?, ?, ?)",
                (email, display_name, created_at, last_active),
            )

        # 迁移设备
        device_ids = user_info.get("device_ids", [])
        for did in device_ids:
            dev = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (did,)
            ).fetchone()
            if not dev:
                conn.execute(
                    "INSERT INTO devices (device_id, email, first_seen, last_seen) VALUES (?, ?, ?, ?)",
                    (did, email, created_at, now),
                )

        # 迁移 sessions
        session_ids = user_info.get("session_ids", [])
        current_session_id = user_info.get("current_session_id", "")

        for sid in session_ids:
            sess = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (sid,)
            ).fetchone()
            if not sess:
                # 读取消息以确定时间
                conv_file = conv_dir / _email_to_dirname(email) / f"{sid}.json"
                messages = []
                if conv_file.exists():
                    messages = json.loads(conv_file.read_text())

                msg_last_active = messages[-1]["timestamp"] if messages else created_at

                conn.execute(
                    "INSERT INTO sessions (session_id, email, title, created_at, last_active, bridge_node) VALUES (?, ?, ?, ?, ?, ?)",
                    (sid, email, "", created_at, msg_last_active, "local"),
                )
                stats["sessions_migrated"] += 1

                # 迁移消息
                for msg in messages:
                    conn.execute(
                        "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            sid,
                            msg.get("role", "user"),
                            msg.get("content", ""),
                            json.dumps({}),
                            msg.get("timestamp", created_at),
                        ),
                    )
                    stats["messages_migrated"] += 1


def _email_to_dirname(email: str) -> str:
    """将邮箱转换为 Portal 使用的目录名格式。"""
    return email.replace("@", "_at_").replace(".", "_")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    portal_data = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user-portal", "data")
    engine_db = os.path.join(os.path.expanduser("~"), ".convey", "engine", "convey_engine.db")

    if "--dry-run" in sys.argv:
        print("=== DRY RUN ===")
        result = migrate_portal_data(portal_data, engine_db, dry_run=True)
    else:
        result = migrate_portal_data(portal_data, engine_db, dry_run=False)

    print(f"Users migrated: {result['users_migrated']}")
    print(f"Sessions migrated: {result['sessions_migrated']}")
    print(f"Messages migrated: {result['messages_migrated']}")
    if result["errors"]:
        print(f"Errors: {result['errors']}")
