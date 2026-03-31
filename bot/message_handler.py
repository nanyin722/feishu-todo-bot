"""
消息处理逻辑
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

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
            import json
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

            # 检查是否为待办消息
            if self.todo_parser.is_todo_message(text):
                return self.handle_todo_message(chat_id, user_id, user_name, text)

            # 检查是否为命令消息（@机器人）
            mentions = message.get('mentions', [])
            if mentions:
                # 如果@了机器人，处理为命令
                return self.handle_command(chat_id, user_id, user_name, text, mentions)

            return True

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return False

    def handle_todo_message(self, chat_id: str, user_id: str,
                           user_name: str, text: str) -> bool:
        """
        处理待办消息

        Args:
            chat_id: 群组ID
            user_id: 用户ID
            user_name: 用户名
            text: 消息文本

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

            # 创建待办对象
            todo = Todo(
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                content=content,
                deadline=deadline
            )

            # 保存到数据库
            todo_id = self.database.add_todo(todo)

            # 发送确认消息
            reply = f"✅ 待办已添加\n\n任务ID: {todo_id}\n内容: {content}\n截止日期: {deadline}\n创建者: {user_name}"
            self.feishu_client.send_text_message(chat_id, reply)

            return True

        except Exception as e:
            logger.error(f"Error handling todo message: {e}", exc_info=True)
            return False

    def handle_command(self, chat_id: str, user_id: str, user_name: str,
                      text: str, mentions: list) -> bool:
        """
        处理命令消息

        Args:
            chat_id: 群组ID
            user_id: 用户ID
            user_name: 用户名
            text: 消息文本
            mentions: @提及列表

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

            # 按日期分组
            from datetime import datetime, date
            today = date.today()

            urgent = []  # 今天到期
            this_week = []  # 本周到期
            later = []  # 后续

            for todo in todos:
                deadline_date = datetime.strptime(todo.deadline, '%Y-%m-%d').date()
                days_diff = (deadline_date - today).days

                if days_diff < 0:
                    urgent.append(todo)  # 已逾期
                elif days_diff == 0:
                    urgent.append(todo)  # 今天到期
                elif days_diff <= 7:
                    this_week.append(todo)
                else:
                    later.append(todo)

            # 构建消息
            lines = [f"📋 待办事项列表（共{len(todos)}项）\n"]

            if urgent:
                lines.append("🔴 紧急/逾期：")
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
            import re
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
            import re
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
                reply = f"❌ 只有创建者可以删除任务"
                self.feishu_client.send_text_message(chat_id, reply)
                return True

            # 删除待办
            if self.database.delete_todo(todo_id):
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

    def handle_help_command(self, chat_id: str) -> bool:
        """处理帮助命令"""
        try:
            help_text = """📖 待办机器人使用说明

📝 添加待办：
待办：任务描述 @YYYY-MM-DD
示例：待办：完成季度报告 @2026-03-25

🔍 查看待办：
@机器人 查看待办

✅ 完成待办：
@机器人 完成 <任务ID>

❌ 删除待办：
@机器人 删除 <任务ID>（仅创建者可删除）

⏰ 设置提醒：
@机器人 设置提醒 周<X> HH:MM
示例：@机器人 设置提醒 周1 09:00

❓ 查看帮助：
@机器人 帮助

---
机器人会在每周固定时间和任务截止当天自动提醒 @所有人"""

            self.feishu_client.send_text_message(chat_id, help_text)
            return True

        except Exception as e:
            logger.error(f"Error handling help command: {e}", exc_info=True)
            return False
