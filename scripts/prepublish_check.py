#!/usr/bin/env python3
"""Offline checks for material intended for publication (Python 3.9+)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata
from urllib.parse import urlsplit

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2
EXTERNAL_SKILL_NAMES: tuple[str, ...] = ()
SKILL_NAMES_LOCAL = "scripts/skill-names.local.txt"
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net",
                         "users.noreply.github.com", "noreply.github.com")
DEFAULT_MAX_SIZE = 1_048_576
DEFAULT_MIN_MATCH = 50
REFERENCE_ENV = "PREPUBLISH_REFERENCES"


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    line: int | None
    message: str


class CheckError(Exception):
    """Only fixed, safe messages may be passed to this exception."""


@dataclass
class ScanContext:
    denylist: list[tuple[int, str]] = field(default_factory=list)
    skill_names: tuple[str, ...] = EXTERNAL_SKILL_NAMES
    max_size: int = DEFAULT_MAX_SIZE
    excluded: set[Path] = field(default_factory=set)
    references: ReferenceIndex | None = None


HOME_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+|~/[A-Za-z0-9._-]+/")
EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                      r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}")
KEY_RE = re.compile(
    r"sk-" + r"[A-Za-z0-9_-]{20,}|(?:ghp_|gho_|github_pat_)"
    + r"[A-Za-z0-9_]{20,}|AKIA" + r"[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9]{10,}|"
    + r"-----BEGIN" + r"[A-Z ]*PRIVATE KEY-----")
ASSIGN_RE = re.compile(
    r"\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?"
    r"([^\s'\"`,;\]}]+)", re.IGNORECASE)
VALUE_RE = re.compile(r"[A-Za-z0-9_\-+/=.]{12,}\Z")
INTERNAL_RE = re.compile(r"\." + r"claude/(?:settings[^/\s]*\.json|hooks/)")
HTTP_URL_RE = re.compile(r"\bhttps?" + r"://[^\s<>\"'()\[\]{},;]+", re.IGNORECASE)
SESSION_PATHS = (
    ("claude" + ".ai", re.compile(r"/(?:code/" + r"session_|chat/|share/)", re.IGNORECASE)),
    ("chatgpt" + ".com", re.compile(r"/(?:c|share)/", re.IGNORECASE)),
    ("chat.openai" + ".com", re.compile(r"/(?:c|share)/", re.IGNORECASE)),
)
IP_OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
INTERNAL_HOST_RE = re.compile(
    r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0|"
    + r"10\." + IP_OCTET + r"\." + IP_OCTET + r"\." + IP_OCTET
    + r"|192\.168\." + IP_OCTET + r"\." + IP_OCTET
    + r"|172\.(?:1[6-9]|2[0-9]|3[01])\." + IP_OCTET + r"\." + IP_OCTET
    + r"|(?:[a-z0-9-]+\.)+(?:local|internal|corp|lan))\Z", re.IGNORECASE)
SESSION_TRAILER_RE = re.compile(r"^Claude" + r"-Session:", re.IGNORECASE | re.MULTILINE)
COAUTHOR_RE = re.compile(
    r"^Co" + r"-Authored-By:[ \t]+[^<>\r\n]+<("
    + re.escape("noreply" + "@" + "anthropic.com") + r")>[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE)
SENSITIVE_RE = re.compile(
    r"(?:\.env(?:\..*)?|id_rsa.*|id_ed25519.*|.*\.(?:pem|key|p12|pfx)|.*\.keychain.*)\Z",
    re.IGNORECASE)


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def email_allowed(address: str) -> bool:
    return address.rsplit("@", 1)[-1].lower() in ALLOWED_EMAIL_DOMAINS


def scan_text(rel: str, text: str, ctx: ScanContext, *,
              history_message: bool = False) -> list[Finding]:
    findings = []

    def add(category: str, offset: int, message: str) -> None:
        findings.append(Finding("ERROR", category, rel, text.count("\n", 0, offset) + 1, message))

    for regex, category, message in (
        (HOME_RE, "home-path", "home directory path detected"),
        (KEY_RE, "api-key-like", "credential-like text detected"),
        (INTERNAL_RE, "internal-config-path", "internal configuration path detected"),
    ):
        for match in regex.finditer(text):
            add(category, match.start(), message)
    for match in HTTP_URL_RE.finditer(text):
        try:
            url = urlsplit(match.group().rstrip(".!"))
            host = (url.hostname or "").rstrip(".")
        except ValueError:
            continue
        if any(host == domain and path.match(url.path) for domain, path in SESSION_PATHS):
            add("session-url", match.start(), "session URL detected")
        if INTERNAL_HOST_RE.fullmatch(host):
            add("internal-url", match.start(), "internal URL detected")
    if history_message:
        for match in SESSION_TRAILER_RE.finditer(text):
            add("session-trailer", match.start(), "session trailer detected")
    exempt_email_spans = set()
    if history_message:
        exempt_email_spans.update(match.span(1) for match in COAUTHOR_RE.finditer(text))
    for match in EMAIL_RE.finditer(text):
        if match.span() not in exempt_email_spans and not email_allowed(match.group()):
            add("email", match.start(), "non-example email address detected")
    for match in ASSIGN_RE.finditer(text):
        value = match.group(1)
        if "<" not in value and VALUE_RE.fullmatch(value) and len(set(value)) > 1:
            add("secret-assignment", match.start(), "credential assignment detected")
    for row, line in enumerate(text.split("\n"), 1):
        for number, term in ctx.denylist:
            if term in normalized(line):
                findings.append(Finding("ERROR", "denylist", rel, row,
                                        f"denylist term #{number} detected"))
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        front = []
        for line in lines[1:21]:
            if line.strip() == "---":
                if all(any(re.match(r"^" + key + r"\s*:", item) for item in front)
                       for key in ("name", "description")):
                    add("skill-body", 0, "skill front matter detected")
                break
            front.append(line)
    for number, name in enumerate(ctx.skill_names, 1):
        if "-" in name:
            for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.IGNORECASE):
                add("external-skill-mention", match.start(), f"external skill name #{number} detected")
    return findings


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    except OSError:
        raise CheckError("git operation unavailable") from None


def git_available(root: Path) -> bool:
    return bool(shutil.which("git")) and git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == b"true"


def collect_files(root: Path, use_git: bool) -> tuple[list[Path], int]:
    if use_git and git_available(root):
        result = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        ignored = git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
        if result.returncode or ignored.returncode:
            raise CheckError("file enumeration failed")
        files = [root / os.fsdecode(p) for p in result.stdout.split(b"\0") if p]
        count = sum((root / os.fsdecode(p)).exists() for p in ignored.stdout.split(b"\0") if p)
        return sorted(set(p for p in files if p.is_file())), count
    files = []

    def fail(_error: OSError) -> None:
        raise CheckError("file enumeration failed")

    for directory, dirs, names in os.walk(root, onerror=fail):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__"))
        files.extend(Path(directory) / name for name in sorted(names))
    return files, 0


def safe_file(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise CheckError("file points outside scan root") from None


def scan_paths(files: list[Path], root: Path, ctx: ScanContext) -> list[Finding]:
    findings = []
    for path in files:
        if path.resolve() in ctx.excluded:
            continue
        safe_file(path, root)
        rel = path.relative_to(root).as_posix()
        name = path.name
        categories = []
        if name.lower() != ".env.example" and SENSITIVE_RE.fullmatch(name):
            categories.append(("sensitive-filename", "sensitive file name detected"))
        if name.lower() == "skill.md":
            categories.append(("skill-file", "skill definition file detected"))
        for number, skill in enumerate(ctx.skill_names, 1):
            if any(part.lower() == skill.lower() for part in path.relative_to(root).parts):
                categories.append(("external-skill-dir", f"external skill path #{number} detected"))
        if path.stat().st_size > ctx.max_size:
            categories.append(("large-file", "file exceeds size limit"))
        with path.open("rb") as source:
            if b"\0" in source.read(8192):
                categories.append(("binary-file", "binary file detected"))
        findings.extend(Finding("ERROR", cat, rel, None, msg) for cat, msg in categories)
        # Paths themselves can contain sensitive text as well as file contents.
        findings.extend(Finding(f.severity, f.category, rel, None, f.message)
                        for f in scan_text(rel, rel, ctx))
    return findings


def normalize_with_lines(text: str) -> tuple[str, list[int]]:
    chars, rows = [], []
    for row, line in enumerate(text.split("\n"), 1):
        clean = "".join(c for c in unicodedata.normalize("NFKC", line) if not c.isspace())
        chars.append(clean)
        rows.extend([row] * len(clean))
    return "".join(chars), rows


@dataclass
class ReferenceIndex:
    min_match: int = DEFAULT_MIN_MATCH
    windows: list[set[str]] = field(default_factory=list)

    def add(self, texts: list[str]) -> None:
        windows = set()
        for text in texts:
            clean, _ = normalize_with_lines(text)
            for start in range(len(clean) - self.min_match + 1):
                window = clean[start:start + self.min_match]
                if any(not (c.isdigit() or (c.isascii() and not c.isalnum())) for c in window):
                    windows.add(window)
        self.windows.append(windows)


def scan_verbatim(rel: str, text: str, ref_index: ReferenceIndex) -> list[Finding]:
    clean, rows = normalize_with_lines(text)
    findings = []
    width = ref_index.min_match
    for number, windows in enumerate(ref_index.windows, 1):
        start_run = last = None

        def emit() -> None:
            if start_run is not None:
                a, b = rows[start_run], rows[last + width - 1]
                findings.append(Finding("ERROR", "verbatim-match", rel, a,
                    f"verbatim match with reference #{number} (>= {width} chars, lines {a}-{b})"))

        for start in range(max(0, len(clean) - width + 1)):
            if clean[start:start + width] in windows:
                if start_run is None:
                    start_run = start
                last = start
            else:
                emit()
                start_run = last = None
        emit()
    return findings


def scan_history(root: Path, ctx: ScanContext) -> list[Finding]:
    commits = git(root, "rev-list", "--all")
    if commits.returncode:
        raise CheckError("history enumeration failed")
    result = git(root, "log", "--all", "-p", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--full-history", "--src-prefix=a/", "--dst-prefix=b/",
                 "--format=%x1e%H%x00%h%x00%P%x00%an%x00%ae%x00%cn%x00%ce", "--", ".")
    if result.returncode:
        raise CheckError("history scan failed")
    findings = []
    if not commits.stdout.strip():
        findings.append(Finding("INFO", "history", "-", None, "no commits"))
    # Commit messages cannot contain NUL; other separators can occur in their bodies.
    messages = git(root, "log", "--all", "-z", "--format=%H%x00%h%x00%B")
    if messages.returncode:
        raise CheckError("history message scan failed")
    fields = messages.stdout.split(b"\0")
    if fields.pop() != b"" or len(fields) % 3:
        raise CheckError("history format invalid")
    message_shas = set()
    for index in range(0, len(fields), 3):
        sha, short, body = (part.decode("utf-8", errors="replace")
                            for part in fields[index:index + 3])
        if (not re.fullmatch(r"[0-9a-f]{40}", sha)
                or not re.fullmatch(r"[0-9a-f]+", short) or not sha.startswith(short)
                or sha in message_shas):
            raise CheckError("history format invalid")
        message_shas.add(sha)
        rel = "commit:" + short
        findings.extend(Finding("ERROR", "history-message-" + item.category,
                                rel, item.line, item.message)
                        for item in scan_text(rel, body, ctx, history_message=True))
    if message_shas != set(commits.stdout.decode("ascii").splitlines()):
        raise CheckError("history format invalid")
    for record in result.stdout.decode("utf-8", errors="replace").split("\x1e")[1:]:
        header, _, patch = record.partition("\n")
        parts = header.split("\0")
        if (len(parts) != 7 or not re.fullmatch(r"[0-9a-f]{40}", parts[0])
                or not re.fullmatch(r"[0-9a-f]+", parts[1])):
            raise CheckError("history format invalid")
        _sha, short, _parents, _author_name, author_email, _committer_name, committer_email = parts
        rel = "commit:" + short
        if not email_allowed(author_email) or not email_allowed(committer_email):
            findings.append(Finding("ERROR", "commit-author-email", rel, None,
                                    "non-example commit email detected"))
        # Scan contiguous additions separately, retaining front matter at their start.
        blocks, current = [], []
        in_hunk = False
        for line in patch.splitlines():
            if line.startswith("@@"):
                in_hunk = True
            if in_hunk and line.startswith("+"):
                current.append(line[1:])
            else:
                if current:
                    blocks.append("\n".join(current))
                    current = []
                if line.startswith("diff --git "):
                    in_hunk = False
        if current:
            blocks.append("\n".join(current))
        for added in blocks:
            items = scan_text(rel, added, ctx)
            if ctx.references:
                items.extend(scan_verbatim(rel, added, ctx.references))
            findings.extend(Finding("ERROR", "history-" + f.category, rel, f.line, f.message) for f in items)
    return findings


class SafeParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise CheckError("invalid arguments")


def read_terms(paths: list[Path], kind: str) -> list[str]:
    terms = []
    for number, path in enumerate(paths, 1):
        try:
            terms.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                         if line.strip() and not line.lstrip().startswith("#"))
        except (OSError, UnicodeError, ValueError):
            raise CheckError(f"{kind} #{number} unreadable") from None
    return terms


def read_references(paths: list[Path], width: int) -> ReferenceIndex:
    index = ReferenceIndex(width)
    for number, path in enumerate(paths, 1):
        try:
            if not path.exists():
                raise OSError()
            candidates = []
            if path.is_dir():
                def fail(_error: OSError) -> None:
                    raise OSError()
                for directory, dirs, names in os.walk(path, onerror=fail):
                    dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
                    candidates.extend(Path(directory) / name for name in sorted(names))
            else:
                candidates = [path]
            texts = []
            for candidate in candidates:
                if candidate.is_symlink() or candidate.stat().st_size > 2 * 1_048_576:
                    continue
                try:
                    texts.append(candidate.read_text(encoding="utf-8"))
                except UnicodeError:
                    if not path.is_dir():
                        raise
            index.add(texts)
        except (OSError, UnicodeError, ValueError):
            raise CheckError(f"reference #{number} unreadable") from None
    return index


def display_path(path: str, ctx: ScanContext) -> str:
    if path == "-" or path.startswith("commit:"):
        return path
    if (scan_text("-", path, ctx) or any(name.lower() in path.lower() for name in ctx.skill_names)
            or any(ord(c) < 32 or ord(c) == 127 for c in path)):
        return "[redacted-path]"
    return path


def print_results(findings: list[Finding], ctx: ScanContext, failed: bool = False) -> int:
    for item in findings:
        location = display_path(item.path, ctx)
        if item.line is not None:
            location += f":{item.line}"
        print(f"{item.severity:<5} {location} [{item.category}] {item.message}")
    errors = sum(f.severity == "ERROR" for f in findings)
    warnings = sum(f.severity == "WARN" for f in findings)
    print(f"RESULT: {'FAIL' if errors or failed else 'PASS'} (errors={errors}, warnings={warnings})")
    return EXIT_VIOLATION if errors else EXIT_OK


def run(argv: list[str] | None = None) -> int:
    ctx = ScanContext()
    findings = []
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
        for option in ("--denylist", "--reference", "--skill-names"):
            parser.add_argument(option, type=Path, action="append", default=[])
        parser.add_argument("--min-match", type=int, default=DEFAULT_MIN_MATCH)
        parser.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE)
        parser.add_argument("--history", action="store_true")
        parser.add_argument("--no-git", action="store_true")
        args = parser.parse_args(argv)
        if args.min_match < 1 or args.max_size < 1 or not args.root.is_dir():
            raise CheckError("invalid scan options")
        root = args.root.resolve()
        deny_paths = args.denylist
        local = root / "scripts" / "denylist.local.txt"
        if not deny_paths and local.exists():
            deny_paths = [local]
        skill_paths = list(args.skill_names)
        local = root / SKILL_NAMES_LOCAL
        if local.exists():
            skill_paths.insert(0, local)
        ctx.excluded = {p.resolve() for p in deny_paths + skill_paths}
        ctx.max_size = args.max_size
        for number, term in enumerate(read_terms(deny_paths, "denylist"), 1):
            term = normalized(term)
            if len(term) < 3:
                findings.append(Finding("WARN", "denylist-short", "-", None,
                                        f"denylist term #{number} ignored (too short)"))
            else:
                ctx.denylist.append((number, term))
        ctx.skill_names = tuple(dict.fromkeys(name.lower() for name in
            (*EXTERNAL_SKILL_NAMES, *read_terms(skill_paths, "skill names"))))
        if not ctx.skill_names:
            findings.append(Finding("WARN", "skill-names-empty", "-", None, "no external skill names loaded"))
        references = list(args.reference)
        references.extend(Path(p) for p in os.environ.get(REFERENCE_ENV, "").split(os.pathsep) if p)
        if references:
            ctx.references = read_references(references, args.min_match)
        else:
            findings.append(Finding("INFO", "verbatim", "-", None, "skipped (no reference)"))
        use_git = not args.no_git and git_available(root)
        if not use_git:
            findings.append(Finding("INFO", "git", "-", None, "git unavailable; filesystem walk used"))
        if args.history and not use_git:
            raise CheckError("history requires git working tree")
        files, ignored = collect_files(root, use_git)
        files = [p for p in files if p.resolve() not in ctx.excluded]
        if use_git:
            findings.append(Finding("INFO", "ignored-files", "-", None,
                                    f"{ignored} ignored file(s) present (not scanned)"))
            config = git(root, "config", "user.email")
            if config.returncode not in (0, 1):
                raise CheckError("git configuration unreadable")
            email = config.stdout.decode("utf-8", errors="replace").strip()
            if email and not email_allowed(email):
                findings.append(Finding("WARN", "git-author-config", "-", None,
                    "configured git user.email is not a noreply/example address"))
        path_findings = scan_paths(files, root, ctx)
        findings.extend(path_findings)
        unread_text = {f.path for f in path_findings if f.category in ("large-file", "binary-file")}
        for path in files:
            rel = path.relative_to(root).as_posix()
            if rel in unread_text:
                continue
            text = path.read_bytes().decode("utf-8", errors="replace")
            findings.extend(scan_text(rel, text, ctx))
            if ctx.references:
                findings.extend(scan_verbatim(rel, text, ctx.references))
        if args.history:
            findings.extend(scan_history(root, ctx))
        return print_results(findings, ctx)
    except CheckError as error:
        print(str(error), file=sys.stderr)
    except (OSError, UnicodeError, ValueError):
        print("scan input unreadable", file=sys.stderr)
    print_results(findings, ctx, failed=True)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(run())
