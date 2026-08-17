import io
import sys
import unittest
from unittest.mock import patch

from weixin_search_mcp.main import configure_stdio_utf8


class StdioEncodingTest(unittest.TestCase):
    def test_reconfigures_legacy_code_page_streams_to_utf8(self) -> None:
        raw_stdin = io.BytesIO()
        raw_stdout = io.BytesIO()
        raw_stderr = io.BytesIO()
        stdin = io.TextIOWrapper(raw_stdin, encoding="cp936")
        stdout = io.TextIOWrapper(raw_stdout, encoding="cp936")
        stderr = io.TextIOWrapper(raw_stderr, encoding="cp936")

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch.object(sys, "stderr", stderr),
        ):
            configure_stdio_utf8()
            stdout.write("微信公众号内容获取")
            stderr.write("微信公众号内容获取")
            stdout.flush()
            stderr.flush()

        self.assertEqual(stdin.encoding, "utf-8")
        self.assertEqual(stdout.encoding, "utf-8")
        self.assertEqual(stderr.encoding, "utf-8")
        self.assertEqual(raw_stdout.getvalue().decode("utf-8"), "微信公众号内容获取")
        self.assertEqual(raw_stderr.getvalue().decode("utf-8"), "微信公众号内容获取")


if __name__ == "__main__":
    unittest.main()
