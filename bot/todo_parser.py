"""
待办消息格式解析器
"""
import re
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TodoParser:
    """待办消息解析器"""

    # 待办格式正则表达式：待办：内容 @YYYY-MM-DD
    TODO_PATTERN = r'待办[：:]\s*(.+?)\s*@(\d{4}-\d{2}-\d{2})'

    @staticmethod
    def parse_todo(message: str) -> Optional[Tuple[str, str]]:
        """
        解析待办消息

        Args:
            message: 消息文本

        Returns:
            (内容, 截止日期) 元组，如果解析失败返回None
        """
        match = re.search(TodoParser.TODO_PATTERN, message)

        if not match:
            return None

        content = match.group(1).strip()
        deadline = match.group(2)

        # 验证日期格式
        try:
            datetime.strptime(deadline, '%Y-%m-%d')
        except ValueError:
            logger.warning(f"Invalid date format: {deadline}")
            return None

        # 验证内容不为空
        if not content:
            logger.warning("Empty todo content")
            return None

        logger.info(f"Parsed todo: {content} @ {deadline}")
        return (content, deadline)

    @staticmethod
    def is_todo_message(message: str) -> bool:
        """
        检查消息是否为待办消息

        Args:
            message: 消息文本

        Returns:
            是否为待办消息
        """
        return bool(re.search(TodoParser.TODO_PATTERN, message))


class CommandParser:
    """命令解析器"""

    @staticmethod
    def parse_command(message: str, bot_mention: str = "") -> Optional[Tuple[str, list]]:
        """
        解析命令消息

        Args:
            message: 消息文本
            bot_mention: 机器人的@标识

        Returns:
            (命令, 参数列表) 元组，如果不是命令返回None
        """
        # 移除@机器人的部分
        if bot_mention:
            message = message.replace(bot_mention, "").strip()

        # 如果消息不是以@机器人开头，则不是命令
        if not message:
            return None

        parts = message.split()
        if not parts:
            return None

        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        return (command, args)

    @staticmethod
    def is_command(message: str, keywords: list) -> bool:
        """
        检查消息是否包含特定关键词命令

        Args:
            message: 消息文本
            keywords: 关键词列表

        Returns:
            是否包含关键词
        """
        message = message.strip()
        for keyword in keywords:
            if keyword in message:
                return True
        return False


class ReminderConfigParser:
    """提醒配置解析器"""

    # 提醒时间配置格式：周X HH:MM
    WEEKLY_PATTERN = r'周([1-7一二三四五六日])\s+(\d{1,2}):(\d{2})'

    WEEKDAY_MAP = {
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7
    }

    @staticmethod
    def parse_weekly_config(text: str) -> Optional[Tuple[int, int, int]]:
        """
        解析每周提醒配置

        Args:
            text: 配置文本，如 "周1 09:00" 或 "周一 9:30"

        Returns:
            (星期, 小时, 分钟) 元组，如果解析失败返回None
        """
        match = re.search(ReminderConfigParser.WEEKLY_PATTERN, text)

        if not match:
            return None

        weekday_str = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3))

        # 转换星期
        weekday = ReminderConfigParser.WEEKDAY_MAP.get(weekday_str)
        if not weekday:
            return None

        # 验证时间范围
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            logger.warning(f"Invalid time: {hour}:{minute}")
            return None

        logger.info(f"Parsed weekly config: weekday={weekday}, time={hour}:{minute}")
        return (weekday, hour, minute)
