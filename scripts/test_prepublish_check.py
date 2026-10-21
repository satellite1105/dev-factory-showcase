#!/usr/bin/env python3
"""Isolated publication-check tests; all problematic fixtures are generated."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepublish_check as checker


def private_email() -> str:
    return "sample" + "@" + "invalid" + ".test"


def credential(prefix: str) -> str:
    return prefix + "Ab4cD8eF2gH6jK9mN3pQ7rS5"


def fictional_skill() -> str:
    return "fictional" + "-" + "helper"


def github_email() -> str:
    return "noreply" + "@" + "github.com"


def coauthor_email() -> str:
    return "noreply" + "@" + "anthropic.com"


def session_urls() -> list[str]:
    routes = [("claude" + ".ai", route) for route in
              ("code/" + "session_", "chat/", "share/")]
    routes.extend((host, route) for host in ("chatgpt" + ".com", "chat.openai" + ".com")
                  for route in ("c/", "share/"))
    return [scheme + "://" + host + "/" + route + "fixture"
            for scheme in ("http", "https", "HTTPS") for host, route in routes]


def internal_urls() -> list[str]:
    hosts = ("localhost", "127.0.0.1", "0.0.0.0", "10.0.0.1", "10.255.255.255",
             "192.168.0.1", "192.168.255.255", "172.16.0.1", "172.31.255.255",
             "sample.local", "nested.sample.internal", "sample.corp", "sample.lan")
    return [scheme + "://" + host + ":8080/fixture"
            for scheme in ("http", "https", "HTTPS") for host in hosts]


def public_urls() -> list[str]:
    hosts = ("github.com/sample/repository", "creativecommons.org/licenses/by/4.0/",
             "172.15.0.1", "172.32.0.1", "192.169.0.1", "11.0.0.1",
             "localhost.example.com", "sample.local.example.com", "10.0.0.1.example.com",
             "sample.example.com/internal", "chatgpt.com.example.com/c/fixture",
             "sample.example.com/claude.ai/" + "chat/fixture")
    return ["https" + "://" + host for host in hosts]


class TestPrepublish(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.hidden_values = [str(self.base), str(self.root)]
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith("GIT_") and k != checker.REFERENCE_ENV}
        environment.update(HOME=str(self.base), GIT_CONFIG_NOSYSTEM="1",
                           GIT_CONFIG_GLOBAL=str(self.base / "gitconfig"),
                           GIT_TERMINAL_PROMPT="0")
        self.environ_patch = patch.dict(os.environ, environment, clear=True)
        self.environ_patch.start()
        self.addCleanup(self.environ_patch.stop)

    def write(self, name: str, text: str = "ordinary publication material\n") -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def external(self, name: str, text: str) -> Path:
        path = self.base / name
        path.write_text(text, encoding="utf-8")
        self.hidden_values.append(str(path))
        return path

    def invoke(self, *args: str, use_git: bool = False, expected: int = 0):
        output, errors = io.StringIO(), io.StringIO()
        command = ["--root", str(self.root)]
        if not use_git:
            command.append("--no-git")
        with redirect_stdout(output), redirect_stderr(errors):
            result = checker.run(command + [str(arg) for arg in args])
        combined = output.getvalue() + errors.getvalue()
        for value in self.hidden_values:
            self.assertTrue(value not in combined, "sensitive fixture value leaked")
        self.assertEqual(result, expected, "unexpected exit status: " + combined)
        self.assertTrue(output.getvalue().splitlines()[-1].startswith("RESULT:"))
        return combined

    def detects(self, category: str, sample: str, *args: str):
        self.write("sample.txt", sample)
        self.hidden_values.append(sample)
        output = self.invoke(*args, expected=1)
        self.assertIn("[" + category + "]", output)
        return output

    def git(self, *args: str):
        self.assertIsNotNone(shutil.which("git"), "git is required; skipping is not a passing result")
        result = subprocess.run(["git", "-C", str(self.root), *args],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, "isolated fixture git command failed")
        return result.stdout

    def init_git(self):
        templates = self.base / "empty-templates"
        templates.mkdir()
        self.git("init", "--quiet", "--template=" + str(templates))
        self.git("config", "core.hooksPath", str(self.base / "absent-hooks"))

    def commit(self, address: str, message: str = "fixture"):
        self.git("add", "--all")
        self.git("-c", "user.name=t", "-c", "user.email=" + address,
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", message)

    def test_clean_repo_and_scanner_sources(self):
        self.write("README.md", "# A clean example\n")
        self.write("docs/guide.md", "# Offline guide\n")
        self.write("sample.py", "print('hello')\n")
        for source in (Path(checker.__file__), Path(__file__).resolve()):
            self.write("scripts/" + source.name, source.read_text(encoding="utf-8"))
        output = self.invoke()
        self.assertIn("RESULT: PASS", output)
        self.assertIn("[skill-names-empty]", output)
        self.assertNotIn("ERROR", output)

    def test_home_paths(self):
        for sample in ("/" + "Users" + "/" + "sample-person",
                       "/" + "home" + "/" + "sample-person",
                       "~" + "/" + "sample-person" + "/"):
            with self.subTest(style=sample.split("/")[0]):
                self.detects("home-path", sample)
        self.write("sample.txt", "/" + "Users" + "/<name> and " + "~/" + "<name>/")
        self.assertNotIn("[home-path]", self.invoke())

    def test_emails_and_allowlist(self):
        self.detects("email", private_email())
        self.write("sample.txt", "\n".join("sample" + "@" + domain
                                         for domain in checker.ALLOWED_EMAIL_DOMAINS))
        self.assertNotIn("[email]", self.invoke())
        self.detects("email", "sample" + "@" + "sub.example.com")

    def test_credential_patterns(self):
        samples = [credential("sk" + "-"), credential("ghp" + "_"), credential("gho" + "_"),
                   credential("github" + "_pat_"), "AK" + "IA" + "0123456789ABCDEF",
                   "xox" + "b-" + "Ab0123456789", "-----" + "BEGIN " + "RSA PRIVATE " + "KEY-----"]
        for number, sample in enumerate(samples):
            with self.subTest(pattern=number):
                self.detects("api-key-like", sample)

    def test_secret_assignments(self):
        value = "Ab4cD8eF2gH6jK9m"
        self.hidden_values.append(value)
        for label in ("api_key", "api-key", "APIKEY", "secret", "token", "password", "passwd"):
            with self.subTest(label=label):
                self.detects("secret-assignment", label + " = '" + value + "'")
        for sample in ("token" + " = <replace-me>", "password" + " = " + "a" * 20,
                       "secret" + " = " + value + "<placeholder>"):
            self.write("sample.txt", sample)
            self.assertNotIn("[secret-assignment]", self.invoke())

    def test_sensitive_filenames(self):
        names = ["." + "env", "." + "env.private", "id_" + "rsa.fixture",
                 "id_" + "ed25519.fixture", "sample." + "pem", "sample." + "key",
                 "sample." + "p12", "sample." + "pfx", "sample." + "keychain-db"]
        for name in names:
            with self.subTest(kind=name.rsplit(".", 1)[-1]):
                path = self.write(name)
                self.assertIn("[sensitive-filename]", self.invoke(expected=1))
                path.unlink()
        self.write("." + "env.example")
        self.assertNotIn("[sensitive-filename]", self.invoke())

    def test_internal_paths(self):
        for sample in ("." + "claude/" + "settings" + ".json",
                       "." + "claude/" + "settings" + ".local.json",
                       "." + "claude/" + "hooks" + "/fixture"):
            self.detects("internal-config-path", sample)

    def test_file_session_urls(self):
        for number, sample in enumerate(session_urls()):
            with self.subTest(pattern=number):
                self.detects("session-url", sample)

    def test_file_internal_urls(self):
        for number, sample in enumerate(internal_urls()):
            with self.subTest(pattern=number):
                self.detects("internal-url", sample)

    def test_file_public_urls_are_allowed(self):
        self.write("sample.txt", "\n".join(public_urls()))
        self.assertNotIn("ERROR", self.invoke())

    def test_file_coauthor_email_is_not_exempt(self):
        sample = "Co" + "-Authored-By: Fixture <" + coauthor_email() + ">"
        self.detects("email", sample)

    def test_denylist_normalization_short_terms_and_exclusion(self):
        term = "private" + "-" + "phrase"
        short = "q" + "z"
        path = self.write("scripts/terms.txt", "# ignored\n\n" + short + "\n" + term)
        self.hidden_values.extend([term, short])
        self.write("sample.txt", "\n" + term.upper())
        output = self.invoke("--denylist", path, expected=1)
        self.assertIn("sample.txt:2 [denylist] denylist term #2", output)
        self.assertIn("[denylist-short]", output)
        self.assertNotIn("ERROR scripts/terms.txt", output)
        self.write("sample.txt", "clean")
        self.invoke("--denylist", path)
        path.write_text("ＡＢＣ\n", encoding="utf-8")
        self.write("sample.txt", "abc")
        self.assertIn("[denylist]", self.invoke("--denylist", path, expected=1))

    def test_local_denylist_is_default_but_explicit_replaces_it(self):
        term = "local" + "-" + "fixture"
        self.hidden_values.append(term)
        self.write("scripts/denylist.local.txt", term)
        self.write("sample.txt", term)
        self.assertIn("[denylist]", self.invoke(expected=1))
        other = self.external("other-list.txt", "unused" + "-" + "term")
        self.invoke("--denylist", other)

    def test_external_skill_directory_and_file_exclusion(self):
        name = fictional_skill()
        self.hidden_values.extend([name, name.upper()])
        names = self.write("scripts/names.txt", name)
        self.write(name.upper() + "/readme.txt", "ordinary")
        output = self.invoke("--skill-names", names, expected=1)
        self.assertIn("[external-skill-dir]", output)
        self.assertNotIn("[skill-names-empty]", output)

    def test_external_skill_mentions_word_boundaries_and_local_names(self):
        name = fictional_skill()
        self.hidden_values.append(name)
        self.write(checker.SKILL_NAMES_LOCAL, "# local\n" + name + "\n")
        self.detects("external-skill-mention", "use " + name + " now")
        self.write("sample.txt", "prefix" + name + "suffix")
        self.assertNotIn("[external-skill-mention]", self.invoke())
        self.write("sample.txt", "(" + name.upper() + ")")
        self.hidden_values.append(name.upper())
        self.assertIn("[external-skill-mention]", self.invoke(expected=1))

    def test_multiple_skill_sources_and_hyphenless_names(self):
        self.write(checker.SKILL_NAMES_LOCAL, fictional_skill())
        additional = "another" + "-" + "fiction"
        self.hidden_values.append(additional)
        names = self.external("names.txt", additional + "\n" + "plainfixture")
        self.detects("external-skill-mention", additional, "--skill-names", names)
        self.write("sample.txt", "plainfixture")
        self.invoke("--skill-names", names)

    def test_skill_file_case_insensitive(self):
        self.write("sKiLl" + ".mD")
        self.assertIn("[skill-file]", self.invoke(expected=1))

    def test_skill_frontmatter(self):
        sample = "---\n" + "name: fixture\n" + "description: sample\n---\n"
        self.detects("skill-body", sample)
        self.write("sample.txt", "intro\n" + sample)
        self.invoke()
        self.write("sample.txt", "---\n" + "name: fixture\n---\n")
        self.invoke()
        self.write("sample.txt", "---\n" + "name: fixture\n" + "\n" * 20 + "description: sample\n---")
        self.invoke()

    def test_binary_detection_and_no_contents_in_output(self):
        value = credential("sk" + "-")
        self.hidden_values.append(value)
        path = self.write("data.bin")
        path.write_bytes(b"\0" + value.encode())
        self.assertIn("[binary-file]", self.invoke(expected=1))

    def test_large_file_and_exact_limit(self):
        self.write("sample.txt", "a" * 20)
        self.assertIn("[large-file]", self.invoke("--max-size", "19", expected=1))
        self.invoke("--max-size", "20")

    def paragraph(self) -> str:
        return "".join(chr(0x4E00 + i) for i in range(120))

    def test_verbatim_japanese_grouping_lines_and_paraphrase(self):
        paragraph = self.paragraph()
        self.hidden_values.append(paragraph)
        reference = self.external("reference.txt", paragraph)
        self.write("sample.txt", "intro\n" + paragraph[:60] + "\n" + paragraph[60:])
        output = self.invoke("--reference", reference, expected=1)
        self.assertEqual(output.count("[verbatim-match]"), 1)
        self.assertIn("sample.txt:2 [verbatim-match]", output)
        self.assertIn("lines 2-3", output)
        self.write("sample.txt", "公開の説明を別の言葉で書き直した文章です。" * 10)
        self.invoke("--reference", reference)

    def test_verbatim_minimum_and_environment(self):
        reference = self.external("reference.txt", self.paragraph())
        self.write("sample.txt", self.paragraph()[:60])
        self.assertIn("[verbatim-match]", self.invoke("--reference", reference, "--min-match", "60", expected=1))
        self.invoke("--reference", reference, "--min-match", "61")
        with patch.dict(os.environ, {checker.REFERENCE_ENV: str(reference)}):
            self.assertIn("[verbatim-match]", self.invoke(expected=1))

    def test_verbatim_normalization_and_nonadjacent_runs(self):
        reference = self.external("reference.txt", "ＡＢＣＤＥＦ" * 12)
        self.write("sample.txt", "AB CD\nEF" * 12 + "!" * 60 + "ABCDEF" * 12)
        output = self.invoke("--reference", reference, expected=1)
        self.assertEqual(output.count("[verbatim-match]"), 2)
        self.assertIn("lines 1-13", output)

    def test_reference_directory_recursion_and_punctuation(self):
        directory = self.base / "references"
        directory.mkdir()
        (directory / "nested").mkdir()
        (directory / "nested" / "text.txt").write_text(self.paragraph(), encoding="utf-8")
        (directory / "nontext.bin").write_bytes(b"\xff\xfe")
        (directory / "oversized.txt").write_bytes(b"a" * (2 * 1_048_576 + 1))
        self.hidden_values.append(str(directory))
        self.write("sample.txt", self.paragraph())
        self.assertIn("[verbatim-match]", self.invoke("--reference", directory, expected=1))
        punctuation = "0123456789|*-#" * 10
        (directory / "table.txt").write_text(punctuation, encoding="utf-8")
        self.write("sample.txt", punctuation)
        self.invoke("--reference", directory)

    def test_multiple_references_and_environment_order(self):
        first = self.external("first.txt", "unrelated text")
        second = self.external("second.txt", self.paragraph())
        self.write("sample.txt", self.paragraph())
        with patch.dict(os.environ, {checker.REFERENCE_ENV: os.pathsep.join([str(second), str(first)])}):
            output = self.invoke("--reference", first, expected=1)
        self.assertIn("reference #2", output)
        self.assertNotIn("reference #1 (", output)

    def test_unreadable_inputs_return_two_without_values(self):
        missing = self.base / "missing-fixture"
        self.hidden_values.append(str(missing))
        for option in ("--reference", "--denylist", "--skill-names"):
            with self.subTest(option=option):
                output = self.invoke(option, missing, expected=2)
                self.assertIn("unreadable", output)
                self.assertIn("RESULT: FAIL", output)

    def test_invalid_arguments_hide_values(self):
        value = credential("sk" + "-")
        self.hidden_values.append(value)
        for args in (("--unknown", value), ("--min-match", value), ("--min-match", "0"),
                     ("--max-size", "0"), ("--root", self.base / "absent")):
            with self.subTest(index=len(args)):
                self.invoke(*args, expected=2)

    def test_sensitive_path_values_are_redacted(self):
        value = private_email()
        self.hidden_values.append(value)
        self.write(value + ".txt")
        output = self.invoke(expected=1)
        self.assertIn("[redacted-path]", output)
        self.assertIn("[email]", output)

    def test_walk_excludes_cache_and_git_directories(self):
        self.write(".git/fixture", credential("sk" + "-"))
        self.write("__pycache__/fixture", credential("sk" + "-"))
        self.write("nested/__pycache__/fixture", credential("sk" + "-"))
        self.invoke()

    def test_no_git_fallback_and_history_failure(self):
        with patch.object(checker.shutil, "which", return_value=None):
            self.assertIn("[git]", self.invoke(use_git=True))
            self.assertIn("history requires", self.invoke("--history", use_git=True, expected=2))

    def test_git_ignored_files_are_counted_and_not_scanned(self):
        self.init_git()
        self.write(".gitignore", "ignored.txt\n")
        sample = credential("sk" + "-")
        self.hidden_values.append(sample)
        self.write("ignored.txt", sample)
        output = self.invoke(use_git=True)
        self.assertIn("[ignored-files] 1 ignored file(s)", output)
        self.assertNotIn("[api-key-like]", output)

    def test_git_author_warning_does_not_fail(self):
        self.init_git()
        address = private_email()
        self.hidden_values.append(address)
        self.git("config", "user.email", address)
        self.assertIn("[git-author-config]", self.invoke(use_git=True))
        self.git("config", "user.email", "sample" + "@" + "example.com")
        self.assertNotIn("[git-author-config]", self.invoke(use_git=True))

    def test_git_history_added_values_and_commit_metadata(self):
        self.init_git()
        sample = credential("sk" + "-")
        address = private_email()
        self.hidden_values.extend([sample, address])
        self.write("sample.txt", sample)
        self.commit(address)
        self.write("sample.txt", "clean now")
        self.commit("sample" + "@" + "example.com")
        self.invoke(use_git=True)
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertRegex(output, r"ERROR commit:[0-9a-f]+:\d+ \[history-api-key-like\]")
        self.assertRegex(output, r"ERROR commit:[0-9a-f]+ \[commit-author-email\]")

    def test_git_history_empty_repo(self):
        self.init_git()
        self.assertIn("[history] no commits", self.invoke("--history", use_git=True))

    def test_history_merge_session_trailer_regression(self):
        self.init_git()
        address = "sample" + "@" + "example.com"
        self.write("sample.txt")
        self.commit(address)
        primary = self.git("symbolic-ref", "--short", "HEAD").decode().strip()
        self.git("branch", "fixture-side")
        self.write("primary.txt")
        self.commit(address)
        self.git("checkout", "--quiet", "fixture-side")
        self.write("side.txt")
        self.commit(address)
        self.git("checkout", "--quiet", primary)
        identifier = uuid.uuid4().hex
        url = "https" + "://" + "claude" + ".ai/code/" + "session_" + identifier
        message = ("Merge fixture\n\nCo" + "-Authored-By: Fixture <" + coauthor_email()
                   + ">\nClaude" + "-Session: " + url)
        self.hidden_values.extend([identifier, url, coauthor_email()])
        self.git("-c", "user.name=t", "-c", "user.email=" + address,
                 "-c", "commit.gpgsign=false", "merge", "--quiet", "--no-ff",
                 "-m", message, "fixture-side")
        parents = self.git("show", "-s", "--format=%P", "HEAD").split()
        self.assertEqual(len(parents), 2)
        short = self.git("show", "-s", "--format=%h", "HEAD").decode().strip()
        self.invoke(use_git=True)
        output = self.invoke("--history", use_git=True, expected=1)
        for category in ("session-url", "session-trailer"):
            self.assertIn("ERROR commit:" + short + ":4 [history-message-" + category + "]", output)
        self.assertNotIn("[history-message-email]", output)

    def test_history_coauthor_allowed_addresses(self):
        self.init_git()
        self.write("sample.txt")
        github = "123+fixture" + "@" + "users.noreply.github.com"
        self.hidden_values.extend([coauthor_email(), github])
        self.commit("sample" + "@" + "example.com",
                    "Fixture\n\nCo" + "-Authored-By: Fixture <" + coauthor_email() + ">\n"
                    + "cO" + "-aUtHoReD-bY: Fixture <" + coauthor_email().upper() + ">\n"
                    + "Co" + "-Authored-By: Fixture <" + github + ">")
        self.assertNotIn("[history-message-email]", self.invoke("--history", use_git=True))

    def test_history_coauthor_exemption_is_narrow(self):
        self.init_git()
        self.write("sample.txt")
        samples = ("Body mentions " + coauthor_email(),
                   "Indented Co" + "-Authored-By: Fixture <" + coauthor_email() + ">",
                   "Co" + "-Authored-By: Fixture <" + private_email() + ">",
                   "Co" + "-Authored-By: Fixture <" + coauthor_email() + "> " + private_email())
        self.hidden_values.extend([coauthor_email(), private_email()])
        self.commit("sample" + "@" + "example.com", "Fixture\n\n" + "\n".join(samples))
        output = self.invoke("--history", use_git=True, expected=1)
        for line in range(3, 7):
            self.assertRegex(output, r"commit:[0-9a-f]+:" + str(line) + r" \[history-message-email\]")

    def test_history_message_session_urls(self):
        self.init_git()
        self.write("sample.txt")
        samples = session_urls()
        self.hidden_values.extend(samples)
        self.commit("sample" + "@" + "example.com", "Fixture\n\n" + "\n".join(samples))
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertEqual(output.count("[history-message-session-url]"), len(samples))
        for line in range(3, len(samples) + 3):
            self.assertRegex(output, r"commit:[0-9a-f]+:" + str(line)
                             + r" \[history-message-session-url\]")

    def test_history_message_internal_urls(self):
        self.init_git()
        self.write("sample.txt")
        samples = internal_urls()
        self.hidden_values.extend(samples)
        self.commit("sample" + "@" + "example.com", "Fixture\n\n" + "\n".join(samples))
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertEqual(output.count("[history-message-internal-url]"), len(samples))

    def test_history_message_public_urls_are_allowed(self):
        self.init_git()
        self.write("sample.txt")
        self.commit("sample" + "@" + "example.com", "Fixture\n\n" + "\n".join(public_urls()))
        self.assertNotIn("ERROR", self.invoke("--history", use_git=True))

    def test_history_session_trailer_without_url_and_case_insensitive(self):
        self.init_git()
        self.write("sample.txt")
        self.commit("sample" + "@" + "example.com",
                    "Fixture\n\ncLaUdE" + "-SeSsIoN: absent\nClaude" + "-Session:")
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertEqual(output.count("[history-message-session-trailer]"), 2)
        self.assertNotIn("[history-message-session-url]", output)

    def test_history_message_existing_string_categories(self):
        self.init_git()
        self.write("sample.txt")
        term = "private" + "-" + "phrase"
        name = fictional_skill()
        self.write("scripts/denylist.local.txt", term)
        self.write(checker.SKILL_NAMES_LOCAL, name)
        samples = {
            "home-path": "/" + "home/" + "fixture-person",
            "api-key-like": credential("sk" + "-"),
            "denylist": term,
            "secret-assignment": "token" + " = Ab4cD8eF2gH6jK9m",
            "internal-config-path": "." + "claude/" + "hooks/fixture",
            "external-skill-mention": name,
        }
        self.hidden_values.extend(samples.values())
        self.commit("sample" + "@" + "example.com", "\n".join(samples.values()))
        output = self.invoke("--history", use_git=True, expected=1)
        for line, category in enumerate(samples, 1):
            self.assertRegex(output, r"commit:[0-9a-f]+:" + str(line)
                             + r" \[history-message-" + category + r"\]")

    def test_history_message_record_separators_do_not_break_parsing(self):
        self.init_git()
        self.write("sample.txt")
        sample = credential("sk" + "-")
        self.hidden_values.append(sample)
        self.commit("sample" + "@" + "example.com", "Fixture\n\nleft\x1eright\x1f\n" + sample)
        self.write("sample.txt", "next version\n")
        self.commit("sample" + "@" + "example.com", "Next\n\nseparator \x1e and \x1f")
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertRegex(output, r"commit:[0-9a-f]+:4 \[history-message-api-key-like\]")

    def test_history_message_malformed_records_return_two(self):
        self.init_git()
        self.write("sample.txt")
        self.commit("sample" + "@" + "example.com")
        sha = self.git("rev-parse", "HEAD").strip()
        hidden = credential("sk" + "-").encode()
        self.hidden_values.append(hidden.decode())
        valid = sha + b"\0" + sha[:7] + b"\0" + hidden + b"\0"
        malformed = (valid[:-1], valid + b"extra\0", b"invalid\0short\0" + hidden + b"\0",
                     sha + b"\0z\0" + hidden + b"\0", valid + valid, b"",
                     sha + b"\0" + b"0" * 41 + b"\0" + hidden + b"\0")
        original = checker.git
        for number, raw in enumerate(malformed):
            with self.subTest(record=number):
                def fake_git(root, *args):
                    if args[:3] == ("log", "--all", "-z"):
                        return subprocess.CompletedProcess(args, 0, raw, b"")
                    return original(root, *args)
                with patch.object(checker, "git", side_effect=fake_git):
                    self.assertIn("history format invalid",
                                  self.invoke("--history", use_git=True, expected=2))

    def test_history_message_log_failure_return_two(self):
        self.init_git()
        original = checker.git
        def fake_git(root, *args):
            if args[:3] == ("log", "--all", "-z"):
                return subprocess.CompletedProcess(args, 1, b"", b"hidden detail")
            return original(root, *args)
        with patch.object(checker, "git", side_effect=fake_git):
            output = self.invoke("--history", use_git=True, expected=2)
        self.assertIn("history message scan failed", output)
        self.assertNotIn("hidden detail", output)

    def test_git_history_committer_is_checked_separately(self):
        self.init_git()
        self.write("sample.txt")
        address = private_email()
        self.hidden_values.append(address)
        with patch.dict(os.environ, {"GIT_COMMITTER_EMAIL": address}):
            self.commit("sample" + "@" + "example.com")
        self.assertIn("[commit-author-email]", self.invoke("--history", use_git=True, expected=1))

    def test_history_root_github_committer_is_rejected(self):
        self.init_git()
        self.write("sample.txt")
        self.hidden_values.append(github_email())
        with patch.dict(os.environ, {"GIT_COMMITTER_NAME": "GitHub",
                                    "GIT_COMMITTER_EMAIL": github_email()}):
            self.commit("sample" + "@" + "example.com")
        self.assertEqual(self.git("show", "-s", "--format=%P", "HEAD").strip(), b"")
        output = self.invoke("--history", use_git=True, expected=1)
        self.assertRegex(output, r"ERROR commit:[0-9a-f]+ \[commit-author-email\]")

    def test_symlink_outside_root_is_not_read(self):
        outside = self.external("outside.txt", credential("sk" + "-"))
        (self.root / "linked.txt").symlink_to(outside)
        self.assertIn("outside scan root", self.invoke(expected=2))

    def test_default_root_independent_of_current_directory(self):
        source = Path(checker.__file__).resolve()
        script = self.write("scripts/" + source.name, source.read_text(encoding="utf-8"))
        result = subprocess.run([sys.executable, str(script), "--no-git"], cwd=self.base,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        self.assertEqual(result.returncode, 0, "standalone default-root execution failed")
        self.assertIn("RESULT: PASS", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
