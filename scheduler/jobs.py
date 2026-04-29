"""
定时任务定义
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .reminder import ReminderService

logger = logging.getLogger(__name__)

CST = 'Asia/Shanghai'


class SchedulerManager:
    """调度器管理器"""

    def __init__(self, reminder_service: ReminderService):
        self.reminder_service = reminder_service
        self.scheduler = BackgroundScheduler(timezone=CST)

    def start(self):
        """启动调度器"""
        try:
            # 每周提醒：每小时触发一次，send_weekly_reminder 内部按各群配置判断是否发送
            self.scheduler.add_job(
                func=self.reminder_service.send_weekly_reminder,
                trigger=IntervalTrigger(hours=1),
                id='weekly_reminder',
                name='每周待办提醒（按各群配置时间）',
                replace_existing=True
            )
            logger.info("Added weekly reminder job: Hourly check with per-chat config")

            # 截止日提醒：每天上午10点（北京时间）
            self.scheduler.add_job(
                func=self.reminder_service.send_daily_deadline_reminder,
                trigger=CronTrigger(hour=10, minute=0, timezone=CST),
                id='daily_deadline_reminder',
                name='每日截止提醒（北京时间10:00）',
                replace_existing=True
            )
            logger.info("Added daily deadline reminder job: Every day at 10:00 CST")

            # 启动调度器
            self.scheduler.start()
            logger.info("Scheduler started successfully")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}", exc_info=True)
            raise

    def stop(self):
        """停止调度器"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)

    def get_jobs(self):
        """获取所有任务"""
        return self.scheduler.get_jobs()

    def pause_job(self, job_id: str):
        """暂停任务"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")

    def resume_job(self, job_id: str):
        """恢复任务"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {e}")

    def trigger_job(self, job_id: str):
        """手动触发任务（用于测试）"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.func()
                logger.info(f"Manually triggered job: {job_id}")
            else:
                logger.warning(f"Job not found: {job_id}")
        except Exception as e:
            logger.error(f"Error triggering job {job_id}: {e}")


def create_scheduler(reminder_service: ReminderService) -> SchedulerManager:
    """
    创建调度器实例

    Args:
        reminder_service: 提醒服务实例

    Returns:
        调度器管理器实例
    """
    return SchedulerManager(reminder_service)
