"""CLI for operating Unigate."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

from .adapters import InternalAdapter
from .kernel import Exchange
from .stores import InMemoryStores, NamespacedSecureStore


DEFAULT_SOCKET_PATH = Path.home() / ".unigate" / "daemon.sock"
DEFAULT_PID_PATH = Path.home() / ".unigate" / "daemon.pid"


def get_daemon_paths() -> tuple[Path, Path]:
    return DEFAULT_SOCKET_PATH, DEFAULT_PID_PATH


def build_exchange() -> Exchange:
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


def daemon_loop(exchange: Exchange, socket_path: Path, shutdown_event: threading.Event) -> None:
    asyncio.run(_daemon_async(exchange, socket_path, shutdown_event))


async def _daemon_async(exchange: Exchange, socket_path: Path, shutdown_event: threading.Event) -> None:
    if socket_path.exists():
        socket_path.unlink()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    server = await asyncio.start_unix_server(_handle_client, path=str(socket_path))
    
    async with server:
        while not shutdown_event.is_set():
            await asyncio.sleep(0.5)
    
    socket_path.unlink(missing_ok=True)


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
    from .kernel import Exchange
    from .stores import InMemoryStores, NamespacedSecureStore

    cmd = command.get("command")
    
    if cmd == "status":
        return {
            "instances": list(_daemon_exchange.instances.keys()),
            "events": len(_daemon_exchange.events),
        }
    
    if cmd == "instances":
        return _daemon_exchange.instance_manager.status()
    
    if cmd == "inbox":
        records = await _daemon_exchange._inbox.list_inbox()
        return {"count": len(records), "records": [{"id": r.message_id} for r in records]}
    
    if cmd == "outbox":
        records = await _daemon_exchange._outbox.list_outbox()
        return {"count": len(records), "records": [{"id": r.outbox_id, "status": r.status} for r in records]}
    
    if cmd == "outbox_retry":
        await _daemon_exchange.flush_outbox()
        return {"ok": True}
    
    if cmd == "dead_letters":
        records = await _daemon_exchange._outbox.list_dead_letters()
        return {"count": len(records)}
    
    if cmd == "ping":
        return {"pong": True}
    
    return {"error": f"unknown command: {cmd}"}


_daemon_exchange: Exchange | None = None
_daemon_shutdown: threading.Event | None = None


def _get_daemon_exchange() -> tuple[Exchange, threading.Event]:
    global _daemon_exchange, _daemon_shutdown
    if _daemon_exchange is None:
        _daemon_exchange = build_exchange()
        _daemon_shutdown = threading.Event()
    return _daemon_exchange, _daemon_shutdown


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unigate", description="Universal messaging exchange")
    parser.add_argument("--config", help="Path to config file")
    
    sub = parser.add_subparsers(dest="command", required=True)
    
    sub.add_parser("serve", help="Start kernel (use with ASGI server)")
    sub.add_parser("status", help="Show daemon status")
    
    start = sub.add_parser("start", help="Start daemon in background")
    start.add_argument("--foreground", "-f", action="store_true", help="Run in foreground")
    
    sub.add_parser("stop", help="Stop daemon")
    
    inst = sub.add_parser("instances", help="Instance operations")
    inst_sub = inst.add_subparsers(dest="subcommand", required=True)
    inst_sub.add_parser("list", help="List instances")
    inst_sub.add_parser("status", help="Show instance status")
    
    inbox = sub.add_parser("inbox", help="Inbox operations")
    inbox_sub = inbox.add_subparsers(dest="subcommand", required=True)
    inbox_sub.add_parser("list", help="List inbox records")
    
    outbox = sub.add_parser("outbox", help="Outbox operations")
    outbox_sub = outbox.add_subparsers(dest="subcommand", required=True)
    outbox_sub.add_parser("list", help="List outbox records")
    outbox_sub.add_parser("retry", help="Retry failed messages")
    outbox_sub.add_parser("dead-letters", help="View dead letters")
    
    args = parser.parse_args(list(argv) if argv is not None else None)
    socket_path, pid_path = get_daemon_paths()
    
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
        
        import time
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
                import os as os_module
                os_module.kill(pid, 9)
            except Exception:
                pass
            pid_path.unlink()
        
        socket_path.unlink(missing_ok=True)
        print("Daemon stopped")
        return 0
    
    if args.command == "serve":
        print("serve: use an ASGI server with unigate.runtime.UnigateASGIApp")
        print("Or run 'unigate start --foreground' for standalone mode")
        return 0
    
    local_exchange = build_exchange()
    
    if args.command == "status":
        if socket_path.exists():
            response = send_daemon_command({"command": "status"})
            print(json.dumps(response, indent=2))
        else:
            print(json.dumps({"instances": list(local_exchange.instances.keys())}, indent=2))
        return 0
    
    if socket_path.exists():
        if args.command == "instances":
            response = send_daemon_command({"command": "instances"})
        elif args.command == "inbox":
            response = send_daemon_command({"command": "inbox"})
        elif args.command == "outbox":
            subcmd = getattr(args, "subcommand", "list")
            cmd = "outbox_retry" if subcmd == "retry" else ("dead_letters" if subcmd == "dead-letters" else "outbox")
            response = send_daemon_command({"command": cmd})
        else:
            response = {"error": "unknown command"}
        
        print(json.dumps(response, indent=2))
        return 0
    
    if args.command == "instances":
        status = local_exchange.instance_manager.status()
        print(json.dumps(status, indent=2))
        return 0
    
    if args.command == "inbox":
        records = asyncio.run(local_exchange._inbox.list_inbox())
        print(json.dumps({"count": len(records)}, indent=2))
        return 0
    
    if args.command == "outbox":
        subcmd = getattr(args, "subcommand", "list")
        if subcmd == "retry":
            asyncio.run(local_exchange.flush_outbox())
            print(json.dumps({"ok": True}, indent=2))
        elif subcmd == "dead-letters":
            records = asyncio.run(local_exchange._outbox.list_dead_letters())
            print(json.dumps({"count": len(records)}, indent=2))
        else:
            records = asyncio.run(local_exchange._outbox.list_outbox())
            print(json.dumps({"count": len(records)}, indent=2))
        return 0
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
