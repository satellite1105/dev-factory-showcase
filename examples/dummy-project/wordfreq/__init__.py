"""wordfreq: 単語頻度カウンタ(説明用のサンプル)。"""
from .core import (
    TOKEN_PATTERN,
    count_words,
    format_rows,
    load_stopwords,
    tokenize,
    top_n,
)

__version__ = "0.1.0"

__all__ = [
    "TOKEN_PATTERN",
    "count_words",
    "format_rows",
    "load_stopwords",
    "tokenize",
    "top_n",
]
