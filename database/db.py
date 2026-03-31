"""
数据库操作
"""
import sqlite3
import logging
from typing import List, Optional
from datetime import datetime, date
from contextlib import contextmanager

from .models import Todo, ReminderConfig

logger = logging.getLogger(__name__)


class Database:
    """数据库操作类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 创建todos表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    content TEXT NOT NULL,
                    deadline DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reminded_daily BOOLEAN DEFAULT 0,
                    completed BOOLEAN DEFAULT 0,
                    completed_at TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_deadline
                ON todos(chat_id, deadline)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_deadline_reminded
                ON todos(deadline, reminded_daily)
            """)

            # 创建reminder_config表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminder_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT UNIQUE NOT NULL,
                    weekly_day INTEGER DEFAULT 1,
                    weekly_hour INTEGER DEFAULT 9,
                    weekly_minute INTEGER DEFAULT 0,
                    daily_hour INTEGER DEFAULT 9,
                    daily_minute INTEGER DEFAULT 0,
                    enabled BOOLEAN DEFAULT 1
                )
            """)

            logger.info("Database initialized successfully")

    # ==================== Todo操作 ====================

    def add_todo(self, todo: Todo) -> int:
        """添加待办事项"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO todos (chat_id, user_id, user_name, content, deadline)
                VALUES (?, ?, ?, ?, ?)
            """, (todo.chat_id, todo.user_id, todo.user_name, todo.content, todo.deadline))

            todo_id = cursor.lastrowid
            logger.info(f"Added todo {todo_id}: {todo.content}")
            return todo_id

    def get_todo_by_id(self, todo_id: int) -> Optional[Todo]:
        """根据ID获取待办"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM todos WHERE id = ?", (todo_id,))
            row = cursor.fetchone()

            if row:
                return Todo.from_dict(dict(row))
            return None

    def get_todos_by_chat(self, chat_id: str, include_completed: bool = False) -> List[Todo]:
        """获取群组的待办列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if include_completed:
                cursor.execute("""
                    SELECT * FROM todos
                    WHERE chat_id = ?
                    ORDER BY deadline ASC, created_at ASC
                """, (chat_id,))
            else:
                cursor.execute("""
                    SELECT * FROM todos
                    WHERE chat_id = ? AND completed = 0
                    ORDER BY deadline ASC, created_at ASC
                """, (chat_id,))

            rows = cursor.fetchall()
            return [Todo.from_dict(dict(row)) for row in rows]

    def get_todos_by_deadline(self, deadline: date, reminded: bool = False) -> List[Todo]:
        """获取指定日期到期的待办"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM todos
                WHERE deadline = ? AND completed = 0 AND reminded_daily = ?
                ORDER BY chat_id, created_at ASC
            """, (deadline.strftime('%Y-%m-%d'), 1 if reminded else 0))

            rows = cursor.fetchall()
            return [Todo.from_dict(dict(row)) for row in rows]

    def complete_todo(self, todo_id: int) -> bool:
        """标记待办为完成"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE todos
                SET completed = 1, completed_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), todo_id))

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Completed todo {todo_id}")
            return success

    def delete_todo(self, todo_id: int) -> bool:
        """删除待办"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted todo {todo_id}")
            return success

    def mark_reminded(self, todo_id: int) -> bool:
        """标记待办已提醒"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE todos
                SET reminded_daily = 1
                WHERE id = ?
            """, (todo_id,))

            return cursor.rowcount > 0

    # ==================== ReminderConfig操作 ====================

    def get_reminder_config(self, chat_id: str) -> ReminderConfig:
        """获取群组的提醒配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminder_config WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()

            if row:
                return ReminderConfig.from_dict(dict(row))
            else:
                # 返回默认配置
                return ReminderConfig(chat_id=chat_id)

    def save_reminder_config(self, config: ReminderConfig) -> bool:
        """保存提醒配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO reminder_config
                (chat_id, weekly_day, weekly_hour, weekly_minute,
                 daily_hour, daily_minute, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (config.chat_id, config.weekly_day, config.weekly_hour,
                  config.weekly_minute, config.daily_hour, config.daily_minute,
                  config.enabled))

            logger.info(f"Saved reminder config for chat {config.chat_id}")
            return True

    def get_all_enabled_chats(self) -> List[str]:
        """获取所有启用提醒的群组"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT chat_id FROM reminder_config WHERE enabled = 1
            """)

            rows = cursor.fetchall()
            return [row['chat_id'] for row in rows]

    def get_all_active_chats(self) -> List[str]:
        """获取所有有待办的群组（包括未设置配置的）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT chat_id FROM todos WHERE completed = 0
            """)

            rows = cursor.fetchall()
            return [row['chat_id'] for row in rows]
