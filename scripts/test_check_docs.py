#!/usr/bin/env python3
"""Self-contained documentation checker tests; no network or git required."""

import contextlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs as checker


def make_clean_repo(root):
    for rel in checker.REQUIRED_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Document\n" if rel.endswith(".md") else "", encoding="utf-8")
    links = "".join(f"- [Document]({rel})\n" for rel in checker.REQUIRED_FILES
                    if rel.endswith(".md") and rel != "README.md")
    (root / "README.md").write_text("# Sample\n" + links, encoding="utf-8")
    for rel in checker.RECONSTRUCTION_FILES:
        with (root / rel).open("a", encoding="utf-8") as stream:
            stream.write(checker.RECONSTRUCTION_MARKER + "\n")
    for rel in checker.MERMAID_REQUIRED:
        with (root / rel).open("a", encoding="utf-8") as stream:
            stream.write('```mermaid\nflowchart TD\nA["Start"] --> B["Finish"]\n```\n')
    (root / checker.STATUS_PATH).write_text(
        "# Status\n| ID | 項目 | ステータス | 根拠 | 限界・注記 |\n"
        "|---|---|---|---|---|\n"
        "| V01 | Sample | 実機検証済み | 2026-10: isolated local test succeeded | Static only |\n"
        "| P08 | Sample | 設計済み(未検証) | Pending | Pending |\n", encoding="utf-8")
    (root / ".gitignore").write_text("\n".join(checker.GITIGNORE_REQUIRED) + "\n", encoding="utf-8")


class TestCheckDocs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        make_clean_repo(self.root)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append(self, rel, text):
        with (self.root / rel).open("a", encoding="utf-8") as stream:
            stream.write("\n" + text + "\n")

    def execute(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = checker.run(["--root", str(self.root)])
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_failure(self, category):
        code, out, err = self.execute()
        self.assertEqual(code, 1, (out, err))
        self.assertIn("[" + category + "]", out)
        self.assertIn("RESULT: FAIL", out)
        self.assertEqual(err, "")

    def diagram(self, body, closed=True, rel="docs/architecture.md"):
        self.write(rel, "# Diagram\n```mermaid\n" + body + ("\n```\n" if closed else "\n"))

    def replace_status(self, old, new):
        path = self.root / checker.STATUS_PATH
        self.write(checker.STATUS_PATH, path.read_text(encoding="utf-8").replace(old, new))

    def test_clean_repo(self):
        code, out, err = self.execute()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("RESULT: PASS (errors=0, warnings=0)", out)
        self.assertIn("[external-links] 0 not checked", out)

    def test_required_file_missing(self):
        for rel in ("LICENSE", "LICENSE-docs.md"):
            with self.subTest(file=rel):
                path = self.root / rel
                original = path.read_text(encoding="utf-8")
                path.unlink()
                self.assert_failure("required-file")
                path.write_text(original, encoding="utf-8")

    def test_broken_link(self):
        self.append("README.md", "[missing](missing.md)")
        self.assert_failure("broken-link")

    def test_image_and_reference_links(self):
        self.append("README.md", "![image](missing.png)\n[ref]: missing.md")
        code, out, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(out.count("[broken-link]"), 2)

    def test_extract_links_and_line_numbers(self):
        text = ('# Title\n[x](folder/a(b).md "title")\n'
                '![x](<space name.md>)\n[ref]: <other file.md> "Title"\n')
        self.assertEqual(checker.extract_links(text), [
            (2, "folder/a(b).md"), (3, "space name.md"), (4, "other file.md")])

    def test_code_links_ignored(self):
        self.append("README.md", "```markdown\n[x](missing.md)\n```\n"
                    "~~~~\n[x](missing.md)\n~~~~\n"
                    "`[x](missing.md)` and ``[x](missing.md)``")
        self.assertEqual(self.execute()[0], 0)

    def test_japanese_duplicate_and_encoded_anchors(self):
        self.append("docs/roles.md", "## 日本語の見出し！\n## 日本語の見出し！\n"
                    "## Repeat\n## Repeat\n## Repeat-1\n## Repeat")
        for fragment in ("日本語の見出し", "日本語の見出し-1", "repeat", "repeat-1", "repeat-1-1", "repeat-2",
                         "%E6%97%A5%E6%9C%AC%E8%AA%9E%E3%81%AE%E8%A6%8B%E5%87%BA%E3%81%97"):
            self.append("README.md", "[heading](docs/roles.md#" + fragment + ")")
        self.assertEqual(self.execute()[0], 0)

    def test_broken_anchor(self):
        self.append("docs/roles.md", "## 日本語\n## 日本語")
        self.append("README.md", "[heading](docs/roles.md#日本語-2)")
        self.assert_failure("broken-anchor")

    def test_slug(self):
        self.assertEqual(checker.github_slug("Hello, 日本語_2!"), "hello-日本語_2")

    def test_same_file_anchor_and_setext(self):
        self.append("README.md", "Local title\n-----------\n[here](#local-title)")
        self.assertEqual(self.execute()[0], 0)

    def test_headings_in_fences_do_not_create_anchors(self):
        self.append("README.md", "```\n## Hidden\n```\n[here](#hidden)")
        self.assert_failure("broken-anchor")

    def test_link_outside_root(self):
        self.append("README.md", "[outside](../outside.md)")
        self.assert_failure("link-outside-root")

    def test_encoded_link_outside_root(self):
        self.append("README.md", "[outside](%2e%2e/outside.md)")
        self.assert_failure("link-outside-root")

    def test_symlink_link_outside_root(self):
        (self.root / "escape").symlink_to(self.root.parent, target_is_directory=True)
        self.append("README.md", "[outside](escape/outside.md)")
        self.assert_failure("link-outside-root")

    def test_unreachable(self):
        path = self.root / "README.md"
        self.write("README.md", path.read_text(encoding="utf-8").replace(
            "- [Document](docs/roles.md)\n", ""))
        self.assert_failure("unreachable")

    def test_reachability_is_transitive(self):
        path = self.root / "README.md"
        self.write("README.md", path.read_text(encoding="utf-8").replace(
            "- [Document](docs/roles.md)\n", ""))
        self.append("docs/architecture.md", "[roles](roles.md)")
        self.assertEqual(self.execute()[0], 0)

    def test_external_links_are_counted_without_connections(self):
        self.append("README.md", "[http](http://example.com)\n"
                    "[https](https://example.org)\n[mail](mailto:" + "reader" + "@" + "example.com)")
        with mock.patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            code, out, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertIn("[external-links] 3 not checked", out)

    def test_mermaid_missing(self):
        self.write("docs/architecture.md", "# Empty\n")
        self.assert_failure("mermaid-missing")

    def test_mermaid_wrong_fence_language(self):
        self.write("docs/architecture.md", "```text\nflowchart TD\n```\n")
        self.assert_failure("mermaid-missing")

    def test_mermaid_type(self):
        self.diagram("unknown TD\nA --> B")
        self.assert_failure("mermaid-type")

    def test_mermaid_empty(self):
        self.diagram("%% Only a comment")
        self.assert_failure("mermaid-type")

    def test_mermaid_direction(self):
        self.diagram("flowchart SIDE\nA --> B")
        self.assert_failure("mermaid-direction")

    def test_mermaid_subgraph(self):
        self.diagram('flowchart TD\nsubgraph GROUP["Group"]\nA --> B')
        self.assert_failure("mermaid-subgraph")

    def test_mermaid_brackets(self):
        self.diagram('flowchart TD\nA["Start" --> B')
        self.assert_failure("mermaid-brackets")

    def test_mermaid_crossed_brackets(self):
        self.diagram("flowchart TD\nA[(])")
        self.assert_failure("mermaid-brackets")

    def test_mermaid_quoted_brackets_and_break(self):
        self.diagram('%% comment\n\nflowchart LR\nsubgraph GROUP["Group"]\n'
                     'A["Text ( [ {<br/>hello"] --> B["Finish"]\nend')
        self.assertEqual(self.execute()[0], 0)

    def test_mermaid_valid_other_types(self):
        self.diagram("stateDiagram-v2\n[*] --> Ready")
        self.diagram("sequenceDiagram\nA->>B: hello", rel="docs/development-flow.md")
        self.assertEqual(self.execute()[0], 0)

    def test_mermaid_unsupported_html(self):
        self.diagram('flowchart TD\nA["<b>text</b>"]')
        self.assert_failure("mermaid-unsupported")

    def test_mermaid_unsupported_click(self):
        self.diagram('flowchart TD\nclick A "https://example.com"')
        self.assert_failure("mermaid-unsupported")

    def test_mermaid_unsupported_init(self):
        self.diagram('%%{init: {}}%%\nflowchart TD')
        self.assert_failure("mermaid-unsupported")

    def test_mermaid_unclosed(self):
        self.diagram("flowchart TD\nA --> B", closed=False)
        self.assert_failure("mermaid-unclosed")

    def test_mermaid_nested_fence_example_is_ignored(self):
        self.append("README.md", "````markdown\n```mermaid\ninvalid\n```\n````")
        self.assertEqual(self.execute()[0], 0)

    def test_case_study_marker_missing(self):
        self.write("docs/case-study.md", "# Example\n")
        self.assert_failure("marker-missing")

    def test_marker_after_ten_lines(self):
        self.write("docs/case-study.md", "\n" * 10 + checker.RECONSTRUCTION_MARKER)
        self.assert_failure("marker-missing")

    def test_marker_on_tenth_line(self):
        self.write("docs/case-study.md", "\n" * 9 + checker.RECONSTRUCTION_MARKER)
        self.assertEqual(self.execute()[0], 0)

    def test_readme_without_public_state_marker(self):
        code, out, err = self.execute()
        self.assertEqual((code, err), (0, ""))
        self.assertNotIn("[marker-missing]", out)

    def test_status_label(self):
        self.replace_status("実機検証済み", "検証済み")
        self.assert_failure("status-label")

    def test_status_evidence(self):
        self.replace_status("2026-10: isolated local test succeeded", "-")
        self.assert_failure("status-evidence")

    def test_status_short_evidence(self):
        self.replace_status("2026-10: isolated local test succeeded", "short")
        self.assert_failure("status-evidence")

    def test_status_duplicate_id(self):
        self.replace_status("| P08 |", "| V01 |")
        self.assert_failure("status-id")

    def test_status_invalid_id(self):
        self.replace_status("| P08 |", "| P09 |")
        self.assert_failure("status-id")

    def test_status_mismatch_in_prose(self):
        self.append("docs/roles.md", "本文。(検証ステータス: 一部検証 / V01)")
        self.assert_failure("status-mismatch")

    def test_status_mismatch_in_table(self):
        self.append("README.md", "| ID | 項目 | ステータス |\n|---|---|---|\n| V01 | Sample | 一部検証 |")
        self.assert_failure("status-mismatch")

    def test_status_unknown_id(self):
        self.append("README.md", "(検証ステータス: 一部検証 / V02)")
        self.assert_failure("status-unknown-id")

    def test_status_unknown_id_in_table(self):
        self.append("README.md", "| ID | ステータス |\n|---|---|\n| V02 | 一部検証 |")
        self.assert_failure("status-unknown-id")

    def test_status_valid_prose_and_multiple_tables(self):
        self.append("README.md", "(検証ステータス: 実機検証済み / V01)\n"
                    "(検証ステータス: 設計済み(未検証) / P08)")
        self.replace_status("| P08 |", "\n| ID | 項目 | ステータス | 根拠 | 限界・注記 |\n"
                            "|---|---|---|---|---|\n| P08 |")
        self.assertEqual(self.execute()[0], 0)

    def test_status_full_id_range(self):
        for prefix, limit in (("V", 24), ("P", 8)):
            for number in range(1, limit + 1):
                self.assertTrue(checker._valid_id(f"{prefix}{number:02d}"))
        for value in ("V00", "V25", "P00", "P09", "Q01", "V1", "V001"):
            self.assertFalse(checker._valid_id(value))

    def test_status_header_columns(self):
        self.replace_status("限界・注記", "Other")
        self.assert_failure("status-table")

    def test_status_missing_table(self):
        self.write(checker.STATUS_PATH, "# Status\n")
        self.assert_failure("status-table")

    def test_fenced_status_reference_ignored(self):
        self.append("README.md", "```markdown\n(検証ステータス: 一部検証 / V99)\n```\n"
                    "`検証ステータス: 一部検証 / V99`")
        self.assertEqual(self.execute()[0], 0)

    def test_work_record_at_root(self):
        self.write("PROJECT_STATE.md", "# Private\n")
        self.assert_failure("work-record")

    def test_work_record_reviews_directory(self):
        (self.root / "docs/reviews").mkdir()
        self.assert_failure("work-record")

    def test_example_work_record_is_allowed(self):
        findings = checker.check_work_records(self.root)
        self.assertEqual(findings, [])
        self.assertTrue((self.root / "examples/dummy-project/PROJECT_STATE.md").is_file())

    def test_gitignore_missing_rule(self):
        self.write(".gitignore", "\n".join(checker.GITIGNORE_REQUIRED[1:]))
        self.assert_failure("gitignore-missing")

    def test_runtime_missing_root(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = checker.run(["--root", str(self.root / "missing")])
        self.assertEqual(code, 2)
        self.assertIn("RESULT: FAIL", stdout.getvalue())
        self.assertNotIn(str(self.root), stdout.getvalue() + stderr.getvalue())

    def test_runtime_invalid_utf8(self):
        (self.root / "README.md").write_bytes(bytes([255]))
        self.assertEqual(self.execute()[0], 2)

    def test_cli_from_unrelated_cwd(self):
        result = subprocess.run([sys.executable, str(Path(checker.__file__).resolve()),
                                 "--root", str(self.root)], cwd=self.root / "docs",
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)

    def test_default_root_uses_script_location(self):
        fake_script = self.root / "scripts/check_docs.py"
        stdout = io.StringIO()
        with mock.patch.object(checker, "__file__", str(fake_script)), \
                contextlib.redirect_stdout(stdout):
            self.assertEqual(checker.run([]), 0)
        self.assertIn("RESULT: PASS", stdout.getvalue())

    def test_cli_invalid_option(self):
        result = subprocess.run([sys.executable, str(Path(checker.__file__).resolve()), "--invalid"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)

    def test_report_line_numbers(self):
        self.append("README.md", "[missing](missing.md)")
        _, out, _ = self.execute()
        self.assertRegex(out, r"ERROR README\.md:\d+ \[broken-link\]")
        self.assertIsNotNone(re.search(r"RESULT: FAIL \(errors=\d+, warnings=0\)", out))


if __name__ == "__main__":
    unittest.main()
