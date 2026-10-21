"""wordfreq のコマンドライン入口(説明用のサンプル)。"""
from __future__ import annotations

import argparse
import sys

from .core import count_words, format_rows, load_stopwords, top_n


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wordfreq", description="Count word frequencies.")
    p.add_argument("files", nargs="*", metavar="FILE",
                   help='input files (default or "-": stdin)')
    p.add_argument("-n", type=int, default=10, help="number of rows (default 10)")
    p.add_argument("--no-lowercase", action="store_true", help="do not case-fold")
    p.add_argument("--stopwords", metavar="FILE", help="stopword file (one per line)")
    p.add_argument("--format", choices=["text", "csv", "json"], default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    """python3 -m wordfreq [FILE ...] [-n N] [--no-lowercase] [--stopwords FILE] [--format text|csv|json]
    戻り値: 0 = 成功、1 = 読めないファイル、2 = 引数の誤り(argparse)。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("-n must be >= 1")

    sources = args.files or ["-"]
    texts = []
    for src in sources:
        try:
            if src == "-":
                texts.append(sys.stdin.read())
            else:
                with open(src, encoding="utf-8") as f:
                    texts.append(f.read())
        except (OSError, UnicodeDecodeError):
            print(f"wordfreq: cannot read {src}", file=sys.stderr)
            return 1

    stopwords = frozenset()
    if args.stopwords:
        try:
            stopwords = load_stopwords(args.stopwords)
        except (OSError, UnicodeDecodeError):
            print(f"wordfreq: cannot read {args.stopwords}", file=sys.stderr)
            return 1

    counter = count_words("\n".join(texts), lowercase=not args.no_lowercase,
                          stopwords=stopwords)
    sys.stdout.write(format_rows(top_n(counter, args.n), args.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())
