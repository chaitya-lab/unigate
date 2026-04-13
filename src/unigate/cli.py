"""Command-line interface for unigate."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from typing import Sequence

from .asgi import create_asgi_app
from .config import build_gate_from_config, describe_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unigate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", required=True, help="Path to a unigate config file.")

    check_cmd = subparsers.add_parser("check-config", parents=[common], help="Validate config.")
    check_cmd.set_defaults(handler=_handle_check_config)

    print_cmd = subparsers.add_parser("print-config", parents=[common], help="Print resolved config summary.")
    print_cmd.set_defaults(handler=_handle_print_config)

    serve_cmd = subparsers.add_parser("serve", parents=[common], help="Run the ASGI app with uvicorn.")
    serve_cmd.add_argument("--host", help="Override bind host.")
    serve_cmd.add_argument("--port", type=int, help="Override bind port.")
    serve_cmd.set_defaults(handler=_handle_serve)

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.handler(args))


def _handle_check_config(args: argparse.Namespace) -> int:
    _, config = build_gate_from_config(args.config)
    summary = describe_config(config)
    print(
        f"Config OK: storage={summary['storage']}, instances={len(summary['instances'])}",
        file=sys.stdout,
    )
    return 0


def _handle_print_config(args: argparse.Namespace) -> int:
    _, config = build_gate_from_config(args.config)
    print(json.dumps(describe_config(config), indent=2, sort_keys=True), file=sys.stdout)
    return 0


def _handle_serve(args: argparse.Namespace) -> int:
    gate, config = build_gate_from_config(args.config)
    settings = config.get("unigate", {})
    if not isinstance(settings, dict):
        settings = {}
    prefix = settings.get("asgi_prefix", "/unigate")
    host = args.host or settings.get("host", "127.0.0.1")
    port = args.port or int(settings.get("port", 8000))

    try:
        uvicorn = _load_uvicorn()
    except ModuleNotFoundError:
        print("uvicorn is required for `unigate serve`. Install it and retry.", file=sys.stderr)
        return 1

    app = create_asgi_app(gate, prefix=str(prefix))
    asyncio.run(gate.recover())
    uvicorn.run(app, host=str(host), port=port)
    return 0


def _load_uvicorn():
    return importlib.import_module("uvicorn")


if __name__ == "__main__":
    raise SystemExit(run())
