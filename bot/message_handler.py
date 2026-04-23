"""
消息处理逻辑
"""
import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date

from .todo_parser import TodoParser, CommandParser, ReminderConfigParser
from .feishu_client import FeishuClient
from database.db import Database
from database.models import Todo, ReminderConfig

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器"""

    def __init__(self, feishu_client: FeishuClient, database: Database):
        self.feishu_client = feishu_client
        self.database = database
        self.todo_parser = TodoParser()
        self.command_parser = CommandParser()
        self.config_parser = ReminderConfigParser()

    def handle_message(self, event_data: Dict[str, Any]) -> bool:
        """
        处理接收到的消息事件

        Args:
            event_data: 事件数据

        Returns:
            是否处理成功
        """
        try:
            # 提取消息信息
            message = event_data.get('message', {})
            sender = event_data.get('sender', {})

            chat_id = message.get('chat_id')
            message_type = message.get('chat_type')
            content = message.get('content')
            message_id = message.get('message_id')

            # 只处理群消息
            if message_type != 'group':
                logger.info(f"Ignoring non-group message: {message_type}")
                return True

            # 解析消息内容（JSON格式）
            try:
                content_obj = json.loads(content)
                text = content_obj.get('text', '')
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse message content: {content}")
                return False

            # 提取发送者信息
            user_id = sender.get('sender_id', {}).get('open_id', '')
            user_name = sender.get('sender_id', {}).get('user_id', user_id)

            logger.info(f"Processing message from {user_name} in chat {chat_id}: {text}")

            # 提取所有 @提及
            mentions = message.get('mentions', [])

            if mentions:
                # 过滤掉机器人自身，只保留真实用户
                bot_open_id = self.feishu_client.bot_open_id
                non_bot_mentions = [
                    m for m in mentions
                    if not bot_open_id or m.get('id', {}).get('open_id', '') != bot_open_id
                ]

                # 清理 @名字 和 @_user_N 占位符，得到纯指令文本
                clean = text
                for m in mentions:
                    clean = clean.replace(f"@{m.get('name', '')}", "").strip()
                clean = re.sub(r'@_user_\d+', '', clean).strip()

                # 判断是否为指令：匹配已知命令关键词（命令完成/删除必须带 ID）
                COMMAND_PATTERNS = [
                    r'查看待办', r'待办列表', r'^查看$', r'^列表$',
                    r'完成\s*\d+', r'删除\s*\d+',
                    r'设置提醒', r'帮助', r'help', r'使用说明',
                    r'生成表格', r'导出表格', r'^表格$',
                ]
                is_command = (not clean) or any(re.search(p, clean) for p in COMMAND_PATTERNS)

                if is_command:
                    # @机器人 + 命令 → 命令处理
                    return self.handle_command(chat_id, user_id, user_name, text, mentions, [])
                else:
                    # @了某人 + 非命令内容 → 待办，@的真实用户作为负责人（已排除机器人）
                    return self.handle_todo_message(chat_id, user_id, user_name, text, non_bot_mentions)

            # 无@：自然语言关键词检测
            if self.todo_parser.is_todo_message(text, has_non_bot_mentions=False):
                return self.handle_todo_message(chat_id, user_id, user_name, text, [])

            return True

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return False

    def handle_todo_message(self, chat_id: str, user_id: str,
                            user_name: str, text: str,
                            non_bot_mentions: list = None) -> bool:
        """
        处理待办消息（支持自然语言）

        Args:
            chat_id: 群组ID
            user_id: 用户ID
            user_name: 用户名
            text: 消息文本
            non_bot_mentions: @的非机器人用户列表

        Returns:
            是否处理成功
        """
        try:
            # 解析待办
            result = self.todo_parser.parse_todo(text)
            if not result:
                logger.warning(f"Failed to parse todo from: {text}")
                return False

            content, deadline = result

            # 提取负责人（消息中@的所有非机器人用户）
            assignee_ids = []
            assignee_names = []
            if non_bot_mentions:
                for m in non_bot_mentions:
                    aid = m.get('id', {}).get('open_id', '') or m.get('open_id', '')
                    aname = m.get('name', '')
                    if aid:
                        assignee_ids.append(aid)
                        assignee_names.append(aname)

            assignee_id = ','.join(assignee_ids) if assignee_ids else None
            assignee_name = ','.join(assignee_names) if assignee_names else None

            # 创建待办对象
            todo = Todo(
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                content=content,
                deadline=deadline,
                assignee_id=assignee_id,
                assignee_name=assignee_name
            )

            # 保存到数据库
            todo_id = self.database.add_todo(todo)
            todo.id = todo_id

            # 追加到表格末尾（不覆盖已有数据）
            self._append_todo_to_spreadsheet(chat_id, todo_id, todo)

            # 构建确认消息
            deadline_str = f"\n截止时间: {deadline}" if deadline else "\n截止时间: 未设置"
            assignee_str = f"\n负责人: {assignee_name}" if assignee_name else ""
            reply = (
                f"✅ 待办已添加\n\n"
                f"任务ID: {todo_id}\n"
                f"内容: {content}"
                f"{deadline_str}"
                f"\n创建者: {user_name}"
                f"{assignee_str}"
            )
            self.feishu_client.send_text_message(chat_id, reply)

            return True

        except Exception as e:
            logger.error(f"Error handling todo message: {e}", exc_info=True)
            return False

    def handle_command(self, chat_id: str, user_id: str, user_name: str,
                       text: str, mentions: list, non_bot_mentions: list = None) -> bool:
        """
        处理命令消息

        Args:
            chat_id: 群组ID
            user_id: 用户ID
            user_name: 用户名
            text: 消息文本
            mentions: @提及列表（含机器人）
            non_bot_mentions: @的非机器人用户列表

        Returns:
            是否处理成功
        """
        try:
            # 清理@标记
            clean_text = text
            for mention in mentions:
                name = mention.get('name', '')
                clean_text = clean_text.replace(f"@{name}", "").strip()

            logger.info(f"Processing command: {clean_text}")

            # 查看待办
            if self.command_parser.is_command(clean_text, ['查看待办', '待办列表', '查看', '列表']):
                return self.handle_list_command(chat_id)

            # 完成待办
            if '完成' in clean_text:
                return self.handle_complete_command(chat_id, user_id, clean_text)

            # 删除待办
            if '删除' in clean_text:
                return self.handle_delete_command(chat_id, user_id, clean_text)

            # 设置提醒
            if '设置提醒' in clean_text:
                return self.handle_set_reminder_command(chat_id, clean_text)

            # 生成表格
            if self.command_parser.is_command(clean_text, ['生成表格', '导出表格', '表格']):
                return self.handle_table_command(chat_id, user_id)

            # 帮助
            if self.command_parser.is_command(clean_text, ['帮助', 'help', '使用说明']):
                return self.handle_help_command(chat_id)

            # 未知命令
            reply = "❓ 未知命令，发送 @机器人 帮助 查看使用说明"
            self.feishu_client.send_text_message(chat_id, reply)
            return True

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            return False

    def handle_list_command(self, chat_id: str) -> bool:
        """处理查看待办命令"""
        try:
            todos = self.database.get_todos_by_chat(chat_id, include_completed=False)

            if not todos:
                reply = "📋 当前没有待办事项"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            today = date.today()

            overdue = []    # 已逾期
            urgent = []     # 今日到期
            this_week = []  # 本周到期（1-7天）
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

            # 构建消息
            lines = [f"📋 待办事项列表（共{len(todos)}项）\n"]

            def _fmt(todo: Todo) -> str:
                assignee = f" 👤{todo.assignee_name}" if todo.assignee_name else ""
                deadline = f" - 截止：{todo.deadline}" if todo.deadline else ""
                return f"• [{todo.id}] 【{todo.user_name}】{todo.content}{assignee}{deadline}"

            if overdue:
                lines.append("🔴 已逾期：")
                for todo in overdue:
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

            reply = "\n".join(lines)
            self.feishu_client.send_text_message(chat_id, reply)
            return True

        except Exception as e:
            logger.error(f"Error handling list command: {e}", exc_info=True)
            return False

    def handle_complete_command(self, chat_id: str, user_id: str, text: str) -> bool:
        """处理完成待办命令"""
        try:
            # 提取任务ID
            match = re.search(r'完成\s+(\d+)', text)
            if not match:
                reply = "❌ 请指定任务ID，格式：@机器人 完成 <任务ID>"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            todo_id = int(match.group(1))

            # 获取待办
            todo = self.database.get_todo_by_id(todo_id)
            if not todo:
                reply = f"❌ 任务 {todo_id} 不存在"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 检查是否属于该群
            if todo.chat_id != chat_id:
                reply = f"❌ 任务 {todo_id} 不在当前群组"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 标记完成
            if self.database.complete_todo(todo_id):
                self._update_todo_status_in_spreadsheet(chat_id, todo_id, "已完成")
                reply = f"✅ 任务 {todo_id} 已完成\n\n{todo.content}"
                self.feishu_client.send_text_message(chat_id, reply)
            else:
                reply = f"❌ 完成任务 {todo_id} 失败"
                self.feishu_client.send_text_message(chat_id, reply)

            return True

        except Exception as e:
            logger.error(f"Error handling complete command: {e}", exc_info=True)
            return False

    def handle_delete_command(self, chat_id: str, user_id: str, text: str) -> bool:
        """处理删除待办命令"""
        try:
            # 提取任务ID
            match = re.search(r'删除\s+(\d+)', text)
            if not match:
                reply = "❌ 请指定任务ID，格式：@机器人 删除 <任务ID>"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            todo_id = int(match.group(1))

            # 获取待办
            todo = self.database.get_todo_by_id(todo_id)
            if not todo:
                reply = f"❌ 任务 {todo_id} 不存在"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 检查是否属于该群
            if todo.chat_id != chat_id:
                reply = f"❌ 任务 {todo_id} 不在当前群组"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 检查权限（只有创建者可以删除）
            if todo.user_id != user_id:
                reply = "❌ 只有创建者可以删除任务"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 删除待办
            if self.database.delete_todo(todo_id):
                self._update_todo_status_in_spreadsheet(chat_id, todo_id, "已删除")
                reply = f"✅ 任务 {todo_id} 已删除"
                self.feishu_client.send_text_message(chat_id, reply)
            else:
                reply = f"❌ 删除任务 {todo_id} 失败"
                self.feishu_client.send_text_message(chat_id, reply)

            return True

        except Exception as e:
            logger.error(f"Error handling delete command: {e}", exc_info=True)
            return False

    def handle_set_reminder_command(self, chat_id: str, text: str) -> bool:
        """处理设置提醒命令"""
        try:
            # 解析配置
            result = self.config_parser.parse_weekly_config(text)
            if not result:
                reply = "❌ 配置格式错误\n\n正确格式：@机器人 设置提醒 周<X> HH:MM\n示例：@机器人 设置提醒 周1 09:00"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            weekday, hour, minute = result

            # 获取当前配置
            config = self.database.get_reminder_config(chat_id)
            config.weekly_day = weekday
            config.weekly_hour = hour
            config.weekly_minute = minute

            # 保存配置
            if self.database.save_reminder_config(config):
                weekday_names = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
                reply = f"✅ 提醒时间已设置\n\n每周提醒：{weekday_names[weekday]} {hour:02d}:{minute:02d}"
                self.feishu_client.send_text_message(chat_id, reply)
            else:
                reply = "❌ 设置提醒失败"
                self.feishu_client.send_text_message(chat_id, reply)

            return True

        except Exception as e:
            logger.error(f"Error handling set reminder command: {e}", exc_info=True)
            return False

    def handle_table_command(self, chat_id: str, user_id: str = None) -> bool:
        """处理生成表格命令"""
        try:
            config = self.database.get_reminder_config(chat_id)

            if config.spreadsheet_url and config.spreadsheet_token:
                # 已有表格：同步最新数据（若 sheet_id 有误会自动清除绑定）
                self._sync_spreadsheet(chat_id)
                # 同步后重新读取，检查绑定是否仍有效
                config = self.database.get_reminder_config(chat_id)

            if config.spreadsheet_url and config.spreadsheet_token and config.spreadsheet_sheet_id:
                reply = (
                    f"📊 待办表格（已同步最新数据）\n\n"
                    f"🔗 {config.spreadsheet_url}\n\n"
                    f"字段：任务ID / 内容 / 负责人 / 创建时间 / 截止时间 / 状态 / 备注"
                )
            else:
                # 没有表格或绑定已被清除：创建新表格
                todos = self.database.get_todos_by_chat(chat_id, include_completed=False)
                result = self.feishu_client.create_todo_spreadsheet(chat_id, todos, user_id=user_id)

                if result:
                    sheet_url, sheet_token, sheet_id = result
                    self.database.save_spreadsheet_info(chat_id, sheet_token, sheet_url, sheet_id)
                    reply = (
                        f"📊 待办表格已生成，可手动修改\n\n"
                        f"🔗 {sheet_url}\n\n"
                        f"字段：任务ID / 内容 / 负责人 / 创建时间 / 截止时间 / 状态 / 备注"
                    )
                else:
                    reply = "❌ 生成表格失败，请检查机器人是否有云文档权限"

            self.feishu_client.send_text_message(chat_id, reply)
            return True

        except Exception as e:
            logger.error(f"Error handling table command: {e}", exc_info=True)
            return False

    def handle_help_command(self, chat_id: str) -> bool:
        """处理帮助命令"""
        try:
            help_text = """📖 待办机器人使用说明

📝 添加待办（自然语言，无需固定格式）：
直接在群内发送包含任务意图的消息即可，例如：
  • 麻烦 @张三 下周五前完成用户调研报告
  • 需要跟进一下客户反馈，3月25日前

@的人自动成为负责人，提到的时间自动为截止日期

🔍 查看待办：
@机器人 查看待办

✅ 完成待办：
@机器人 完成 <任务ID>

❌ 删除待办：
@机器人 删除 <任务ID>（仅创建者可删除）

⏰ 设置提醒时间：
@机器人 设置提醒 周<X> HH:MM
示例：@机器人 设置提醒 周一 09:00

📊 生成飞书表格：
@机器人 生成表格

❓ 查看帮助：
@机器人 帮助

---
机器人会在每周固定时间和任务截止当天自动 @负责人 提醒"""

            self.feishu_client.send_text_message(chat_id, help_text)
            return True

        except Exception as e:
            logger.error(f"Error handling help command: {e}", exc_info=True)
            return False

    def _append_todo_to_spreadsheet(self, chat_id: str, todo_id: int, todo) -> None:
        """追加单条新待办到表格末尾"""
        try:
            config = self.database.get_reminder_config(chat_id)
            if not config.spreadsheet_token or not config.spreadsheet_sheet_id:
                return
            if config.spreadsheet_sheet_id == "Sheet1":
                self.database.save_spreadsheet_info(chat_id, None, None, None)
                return
            self.feishu_client.append_todo_row(
                config.spreadsheet_token, config.spreadsheet_sheet_id, todo, todo_id
            )
        except Exception as e:
            logger.error(f"Error appending todo to spreadsheet: {e}", exc_info=True)

    def _update_todo_status_in_spreadsheet(self, chat_id: str, todo_id: int, status: str) -> None:
        """更新表格中指定任务的状态列"""
        try:
            config = self.database.get_reminder_config(chat_id)
            if not config.spreadsheet_token or not config.spreadsheet_sheet_id:
                return
            if config.spreadsheet_sheet_id == "Sheet1":
                self.database.save_spreadsheet_info(chat_id, None, None, None)
                return
            self.feishu_client.update_todo_status_row(
                config.spreadsheet_token, config.spreadsheet_sheet_id, todo_id, status
            )
        except Exception as e:
            logger.error(f"Error updating todo status in spreadsheet: {e}", exc_info=True)

    def _sync_spreadsheet(self, chat_id: str):
        """
        将当前群组的待办数据同步到飞书表格（如有关联表格则更新，否则静默跳过）
        """
        try:
            config = self.database.get_reminder_config(chat_id)
            if not config.spreadsheet_token or not config.spreadsheet_sheet_id:
                return  # 尚未关联表格，跳过同步

            # 检测历史遗留的错误 sheet_id，自动清除绑定等待重新生成
            if config.spreadsheet_sheet_id == "Sheet1":
                logger.warning(f"Invalid sheet_id 'Sheet1' detected for chat {chat_id}, clearing binding")
                self.database.save_spreadsheet_info(chat_id, None, None, None)
                return

            todos = self.database.get_todos_by_chat(chat_id, include_completed=False)
            self.feishu_client.update_todo_spreadsheet(
                config.spreadsheet_token,
                config.spreadsheet_sheet_id,
                todos
            )
        except Exception as e:
            logger.error(f"Error syncing spreadsheet for chat {chat_id}: {e}", exc_info=True)
