"""Complete CLI for operating Unigate."""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import yaml

from .adapters import InternalAdapter
from .kernel import Exchange
from .storage_config import StorageConfig, StorageFactory
from .stores import InMemoryStores, NamespacedSecureStore, SQLiteStores, FileStores


DEFAULT_SOCKET_PATH = Path.home() / ".unigate" / "daemon.sock"
DEFAULT_PID_PATH = Path.home() / ".unigate" / "daemon.pid"


def get_daemon_paths() -> tuple[Path, Path]:
    return DEFAULT_SOCKET_PATH, DEFAULT_PID_PATH


def build_exchange(
    config_path: str | None = None,
    storage_backend: str = "memory",
    storage_path: str | None = None,
    retention_days: int = 7,
) -> Exchange:
    """Build exchange with specified storage backend."""
    storage_config = StorageConfig(
        backend=storage_backend,
        path=storage_path,
        retention_days=retention_days,
    )
    
    inbox, outbox, sessions, dedup, interactions = StorageFactory.create_stores(
        storage_config, namespace="default"
    )
    
    exchange = Exchange(
        inbox=inbox,
        outbox=outbox,
        sessions=sessions,
        dedup=dedup,
        interactions=interactions,
        default_storage=storage_config,
    )
    store = NamespacedSecureStore()
    adapter = InternalAdapter("default", store.for_instance("default"), exchange)
    exchange.register_instance("default", adapter)
    exchange.set_retry_policy("default", max_attempts=5, retry_base_seconds=2, retry_max_seconds=30)
    return exchange


def send_daemon_command(command: dict[str, Any]) -> dict[str, Any]:
    """Send command to running daemon via Unix socket."""
    socket_path, _ = get_daemon_paths()
    if not socket_path.exists():
        return {"error": "daemon not running"}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect(str(socket_path))
            sock.sendall((json.dumps(command) + "\n").encode())
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\n" in response:
                    break
            return json.loads(response.decode().strip())
    except Exception as exc:
        return {"error": str(exc)}


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle incoming daemon client connection."""
    try:
        data = await reader.readuntil(b"\n")
        command = json.loads(data.decode().strip())
        response = await _process_command(command)
        writer.write((json.dumps(response) + "\n").encode())
        await writer.drain()
    except Exception as exc:
        error_response = json.dumps({"error": str(exc)})
        writer.write((error_response + "\n").encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def _process_command(command: dict[str, Any]) -> dict[str, Any]:
    """Process command from daemon client."""
    cmd = command.get("command")
    args = command.get("args", {})
    
    if cmd == "status":
        instances_status = _daemon_exchange.instance_manager.status()
        return {
            "uptime": time.time() - _start_time,
            "instances": list(_daemon_exchange.instances.keys()),
            "instances_detail": instances_status,
            "events_count": len(_daemon_exchange.events),
        }
    
    if cmd == "instances":
        return _daemon_exchange.instance_manager.status()
    
    if cmd == "instances_health":
        results = {}
        for instance_id in _daemon_exchange.instances:
            try:
                health = await _daemon_exchange.instance_manager.health(instance_id)
                results[instance_id] = {"status": health.value, "ok": health.value == "healthy"}
            except Exception as e:
                results[instance_id] = {"status": "error", "error": str(e), "ok": False}
        return results
    
    if cmd == "inbox_list":
        limit = args.get("limit", 50)
        instance_filter = args.get("instance")
        records = await _daemon_exchange._inbox.list_inbox(limit=limit * 10)
        if instance_filter:
            records = [r for r in records if r.instance_id == instance_filter]
        records = records[:limit]
        return {
            "count": len(records),
            "records": [
                {
                    "message_id": r.message_id,
                    "instance_id": r.instance_id,
                    "received_at": r.received_at.isoformat(),
                    "text": r.message.text[:50] if r.message.text else "(no text)",
                    "sender": r.message.sender.name,
                }
                for r in records
            ],
        }
    
    if cmd == "inbox_show":
        msg_id = args.get("message_id")
        records = await _daemon_exchange._inbox.list_inbox(limit=10000)
        for r in records:
            if r.message_id == msg_id:
                return {
                    "message_id": r.message_id,
                    "instance_id": r.instance_id,
                    "received_at": r.received_at.isoformat(),
                    "message": _message_to_dict(r.message),
                    "full_message": _message_to_full_dict(r.message),
                }
        return {"error": "message not found"}
    
    if cmd == "inbox_replay":
        msg_id = args.get("message_id")
        records = await _daemon_exchange._inbox.list_inbox(limit=10000)
        for r in records:
            if r.message_id == msg_id:
                await _daemon_exchange.ingest(r.instance_id, r.message.raw)
                return {"ok": True, "message_id": msg_id}
        return {"error": "message not found"}
    
    if cmd == "inbox_skip":
        msg_id = args.get("message_id")
        await _daemon_exchange.emit_event(
            _daemon_exchange.events[0].__class__(name="inbox.skipped", payload={"message_id": msg_id})
        )
        return {"ok": True, "message_id": msg_id, "action": "skipped"}
    
    if cmd == "outbox_list":
        limit = args.get("limit", 50)
        instance_filter = args.get("instance")
        status_filter = args.get("status")
        records = await _daemon_exchange._outbox.list_outbox(limit=limit * 10)
        if instance_filter:
            records = [r for r in records if r.destination == instance_filter]
        if status_filter:
            records = [r for r in records if r.status == status_filter]
        records = records[:limit]
        return {
            "count": len(records),
            "records": [
                {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "status": r.status,
                    "attempts": r.attempts,
                    "last_error": r.last_error[:100] if r.last_error else None,
                    "next_retry": r.next_attempt_at.isoformat() if r.next_attempt_at else None,
                }
                for r in records
            ],
        }
    
    if cmd == "outbox_show":
        outbox_id = args.get("outbox_id")
        records = await _daemon_exchange._outbox.list_outbox(limit=10000)
        for r in records:
            if r.outbox_id == outbox_id:
                return {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "status": r.status,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                    "next_retry": r.next_attempt_at.isoformat() if r.next_attempt_at else None,
                    "message": _message_to_full_dict(r.message),
                }
        return {"error": "outbox record not found"}
    
    if cmd == "outbox_retry":
        await _daemon_exchange.flush_outbox()
        return {"ok": True}
    
    if cmd == "outbox_fail":
        outbox_id = args.get("outbox_id")
        await _daemon_exchange._outbox.move_to_dead_letter(outbox_id, "manual fail")
        return {"ok": True, "outbox_id": outbox_id}
    
    if cmd == "outbox_skip":
        outbox_id = args.get("outbox_id")
        records = await _daemon_exchange._outbox.list_outbox(limit=10000)
        for r in records:
            if r.outbox_id == outbox_id:
                await _daemon_exchange._outbox.mark_sent(outbox_id)
                return {"ok": True, "outbox_id": outbox_id, "action": "skipped"}
        return {"error": "outbox record not found"}
    
    if cmd == "dead_letters":
        limit = args.get("limit", 50)
        records = await _daemon_exchange._outbox.list_dead_letters(limit=limit)
        return {
            "count": len(records),
            "records": [
                {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "attempts": r.attempts,
                    "last_error": r.last_error[:100] if r.last_error else None,
                    "failed_at": r.failed_at.isoformat(),
                }
                for r in records
            ],
        }
    
    if cmd == "dead_letters_show":
        outbox_id = args.get("outbox_id")
        records = await _daemon_exchange._outbox.list_dead_letters(limit=10000)
        for r in records:
            if r.outbox_id == outbox_id:
                return {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                    "failed_at": r.failed_at.isoformat(),
                    "message": _message_to_full_dict(r.message),
                }
        return {"error": "dead letter not found"}
    
    if cmd == "dead_letters_requeue":
        outbox_id = args.get("outbox_id")
        records = await _daemon_exchange._outbox.list_dead_letters(limit=10000)
        for r in records:
            if r.outbox_id == outbox_id:
                await _daemon_exchange.enqueue_outbound(r.destination, r.message)
                return {"ok": True, "outbox_id": outbox_id, "action": "requeued"}
        return {"error": "dead letter not found"}
    
    if cmd == "send":
        to = args.get("to", "default")
        text = args.get("text", "")
        session_id = args.get("session_id", f"cli-{int(time.time())}")
        from .message import Message, Sender
        msg = Message(
            id=f"cli-{int(time.time() * 1000)}",
            session_id=session_id,
            from_instance="cli",
            sender=Sender(platform_id="cli", name="CLI"),
            ts=datetime.now(),
            text=text,
        )
        await _daemon_exchange.enqueue_outbound("cli", msg)
        await _daemon_exchange.flush_outbox()
        return {"ok": True, "message_id": msg.id, "session_id": session_id, "to": to}
    
    if cmd == "logs":
        limit = args.get("limit", 100)
        events = _daemon_exchange.events[-limit:]
        return {
            "count": len(events),
            "events": [
                {"name": e.name, "payload": e.payload, "timestamp": e.timestamp.isoformat() if hasattr(e, 'timestamp') else None}
                for e in events
            ],
        }
    
    if cmd == "cleanup":
        deleted = await _daemon_exchange.run_cleanup_once()
        return {"ok": True, "deleted_count": deleted}
    
    if cmd == "ping":
        return {"pong": True, "timestamp": time.time()}
    
    return {"error": f"unknown command: {cmd}"}


def _message_to_dict(msg: Any) -> dict:
    """Convert message to dict for JSON serialization."""
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "from_instance": msg.from_instance,
        "text": msg.text[:100] if msg.text else None,
        "sender": {"platform_id": msg.sender.platform_id, "name": msg.sender.name},
        "group_id": msg.group_id,
        "thread_id": msg.thread_id,
        "has_media": len(msg.media) > 0 if msg.media else False,
        "has_interactive": msg.interactive is not None,
    }


def _message_to_full_dict(msg: Any) -> dict:
    """Convert full message to dict for JSON serialization."""
    return {
        "id": msg.id,
        "platform_id": msg.platform_id,
        "session_id": msg.session_id,
        "from_instance": msg.from_instance,
        "to": msg.to,
        "sender": {
            "platform_id": msg.sender.platform_id,
            "name": msg.sender.name,
            "handle": msg.sender.handle,
            "is_bot": msg.sender.is_bot,
        },
        "ts": msg.ts.isoformat() if msg.ts else None,
        "text": msg.text,
        "group_id": msg.group_id,
        "thread_id": msg.thread_id,
        "receiver_id": msg.receiver_id,
        "bot_mentioned": msg.bot_mentioned,
        "media": [
            {
                "media_id": m.media_id,
                "type": m.type.value if hasattr(m.type, 'value') else str(m.type),
                "mime_type": m.mime_type,
                "filename": m.filename,
            }
            for m in (msg.media or [])
        ],
        "interactive": {
            "interaction_id": msg.interactive.interaction_id,
            "type": msg.interactive.type,
            "prompt": msg.interactive.prompt,
            "options": msg.interactive.options,
        } if msg.interactive else None,
        "actions": [{"type": a.type} for a in (msg.actions or [])],
        "reply_to_id": msg.reply_to_id,
        "edit_of_id": msg.edit_of_id,
        "deleted_id": msg.deleted_id,
        "metadata": msg.metadata,
        "raw": msg.raw if len(str(msg.raw)) < 2000 else {"truncated": True},
    }


_daemon_exchange: Exchange | None = None
_daemon_shutdown: threading.Event | None = None
_start_time: float = 0


async def _daemon_async(exchange: Exchange, socket_path: Path, shutdown_event: threading.Event) -> None:
    """Run daemon async main loop."""
    global _daemon_exchange, _start_time
    _daemon_exchange = exchange
    _start_time = time.time()
    
    # Start cleanup task
    await exchange.start_cleanup_task()
    
    if socket_path.exists():
        socket_path.unlink()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    server = await asyncio.start_unix_server(_handle_client, path=str(socket_path))
    
    async with server:
        while not shutdown_event.is_set():
            await asyncio.sleep(0.5)
    
    socket_path.unlink(missing_ok=True)


def _get_daemon_exchange(
    storage_backend: str = "memory",
    storage_path: str | None = None,
    retention_days: int = 7,
) -> tuple[Exchange, threading.Event]:
    """Get or create daemon exchange instance."""
    global _daemon_exchange, _daemon_shutdown
    if _daemon_exchange is None:
        _daemon_exchange = build_exchange(
            storage_backend=storage_backend,
            storage_path=storage_path,
            retention_days=retention_days,
        )
        _daemon_shutdown = threading.Event()
    return _daemon_exchange, _daemon_shutdown


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="unigate",
        description="Universal messaging exchange - route messages between channels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start daemon
  unigate start
  unigate start --backend sqlite
  unigate start -f

  # Check status
  unigate status
  unigate health

  # Manage instances
  unigate instances list
  unigate instances status

  # View messages
  unigate inbox list
  unigate inbox show <message_id>
  unigate inbox replay <message_id>
  unigate inbox --instance my_bot list

  # Manage outbox
  unigate outbox list
  unigate outbox show <outbox_id>
  unigate outbox retry
  unigate outbox fail <outbox_id>

  # Dead letters
  unigate dead-letters
  unigate dead-letters show <outbox_id>
  unigate dead-letters requeue <outbox_id>

  # Send test message
  unigate send --to my_bot --text "Hello world"

  # Cleanup
  unigate cleanup

  # Plugin management
  unigate plugins list
  unigate plugins status
  unigate plugins enable telegram
  unigate plugins gen-config --output unigate.yaml
        """
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file (YAML)",
    )
    parser.add_argument(
        "--backend",
        choices=["memory", "sqlite", "file"],
        default="memory",
        help="Storage backend to use (default: memory)",
    )
    parser.add_argument(
        "--storage-path",
        help="Path for storage (SQLite db file or FileStores base directory). Default: ~/.unigate/",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=7,
        help="Days to retain sent messages before cleanup (default: 7)",
    )
    
    sub = parser.add_subparsers(dest="command", required=True)
    
    # Status command
    status_parser = sub.add_parser(
        "status",
        help="Show daemon status and uptime",
        description="Show current daemon status, uptime, and instance count",
    )
    
    # Health command
    health_parser = sub.add_parser(
        "health",
        help="Check health of all instances",
        description="Check the health status of all registered instances",
    )
    
    # Start command
    start_parser = sub.add_parser(
        "start",
        help="Start unigate server",
        description="Start the unigate server with HTTP routes and all configured instances.",
    )
    start_parser.add_argument(
        "--config", "-c",
        default="unigate.yaml",
        help="Path to configuration file (default: unigate.yaml)",
    )
    start_parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground instead of background",
    )
    start_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    start_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    start_parser.add_argument(
        "--mount-prefix",
        default="/unigate",
        help="URL prefix for all routes (default: /unigate)",
    )
    start_parser.add_argument(
        "--storage-path",
        help="Path for storage (overrides config)",
    )
    start_parser.add_argument(
        "--retention",
        type=int,
        default=7,
        help="Days to retain sent messages (default: 7)",
    )
    
    # Stop command
    stop_parser = sub.add_parser(
        "stop",
        help="Stop running daemon",
        description="Stop the background daemon. Sends shutdown signal and cleans up.",
    )
    
    # Cleanup command
    cleanup_parser = sub.add_parser(
        "cleanup",
        help="Run cleanup of old data",
        description="Run cleanup to delete old sent messages and dedup keys. Works with or without daemon.",
    )
    cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    
    # Logs command
    logs_parser = sub.add_parser(
        "logs",
        help="Show recent events",
        description="Show recent kernel events for debugging",
    )
    logs_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=100,
        help="Number of events to show (default: 100)",
    )
    logs_parser.add_argument(
        "--type", "-t",
        dest="event_type",
        help="Filter by event name prefix (e.g., 'outbox.', 'health.')",
    )
    
    # Instances command
    inst_parser = sub.add_parser(
        "instances",
        help="Instance management",
        description="Manage messaging channel instances",
    )
    inst_sub = inst_parser.add_subparsers(dest="subcommand", required=True)
    
    inst_list = inst_sub.add_parser(
        "list",
        help="List all instances",
        description="List all registered channel instances with their states",
    )
    inst_list.add_argument(
        "--state",
        choices=["active", "degraded", "unconfigured", "setup_required"],
        help="Filter by instance state",
    )
    
    inst_status = inst_sub.add_parser(
        "status",
        help="Show instance details",
        description="Show detailed status of all instances including retry policy and errors",
    )
    inst_status.add_argument(
        "instance_id",
        nargs="?",
        help="Specific instance to show (optional, shows all if omitted)",
    )
    
    inst_enable = inst_sub.add_parser(
        "enable",
        help="Enable an instance",
        description="Enable a disabled instance",
    )
    inst_enable.add_argument("instance_id", help="Instance name to enable")
    
    inst_disable = inst_sub.add_parser(
        "disable",
        help="Disable an instance",
        description="Disable an instance (stops processing)",
    )
    inst_disable.add_argument("instance_id", help="Instance name to disable")
    
    # Inbox command
    inbox_parser = sub.add_parser(
        "inbox",
        help="Inbox message operations",
        description="View and manage received messages in the inbox",
    )
    inbox_sub = inbox_parser.add_subparsers(dest="subcommand", required=True)
    
    inbox_list = inbox_sub.add_parser(
        "list",
        help="List inbox messages",
        description="List messages received by the exchange",
    )
    inbox_list.add_argument(
        "--limit", "-n",
        type=int,
        default=50,
        help="Maximum messages to show (default: 50)",
    )
    inbox_list.add_argument(
        "--instance", "-i",
        dest="instance",
        help="Filter by instance name",
    )
    inbox_list.add_argument(
        "--since",
        help="Show messages received since timestamp (ISO format)",
    )
    
    inbox_show = inbox_sub.add_parser(
        "show",
        help="Show message details",
        description="Show full details of a specific message",
    )
    inbox_show.add_argument(
        "message_id",
        help="Message ID to display",
    )
    inbox_show.add_argument(
        "--full",
        action="store_true",
        help="Show full message including raw payload",
    )
    
    inbox_replay = inbox_sub.add_parser(
        "replay",
        help="Replay a message",
        description="Re-process a message through the exchange (for debugging)",
    )
    inbox_replay.add_argument(
        "message_id",
        help="Message ID to replay",
    )
    
    inbox_skip = inbox_sub.add_parser(
        "skip",
        help="Skip a message",
        description="Mark a message as skipped (emits skip event without processing)",
    )
    inbox_skip.add_argument(
        "message_id",
        help="Message ID to skip",
    )
    
    # Outbox command
    outbox_parser = sub.add_parser(
        "outbox",
        help="Outbox message operations",
        description="View and manage pending outbound messages",
    )
    outbox_sub = outbox_parser.add_subparsers(dest="subcommand", required=True)
    
    outbox_list = outbox_sub.add_parser(
        "list",
        help="List outbox messages",
        description="List pending and failed outbound messages",
    )
    outbox_list.add_argument(
        "--limit", "-n",
        type=int,
        default=50,
        help="Maximum messages to show (default: 50)",
    )
    outbox_list.add_argument(
        "--instance", "-i",
        dest="instance",
        help="Filter by destination instance",
    )
    outbox_list.add_argument(
        "--status", "-s",
        choices=["pending", "retry", "sent", "failed"],
        help="Filter by message status",
    )
    
    outbox_show = outbox_sub.add_parser(
        "show",
        help="Show outbox record",
        description="Show full details of an outbox record",
    )
    outbox_show.add_argument(
        "outbox_id",
        help="Outbox ID to display",
    )
    outbox_show.add_argument(
        "--full",
        action="store_true",
        help="Show full message content",
    )
    
    outbox_retry = outbox_sub.add_parser(
        "retry",
        help="Retry failed messages",
        description="Retry all pending/failed outbox messages",
    )
    outbox_retry.add_argument(
        "--instance",
        help="Retry only messages for specific instance",
    )
    
    outbox_fail = outbox_sub.add_parser(
        "fail",
        help="Mark message as failed",
        description="Manually mark a message as failed (moves to dead letters)",
    )
    outbox_fail.add_argument(
        "outbox_id",
        help="Outbox ID to mark as failed",
    )
    
    outbox_skip = outbox_sub.add_parser(
        "skip",
        help="Skip a message (mark as sent)",
        description="Mark a message as sent without actually sending (use with caution)",
    )
    outbox_skip.add_argument(
        "outbox_id",
        help="Outbox ID to skip",
    )
    
    # Dead letters command
    dead_parser = sub.add_parser(
        "dead-letters",
        help="Dead letter queue operations",
        description="View and manage messages that failed permanently",
    )
    dead_sub = dead_parser.add_subparsers(dest="subcommand", required=True)
    
    dead_list = dead_sub.add_parser(
        "list",
        help="List dead letters",
        description="List messages in the dead letter queue",
    )
    dead_list.add_argument(
        "--limit", "-n",
        type=int,
        default=50,
        help="Maximum records to show (default: 50)",
    )
    dead_list.add_argument(
        "--instance",
        help="Filter by destination instance",
    )
    
    dead_show = dead_sub.add_parser(
        "show",
        help="Show dead letter details",
        description="Show full details of a dead letter record",
    )
    dead_show.add_argument(
        "outbox_id",
        help="Dead letter outbox ID to display",
    )
    
    dead_requeue = dead_sub.add_parser(
        "requeue",
        help="Requeue a dead letter",
        description="Re-queue a dead letter message for delivery",
    )
    dead_requeue.add_argument(
        "outbox_id",
        help="Dead letter outbox ID to requeue",
    )
    
    dead_purge = dead_sub.add_parser(
        "purge",
        help="Purge dead letters",
        description="Delete all dead letter records (use with caution)",
    )
    dead_purge.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm purge operation",
    )
    
    # Send command
    send_parser = sub.add_parser(
        "send",
        help="Send a test message",
        description="Send a test message to an instance via the outbox",
    )
    send_parser.add_argument(
        "--to", "-t",
        required=True,
        help="Destination instance name",
    )
    send_parser.add_argument(
        "--text",
        required=True,
        help="Message text to send",
    )
    send_parser.add_argument(
        "--session",
        help="Session ID (auto-generated if not provided)",
    )
    send_parser.add_argument(
        "--group",
        help="Group ID for group messages",
    )
    
    # Plugins command
    plug_parser = sub.add_parser(
        "plugins",
        help="Plugin management",
        description="Manage channel, matcher, transform, and transport plugins",
    )
    plug_sub = plug_parser.add_subparsers(dest="subcommand", required=True)
    
    plug_list = plug_sub.add_parser(
        "list",
        help="List all plugins",
        description="List all available plugins by type",
    )
    plug_list.add_argument(
        "--type", "-t",
        choices=["channel", "match", "transform", "transport"],
        help="Filter by plugin type",
    )
    plug_list.add_argument(
        "--enabled", "-e",
        action="store_true",
        help="Show only enabled plugins",
    )
    plug_list.add_argument(
        "--disabled", "-d",
        action="store_true",
        help="Show only disabled plugins",
    )
    
    plug_status = plug_sub.add_parser(
        "status",
        help="Show plugin status",
        description="Show detailed status of plugins",
    )
    plug_status.add_argument(
        "plugin",
        nargs="?",
        help="Specific plugin to check (shows summary if omitted)",
    )
    
    plug_enable = plug_sub.add_parser(
        "enable",
        help="Enable a plugin",
        description="Enable a disabled plugin",
    )
    plug_enable.add_argument("plugin", help="Plugin name to enable")
    
    plug_disable = plug_sub.add_parser(
        "disable",
        help="Disable a plugin",
        description="Disable an enabled plugin",
    )
    plug_disable.add_argument("plugin", help="Plugin name to disable")
    
    plug_gen = plug_sub.add_parser(
        "gen-config",
        help="Generate config template",
        description="Generate a configuration file template from available plugins",
    )
    plug_gen.add_argument(
        "--output", "-o",
        help="Output file path (prints to stdout if not specified)",
    )
    
    plug_validate = plug_sub.add_parser(
        "validate",
        help="Validate configuration",
        description="Validate a configuration file against available plugins",
    )
    plug_validate.add_argument(
        "--config", "-c",
        required=True,
        help="Configuration file to validate",
    )
    
    args = parser.parse_args(list(argv) if argv is not None else None)
    socket_path, pid_path = get_daemon_paths()
    
    # Handle commands
    if args.command == "start":
        from .runtime import create_app
        from .gate import Unigate
        
        config_path = args.config
        if not Path(config_path).exists():
            print(f"Config file not found: {config_path}", file=sys.stderr)
            print("Creating default config...")
            default_config = """# Unigate Configuration
unigate:
  mount_prefix: /unigate

storage:
  backend: memory

instances:
  web:
    type: webui
"""
            Path(config_path).write_text(default_config)
            print(f"Created: {config_path}")
            print("Edit the config file and run 'unigate start' again")
            return 1
        
        try:
            gate = Unigate.from_config(config_path)
        except Exception as e:
            print(f"Failed to load config: {e}", file=sys.stderr)
            return 1
        
        exchange = gate._exchange
        storage_path = getattr(args, 'storage_path', None)
        retention = getattr(args, 'retention', 7)
        host = getattr(args, 'host', '0.0.0.0')
        port = getattr(args, 'port', 8080)
        mount_prefix = getattr(args, 'mount_prefix', '/unigate')
        
        if args.foreground:
            print(f"\n{'='*60}")
            print("Unigate Server")
            print(f"{'='*60}")
            print(f"  Config: {config_path}")
            print(f"  Server: http://{host}:{port}{mount_prefix}/")
            print(f"\nRoutes:")
            print(f"  GET  {mount_prefix}/status      - Status dashboard")
            print(f"  GET  {mount_prefix}/health     - Health check")
            print(f"  GET  {mount_prefix}/instances  - Instance list")
            for instance_id, inst in exchange.instances.items():
                channel = inst.channel if hasattr(inst, "channel") else inst
                name = getattr(channel, "name", None)
                if name == "webui":
                    print(f"  GET  {mount_prefix}/web/{instance_id}    - Web UI")
                else:
                    print(f"  POST {mount_prefix}/webhook/{instance_id} - Webhook")
            print(f"\nInstances:")
            for instance_id, inst in exchange.instances.items():
                channel = inst.channel if hasattr(inst, "channel") else inst
                state = "active"
                if hasattr(channel, "state"):
                    s = channel.state
                    state = s.value if hasattr(s, "value") else str(s)
                print(f"  [{state}] {instance_id}")
            print(f"\n{'='*60}")
            print("Press Ctrl+C to stop\n")
            
            app = create_app(exchange=exchange, mount_prefix=mount_prefix, port=port)
            for instance_id, inst in exchange.instances.items():
                channel = inst.channel if hasattr(inst, "channel") else inst
                if getattr(channel, "name", None) == "webui":
                    app.register_webui(instance_id, channel)
            
            for inst in exchange.instances.values():
                channel = inst.channel if hasattr(inst, "channel") else inst
                try:
                    if hasattr(channel, "setup"):
                        asyncio.run(channel.setup())
                    if hasattr(channel, "start"):
                        asyncio.run(channel.start())
                except Exception as e:
                    print(f"Warning: Failed to start instance: {e}", file=sys.stderr)
            
            try:
                import uvicorn
                uvicorn.run(app, host=host, port=port, log_level="info")
            except ImportError:
                print("uvicorn not installed. Install with: pip install uvicorn")
                return 1
            except KeyboardInterrupt:
                print("\nShutting down...")
            finally:
                for inst in exchange.instances.values():
                    channel = inst.channel if hasattr(inst, "channel") else inst
                    try:
                        if hasattr(channel, "stop"):
                            asyncio.run(channel.stop())
                    except Exception:
                        pass
            return 0
        
        def run_server():
            async def _run():
                app = create_app(exchange=exchange, mount_prefix=mount_prefix, port=port)
                for instance_id, inst in exchange.instances.items():
                    channel = inst.channel if hasattr(inst, "channel") else inst
                    if getattr(channel, "name", None) == "webui":
                        app.register_webui(instance_id, channel)
                
                for inst in exchange.instances.values():
                    channel = inst.channel if hasattr(inst, "channel") else inst
                    try:
                        if hasattr(channel, "setup"):
                            await channel.setup()
                        if hasattr(channel, "start"):
                            await channel.start()
                    except Exception:
                        pass
                
                import uvicorn
                config = uvicorn.Config(app, host=host, port=port, log_level="warning")
                server = uvicorn.Server(config)
                await server.serve()
            
            asyncio.run(_run())
        
        proc = ctx.Process(target=run_server, daemon=True)
        proc.start()
        
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(proc.pid))
        
        time.sleep(0.5)
        if proc.is_alive():
            print(f"Unigate started (PID: {proc.pid})")
            print(f"  Config: {config_path}")
            print(f"  Server: http://{host}:{port}{mount_prefix}/")
            print(f"  Routes:")
            print(f"    GET  {mount_prefix}/status     - Status")
            print(f"    GET  {mount_prefix}/health    - Health")
            print(f"    GET  {mount_prefix}/instances - Instances")
            for instance_id, inst in exchange.instances.items():
                channel = inst.channel if hasattr(inst, "channel") else inst
                name = getattr(channel, "name", None)
                if name == "webui":
                    print(f"    GET  {mount_prefix}/web/{instance_id}  - Web UI")
                else:
                    print(f"    POST {mount_prefix}/webhook/{instance_id} - Webhook")
            return 0
        else:
            print("Failed to start unigate", file=sys.stderr)
            return 1
    
    if args.command == "stop":
        if not socket_path.exists():
            print("daemon not running", file=sys.stderr)
            return 1
        
        send_daemon_command({"command": "shutdown"})
        
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text())
                os.kill(pid, 9)
            except Exception:
                pass
            pid_path.unlink()
        
        socket_path.unlink(missing_ok=True)
        print("Daemon stopped")
        return 0
    
    if args.command == "status":
        if socket_path.exists():
            response = send_daemon_command({"command": "status"})
            print(json.dumps(response, indent=2))
        else:
            exchange = build_exchange(storage_backend=args.backend)
            print(json.dumps({
                "daemon": "not running",
                "instances": list(exchange.instances.keys()),
            }, indent=2))
        return 0
    
    if args.command == "health":
        if socket_path.exists():
            response = send_daemon_command({"command": "instances_health"})
            print(json.dumps(response, indent=2))
        else:
            print("daemon not running", file=sys.stderr)
            return 1
        return 0
    
    if args.command == "logs":
        if socket_path.exists():
            response = send_daemon_command({"command": "logs", "args": {"limit": args.limit}})
            print(json.dumps(response, indent=2))
        else:
            print("daemon not running", file=sys.stderr)
            return 1
        return 0
    
    if args.command == "cleanup":
        if socket_path.exists():
            response = send_daemon_command({"command": "cleanup"})
            print(json.dumps(response, indent=2))
        else:
            exchange = build_exchange(storage_backend=args.backend)
            deleted = asyncio.run(exchange.run_cleanup_once())
            print(json.dumps({"ok": True, "deleted_count": deleted, "daemon": "standalone"}, indent=2))
        return 0
    
    if args.command == "send":
        if socket_path.exists():
            response = send_daemon_command({
                "command": "send",
                "args": {
                    "to": args.to,
                    "text": args.text,
                    "session_id": args.session,
                }
            })
            print(json.dumps(response, indent=2))
        else:
            print("daemon not running", file=sys.stderr)
            return 1
        return 0
    
    if args.command == "dead-letters":
        if not socket_path.exists():
            print("daemon not running", file=sys.stderr)
            return 1
        
        if args.subcommand == "list":
            response = send_daemon_command({"command": "dead_letters", "args": {"limit": args.limit}})
            print(json.dumps(response, indent=2))
        elif args.subcommand == "show":
            response = send_daemon_command({"command": "dead_letters_show", "args": {"outbox_id": args.outbox_id}})
            print(json.dumps(response, indent=2))
        elif args.subcommand == "requeue":
            response = send_daemon_command({"command": "dead_letters_requeue", "args": {"outbox_id": args.outbox_id}})
            print(json.dumps(response, indent=2))
        elif args.subcommand == "purge":
            if not args.confirm:
                print("Use --confirm to actually purge dead letters", file=sys.stderr)
                return 1
            response = send_daemon_command({"command": "dead_letters_purge"})
            print(json.dumps(response, indent=2))
        return 0
    
    # Commands that work with or without daemon
    if args.command == "instances":
        if socket_path.exists():
            response = send_daemon_command({"command": "instances"})
            print(json.dumps(response, indent=2))
        else:
            exchange = build_exchange(storage_backend=args.backend)
            response = exchange.instance_manager.status()
            print(json.dumps(response, indent=2))
        return 0
    
    if args.command == "inbox":
        if socket_path.exists():
            if args.subcommand == "list":
                response = send_daemon_command({"command": "inbox_list", "args": {
                    "limit": args.limit,
                    "instance": args.instance,
                }})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "show":
                response = send_daemon_command({"command": "inbox_show", "args": {"message_id": args.message_id}})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "replay":
                response = send_daemon_command({"command": "inbox_replay", "args": {"message_id": args.message_id}})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "skip":
                response = send_daemon_command({"command": "inbox_skip", "args": {"message_id": args.message_id}})
                print(json.dumps(response, indent=2))
            else:
                print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
                return 1
        else:
            print("daemon not running - inbox operations require daemon", file=sys.stderr)
            return 1
        return 0
    
    if args.command == "outbox":
        if socket_path.exists():
            if args.subcommand == "list":
                response = send_daemon_command({"command": "outbox_list", "args": {
                    "limit": args.limit,
                    "instance": args.instance,
                    "status": args.status,
                }})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "show":
                response = send_daemon_command({"command": "outbox_show", "args": {"outbox_id": args.outbox_id}})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "retry":
                response = send_daemon_command({"command": "outbox_retry"})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "fail":
                response = send_daemon_command({"command": "outbox_fail", "args": {"outbox_id": args.outbox_id}})
                print(json.dumps(response, indent=2))
            elif args.subcommand == "skip":
                response = send_daemon_command({"command": "outbox_skip", "args": {"outbox_id": args.outbox_id}})
                print(json.dumps(response, indent=2))
            else:
                print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
                return 1
        else:
            print("daemon not running - outbox operations require daemon", file=sys.stderr)
            return 1
        return 0
    
    # Plugin management commands (work without daemon)
    if args.command == "plugins":
        from .plugins.base import get_registry
        
        registry = get_registry()
        
        if args.subcommand == "list":
            plugins = registry.list_plugins()
            
            for p in plugins:
                if args.type and p.type != args.type:
                    continue
                if args.enabled and not p.enabled:
                    continue
                if args.disabled and p.enabled:
                    continue
                
                status = "[+]" if p.enabled else "[-]"
                print(f"{status} {p.type:10} {p.full_name}")
            return 0
        
        if args.subcommand == "status":
            if args.plugin:
                full_name = registry._resolve_name(args.plugin)
                found = False
                for reg_name, entry in list(registry.channels.items()) + list(registry.matches.items()) + list(registry.transforms.items()) + list(registry.transports.items()):
                    if reg_name == full_name:
                        print(f"Plugin: {reg_name}")
                        print(f"  Type: {entry.cls.type}")
                        print(f"  Enabled: {entry.enabled}")
                        print(f"  Source: {entry.source}")
                        print(f"  Description: {getattr(entry.cls, 'description', '')}")
                        found = True
                        break
                if not found:
                    print(f"Plugin '{args.plugin}' not found", file=sys.stderr)
                    return 1
            else:
                plugins = registry.list_plugins()
                total = len(plugins)
                enabled = sum(1 for p in plugins if p.enabled)
                by_type = {}
                for p in plugins:
                    by_type.setdefault(p.type, []).append(p.full_name)
                
                print("Plugin Summary:")
                print(f"  Total: {total}")
                print(f"  Enabled: {enabled}")
                print(f"  Disabled: {total - enabled}")
                print()
                for ptype, names in sorted(by_type.items()):
                    print(f"  {ptype}s ({len(names)}): {', '.join(sorted(names))}")
            return 0
        
        if args.subcommand == "enable":
            if registry.enable(args.plugin):
                print(f"Enabled: {args.plugin}")
                return 0
            else:
                print(f"Plugin '{args.plugin}' not found", file=sys.stderr)
                return 1
        
        if args.subcommand == "disable":
            if registry.disable(args.plugin):
                print(f"Disabled: {args.plugin}")
                return 0
            else:
                print(f"Plugin '{args.plugin}' not found", file=sys.stderr)
                return 1
        
        if args.subcommand == "gen-config":
            config = registry.generate_config()
            output = args.output
            if output:
                Path(output).write_text(yaml.dump(config, default_flow_style=False))
                print(f"Config written to: {output}")
            else:
                print(yaml.dump(config, default_flow_style=False))
            return 0
        
        if args.subcommand == "validate":
            if args.config:
                with open(args.config) as f:
                    config = yaml.safe_load(f)
            else:
                print("No config file specified", file=sys.stderr)
                return 1
            
            from .routing import load_rules_from_config
            rules, warnings = load_rules_from_config(config, strict=False)
            
            print(f"Rules loaded: {len(rules)}")
            if warnings:
                print(f"Warnings: {len(warnings)}")
                for w in warnings:
                    print(f"  - {w}")
            else:
                print("No warnings")
            return 0
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
