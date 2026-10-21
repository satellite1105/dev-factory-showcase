#!/usr/bin/env python3
"""Check local documentation without fetching external resources."""

import argparse
from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from typing import Optional
from urllib.parse import unquote, urlsplit

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE = 0, 1, 2
REQUIRED_FILES = (
    "README.md", "LICENSE", "SECURITY.md", ".gitignore",
    "docs/architecture.md", "docs/development-flow.md", "docs/roles.md",
    "docs/delegation-and-state.md", "docs/verification-status.md",
    "docs/case-study.md", "docs/prepublish-checklist.md",
    "docs/rights-and-attribution.md", "docs/public-release-gate.md",
    "examples/dummy-project/README.md", "examples/dummy-project/spec.md",
    "examples/dummy-project/PROJECT_STATE.md", "examples/dummy-project/REVIEW.md",
    "scripts/prepublish_check.py", "scripts/test_prepublish_check.py",
    "scripts/check_docs.py", "scripts/test_check_docs.py",
    "scripts/denylist.example.txt",
)
MERMAID_REQUIRED = ("docs/architecture.md", "docs/development-flow.md")
DIAGRAM_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "stateDiagram-v2",
    "stateDiagram", "classDiagram", "erDiagram", "gantt", "journey", "pie",
    "gitGraph", "mindmap", "timeline",
)
RECONSTRUCTION_MARKER = "説明用の再構成"
RECONSTRUCTION_FILES = (
    "docs/case-study.md", "examples/dummy-project/README.md",
    "examples/dummy-project/spec.md", "examples/dummy-project/PROJECT_STATE.md",
    "examples/dummy-project/REVIEW.md",
)
STATUS_LABELS = ("実機検証済み", "一部検証", "設計済み(未検証)")
FORBIDDEN_WORK_RECORDS = (
    "PROJECT_STATE.md", "docs/spec.md", "docs/design.md", "docs/tasks.md",
    "docs/facts.md", "docs/reviews", "memory",
)
GITIGNORE_REQUIRED = (".env*", "*.local.*", "denylist.local.txt", "tmp/", "__pycache__/")
STATUS_PATH = "docs/verification-status.md"
STATUS_COLUMNS = ("ID", "項目", "ステータス", "根拠", "限界・注記")


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    line: Optional[int]
    message: str


def _error(category, path, line, message):
    return Finding("ERROR", category, path, line, message)


def _inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _documents(root):
    """Do not follow directory symlinks or read files outside the root."""
    found = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__")
                         and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() == ".md" and _inside(path, root):
                found.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
    return found


def _blank(text):
    return re.sub(r"[^\n]", " ", text)


def _fences(text):
    """Return prose with fenced code masked and (start, info, body, closed)."""
    prose, blocks, body = [], [], []
    active = None
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        if active is None:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})([^\n]*)", line)
            if opening:
                fence, info = opening.groups()
                active = (number, fence, info.strip())
                body = []
                prose.append(_blank(line))
            else:
                prose.append(line)
        else:
            start, fence, info = active
            closing = re.fullmatch(r" {0,3}" + re.escape(fence[0])
                                   + "{" + str(len(fence)) + r",}\s*", line)
            prose.append(_blank(line))
            if closing:
                blocks.append((start, info, body, True))
                active = None
            else:
                body.append((number, line.rstrip("\r\n")))
    if active:
        blocks.append((active[0], active[2], body, False))
    return "".join(prose), blocks


def _prose(text):
    text = _fences(text)[0]
    # Equal length backtick runs delimit inline code, including multiline spans.
    pattern = r"(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)"
    return re.sub(pattern, lambda match: _blank(match.group()), text)


def extract_links(md_text):
    text = _prose(md_text)
    links = []
    definition = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|(\S+))", re.M)
    for match in definition.finditer(text):
        links.append((text.count("\n", 0, match.start()) + 1,
                      match.group(1) or match.group(2)))
    opening = re.compile(r"!?\[(?:\\.|[^\]\\\n])*\]\(\s*")
    for match in opening.finditer(text):
        start = match.end()
        if start < len(text) and text[start] == "<":
            end = text.find(">", start + 1)
            if end == -1:
                continue
            target = text[start + 1:end]
            tail = text[end + 1:]
            if not re.match(r'\s*(?:["\'][^\n]*?["\']\s*)?\)', tail):
                continue
        else:
            depth, end = 0, start
            while end < len(text):
                char = text[end]
                if char == "\\" and end + 1 < len(text):
                    end += 2
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        break
                    depth -= 1
                elif char.isspace() and depth == 0:
                    break
                end += 1
            target = text[start:end]
            if not re.match(r'\s*(?:["\'][^\n]*?["\']\s*)?\)', text[end:]):
                continue
        links.append((text.count("\n", 0, match.start()) + 1,
                      re.sub(r"\\([\\()\[\] ])", r"\1", target)))
    return sorted(links)


def github_slug(heading):
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", heading.lower()))


def _anchors(text):
    used = set()
    lines = _fences(text)[0].splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        heading = match.group(1) if match else None
        if heading is None and index + 1 < len(lines) and line.strip():
            if re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1]):
                heading = line.strip()
        if heading is None:
            continue
        heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", heading)
        base, suffix = github_slug(heading), 0
        slug = base
        while slug in used:
            suffix += 1
            slug = base + "-" + str(suffix)
        used.add(slug)
    return used


def _target(root, source, target):
    parts = urlsplit(target)
    if parts.scheme.lower() in ("http", "https", "mailto") or parts.netloc:
        return "external", None, ""
    if parts.scheme:
        return "outside", None, ""
    path = root / source if not parts.path else (root / source).parent / unquote(parts.path)
    path = path.resolve()
    return ("local" if _inside(path, root) else "outside"), path, unquote(parts.fragment)


def check_required(root):
    return [_error("required-file", rel, None, "required file is missing or outside root")
            for rel in REQUIRED_FILES
            if not (root / rel).is_file() or not _inside(root / rel, root)]


def check_links(root):
    findings, external = [], 0
    for rel, text in _documents(root):
        for line, target in extract_links(text):
            kind, path, fragment = _target(root, rel, target)
            if kind == "external":
                external += 1
            elif kind == "outside":
                findings.append(_error("link-outside-root", rel, line, "link leaves repository root"))
            elif not path.exists():
                findings.append(_error("broken-link", rel, line, "local link target does not exist"))
            elif fragment and path.is_file() and path.suffix.lower() == ".md":
                if fragment not in _anchors(path.read_text(encoding="utf-8")):
                    findings.append(_error("broken-anchor", rel, line, "heading anchor does not exist"))
    findings.append(Finding("INFO", "external-links", "-", None, str(external) + " not checked"))
    return findings


def check_reachability(root):
    documents = dict(_documents(root))
    visited, pending = set(), deque(["README.md"])
    while pending:
        rel = pending.popleft()
        if rel in visited or rel not in documents:
            continue
        visited.add(rel)
        for _, target in extract_links(documents[rel]):
            kind, path, _ = _target(root, rel, target)
            if kind == "local" and path.suffix.lower() == ".md":
                pending.append(path.relative_to(root.resolve()).as_posix())
    return [_error("unreachable", rel, None, "required document is unreachable from README")
            for rel in REQUIRED_FILES if rel.endswith(".md") and rel not in visited]


def _brackets_balanced(line):
    stack, quoted = [], False
    pairs = {"]": "[", ")": "(", "}": "{"}
    for char in line:
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char in "[({":
                stack.append(char)
            elif char in "])}" and (not stack or stack.pop() != pairs[char]):
                return False
    return not stack and not quoted


def check_mermaid(root):
    findings, present = [], set()
    for rel, text in _documents(root):
        for start, info, body, closed in _fences(text)[1]:
            if info != "mermaid":
                continue
            present.add(rel)
            if not closed:
                findings.append(_error("mermaid-unclosed", rel, start, "Mermaid fence is not closed"))
            meaningful = [(n, line.strip()) for n, line in body
                          if line.strip() and not line.strip().startswith("%%")]
            first = meaningful[0] if meaningful else (start, "")
            diagram = first[1].split()[0] if first[1] else ""
            if diagram not in DIAGRAM_TYPES:
                findings.append(_error("mermaid-type", rel, first[0], "unknown diagram type"))
            elif diagram in ("flowchart", "graph"):
                if not re.match(r"^(?:flowchart|graph)\s+(?:TD|TB|BT|LR|RL)(?:\s|;|$)", first[1]):
                    findings.append(_error("mermaid-direction", rel, first[0], "invalid flow direction"))
            subgraphs = sum(bool(re.match(r"subgraph\b", line)) for _, line in meaningful)
            ends = sum(line == "end" for _, line in meaningful)
            if subgraphs != ends:
                findings.append(_error("mermaid-subgraph", rel, start, "subgraph and end counts differ"))
            for number, line in body:
                stripped = line.strip()
                if stripped.startswith("%%"):
                    if re.match(r"%%\s*\{\s*init\b", stripped):
                        findings.append(_error("mermaid-unsupported", rel, number, "diagram directive is unsupported"))
                    continue
                if not _brackets_balanced(line):
                    findings.append(_error("mermaid-brackets", rel, number, "unbalanced diagram brackets or quotes"))
                tags = re.findall(r"<[^>]+>", line)
                if (any(tag != "<br/>" for tag in tags)
                        or re.match(r"\s*click\b", line)
                        or re.search(r"\b(?:img|image)\s*:", line)):
                    findings.append(_error("mermaid-unsupported", rel, number, "unsupported diagram content"))
    findings.extend(_error("mermaid-missing", rel, None, "required Mermaid block is missing")
                    for rel in MERMAID_REQUIRED if rel not in present)
    return findings


def check_markers(root):
    documents = dict(_documents(root))
    findings = []
    for rel in RECONSTRUCTION_FILES:
        if RECONSTRUCTION_MARKER not in "\n".join(documents.get(rel, "").splitlines()[:10]):
            findings.append(_error("marker-missing", rel, None, "reconstruction marker missing from first ten lines"))
    return findings


def _cells(line):
    return [cell.strip().strip("`") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _tables(text):
    lines = _fences(text)[0].splitlines()
    index = 0
    while index + 1 < len(lines):
        header, divider = _cells(lines[index]), _cells(lines[index + 1])
        if ("|" not in lines[index] or len(header) != len(divider)
                or not all(re.fullmatch(r":?-+:?", cell) for cell in divider)):
            index += 1
            continue
        index += 2
        rows = []
        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            rows.append((index + 1, _cells(lines[index])))
            index += 1
        yield header, rows


def _valid_id(value):
    return bool(re.fullmatch(r"(?:V(?:0[1-9]|1[0-9]|2[0-4])|P0[1-8])", value))


def _status_data(root):
    documents = dict(_documents(root))
    findings, statuses, seen, count = [], {}, set(), 0
    for header, rows in _tables(documents.get(STATUS_PATH, "")):
        if not header or header[0] != "ID":
            continue
        count += 1
        if tuple(header) != STATUS_COLUMNS:
            findings.append(_error("status-table", STATUS_PATH, None, "invalid status table columns"))
            continue
        for number, cells in rows:
            if len(cells) != len(STATUS_COLUMNS):
                findings.append(_error("status-table", STATUS_PATH, number, "invalid status row columns"))
                continue
            identifier, _, label, evidence, _ = cells
            if not _valid_id(identifier) or identifier in seen:
                findings.append(_error("status-id", STATUS_PATH, number, "invalid or duplicate status ID"))
            seen.add(identifier)
            if label not in STATUS_LABELS:
                findings.append(_error("status-label", STATUS_PATH, number, "invalid status label"))
            if label == STATUS_LABELS[0] and (evidence == "-" or len(evidence) < 10):
                findings.append(_error("status-evidence", STATUS_PATH, number, "verified row needs substantive evidence"))
            statuses.setdefault(identifier, label)
    if not count:
        findings.append(_error("status-table", STATUS_PATH, None, "status table is missing"))
    return findings, statuses


def check_status_table(root):
    return _status_data(root)[0]


def check_status_consistency(root):
    statuses = _status_data(root)[1]
    findings = []
    for rel, text in _documents(root):
        if rel == STATUS_PATH:
            continue
        mentions = []
        for number, line in enumerate(_prose(text).splitlines(), 1):
            for match in re.finditer(r"検証ステータス\s*[:：]\s*([^\n/]+?)\s*/\s*([A-Za-z]\d+)\b", line):
                mentions.append((number, match.group(2), match.group(1).strip()))
        for header, rows in _tables(text):
            if "ID" in header and "ステータス" in header:
                id_col, label_col = header.index("ID"), header.index("ステータス")
                for number, cells in rows:
                    if len(cells) <= max(id_col, label_col):
                        findings.append(_error("status-mismatch", rel, number, "incomplete status reference row"))
                    else:
                        mentions.append((number, cells[id_col], cells[label_col]))
        for number, identifier, label in mentions:
            if identifier not in statuses or not _valid_id(identifier):
                findings.append(_error("status-unknown-id", rel, number, "status ID is absent from canonical table"))
            elif label != statuses[identifier]:
                findings.append(_error("status-mismatch", rel, number, "status label differs from canonical table"))
    return findings


def check_work_records(root):
    return [_error("work-record", rel, None, "private work record is present")
            for rel in FORBIDDEN_WORK_RECORDS if os.path.lexists(root / rel)]


def check_gitignore(root):
    path = root / ".gitignore"
    lines = set(path.read_text(encoding="utf-8").splitlines()) if path.is_file() and _inside(path, root) else set()
    return [_error("gitignore-missing", ".gitignore", None, "required ignore rule is missing")
            for rule in GITIGNORE_REQUIRED if rule not in lines]


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if not root.is_dir():
            raise OSError
        findings = []
        for check in (check_required, check_links, check_reachability, check_mermaid,
                      check_markers, check_status_table, check_status_consistency,
                      check_work_records, check_gitignore):
            findings.extend(check(root))
    except (OSError, UnicodeError, ValueError):
        print("ERROR - [runtime] documentation input could not be read", file=sys.stderr)
        print("RESULT: FAIL (errors=1, warnings=0)")
        return EXIT_USAGE
    for finding in findings:
        # Keep a malicious filename from injecting additional report lines.
        location = finding.path.replace("\n", "\\n").replace("\r", "\\r")
        if finding.line is not None:
            location += ":" + str(finding.line)
        print(f"{finding.severity} {location} [{finding.category}] {finding.message}")
    errors = sum(f.severity == "ERROR" for f in findings)
    warnings = sum(f.severity == "WARN" for f in findings)
    print(f"RESULT: {'FAIL' if errors else 'PASS'} (errors={errors}, warnings={warnings})")
    return EXIT_VIOLATION if errors else EXIT_OK


if __name__ == "__main__":
    sys.exit(run())
