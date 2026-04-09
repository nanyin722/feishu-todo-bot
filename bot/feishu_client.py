"""
飞书API客户端封装
"""
import json
import logging
from typing import Optional, Dict, Any, List, Tuple

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

logger = logging.getLogger(__name__)


class FeishuClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    def send_message(self, receive_id: str, msg_type: str, content: str,
                     receive_id_type: str = "chat_id") -> bool:
        """
        发送消息到群组

        Args:
            receive_id: 接收者ID（群组ID或用户ID）
            msg_type: 消息类型（text, post等）
            content: 消息内容（JSON字符串）
            receive_id_type: 接收者ID类型（chat_id, open_id, user_id等）

        Returns:
            是否发送成功
        """
        try:
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                ) \
                .build()

            response = self.client.im.v1.message.create(request)

            if not response.success():
                logger.error(f"Failed to send message: {response.code} - {response.msg}")
                return False

            logger.info(f"Message sent successfully to {receive_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_text_message(self, chat_id: str, text: str, at_all: bool = False) -> bool:
        """
        发送文本消息

        Args:
            chat_id: 群组ID
            text: 文本内容
            at_all: 是否@所有人

        Returns:
            是否发送成功
        """
        content = {"text": text}

        # 如果需要@所有人
        if at_all:
            content["text"] = f"<at user_id=\"all\">所有人</at> {text}"

        return self.send_message(chat_id, "text", json.dumps(content))

    def send_text_message_with_at_users(self, chat_id: str, text: str,
                                        at_open_ids: List[str]) -> bool:
        """
        发送文本消息并@指定用户

        Args:
            chat_id: 群组ID
            text: 文本内容
            at_open_ids: 需要@的用户 open_id 列表

        Returns:
            是否发送成功
        """
        if not at_open_ids:
            return self.send_text_message(chat_id, text)

        at_tags = " ".join(
            f"<at user_id=\"{oid}\"></at>" for oid in at_open_ids
        )
        content = {"text": f"{at_tags} {text}"}
        return self.send_message(chat_id, "text", json.dumps(content))

    def send_rich_text_message(self, chat_id: str, title: str,
                               content_lines: list, at_all: bool = False) -> bool:
        """
        发送富文本消息

        Args:
            chat_id: 群组ID
            title: 标题
            content_lines: 内容行列表，每行是一个包含文本元素的列表
            at_all: 是否@所有人

        Returns:
            是否发送成功
        """
        # 如果需要@所有人，在标题前添加
        if at_all:
            at_element = [{
                "tag": "at",
                "user_id": "all"
            }]
            # 在第一行前添加@所有人
            if content_lines:
                content_lines = [at_element] + content_lines
            else:
                content_lines = [at_element]

        post_content = {
            "zh_cn": {
                "title": title,
                "content": content_lines
            }
        }

        content = {"post": post_content}

        return self.send_message(chat_id, "post", json.dumps(content))

    def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        获取群组信息

        Args:
            chat_id: 群组ID

        Returns:
            群组信息字典，失败返回None
        """
        try:
            request = GetChatRequest.builder() \
                .chat_id(chat_id) \
                .build()

            response = self.client.im.v1.chat.get(request)

            if not response.success():
                logger.error(f"Failed to get chat info: {response.code} - {response.msg}")
                return None

            return response.data

        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None

    def get_user_info(self, user_id: str, user_id_type: str = "open_id") -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户ID
            user_id_type: 用户ID类型（open_id, user_id, union_id）

        Returns:
            用户信息字典，失败返回None
        """
        try:
            # 这里需要使用contact API，简化版本先返回None
            # 实际使用时需要添加相应的权限和API调用
            logger.info(f"Get user info for {user_id} (type: {user_id_type})")
            return {"user_id": user_id}

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def create_todo_spreadsheet(self, chat_id: str, todos: list) -> Optional[Tuple[str, str]]:
        """
        创建飞书电子表格并写入待办数据

        Args:
            chat_id: 群组ID（用于表格标题）
            todos: Todo 对象列表

        Returns:
            (spreadsheet_url, spreadsheet_token)，失败返回 None
        """
        try:
            import requests
            from datetime import datetime as dt

            # 获取访问令牌
            token = self._get_tenant_access_token()
            if not token:
                logger.error("Failed to get tenant access token")
                return None

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }

            # 1. 创建电子表格
            title = f"待办列表 {dt.now().strftime('%Y-%m-%d %H:%M')}"
            create_resp = requests.post(
                "https://open.feishu.cn/open-apis/sheets/v3/spreadsheets",
                headers=headers,
                json={"title": title}
            )
            create_data = create_resp.json()

            if create_data.get("code") != 0:
                logger.error(f"Failed to create spreadsheet: {create_data}")
                return None

            spreadsheet_token = create_data["data"]["spreadsheet"]["spreadsheet_token"]
            spreadsheet_url = create_data["data"]["spreadsheet"]["url"]
            sheet_id = create_data["data"]["spreadsheet"]["sheets"][0]["sheet_id"] \
                if create_data["data"]["spreadsheet"].get("sheets") else "Sheet1"

            logger.info(f"Created spreadsheet: {spreadsheet_token}")

            # 2. 写入表头 + 数据
            header = [["内容", "负责人", "创建时间", "截止时间", "状态", "备注"]]
            rows = []
            for todo in todos:
                status = "已完成" if todo.completed else "进行中"
                rows.append([
                    todo.content or "",
                    todo.assignee_name or todo.user_name or "",
                    todo.created_at or "",
                    todo.deadline or "未设置",
                    status,
                    ""  # 备注留空供手动填写
                ])

            all_rows = header + rows
            end_row = len(all_rows)
            range_str = f"{sheet_id}!A1:F{end_row}"

            write_resp = requests.put(
                f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values",
                headers=headers,
                json={
                    "valueRange": {
                        "range": range_str,
                        "values": all_rows
                    }
                }
            )
            write_data = write_resp.json()

            if write_data.get("code") != 0:
                logger.error(f"Failed to write spreadsheet data: {write_data}")
                # 表格已创建，仍返回 URL
                return (spreadsheet_url, spreadsheet_token)

            logger.info(f"Spreadsheet data written: {len(rows)} rows")
            return (spreadsheet_url, spreadsheet_token)

        except Exception as e:
            logger.error(f"Error creating todo spreadsheet: {e}", exc_info=True)
            return None

    def _get_tenant_access_token(self) -> Optional[str]:
        """获取租户访问令牌"""
        try:
            import requests
            resp = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret}
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("tenant_access_token")
            logger.error(f"Failed to get tenant access token: {data}")
            return None
        except Exception as e:
            logger.error(f"Error getting tenant access token: {e}")
            return None
