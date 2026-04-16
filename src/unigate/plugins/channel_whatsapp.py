"""WhatsApp channel adapter using Meta Business API."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, ClassVar

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..events import KernelEvent
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Message, Sender
from ..stores import SecureStore


class WhatsAppChannelPlugin:
    """WhatsApp channel plugin (simple version for routing)."""
    
    name = "whatsapp"
    type = "channel"
    description = "WhatsApp Business API integration"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        from datetime import datetime, timezone
        entry = raw.get("entry", [])
        if not entry:
            return None
        
        changes = entry[0].get("changes", [])
        if not changes:
            return None
        
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None
        
        msg = messages[0]
        contacts = value.get("contacts", [])
        profile = contacts[0].get("profile", {}) if contacts else {}
        
        sender = Sender(
            platform_id=str(msg.get("from", "unknown")),
            name=profile.get("name", f"User:{msg.get('from', '')}"),
        )
        
        text = ""
        msg_type = msg.get("type", "text")
        if msg_type == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            text = "[Image]"
        elif msg_type == "video":
            text = "[Video]"
        elif msg_type == "audio":
            text = "[Audio]"
        elif msg_type == "document":
            text = "[Document]"
        elif msg_type == "location":
            loc = msg.get("location", {})
            text = f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
        elif msg_type == "sticker":
            text = "[Sticker]"
        elif msg_type == "reaction":
            reaction = msg.get("reaction", {})
            text = f"[Reaction to {reaction.get('message_id', '')}: {reaction.get('emoji', '')}]"
        elif msg_type == "contacts":
            text = "[Contacts]"
        
        return Message(
            id=str(msg.get("id", "")),
            session_id=str(msg.get("from", "unknown")),
            from_instance=self.name,
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=text,
            raw=raw,
            metadata={
                "msg_type": msg_type,
                "wa_id": msg.get("from"),
                "timestamp": msg.get("timestamp"),
            },
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        return {"text": msg.text}


class WhatsAppChannel(BaseChannel):
    """WhatsApp Business API channel adapter.
    
    Supports:
    - Webhook mode for receiving messages
    - REST API for sending messages
    - Media uploads
    - Interactive messages (buttons, lists, catalogs)
    """
    
    name: ClassVar[str] = "whatsapp"
    transport: ClassVar[str] = "https"
    auth_method: ClassVar[str] = "token"
    
    API_URL = "https://graph.facebook.com/v18.0"
    
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
        self._phone_number_id: str | None = None
        self._access_token: str | None = None
        self._verify_token: str | None = None
        self._started = False
        self._sent: list[Message] = []
    
    async def setup(self) -> SetupResult:
        self._phone_number_id = self.config.get("phone_number_id")
        if not self._phone_number_id:
            self._phone_number_id = await self.store.get("phone_number_id")
        
        self._access_token = self.config.get("access_token")
        if not self._access_token:
            self._access_token = await self.store.get("access_token")
        
        self._verify_token = self.config.get("verify_token")
        if not self._verify_token:
            self._verify_token = await self.store.get("verify_token")
        
        if not self._phone_number_id:
            return SetupResult(
                status=SetupStatus.NEEDS_INTERACTION,
                interaction_type="token",
                interaction_data={
                    "prompt": "Enter your WhatsApp Phone Number ID:",
                    "field": "phone_number_id",
                },
            )
        
        if not self._access_token:
            return SetupResult(
                status=SetupStatus.NEEDS_INTERACTION,
                interaction_type="token",
                interaction_data={
                    "prompt": "Enter your WhatsApp Access Token:",
                    "field": "access_token",
                    "is_secret": True,
                },
            )
        
        return SetupResult(status=SetupStatus.READY)
    
    async def start(self) -> None:
        self._started = True
    
    async def stop(self) -> None:
        self._started = False
    
    def to_message(self, raw: dict[str, Any]) -> Message:
        from datetime import datetime, timezone
        
        entry = raw.get("entry", [])
        if not entry:
            return Message(
                id=str(time.time()),
                from_instance=self.instance_id,
                sender=Sender(platform_id="unknown", name="Unknown"),
                ts=datetime.now(timezone.utc),
                raw=raw,
            )
        
        changes = entry[0].get("changes", [])
        if not changes:
            return Message(
                id=str(time.time()),
                from_instance=self.instance_id,
                sender=Sender(platform_id="unknown", name="Unknown"),
                ts=datetime.now(timezone.utc),
                raw=raw,
            )
        
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            statuses = value.get("statuses", [])
            if statuses:
                status = statuses[0]
                return Message(
                    id=str(status.get("id", "")),
                    from_instance=self.instance_id,
                    sender=Sender(platform_id="system", name="WhatsApp"),
                    ts=datetime.fromtimestamp(int(status.get("timestamp", 0)), timezone.utc),
                    raw=raw,
                    metadata={
                        "status": status.get("status"),
                        "recipient_id": status.get("recipient_id"),
                    },
                )
            return Message(
                id=str(time.time()),
                from_instance=self.instance_id,
                sender=Sender(platform_id="unknown", name="Unknown"),
                ts=datetime.now(timezone.utc),
                raw=raw,
            )
        
        msg = messages[0]
        contacts = value.get("contacts", [])
        profile = {}
        if contacts:
            profile = contacts[0].get("profile", {})
        
        sender = Sender(
            platform_id=str(msg.get("from", "unknown")),
            name=profile.get("name", f"User:{msg.get('from', '')}"),
            raw=profile,
        )
        
        text = ""
        msg_type = msg.get("type", "text")
        if msg_type == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg_type == "image":
            img = msg.get("image", {})
            text = f"[Image: {img.get('id', '')}]"
        elif msg_type == "video":
            vid = msg.get("video", {})
            text = f"[Video: {vid.get('id', '')}]"
        elif msg_type == "audio":
            aud = msg.get("audio", {})
            text = f"[Audio: {aud.get('id', '')}]"
        elif msg_type == "document":
            doc = msg.get("document", {})
            text = f"[Document: {doc.get('filename', 'file')}]"
        elif msg_type == "location":
            loc = msg.get("location", {})
            text = f"[Location: {loc.get('latitude')}, {loc.get('longitude')} - {loc.get('name', '')}]"
        elif msg_type == "sticker":
            text = "[Sticker]"
        elif msg_type == "reaction":
            reaction = msg.get("reaction", {})
            text = f"[Reaction: {reaction.get('emoji', '🙂')}]"
        elif msg_type == "contacts":
            text = "[Contacts shared]"
        
        metadata = {
            "msg_type": msg_type,
            "wa_id": msg.get("from"),
            "timestamp": msg.get("timestamp"),
        }
        
        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            ib_type = interactive.get("type", "")
            if ib_type == "button_reply":
                btn = interactive.get("button_reply", {})
                metadata["button_id"] = btn.get("id")
                metadata["button_title"] = btn.get("title")
                text = f"[Button: {btn.get('title', '')}]"
            elif ib_type == "list_reply":
                lst = interactive.get("list_reply", {})
                metadata["list_id"] = lst.get("id")
                metadata["list_title"] = lst.get("title")
                text = f"[List: {lst.get('title', '')}]"
        
        return Message(
            id=str(msg.get("id", "")),
            session_id=str(msg.get("from", "unknown")),
            from_instance=self.instance_id,
            sender=sender,
            ts=datetime.fromtimestamp(int(msg.get("timestamp", 0)), timezone.utc),
            text=text,
            raw=raw,
            metadata=metadata,
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        if not self._phone_number_id or not self._access_token:
            return SendResult(success=False, error="not configured")
        
        try:
            recipient = msg.group_id or msg.session_id or msg.receiver_id
            if not recipient:
                return SendResult(success=False, error="no recipient")
            
            if msg.interactive:
                payload = await self._build_interactive_payload(recipient, msg)
            elif msg.media:
                payload = await self._build_media_payload(recipient, msg)
            else:
                payload = self._build_text_payload(recipient, msg)
            
            result = await self._api_call("POST", payload)
            
            if result.get("messages"):
                msg_id = result["messages"][0].get("id", "")
                self._sent.append(msg)
                return SendResult(success=True, provider_message_id=msg_id)
            
            return SendResult(success=False, error=str(result))
        
        except Exception as exc:
            return SendResult(success=False, error=str(exc))
    
    def _build_text_payload(self, recipient: str, msg: Message) -> dict[str, Any]:
        return {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": msg.text or ""},
        }
    
    async def _build_media_payload(self, recipient: str, msg: Message) -> dict[str, Any]:
        media = msg.media[0] if msg.media else {}
        media_type = media.get("type", "image")
        media_id = media.get("id") or media.get("url")
        
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": media_type,
        }
        
        if media_id:
            payload[media_type] = {"id": media_id}
        else:
            url = media.get("url", "")
            if url:
                payload[media_type] = {"link": url}
        
        if msg.text and media_type in ("image", "video", "document"):
            payload[media_type]["caption"] = msg.text
        
        return payload
    
    async def _build_interactive_payload(self, recipient: str, msg: Message) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "interactive",
        }
        
        interactive_type = msg.interactive.get("type", "button")
        
        if interactive_type == "button":
            buttons = []
            for i, btn in enumerate(msg.interactive.get("buttons", [])[:3]):
                buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn.get("id", f"btn_{i}"),
                        "title": btn.get("title", "")[:20],
                    },
                })
            payload["interactive"] = {
                "type": "buttons",
                "body": {"text": msg.text or "Select an option:"},
                "action": {"buttons": buttons},
            }
        elif interactive_type == "list":
            rows = []
            for i, item in enumerate(msg.interactive.get("items", [])[:10]):
                rows.append({
                    "id": item.get("id", f"item_{i}"),
                    "title": item.get("title", "")[:100],
                    "description": item.get("description", "")[:2000],
                })
            payload["interactive"] = {
                "type": "list",
                "header": {"type": "text", "text": msg.interactive.get("header", "Select")},
                "body": {"text": msg.text or "Choose:"},
                "action": {
                    "button": msg.interactive.get("button", "Select"),
                    "sections": [{"rows": rows}],
                },
            }
        
        return payload
    
    async def _api_call(self, method: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._phone_number_id or not self._access_token:
            return {"error": "not configured"}
        
        url = f"{self.API_URL}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode() if data else None,
                headers=headers,
                method=method,
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return {"error": f"HTTP {e.code}: {body}"}
        except Exception as exc:
            return {"error": str(exc)}
    
    async def verify_signature(self, request: RawRequest) -> bool:
        if not self._verify_token:
            return True
        
        mode = request.headers.get("x-hub-mode", "")
        if mode != "subscribe":
            return False
        
        token = request.headers.get("x-hub-signature", "")
        expected = "sha256=" + hmac.new(
            self._verify_token.encode(),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(token, expected)
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=False,
            supports_threads=False,
            supports_reactions=True,
            supports_reply_to=False,
            supports_edit=False,
            supports_delete=False,
            supports_typing_indicator=False,
            supports_media_send=True,
            supported_interaction_types=["button", "list"],
            max_message_length=4096,
        )
    
    async def reset_setup(self) -> None:
        self._phone_number_id = None
        self._access_token = None
    
    async def health_check(self) -> HealthStatus:
        if not self._access_token:
            return HealthStatus.UNKNOWN
        
        result = await self._api_call("GET", None)
        if "error" in result:
            return HealthStatus.UNHEALTHY
        
        return HealthStatus.HEALTHY
    
    async def background_tasks(self) -> list[object]:
        return []
    
    async def emit_event(self, event: KernelEvent) -> None:
        if self.kernel:
            await self.kernel.emit_event(event)
