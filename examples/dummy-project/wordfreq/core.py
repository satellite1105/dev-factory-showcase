"""単語頻度カウンタの中核ロジック(説明用のサンプル)。

架空の小さなツールで、標準ライブラリだけで動く。
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter

TOKEN_PATTERN = r"\w+(?:'\w+)?"   # re.UNICODE。数字だけのトークンも語として数える
_TOKEN_RE = re.compile(TOKEN_PATTERN, re.UNICODE)


def tokenize(text: str, *, lowercase: bool = True) -> list[str]:
    """TOKEN_PATTERN で抜き出す。lowercase=True なら str.casefold() をかける。空文字列なら []。"""
    tokens = _TOKEN_RE.findall(text)
    if lowercase:
        tokens = [t.casefold() for t in tokens]
    return tokens


def count_words(text: str, *, lowercase: bool = True,
                stopwords: frozenset[str] = frozenset()) -> Counter[str]:
    """tokenize してから stopwords を除いて数える。stopwords も同じ正規化(casefold)で比べる。"""
    stops = frozenset(w.casefold() for w in stopwords)
    counter: Counter[str] = Counter()
    for token in tokenize(text, lowercase=lowercase):
        if token.casefold() in stops:
            continue
        counter[token] += 1
    return counter


def top_n(counter: Counter[str], n: int) -> list[tuple[str, int]]:
    """回数の多い順、同じ回数なら語の昇順。n < 1 は ValueError。"""
    if n < 1:
        raise ValueError("n must be >= 1")
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def format_rows(rows: list[tuple[str, int]], fmt: str = "text") -> str:
    """fmt: "text" は `<語>\\t<回数>` の行。"csv" は見出し行 `word,count` つき。
    "json" は [{"word": ..., "count": ...}] を ensure_ascii=False で出す。それ以外は ValueError。
    rows が空のとき、text は空文字列、csv は見出しだけ、json は "[]"。"""
    if fmt == "text":
        return "".join(f"{word}\t{count}\n" for word, count in rows)
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["word", "count"])
        writer.writerows(rows)
        return buf.getvalue()
    if fmt == "json":
        return json.dumps(
            [{"word": w, "count": c} for w, c in rows], ensure_ascii=False
        )
    raise ValueError(f"unknown format: {fmt}")


def load_stopwords(path: str) -> frozenset[str]:
    """UTF-8 で1行1語。空行と # で始まる行は飛ばす。"""
    words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.add(line)
    return frozenset(words)
