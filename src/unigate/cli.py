"""Minimal CLI for operating Unigate."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Sequence

from .adapters import InternalAdapter
from .kernel import Exchange
from .stores import InMemoryStores, NamespacedSecureStore


def build_exchange() -> Exchange:
    memory = InMemoryStores()
    exchange = Exchange(inbox=memory, outbox=memory, sessions=memory, dedup=memory)
    store = NamespacedSecureStore()
    adapter = InternalAdapter("default", store.for_instance("default"), exchange)
    exchange.register_instance("default", adapter)
    exchange.set_retry_policy("default", max_attempts=5, retry_base_seconds=2, retry_max_seconds=30)
    return exchange


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unigate")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    sub.add_parser("status")
    inst = sub.add_parser("instances")
    inst_sub = inst.add_subparsers(dest="subcommand", required=True)
    inst_sub.add_parser("list")
    inst_sub.add_parser("status")
    inbox = sub.add_parser("inbox")
    inbox_sub = inbox.add_subparsers(dest="subcommand", required=True)
    inbox_sub.add_parser("list")
    outbox = sub.add_parser("outbox")
    outbox_sub = outbox.add_subparsers(dest="subcommand", required=True)
    outbox_sub.add_parser("list")
    outbox_sub.add_parser("retry")
    outbox_sub.add_parser("dead-letters")

    args = parser.parse_args(list(argv) if argv is not None else None)
    exchange = build_exchange()
    if args.command == "serve":
        print("serve: use an ASGI server with unigate.runtime.UnigateASGIApp")
        return 0
    if args.command == "status":
        print(json.dumps({"instances": list(exchange.instances.keys())}))
        return 0
    if args.command == "instances":
        print(json.dumps(exchange.instance_manager.status(), sort_keys=True))
        return 0
    if args.command == "inbox":
        records = asyncio.run(exchange._inbox.list_inbox())  # intentionally small CLI shim
        print(json.dumps({"count": len(records)}))
        return 0
    if args.command == "outbox":
        if args.subcommand == "retry":
            asyncio.run(exchange.flush_outbox())
        if args.subcommand == "dead-letters":
            records = asyncio.run(exchange._outbox.list_dead_letters())  # intentionally small CLI shim
            print(json.dumps({"count": len(records)}))
            return 0
        records = asyncio.run(exchange._outbox.list_outbox())  # intentionally small CLI shim
        print(json.dumps({"count": len(records)}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
