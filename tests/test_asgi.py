import json
import unittest

from unigate import ApiChannel, Unigate, WebChannel, WebSocketServerChannel, create_asgi_app


class AsgiTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_http_endpoint(self) -> None:
        gate = Unigate()
        gate.register_instance("public_api", ApiChannel())

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"api:{message.text}")

        app = create_asgi_app(gate)
        events = await run_http_request(
            app,
            path="/unigate/channels/api/public_api/messages",
            body={
                "request_id": "req-1",
                "client_id": "client-1",
                "sender_name": "Client One",
                "text": "status",
                "conversation_id": "conv-1",
            },
        )
        body = decode_http_body(events)

        self.assertEqual(body["reply_text"], "api:status")
        self.assertTrue(body["session_id"])

    async def test_web_http_endpoint(self) -> None:
        gate = Unigate()
        gate.register_instance("site_chat", WebChannel())

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"web:{message.text}")

        app = create_asgi_app(gate)
        events = await run_http_request(
            app,
            path="/unigate/channels/web/site_chat/messages",
            body={
                "message_id": "web-1",
                "browser_session_id": "browser-1",
                "visitor_id": "visitor-1",
                "visitor_name": "Visitor One",
                "text": "help",
            },
        )
        body = decode_http_body(events)

        self.assertEqual(body["reply_text"], "web:help")

    async def test_websocket_endpoint(self) -> None:
        gate = Unigate()
        gate.register_instance("socket_gateway", WebSocketServerChannel())

        @gate.on_message
        def handle(message):
            return gate.reply(message, text=f"ws:{message.text}")

        app = create_asgi_app(gate)
        events = await run_websocket_session(
            app,
            path="/unigate/channels/ws/socket_gateway",
            incoming_texts=[
                {
                    "frame_id": "frame-1",
                    "connection_id": "conn-1",
                    "sender_id": "peer-1",
                    "sender_name": "Peer One",
                    "text": "ping",
                }
            ],
        )
        send_events = [event for event in events if event["type"] == "websocket.send"]
        payload = json.loads(send_events[0]["text"])

        self.assertEqual(payload["reply_text"], "ws:ping")


async def run_http_request(app, *, path: str, body: dict[str, str]):
    encoded = json.dumps(body).encode("utf-8")
    queue = [
        {"type": "http.request", "body": encoded, "more_body": False},
    ]
    sent: list[dict[str, object]] = []

    async def receive():
        return queue.pop(0)

    async def send(event):
        sent.append(event)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": path,
        },
        receive,
        send,
    )
    return sent


def decode_http_body(events):
    body = b"".join(event.get("body", b"") for event in events if event["type"] == "http.response.body")
    return json.loads(body.decode("utf-8"))


async def run_websocket_session(app, *, path: str, incoming_texts: list[dict[str, str]]):
    queue = [{"type": "websocket.connect"}]
    queue.extend({"type": "websocket.receive", "text": json.dumps(item)} for item in incoming_texts)
    queue.append({"type": "websocket.disconnect"})
    sent: list[dict[str, object]] = []

    async def receive():
        return queue.pop(0)

    async def send(event):
        sent.append(event)

    await app({"type": "websocket", "path": path}, receive, send)
    return sent
