"""
飞书API客户端封装
"""
import logging
from typing import Optional, Dict, Any

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
        import json

        content = {"text": text}

        # 如果需要@所有人
        if at_all:
            content["text"] = f"<at user_id=\"all\">所有人</at> {text}"

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
        import json

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
