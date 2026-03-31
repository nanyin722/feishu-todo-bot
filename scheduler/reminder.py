"""
提醒任务调度逻辑
"""
import logging
from datetime import datetime, date
from typing import List

from bot.feishu_client import FeishuClient
from database.db import Database
from database.models import Todo

logger = logging.getLogger(__name__)


class ReminderService:
    """提醒服务"""

    def __init__(self, feishu_client: FeishuClient, database: Database):
        self.feishu_client = feishu_client
        self.database = database

    def send_weekly_reminder(self):
        """发送每周统一提醒"""
        try:
            logger.info("Starting weekly reminder task")

            # 获取所有有待办的群组
            chat_ids = self.database.get_all_active_chats()

            for chat_id in chat_ids:
                self._send_weekly_reminder_for_chat(chat_id)

            logger.info(f"Weekly reminder completed for {len(chat_ids)} chats")

        except Exception as e:
            logger.error(f"Error in weekly reminder task: {e}", exc_info=True)

    def _send_weekly_reminder_for_chat(self, chat_id: str):
        """为单个群组发送每周提醒"""
        try:
            # 获取未完成的待办
            todos = self.database.get_todos_by_chat(chat_id, include_completed=False)

            if not todos:
                logger.info(f"No todos for chat {chat_id}, skipping reminder")
                return

            # 按日期分类
            today = date.today()
            urgent = []  # 今天到期或已逾期
            this_week = []  # 本周到期
            later = []  # 后续

            for todo in todos:
                deadline_date = datetime.strptime(todo.deadline, '%Y-%m-%d').date()
                days_diff = (deadline_date - today).days

                if days_diff <= 0:
                    urgent.append(todo)
                elif days_diff <= 7:
                    this_week.append(todo)
                else:
                    later.append(todo)

            # 构建提醒消息
            message = self._build_weekly_reminder_message(
                len(todos), urgent, this_week, later
            )

            # 发送消息（@所有人）
            self.feishu_client.send_text_message(chat_id, message, at_all=True)
            logger.info(f"Sent weekly reminder to chat {chat_id}")

        except Exception as e:
            logger.error(f"Error sending weekly reminder to chat {chat_id}: {e}", exc_info=True)

    def _build_weekly_reminder_message(self, total: int,
                                      urgent: List[Todo],
                                      this_week: List[Todo],
                                      later: List[Todo]) -> str:
        """构建每周提醒消息"""
        lines = [f"📋 本周待办提醒\n", f"本周有 {total} 个待办事项：\n"]

        if urgent:
            lines.append("🔴 紧急（今天到期或已逾期）：")
            for todo in urgent:
                lines.append(f"• [{todo.id}] 【{todo.user_name}】{todo.content} - 截止：{todo.deadline}")
            lines.append("")

        if this_week:
            lines.append("🟡 本周到期：")
            for todo in this_week:
                lines.append(f"• [{todo.id}] 【{todo.user_name}】{todo.content} - 截止：{todo.deadline}")
            lines.append("")

        if later:
            lines.append("⚪ 后续待办：")
            for todo in later:
                lines.append(f"• [{todo.id}] 【{todo.user_name}】{todo.content} - 截止：{todo.deadline}")
            lines.append("")

        lines.append("请大家按时完成！回复 @机器人 完成 <任务ID> 可标记完成")

        return "\n".join(lines)

    def send_daily_deadline_reminder(self):
        """发送截止日提醒"""
        try:
            logger.info("Starting daily deadline reminder task")

            today = date.today()

            # 获取今天到期且未提醒的待办
            todos = self.database.get_todos_by_deadline(today, reminded=False)

            if not todos:
                logger.info("No todos due today, skipping deadline reminder")
                return

            # 按群组分组
            todos_by_chat = {}
            for todo in todos:
                if todo.chat_id not in todos_by_chat:
                    todos_by_chat[todo.chat_id] = []
                todos_by_chat[todo.chat_id].append(todo)

            # 为每个群组发送提醒
            for chat_id, chat_todos in todos_by_chat.items():
                self._send_deadline_reminder_for_chat(chat_id, chat_todos)

            logger.info(f"Daily deadline reminder completed for {len(todos_by_chat)} chats")

        except Exception as e:
            logger.error(f"Error in daily deadline reminder task: {e}", exc_info=True)

    def _send_deadline_reminder_for_chat(self, chat_id: str, todos: List[Todo]):
        """为单个群组发送截止日提醒"""
        try:
            # 构建提醒消息
            lines = [
                "⏰ 待办截止提醒\n",
                "以下待办今天到期：\n"
            ]

            for todo in todos:
                lines.append(f"• [{todo.id}] 【{todo.user_name}】{todo.content}")

            lines.append("\n请尽快完成！回复 @机器人 完成 <任务ID> 可标记完成")

            message = "\n".join(lines)

            # 发送消息（@所有人）
            self.feishu_client.send_text_message(chat_id, message, at_all=True)

            # 标记为已提醒
            for todo in todos:
                self.database.mark_reminded(todo.id)

            logger.info(f"Sent deadline reminder to chat {chat_id} for {len(todos)} todos")

        except Exception as e:
            logger.error(f"Error sending deadline reminder to chat {chat_id}: {e}", exc_info=True)

    def check_overdue_todos(self):
        """检查逾期待办（可选功能）"""
        try:
            logger.info("Checking for overdue todos")

            # 这里可以添加逾期待办的特殊处理逻辑
            # 例如：每天检查一次，发送逾期提醒等

            # 当前版本暂不实现，预留接口

        except Exception as e:
            logger.error(f"Error checking overdue todos: {e}", exc_info=True)
