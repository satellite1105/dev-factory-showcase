"""wordfreq の CLI のテスト(説明用のサンプル)。"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from wordfreq.__main__ import main

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_main(argv, stdin_text=""):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin_text)), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_single_file(self):
        p = self.write("a.txt", "b a b c")
        code, out, _ = run_main([p])
        self.assertEqual(code, 0)
        self.assertEqual(out, "b\t2\na\t1\nc\t1\n")

    def test_multiple_files_merged(self):
        p1 = self.write("a.txt", "x y")
        p2 = self.write("b.txt", "y z y")
        code, out, _ = run_main([p1, p2])
        self.assertEqual(code, 0)
        self.assertEqual(out, "y\t3\nx\t1\nz\t1\n")

    def test_stdin_default(self):
        code, out, _ = run_main([], "hi hi there")
        self.assertEqual(code, 0)
        self.assertEqual(out, "hi\t2\nthere\t1\n")

    def test_stdin_dash(self):
        code, out, _ = run_main(["-"], "q q")
        self.assertEqual((code, out), (0, "q\t2\n"))

    def test_n_option(self):
        p = self.write("a.txt", "a a a b b c")
        code, out, _ = run_main([p, "-n", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "a\t3\nb\t2\n")

    def test_json_format(self):
        p = self.write("a.txt", "日本 日本 go")
        code, out, _ = run_main([p, "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"word": "日本", "count": 2}, {"word": "go", "count": 1}])

    def test_csv_format(self):
        p = self.write("a.txt", "a")
        _, out, _ = run_main([p, "--format", "csv"])
        self.assertTrue(out.startswith("word,count"))

    def test_no_lowercase(self):
        p = self.write("a.txt", "Go go")
        _, out, _ = run_main([p, "--no-lowercase"])
        self.assertEqual(out, "Go\t1\ngo\t1\n")

    def test_stopwords(self):
        p = self.write("a.txt", "the cat the dog")
        sw = self.write("sw.txt", "# c\nthe\n")
        code, out, _ = run_main([p, "--stopwords", sw])
        self.assertEqual(code, 0)
        self.assertEqual(out, "cat\t1\ndog\t1\n")

    def test_missing_file(self):
        missing = os.path.join(self.dir, "nope.txt")
        code, out, err = run_main([missing])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err.strip(), "wordfreq: cannot read " + missing)

    def test_not_utf8(self):
        path = os.path.join(self.dir, "bad.bin")
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\xfa")
        code, _, err = run_main([path])
        self.assertEqual(code, 1)
        self.assertIn("wordfreq: cannot read", err)

    def test_n_zero_is_usage_error(self):
        p = self.write("a.txt", "a")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                run_main([p, "-n", "0"])
        self.assertEqual(cm.exception.code, 2)

    def test_subprocess_integration(self):
        p = self.write("a.txt", "z z y")
        result = subprocess.run(
            [sys.executable, "-m", "wordfreq", p],
            cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "z\t2\ny\t1\n")


if __name__ == "__main__":
    unittest.main()
