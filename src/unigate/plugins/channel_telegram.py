"""Telegram channel adapter using the Bot API."""

from __future__ import annotations

import asyncio
import json
from typing import Any, ClassVar
from urllib.request import Request, urlopen

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..events import KernelEvent
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Action, Message, Sender
from ..stores import SecureStore


class TelegramChannelPlugin:
    """Telegram channel plugin (simple version)."""
    
    name = "telegram"
    type = "channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        from datetime import datetime, timezone
        update = raw.get("update", raw)
        message = update.get("message", update)
        if not message:
            return None
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        sender = Sender(
            platform_id=str(from_user.get("id", "")),
            name=from_user.get("first_name", "User"),
            handle=from_user.get("username"),
        )
        return Message(
            id=str(message.get("message_id", "")),
            session_id=str(chat.get("id", "")),
            from_instance=self.name,
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=message.get("text") or message.get("caption", ""),
            raw=message,
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        return {"text": msg.text}


class TelegramChannel:
    """Telegram Bot API channel adapter.
    
    Supports two modes:
    - polling: Long polling with getUpdates (default, good for development)
    - webhook: Telegram pushes updates to your URL (better for production)
    """

    name: ClassVar[str] = "telegram"
    type: ClassVar[str] = "channel"
    transport: ClassVar[str] = "http"
    auth_method: ClassVar[str] = "token"

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        instance_id: str,
        store: SecureStore,
        kernel: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self._token: str | None = None
        self._started = False
        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._sent: list[Message] = []

    async def setup(self) -> SetupResult:
        token = self.config.get("token")
        if not token:
            token = await self.store.get("bot_token")
        if not token:
            return SetupResult(
                status=SetupStatus.NEEDS_INTERACTION,
                interaction_type="token",
                interaction_data={"prompt": "Enter your Telegram bot token:"},
            )
        self._token = token
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        self._started = True
        mode = self.config.get("mode", "polling")
        if mode == "polling":
            self._poll_task = asyncio.create_task(self._poll_loop())
        elif mode == "webhook":
            await self._setup_webhook()

    async def stop(self) -> None:
        self._started = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None

    async def _setup_webhook(self) -> None:
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return
        secret = self.config.get("webhook_secret")
        await self._api_call("setWebhook", {
            "url": webhook_url,
            "secret_token": secret,
        })

    async def _poll_loop(self) -> None:
        while self._started:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
                if updates:
                    last_update_id = max(u.get("update_id", 0) for u in updates)
                    self._offset = last_update_id + 1
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)
                continue

    async def _get_updates(self) -> list[dict[str, Any]]:
        if not self._token:
            return []
        url = f"{self.BASE_URL}/bot{self._token}/getUpdates"
        params = f"?offset={self._offset}&timeout=55&allowed_updates=message,edited_message,callback_query"
        try:
            req = Request(url + params)
            with urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode())
                if data.get("ok"):
                    return data.get("result", [])
        except Exception:
            pass
        return []

    async def _handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("update_id")
        
        # Handle edited messages
        edited_message = update.get("edited_message")
        if edited_message:
            raw = self._normalize_telegram_message(edited_message, update)
            raw["edit_of_id"] = str(edited_message.get("message_id", ""))
            await self.kernel.ingest(self.instance_id, raw)
            return
        
        # Handle deleted messages (callback from Telegram)
        # Note: Telegram doesn't send explicit delete events, but we can detect
        # message ID gaps in polling mode
        
        # Handle regular messages
        message = update.get("message")
        if not message:
            callback = update.get("callback_query")
            if callback:
                message = callback.get("message")
        
        if message and self.kernel:
            raw = self._normalize_telegram_message(message, update)
            await self.kernel.ingest(self.instance_id, raw)

    def _normalize_telegram_message(self, msg: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        
        # Instance-scoped session: instance_id:chat_id
        # This ensures conversations are isolated per bot instance
        chat_id = str(chat.get("id", "unknown"))
        session_id = f"{self.instance_id}:{chat_id}"
        
        # Detect if this is an edited message
        edit_of_id = msg.get("edit_date")
        
        return {
            "id": str(msg.get("message_id", "")),
            "session_id": session_id,
            "from_instance": self.instance_id,
            "platform_id": str(msg.get("message_id", "")),
            "sender": {
                "id": str(user.get("id", "unknown")),
                "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Unknown",
                "username": user.get("username"),
                "is_bot": user.get("is_bot", False),
            },
            "text": msg.get("text") or msg.get("caption", ""),
            "group_id": str(chat["id"]) if chat.get("type") != "private" else None,
            "thread_id": msg.get("message_thread_id"),
            "receiver_id": f"bot:{self._token}",
            "bot_mentioned": True,
            "reply_to_id": str(msg.get("reply_to_message", {}).get("message_id")) if msg.get("reply_to_message") else None,
            "edit_of_id": str(msg.get("message_id")) if edit_of_id else None,
            "deleted_id": None,  # Telegram doesn't send explicit deletes
            "raw": msg,
            "metadata": {"update_id": update.get("update_id"), "edit_date": edit_of_id},
        }

    def to_message(self, raw: dict[str, Any]) -> Message:
        from datetime import datetime, timezone
        sender_data = raw.get("sender", {})
        sender = Sender(
            platform_id=str(sender_data.get("id", "unknown")),
            name=str(sender_data.get("name", "Unknown")),
            handle=sender_data.get("username"),
            is_bot=sender_data.get("is_bot", False),
            raw=sender_data,
        )
        return Message(
            id=raw.get("id", str(raw.get("platform_id", ""))),
            session_id=raw.get("session_id", "unknown"),
            from_instance=self.instance_id,
            sender=sender,
            ts=datetime.now(timezone.utc),
            platform_id=raw.get("platform_id"),
            to=[],
            thread_id=raw.get("thread_id"),
            group_id=raw.get("group_id"),
            receiver_id=raw.get("receiver_id"),
            bot_mentioned=raw.get("bot_mentioned", True),
            text=raw.get("text", ""),
            raw=raw.get("raw", {}),
            metadata=raw.get("metadata", {}),
        )

    async def from_message(self, msg: Message) -> SendResult:
        if not self._token:
            return SendResult(success=False, error="not configured")
        try:
            chat_id = msg.group_id or msg.session_id
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": msg.text or "",
            }
            if msg.reply_to_id:
                payload["reply_to_message_id"] = int(msg.reply_to_id)
            if msg.actions:
                for action in msg.actions:
                    if action.type == "typing_on":
                        payload["action"] = "typing"
                        await self._send_action(payload)
                        break
            result = await self._api_call("sendMessage", payload)
            if result.get("ok"):
                self._sent.append(msg)
                return SendResult(
                    success=True,
                    provider_message_id=str(result["result"]["message_id"]),
                )
            return SendResult(success=False, error=str(result))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def _send_action(self, payload: dict[str, Any]) -> None:
        await self._api_call("sendChatAction", payload)

    async def _api_call(self, method: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._token:
            return {"ok": False, "error": "no token"}
        url = f"{self.BASE_URL}/bot{self._token}/{method}"
        try:
            if data is not None:
                req = Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
            else:
                req = Request(url)
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def verify_signature(self, request: RawRequest) -> bool:
        secret = self.config.get("webhook_secret")
        if not secret:
            return True
        header_name = "x-telegram-bot-api-secret-token"
        token = request.headers.get(header_name, "")
        return token == secret

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=True,
            supports_reactions=True,
            supports_reply_to=True,
            supports_edit=True,
            supports_delete=True,
            supports_typing_indicator=True,
            supports_media_send=True,
            supported_interaction_types=["confirm", "select", "inline_keyboard"],
            max_message_length=4096,
        )

    async def reset_setup(self) -> None:
        self._token = None

    async def health_check(self) -> HealthStatus:
        if not self._token:
            return HealthStatus.UNKNOWN
        result = await self._api_call("getMe")
        return HealthStatus.HEALTHY if result.get("ok") else HealthStatus.UNHEALTHY

    async def background_tasks(self) -> list[object]:
        return []

    async def emit_event(self, event: KernelEvent) -> None:
        if self.kernel:
            await self.kernel.emit_event(event)
