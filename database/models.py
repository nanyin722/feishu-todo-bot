"""
数据模型定义
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Todo:
    """待办事项模型"""
    id: Optional[int] = None
    chat_id: str = ""
    user_id: str = ""
    user_name: str = ""
    content: str = ""
    deadline: str = ""  # YYYY-MM-DD格式，为空表示未设截止日期
    created_at: Optional[str] = None
    reminded_daily: bool = False
    completed: bool = False
    completed_at: Optional[str] = None
    assignee_id: Optional[str] = None    # 负责人 open_id
    assignee_name: Optional[str] = None  # 负责人显示名

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'content': self.content,
            'deadline': self.deadline,
            'created_at': self.created_at,
            'reminded_daily': self.reminded_daily,
            'completed': self.completed,
            'completed_at': self.completed_at,
            'assignee_id': self.assignee_id,
            'assignee_name': self.assignee_name
        }

    @staticmethod
    def from_dict(data: dict) -> 'Todo':
        """从字典创建对象"""
        return Todo(
            id=data.get('id'),
            chat_id=data.get('chat_id', ''),
            user_id=data.get('user_id', ''),
            user_name=data.get('user_name', ''),
            content=data.get('content', ''),
            deadline=data.get('deadline', ''),
            created_at=data.get('created_at'),
            reminded_daily=bool(data.get('reminded_daily', 0)),
            completed=bool(data.get('completed', 0)),
            completed_at=data.get('completed_at'),
            assignee_id=data.get('assignee_id'),
            assignee_name=data.get('assignee_name')
        )


@dataclass
class ReminderConfig:
    """提醒配置模型"""
    id: Optional[int] = None
    chat_id: str = ""
    weekly_day: int = 1  # 1-7 (周一到周日)
    weekly_hour: int = 9  # 0-23
    weekly_minute: int = 0  # 0-59
    daily_hour: int = 9  # 0-23
    daily_minute: int = 0  # 0-59
    enabled: bool = True

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'weekly_day': self.weekly_day,
            'weekly_hour': self.weekly_hour,
            'weekly_minute': self.weekly_minute,
            'daily_hour': self.daily_hour,
            'daily_minute': self.daily_minute,
            'enabled': self.enabled
        }

    @staticmethod
    def from_dict(data: dict) -> 'ReminderConfig':
        """从字典创建对象"""
        return ReminderConfig(
            id=data.get('id'),
            chat_id=data.get('chat_id', ''),
            weekly_day=data.get('weekly_day', 1),
            weekly_hour=data.get('weekly_hour', 9),
            weekly_minute=data.get('weekly_minute', 0),
            daily_hour=data.get('daily_hour', 9),
            daily_minute=data.get('daily_minute', 0),
            enabled=bool(data.get('enabled', 1))
        )
