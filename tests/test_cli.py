from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from unigate.cli import main


class CliTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, dict[str, object] | str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        raw = buf.getvalue().strip()
        try:
            return code, json.loads(raw)
        except json.JSONDecodeError:
            return code, raw

    def test_status_command(self) -> None:
        code, payload = self._run(["status"])
        self.assertEqual(code, 0)
        assert isinstance(payload, dict)
        self.assertIn("instances", payload)

    def test_instances_status_includes_retry_policy(self) -> None:
        code, payload = self._run(["instances", "status"])
        self.assertEqual(code, 0)
        assert isinstance(payload, dict)
        self.assertIn("default", payload)
        default = payload["default"]
        assert isinstance(default, dict)
        self.assertEqual(default["max_attempts"], 5)

    def test_dead_letters_command(self) -> None:
        code, payload = self._run(["outbox", "dead-letters"])
        self.assertEqual(code, 0)
        assert isinstance(payload, dict)
        self.assertIn("count", payload)
