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

    def create_todo_spreadsheet(self, chat_id: str, todos: list) -> Optional[Tuple[str, str, str]]:
        """
        创建飞书电子表格并写入待办数据

        Args:
            chat_id: 群组ID（用于表格标题）
            todos: Todo 对象列表

        Returns:
            (spreadsheet_url, spreadsheet_token, sheet_id)，失败返回 None
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
            try:
                create_data = create_resp.json()
            except Exception as e:
                logger.error(f"Failed to parse create response: {e}, raw: {create_resp.text[:200]}")
                return None

            if create_data.get("code") != 0:
                logger.error(f"Failed to create spreadsheet: {create_data}")
                return None

            spreadsheet_token = create_data["data"]["spreadsheet"]["spreadsheet_token"]
            spreadsheet_url = create_data["data"]["spreadsheet"]["url"]
            logger.info(f"Created spreadsheet: {spreadsheet_token}")

            # 2. 通过 v2 metainfo 接口获取真实 sheetId
            sheet_id = None
            try:
                meta_resp = requests.get(
                    f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                    f"/{spreadsheet_token}/metainfo",
                    headers=headers
                )
                meta_data = meta_resp.json()
                if meta_data.get("code") == 0:
                    sheets = meta_data.get("data", {}).get("sheets", [])
                    sheet_id = sheets[0].get("sheetId") if sheets else None
                if not sheet_id:
                    logger.error(f"Could not get sheetId from metainfo: {meta_data}")
                    return None
            except Exception as e:
                logger.error(f"Failed to get metainfo: {e}")
                return None

            logger.info(f"Got sheetId: {sheet_id}")

            # 3. 写入表头 + 数据
            self._write_spreadsheet_data(spreadsheet_token, sheet_id, todos, headers)

            return (spreadsheet_url, spreadsheet_token, sheet_id)

        except Exception as e:
            logger.error(f"Error creating todo spreadsheet: {e}", exc_info=True)
            return None

    def update_todo_spreadsheet(self, spreadsheet_token: str, sheet_id: str, todos: list) -> bool:
        """
        更新已有飞书电子表格的待办数据（保留用户手动填写的备注列）
        """
        try:
            import requests

            token = self._get_tenant_access_token()
            if not token:
                return False

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }

            # 1. 读取现有备注列（G列）
            existing_notes = {}
            try:
                read_range = f"{sheet_id}!A2:G1000"
                read_resp = requests.get(
                    f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                    f"/{spreadsheet_token}/values/{read_range}",
                    headers=headers
                )
                read_data = read_resp.json()
                if read_data.get("code") == 0:
                    rows = read_data.get("data", {}).get("valueRange", {}).get("values", []) or []
                    for row in rows:
                        if row and row[0]:
                            try:
                                task_id = int(str(row[0]))
                                note = row[6] if len(row) > 6 else ""
                                existing_notes[task_id] = note or ""
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                logger.warning(f"Failed to read existing notes: {e}")

            # 2. 清除旧数据
            try:
                requests.post(
                    f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                    f"/{spreadsheet_token}/values_batch_clear",
                    headers=headers,
                    json={"ranges": [f"{sheet_id}!A1:G1000"]}
                )
            except Exception as e:
                logger.warning(f"Failed to clear spreadsheet: {e}")

            # 3. 重写数据
            self._write_spreadsheet_data(spreadsheet_token, sheet_id, todos, headers, existing_notes)

            logger.info(f"Spreadsheet {spreadsheet_token} updated: {len(todos)} todos")
            return True

        except Exception as e:
            logger.error(f"Error updating spreadsheet: {e}", exc_info=True)
            return False

    def _write_spreadsheet_data(self, spreadsheet_token: str, sheet_id: str,
                                todos: list, headers: dict,
                                existing_notes: dict = None) -> bool:
        """写入表头和待办数据"""
        try:
            import requests

            if existing_notes is None:
                existing_notes = {}

            header = [["任务ID", "内容", "负责人", "创建时间", "截止时间", "状态", "备注"]]
            rows = []
            for todo in todos:
                status = "已完成" if todo.completed else "进行中"
                note = existing_notes.get(todo.id, "")
                rows.append([
                    str(todo.id),
                    todo.content or "",
                    todo.assignee_name or todo.user_name or "",
                    todo.created_at or "",
                    todo.deadline or "未设置",
                    status,
                    note
                ])

            all_rows = header + rows
            end_row = max(len(all_rows), 1)
            range_str = f"{sheet_id}!A1:G{end_row}"

            write_resp = requests.put(
                f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                f"/{spreadsheet_token}/values",
                headers=headers,
                json={
                    "valueRange": {
                        "range": range_str,
                        "values": all_rows
                    }
                }
            )
            try:
                write_data = write_resp.json()
            except Exception as e:
                logger.error(f"Failed to parse write response: {e}, raw: {write_resp.text[:200]}")
                return False

            if write_data.get("code") != 0:
                logger.error(f"Failed to write spreadsheet data: {write_data}")
                return False

            logger.info(f"Spreadsheet data written: {len(rows)} rows")
            return True

        except Exception as e:
            logger.error(f"Error writing spreadsheet data: {e}", exc_info=True)
            return False

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
