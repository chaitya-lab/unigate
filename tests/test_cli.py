from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

from unigate.cli import main


class CliTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, dict[str, object] | str, str]:
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            code = main(argv)
        raw = out_buf.getvalue().strip()
        err = err_buf.getvalue().strip()
        try:
            return code, json.loads(raw), err
        except json.JSONDecodeError:
            return code, raw, err

    def test_status_command(self) -> None:
        code, payload, _ = self._run(["status"])
        self.assertEqual(code, 0)
        assert isinstance(payload, dict)
        self.assertIn("instances", payload)

    def test_instances_status_includes_retry_policy(self) -> None:
        code, payload, _ = self._run(["instances", "status"])
        self.assertEqual(code, 0)
        assert isinstance(payload, dict)
        self.assertIn("default", payload)
        default = payload["default"]
        assert isinstance(default, dict)
        self.assertEqual(default["max_attempts"], 5)

    def test_dead_letters_command_requires_daemon(self) -> None:
        """dead-letters list requires daemon to be running"""
        code, _, err = self._run(["dead-letters", "list"])
        self.assertEqual(code, 1)
        self.assertIn("daemon not running", err)
