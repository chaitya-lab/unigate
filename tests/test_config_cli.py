import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from unigate.cli import run
from unigate.config import build_gate_from_config, load_config


class ConfigCliTests(unittest.TestCase):
    def test_load_json_config_and_build_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "unigate.json"
            db_path = Path(temp_dir) / "state.db"
            config_path.write_text(
                json.dumps(
                    {
                        "unigate": {
                            "storage": "sqlite",
                            "sqlite_path": str(db_path.name),
                            "asgi_prefix": "/gateway",
                        },
                        "instances": {
                            "public_api": {"type": "api"},
                            "site_chat": {"type": "web"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            gate, config = build_gate_from_config(config_path)

            self.assertEqual(config["unigate"]["storage"], "sqlite")
            self.assertEqual(sorted(config["instances"].keys()), ["public_api", "site_chat"])
            self.assertEqual(gate.instances.get("public_api").channel_type, "api")
            self.assertEqual(gate.instances.get("site_chat").channel_type, "web")

    def test_load_toml_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "unigate.toml"
            config_path.write_text(
                """
[unigate]
storage = "memory"
asgi_prefix = "/unigate"

[instances.api_one]
type = "api"

[instances.ws_one]
type = "websocket_server"
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config["unigate"]["storage"], "memory")
            self.assertEqual(config["instances"]["api_one"]["type"], "api")
            self.assertEqual(config["instances"]["ws_one"]["type"], "websocket_server")

    def test_check_config_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "unigate.json"
            config_path.write_text(
                json.dumps(
                    {
                        "unigate": {"storage": "memory"},
                        "instances": {"public_api": {"type": "api"}},
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = run(["check-config", "--config", str(config_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Config OK", stdout.getvalue())

    def test_print_config_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "unigate.json"
            config_path.write_text(
                json.dumps(
                    {
                        "unigate": {"storage": "memory", "port": 9100},
                        "instances": {"public_api": {"type": "api"}},
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = run(["print-config", "--config", str(config_path)])

            self.assertEqual(exit_code, 0)
            self.assertIn('"port": 9100', stdout.getvalue())

    def test_serve_command_without_uvicorn_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "unigate.json"
            config_path.write_text(
                json.dumps(
                    {
                        "unigate": {"storage": "memory"},
                        "instances": {"public_api": {"type": "api"}},
                    }
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), patch(
                "unigate.cli._load_uvicorn", side_effect=ModuleNotFoundError
            ):
                exit_code = run(["serve", "--config", str(config_path)])

            self.assertEqual(exit_code, 1)
            self.assertIn("uvicorn is required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
