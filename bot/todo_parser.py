"""
待办消息格式解析器
"""
import re
import logging
from typing import Optional, Tuple
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# 任务意图关键词：包含这些词的消息视为可能的待办
TODO_INTENT_KEYWORDS = [
    '需要', '请', '麻烦', '记得', '安排', '负责', '完成', '处理', '跟进',
    '确认', '调研', '准备', '提交', '协调', '帮忙', '联系', '检查', '审核',
    '发送', '提供', '整理', '更新', '盯一下', '关注', '跟一下', '推进',
    '回复', '对接', '输出', '梳理', '落实', '执行', '跟踪', '待办',
]


class NaturalDateParser:
    """中文自然语言日期/时间解析器"""

    WEEKDAY_CN = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7,
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    }

    @staticmethod
    def parse(text: str) -> Optional[str]:
        """
        从自然语言文本中提取日期（含时间）

        Returns:
            'YYYY-MM-DD HH:MM' 若识别到时间，否则 'YYYY-MM-DD'，无法识别返回 None
        """
        date_str = NaturalDateParser._parse_date_only(text)
        if not date_str:
            return None
        time_str = NaturalDateParser._parse_time(text)
        return f'{date_str} {time_str}' if time_str else date_str

    @staticmethod
    def _parse_date_only(text: str) -> Optional[str]:
        """仅解析日期部分，返回 YYYY-MM-DD 或 None"""
        today = date.today()

        # 优先匹配精确格式 YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return d.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # X月X日 / X月X号
        m = re.search(r'(\d{1,2})月(\d{1,2})[日号]', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            year = today.year
            try:
                d = date(year, month, day)
                if d < today:
                    d = date(year + 1, month, day)
                return d.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # 昨天
        if '昨天' in text or '昨日' in text:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')

        # 今天
        if '今天' in text or '今日' in text:
            return today.strftime('%Y-%m-%d')

        # 明天
        if '明天' in text or '明日' in text:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # 后天
        if '后天' in text:
            return (today + timedelta(days=2)).strftime('%Y-%m-%d')

        # 大后天
        if '大后天' in text:
            return (today + timedelta(days=3)).strftime('%Y-%m-%d')

        # 本周X / 这周X
        m = re.search(r'[本这]周([一二三四五六日天1-7])', text)
        if m:
            target_wd = NaturalDateParser.WEEKDAY_CN.get(m.group(1))
            if target_wd:
                current_wd = today.isoweekday()
                delta = target_wd - current_wd
                if delta < 0:
                    delta += 7
                return (today + timedelta(days=delta)).strftime('%Y-%m-%d')

        # 下周X
        m = re.search(r'下周([一二三四五六日天1-7])', text)
        if m:
            target_wd = NaturalDateParser.WEEKDAY_CN.get(m.group(1))
            if target_wd:
                current_wd = today.isoweekday()
                delta = 7 - current_wd + target_wd
                return (today + timedelta(days=delta)).strftime('%Y-%m-%d')

        # 下下周X
        m = re.search(r'下下周([一二三四五六日天1-7])', text)
        if m:
            target_wd = NaturalDateParser.WEEKDAY_CN.get(m.group(1))
            if target_wd:
                current_wd = today.isoweekday()
                delta = 14 - current_wd + target_wd
                return (today + timedelta(days=delta)).strftime('%Y-%m-%d')

        # 本月底 / 月底
        if '月底' in text:
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            return date(today.year, today.month, last_day).strftime('%Y-%m-%d')

        # X天后 / X天内
        m = re.search(r'(\d+)天[后内]', text)
        if m:
            return (today + timedelta(days=int(m.group(1)))).strftime('%Y-%m-%d')

        return None

    @staticmethod
    def _parse_time(text: str) -> Optional[str]:
        """
        从文本中提取时间点，返回 HH:MM 字符串，无法识别返回 None

        支持：下班前 → 18:00，HH:MM，下午/晚上X点，上午X点，X点半，X点Y分
        """
        # 下班前 → 18:00
        if '下班前' in text:
            return '18:00'

        # 数字格式 HH:MM（优先处理，避免被中文模式误抢）
        m = re.search(r'(\d{1,2}):(\d{2})', text)
        if m:
            h, minute = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= minute <= 59:
                return f'{h:02d}:{minute:02d}'

        # 下午/晚上/午后 X点Y分 or X点半 or X点
        m = re.search(r'(?:下午|晚上|午后)\s*(\d{1,2})[点时](?:(\d{1,2})分|半)?', text)
        if m:
            h = int(m.group(1))
            if m.group(2):
                minute = int(m.group(2))
            elif '半' in (m.group(0) or ''):
                minute = 30
            else:
                minute = 0
            if h < 12:
                h += 12
            if 0 <= h <= 23:
                return f'{h:02d}:{minute:02d}'

        # 上午 X点Y分 or X点半 or X点
        m = re.search(r'上午\s*(\d{1,2})[点时](?:(\d{1,2})分|半)?', text)
        if m:
            h = int(m.group(1))
            if m.group(2):
                minute = int(m.group(2))
            elif '半' in (m.group(0) or ''):
                minute = 30
            else:
                minute = 0
            if 0 <= h <= 11:
                return f'{h:02d}:{minute:02d}'

        # X点半（无前缀）
        m = re.search(r'(\d{1,2})点半', text)
        if m:
            h = int(m.group(1))
            if 0 <= h <= 23:
                return f'{h:02d}:30'

        # X点Y分（无前缀）
        m = re.search(r'(\d{1,2})[点时](\d{1,2})分', text)
        if m:
            h, minute = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= minute <= 59:
                return f'{h:02d}:{minute:02d}'

        return None


class TodoParser:
    """待办消息解析器（支持自然语言，无需固定格式）"""

    # 保留旧格式作为精确匹配备选
    TODO_PATTERN = r'待办[：:]\s*(.+?)\s*@(\d{4}-\d{2}-\d{2})'

    @staticmethod
    def parse_todo(message: str) -> Optional[Tuple[str, str]]:
        """
        解析待办消息，支持自然语言

        Args:
            message: 消息文本

        Returns:
            (内容, 截止日期) 元组，截止日期可为空字符串，解析失败返回 None
        """
        # 旧格式精确匹配（向后兼容）
        match = re.search(TodoParser.TODO_PATTERN, message)
        if match:
            content = match.group(1).strip()
            deadline = match.group(2)
            try:
                datetime.strptime(deadline, '%Y-%m-%d')
                if content:
                    return (content, deadline)
            except ValueError:
                pass

        # 自然语言：提取内容（清理@提及和日期表达后的剩余文本）
        content = TodoParser._extract_content(message)
        if not content:
            return None

        # 提取日期
        deadline = NaturalDateParser.parse(message) or ''

        logger.info(f"Parsed todo (NL): content='{content}', deadline='{deadline}'")
        return (content, deadline)

    @staticmethod
    def _extract_content(message: str) -> str:
        """从自然语言消息中提取待办内容"""
        text = message.strip()

        # 移除 @XXX 提及（飞书格式：@name 或 <at>）
        text = re.sub(r'<at[^>]*>[^<]*</at>', '', text)
        text = re.sub(r'@\S+', '', text)

        # 移除日期表达
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,2}月\d{1,2}[日号]',
            r'[本这下]+周[一二三四五六日天1-7]',
            r'\d+天[后内]',
            r'昨天|昨日|今天|今日|明天|明日|后天|大后天|月底',
        ]
        for pat in date_patterns:
            text = re.sub(pat, '', text)

        # 移除时间表达
        time_patterns = [
            r'下班前',
            r'\d{1,2}:\d{2}',
            r'(?:下午|晚上|午后|上午)\s*\d{1,2}[点时](?:\d{1,2}分|半)?',
            r'\d{1,2}点半',
            r'\d{1,2}[点时]\d{1,2}分',
        ]
        for pat in time_patterns:
            text = re.sub(pat, '', text)

        # 移除"待办："前缀
        text = re.sub(r'^待办[：:]\s*', '', text)

        # 清理多余空白和标点
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.strip('，。、；：,.;:')

        return text

    @staticmethod
    def is_todo_message(message: str, has_non_bot_mentions: bool = False) -> bool:
        """
        判断消息是否为待办意图

        规则：
        1. 旧格式（待办：XXX @YYYY-MM-DD）直接匹配
        2. 消息中@了非机器人用户（任务分配场景）
        3. 消息包含任务意图关键词

        Args:
            message: 消息文本
            has_non_bot_mentions: 是否@了非机器人用户

        Returns:
            是否为待办消息
        """
        # 旧精确格式
        if re.search(TodoParser.TODO_PATTERN, message):
            return True

        # @了非机器人用户，视为任务分配
        if has_non_bot_mentions:
            return True

        # 包含任务意图关键词
        for kw in TODO_INTENT_KEYWORDS:
            if kw in message:
                return True

        return False


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
