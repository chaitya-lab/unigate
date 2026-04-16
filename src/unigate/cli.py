"""Complete CLI for operating Unigate."""

from __future__ import annotations

import argparse
import asyncio
import json
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
from .stores import InMemoryStores, NamespacedSecureStore


DEFAULT_SOCKET_PATH = Path.home() / ".unigate" / "daemon.sock"
DEFAULT_PID_PATH = Path.home() / ".unigate" / "daemon.pid"


def get_daemon_paths() -> tuple[Path, Path]:
    return DEFAULT_SOCKET_PATH, DEFAULT_PID_PATH


def build_exchange(config_path: str | None = None) -> Exchange:
    memory = InMemoryStores()
    exchange = Exchange(inbox=memory, outbox=memory, sessions=memory, dedup=memory)
    store = NamespacedSecureStore()
    adapter = InternalAdapter("default", store.for_instance("default"), exchange)
    exchange.register_instance("default", adapter)
    exchange.set_retry_policy("default", max_attempts=5, retry_base_seconds=2, retry_max_seconds=30)
    return exchange


def send_daemon_command(command: dict[str, Any]) -> dict[str, Any]:
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
        records = await _daemon_exchange._inbox.list_inbox(limit=limit)
        return {
            "count": len(records),
            "records": [
                {
                    "message_id": r.message_id,
                    "instance_id": r.instance_id,
                    "received_at": r.received_at.isoformat(),
                }
                for r in records
            ],
        }
    
    if cmd == "inbox_show":
        msg_id = args.get("message_id")
        records = await _daemon_exchange._inbox.list_inbox(limit=1000)
        for r in records:
            if r.message_id == msg_id:
                return {
                    "message_id": r.message_id,
                    "instance_id": r.instance_id,
                    "received_at": r.received_at.isoformat(),
                    "message": _message_to_dict(r.message),
                }
        return {"error": "message not found"}
    
    if cmd == "inbox_replay":
        msg_id = args.get("message_id")
        records = await _daemon_exchange._inbox.list_inbox(limit=1000)
        for r in records:
            if r.message_id == msg_id:
                await _daemon_exchange.ingest(r.instance_id, r.message.raw)
                return {"ok": True, "message_id": msg_id}
        return {"error": "message not found"}
    
    if cmd == "outbox_list":
        limit = args.get("limit", 50)
        records = await _daemon_exchange._outbox.list_outbox(limit=limit)
        return {
            "count": len(records),
            "records": [
                {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "status": r.status,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                }
                for r in records
            ],
        }
    
    if cmd == "outbox_show":
        outbox_id = args.get("outbox_id")
        records = await _daemon_exchange._outbox.list_outbox(limit=1000)
        for r in records:
            if r.outbox_id == outbox_id:
                return {
                    "outbox_id": r.outbox_id,
                    "destination": r.destination,
                    "status": r.status,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                    "message": _message_to_dict(r.message),
                }
        return {"error": "outbox record not found"}
    
    if cmd == "outbox_retry":
        await _daemon_exchange.flush_outbox()
        return {"ok": True}
    
    if cmd == "outbox_fail":
        outbox_id = args.get("outbox_id")
        await _daemon_exchange._outbox.move_to_dead_letter(outbox_id, "manual fail")
        return {"ok": True, "outbox_id": outbox_id}
    
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
                    "last_error": r.last_error,
                    "failed_at": r.failed_at.isoformat(),
                }
                for r in records
            ],
        }
    
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
    
    if cmd == "ping":
        return {"pong": True, "timestamp": time.time()}
    
    return {"error": f"unknown command: {cmd}"}


def _message_to_dict(msg: Any) -> dict:
    """Convert message to dict for JSON serialization."""
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "from_instance": msg.from_instance,
        "text": msg.text,
        "sender": {"platform_id": msg.sender.platform_id, "name": msg.sender.name},
        "group_id": msg.group_id,
        "thread_id": msg.thread_id,
    }


_daemon_exchange: Exchange | None = None
_daemon_shutdown: threading.Event | None = None
_start_time: float = 0


async def _daemon_async(exchange: Exchange, socket_path: Path, shutdown_event: threading.Event) -> None:
    global _daemon_exchange, _start_time
    _daemon_exchange = exchange
    _start_time = time.time()
    
    if socket_path.exists():
        socket_path.unlink()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    server = await asyncio.start_unix_server(_handle_client, path=str(socket_path))
    
    async with server:
        while not shutdown_event.is_set():
            await asyncio.sleep(0.5)
    
    socket_path.unlink(missing_ok=True)


def _get_daemon_exchange() -> tuple[Exchange, threading.Event]:
    global _daemon_exchange, _daemon_shutdown
    if _daemon_exchange is None:
        _daemon_exchange = build_exchange()
        _daemon_shutdown = threading.Event()
    return _daemon_exchange, _daemon_shutdown


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="unigate", 
        description="Universal messaging exchange CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  unigate status                    Show daemon status
  unigate start                    Start daemon in background
  unigate start -f                 Start daemon in foreground
  unigate stop                     Stop daemon
  unigate instances list           List all instances
  unigate instances status         Show instance details
  unigate inbox list               List inbox messages
  unigate inbox show <id>          Show message details
  unigate inbox replay <id>        Replay a message
  unigate outbox list              List pending messages
  unigate outbox show <id>         Show outbox record
  unigate outbox retry             Retry failed messages
  unigate outbox fail <id>         Mark message as failed
  unigate dead-letters             List dead letters
  unigate send --to my_bot --text "Hello"
  unigate logs                     Show recent events
  unigate health                   Check instance health
        """
    )
    parser.add_argument("--config", help="Path to config file")
    
    sub = parser.add_subparsers(dest="command", required=True)
    
    # Status
    sub.add_parser("status", help="Show daemon status")
    
    # Start/Stop
    start = sub.add_parser("start", help="Start daemon in background")
    start.add_argument("--foreground", "-f", action="store_true", help="Run in foreground")
    
    sub.add_parser("stop", help="Stop daemon")
    
    # Health
    sub.add_parser("health", help="Check health of all instances")
    
    # Instances
    inst = sub.add_parser("instances", help="Instance operations")
    inst_sub = inst.add_subparsers(dest="subcommand", required=True)
    inst_sub.add_parser("list", help="List all instances")
    inst_sub.add_parser("status", help="Show detailed instance status")
    
    # Inbox
    inbox = sub.add_parser("inbox", help="Inbox operations")
    inbox_sub = inbox.add_subparsers(dest="subcommand", required=True)
    inbox_sub.add_parser("list", help="List inbox messages")
    inbox_show = inbox_sub.add_parser("show", help="Show message details")
    inbox_show.add_argument("message_id", help="Message ID to show")
    inbox_replay = inbox_sub.add_parser("replay", help="Replay a message")
    inbox_replay.add_argument("message_id", help="Message ID to replay")
    
    # Outbox
    outbox = sub.add_parser("outbox", help="Outbox operations")
    outbox_sub = outbox.add_subparsers(dest="subcommand", required=True)
    outbox_sub.add_parser("list", help="List pending messages")
    outbox_show = outbox_sub.add_parser("show", help="Show outbox record")
    outbox_show.add_argument("outbox_id", help="Outbox ID to show")
    outbox_sub.add_parser("retry", help="Retry failed messages")
    outbox_fail = outbox_sub.add_parser("fail", help="Mark message as failed")
    outbox_fail.add_argument("outbox_id", help="Outbox ID to fail")
    
    # Dead letters
    dead = sub.add_parser("dead-letters", help="View dead letters")
    dead.add_argument("--limit", "-n", type=int, default=50, help="Number of records to show")
    
    # Send
    send = sub.add_parser("send", help="Send a test message")
    send.add_argument("--to", default="default", help="Destination instance")
    send.add_argument("--text", required=True, help="Message text")
    send.add_argument("--session", help="Session ID")
    
    # Logs
    logs = sub.add_parser("logs", help="Show recent events")
    logs.add_argument("--limit", "-n", type=int, default=100, help="Number of events to show")
    
    # Plugins
    plug = sub.add_parser("plugins", help="Plugin management")
    plug_sub = plug.add_subparsers(dest="subcommand", required=True)
    
    plug_list = plug_sub.add_parser("list", help="List all available plugins")
    plug_list.add_argument("--type", "-t", choices=["channel", "match", "transform", "transport"], help="Filter by type")
    plug_list.add_argument("--enabled", "-e", action="store_true", help="Show only enabled")
    plug_list.add_argument("--disabled", "-d", action="store_true", help="Show only disabled")
    
    plug_status = plug_sub.add_parser("status", help="Show plugin status details")
    plug_status.add_argument("plugin", nargs="?", help="Plugin name to check")
    
    plug_enable = plug_sub.add_parser("enable", help="Enable a plugin")
    plug_enable.add_argument("plugin", help="Plugin name to enable")
    
    plug_disable = plug_sub.add_parser("disable", help="Disable a plugin")
    plug_disable.add_argument("plugin", help="Plugin name to disable")
    
    plug_gen = plug_sub.add_parser("gen-config", help="Generate config template from plugins")
    plug_gen.add_argument("--output", "-o", help="Output file path")
    
    plug_validate = plug_sub.add_parser("validate", help="Validate plugins in config")
    plug_validate.add_argument("--config", "-c", help="Config file to validate")
    
    args = parser.parse_args(list(argv) if argv is not None else None)
    socket_path, pid_path = get_daemon_paths()
    
    # Handle daemon commands
    if args.command == "start":
        if socket_path.exists():
            print("daemon already running", file=sys.stderr)
            return 1
        
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        
        if args.foreground:
            exchange, shutdown = _get_daemon_exchange()
            print("Starting daemon in foreground... (Ctrl+C to stop)")
            try:
                asyncio.run(_daemon_async(exchange, socket_path, shutdown))
            except KeyboardInterrupt:
                shutdown.set()
            return 0
        
        import multiprocessing
        exchange, shutdown = _get_daemon_exchange()
        
        def run_daemon():
            asyncio.run(_daemon_async(exchange, socket_path, shutdown))
        
        ctx = multiprocessing.get_context("spawn")
        proc = ctx.Process(target=run_daemon, daemon=True)
        proc.start()
        
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(proc.pid))
        
        time.sleep(0.5)
        if proc.is_alive():
            print(f"Daemon started (PID: {proc.pid})")
            return 0
        else:
            print("Failed to start daemon", file=sys.stderr)
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
            exchange = build_exchange()
            print(json.dumps({"instances": list(exchange.instances.keys())}, indent=2))
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
        if socket_path.exists():
            response = send_daemon_command({"command": "dead_letters", "args": {"limit": args.limit}})
            print(json.dumps(response, indent=2))
        else:
            print("daemon not running", file=sys.stderr)
            return 1
        return 0
    
    # Commands that work with or without daemon
    local_exchange = build_exchange()
    
    if args.command == "instances":
        if socket_path.exists():
            response = send_daemon_command({"command": "instances"})
            print(json.dumps(response, indent=2))
        else:
            response = local_exchange.instance_manager.status()
            print(json.dumps(response, indent=2))
        return 0
    
    if args.command == "inbox":
        if socket_path.exists():
            if args.subcommand == "list":
                response = send_daemon_command({"command": "inbox_list"})
            elif args.subcommand == "show":
                response = send_daemon_command({"command": "inbox_show", "args": {"message_id": args.message_id}})
            elif args.subcommand == "replay":
                response = send_daemon_command({"command": "inbox_replay", "args": {"message_id": args.message_id}})
            else:
                response = {"error": "unknown subcommand"}
            print(json.dumps(response, indent=2))
        else:
            print("daemon not running - inbox operations require daemon", file=sys.stderr)
            return 1
        return 0
    
    if args.command == "outbox":
        if socket_path.exists():
            if args.subcommand == "list":
                response = send_daemon_command({"command": "outbox_list"})
            elif args.subcommand == "show":
                response = send_daemon_command({"command": "outbox_show", "args": {"outbox_id": args.outbox_id}})
            elif args.subcommand == "retry":
                response = send_daemon_command({"command": "outbox_retry"})
            elif args.subcommand == "fail":
                response = send_daemon_command({"command": "outbox_fail", "args": {"outbox_id": args.outbox_id}})
            else:
                response = {"error": "unknown subcommand"}
            print(json.dumps(response, indent=2))
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
