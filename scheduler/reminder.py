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

    def _get_completed_from_spreadsheet(self, chat_id: str) -> set:
        """从表格读取已手动标记为'已完成'的任务ID集合"""
        try:
            import requests

            config = self.database.get_reminder_config(chat_id)
            if not config.spreadsheet_token or not config.spreadsheet_sheet_id:
                return set()

            token = self.feishu_client._get_tenant_access_token()
            if not token:
                return set()

            headers = {"Authorization": f"Bearer {token}"}
            read_range = f"{config.spreadsheet_sheet_id}!A2:F2000"
            resp = requests.get(
                f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                f"/{config.spreadsheet_token}/values/{read_range}",
                headers=headers
            )
            data = resp.json()
            completed_ids = set()
            if data.get("code") == 0:
                rows = data.get("data", {}).get("valueRange", {}).get("values", []) or []
                for row in rows:
                    if row and len(row) >= 6 and row[0]:
                        try:
                            task_id = int(str(row[0]))
                            status = str(row[5]) if row[5] else ""
                            if "已完成" in status:
                                completed_ids.add(task_id)
                        except (ValueError, TypeError):
                            pass
            return completed_ids
        except Exception as e:
            logger.warning(f"Failed to read spreadsheet status for chat {chat_id}: {e}")
            return set()

    def send_weekly_reminder(self):
        """
        发送每周统一提醒。
        每小时触发一次，根据各群组配置的 weekly_day/weekly_hour/weekly_minute
        判断当前是否匹配，匹配则发送（每次触发时检查当前小时内是否应发送）。
        """
        try:
            logger.info("Starting weekly reminder check")

            now = datetime.now()
            current_weekday = now.isoweekday()  # 1=周一 ... 7=周日
            current_hour = now.hour
            current_minute = now.minute

            chat_ids = self.database.get_all_active_chats()

            sent_count = 0
            for chat_id in chat_ids:
                config = self.database.get_reminder_config(chat_id)
                # 判断当前时间是否匹配该群配置（分钟误差在0-59分钟内均视为本小时应发送）
                if (config.weekly_day == current_weekday
                        and config.weekly_hour == current_hour):
                    self._send_weekly_reminder_for_chat(chat_id)
                    sent_count += 1

            logger.info(f"Weekly reminder check completed, sent to {sent_count} chats")

        except Exception as e:
            logger.error(f"Error in weekly reminder task: {e}", exc_info=True)

    def _send_weekly_reminder_for_chat(self, chat_id: str):
        """为单个群组发送每周提醒"""
        try:
            # 获取未完成的待办
            todos = self.database.get_todos_by_chat(chat_id, include_completed=False)

            # 排除表格中已手动标记为已完成的任务
            completed_in_sheet = self._get_completed_from_spreadsheet(chat_id)
            if completed_in_sheet:
                todos = [t for t in todos if t.id not in completed_in_sheet]

            if not todos:
                logger.info(f"No todos for chat {chat_id}, skipping reminder")
                return

            # 按日期分类
            today = date.today()
            overdue = []    # 已逾期
            urgent = []     # 今日到期
            this_week = []  # 本周到期
            later = []      # 后续

            for todo in todos:
                if not todo.deadline:
                    later.append(todo)
                    continue
                deadline_date = datetime.strptime(todo.deadline[:10], '%Y-%m-%d').date()
                days_diff = (deadline_date - today).days

                if days_diff < 0:
                    overdue.append(todo)
                elif days_diff == 0:
                    urgent.append(todo)
                elif days_diff <= 7:
                    this_week.append(todo)
                else:
                    later.append(todo)

            # 收集所有需要@的负责人（支持逗号分隔的多负责人）
            seen_ids = set()
            at_ids = []
            for todo in todos:
                if todo.assignee_id:
                    for aid in todo.assignee_id.split(','):
                        aid = aid.strip()
                        if aid and aid not in seen_ids:
                            seen_ids.add(aid)
                            at_ids.append(aid)

            # 构建提醒消息
            message = self._build_weekly_reminder_message(
                len(todos), overdue, urgent, this_week, later
            )

            # 发送消息：有负责人则@负责人，否则@所有人
            if at_ids:
                self.feishu_client.send_text_message_with_at_users(chat_id, message, at_ids)
            else:
                self.feishu_client.send_text_message(chat_id, message, at_all=True)

            logger.info(f"Sent weekly reminder to chat {chat_id}")

        except Exception as e:
            logger.error(f"Error sending weekly reminder to chat {chat_id}: {e}", exc_info=True)

    def _build_weekly_reminder_message(self, total: int,
                                       overdue: List[Todo],
                                       urgent: List[Todo],
                                       this_week: List[Todo],
                                       later: List[Todo]) -> str:
        """构建每周提醒消息"""
        lines = [f"📋 本周待办提醒\n", f"本周有 {total} 个待办事项：\n"]

        def _fmt(todo: Todo) -> str:
            assignee = f" 👤{todo.assignee_name}" if todo.assignee_name else ""
            deadline = f" - 截止：{todo.deadline}" if todo.deadline else ""
            return f"• [{todo.id}] 【{todo.user_name}】{todo.content}{assignee}{deadline}"

        if overdue:
            lines.append("🔴 已逾期：")
            for todo in overdue:
                today = date.today()
                days_ago = (today - datetime.strptime(todo.deadline[:10], '%Y-%m-%d').date()).days
                lines.append(f"{_fmt(todo)} (逾期{days_ago}天)")
            lines.append("")

        if urgent:
            lines.append("🟠 今日到期：")
            for todo in urgent:
                lines.append(_fmt(todo))
            lines.append("")

        if this_week:
            lines.append("🟡 本周到期：")
            for todo in this_week:
                lines.append(_fmt(todo))
            lines.append("")

        if later:
            lines.append("⚪ 后续待办：")
            for todo in later:
                lines.append(_fmt(todo))
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
                # 排除表格中已手动标记为已完成的任务
                completed_in_sheet = self._get_completed_from_spreadsheet(chat_id)
                if completed_in_sheet:
                    chat_todos = [t for t in chat_todos if t.id not in completed_in_sheet]
                if chat_todos:
                    self._send_deadline_reminder_for_chat(chat_id, chat_todos)

            logger.info(f"Daily deadline reminder completed for {len(todos_by_chat)} chats")

        except Exception as e:
            logger.error(f"Error in daily deadline reminder task: {e}", exc_info=True)

    def _send_deadline_reminder_for_chat(self, chat_id: str, todos: List[Todo]):
        """为单个群组发送截止日提醒，@对应负责人"""
        try:
            lines = [
                "⏰ 待办截止提醒\n",
                "以下待办今天到期：\n"
            ]

            for todo in todos:
                assignee = f" 👤{todo.assignee_name}" if todo.assignee_name else ""
                lines.append(f"• [{todo.id}] 【{todo.user_name}】{todo.content}{assignee}")

            lines.append("\n请尽快完成！回复 @机器人 完成 <任务ID> 可标记完成")

            message = "\n".join(lines)

            # 收集该群到期任务的负责人（支持逗号分隔的多负责人）
            seen_ids = set()
            at_ids = []
            for todo in todos:
                if todo.assignee_id:
                    for aid in todo.assignee_id.split(','):
                        aid = aid.strip()
                        if aid and aid not in seen_ids:
                            seen_ids.add(aid)
                            at_ids.append(aid)

            # @负责人，无负责人则@所有人
            if at_ids:
                self.feishu_client.send_text_message_with_at_users(chat_id, message, at_ids)
            else:
                self.feishu_client.send_text_message(chat_id, message, at_all=True)

            # 标记为已提醒
            for todo in todos:
                self.database.mark_reminded(todo.id)

            logger.info(f"Sent deadline reminder to chat {chat_id} for {len(todos)} todos")

        except Exception as e:
            logger.error(f"Error sending deadline reminder to chat {chat_id}: {e}", exc_info=True)

    def check_overdue_todos(self):
        """检查并推送逾期待办提醒"""
        try:
            logger.info("Checking for overdue todos")

            today = date.today()
            chat_ids = self.database.get_all_active_chats()

            for chat_id in chat_ids:
                todos = self.database.get_todos_by_chat(chat_id, include_completed=False)
                overdue = [
                    t for t in todos
                    if t.deadline and
                    datetime.strptime(t.deadline[:10], '%Y-%m-%d').date() < today
                ]

                if not overdue:
                    continue

                # 排除表格中已手动标记为已完成的任务
                completed_in_sheet = self._get_completed_from_spreadsheet(chat_id)
                if completed_in_sheet:
                    overdue = [t for t in overdue if t.id not in completed_in_sheet]

                if not overdue:
                    continue

                lines = ["⚠️ 逾期待办提醒\n以下任务已超过截止日期：\n"]
                for todo in overdue:
                    days_ago = (today - datetime.strptime(todo.deadline[:10], '%Y-%m-%d').date()).days
                    assignee = f" 👤{todo.assignee_name}" if todo.assignee_name else ""
                    lines.append(
                        f"• [{todo.id}] 【{todo.user_name}】{todo.content}{assignee}"
                        f" - 截止：{todo.deadline}（逾期{days_ago}天）"
                    )

                lines.append("\n请尽快处理！回复 @机器人 完成 <任务ID> 可标记完成")
                message = "\n".join(lines)

                seen_ids = set()
                at_ids = []
                for t in overdue:
                    if t.assignee_id:
                        for aid in t.assignee_id.split(','):
                            aid = aid.strip()
                            if aid and aid not in seen_ids:
                                seen_ids.add(aid)
                                at_ids.append(aid)
                if at_ids:
                    self.feishu_client.send_text_message_with_at_users(chat_id, message, at_ids)
                else:
                    self.feishu_client.send_text_message(chat_id, message, at_all=True)

                logger.info(f"Sent overdue reminder to chat {chat_id} for {len(overdue)} todos")

        except Exception as e:
            logger.error(f"Error checking overdue todos: {e}", exc_info=True)
