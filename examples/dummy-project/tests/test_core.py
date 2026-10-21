"""wordfreq.core のテスト(説明用のサンプル)。"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from collections import Counter

from wordfreq.core import (
    count_words,
    format_rows,
    load_stopwords,
    tokenize,
    top_n,
)


class TestTokenize(unittest.TestCase):
    def test_lowercase_default(self):
        self.assertEqual(tokenize("Hello WORLD"), ["hello", "world"])

    def test_no_lowercase(self):
        self.assertEqual(tokenize("Hello WORLD", lowercase=False), ["Hello", "WORLD"])

    def test_apostrophe(self):
        self.assertEqual(tokenize("Don't stop"), ["don't", "stop"])

    def test_numbers_are_words(self):
        self.assertEqual(tokenize("room 101 and 7"), ["room", "101", "and", "7"])

    def test_empty(self):
        self.assertEqual(tokenize(""), [])

    def test_punctuation_only(self):
        self.assertEqual(tokenize("... !? ,"), [])

    def test_japanese_chunk_is_one_word(self):
        self.assertEqual(tokenize("今日は晴れ、明日は雨"), ["今日は晴れ", "明日は雨"])


class TestCountWords(unittest.TestCase):
    def test_basic(self):
        c = count_words("a b a c a b")
        self.assertEqual(c, Counter({"a": 3, "b": 2, "c": 1}))

    def test_case_folding(self):
        self.assertEqual(count_words("The the THE")["the"], 3)

    def test_stopwords_removed(self):
        c = count_words("the cat and the dog", stopwords=frozenset({"the", "and"}))
        self.assertEqual(c, Counter({"cat": 1, "dog": 1}))

    def test_stopwords_compared_with_casefold(self):
        c = count_words("The cat", stopwords=frozenset({"THE"}))
        self.assertEqual(c, Counter({"cat": 1}))

    def test_no_lowercase(self):
        c = count_words("Go go", lowercase=False)
        self.assertEqual(c, Counter({"Go": 1, "go": 1}))


class TestTopN(unittest.TestCase):
    def test_order_by_count_then_word(self):
        c = Counter({"b": 2, "a": 2, "c": 5, "d": 1})
        self.assertEqual(top_n(c, 3), [("c", 5), ("a", 2), ("b", 2)])

    def test_n_larger_than_size(self):
        self.assertEqual(top_n(Counter({"a": 1}), 10), [("a", 1)])

    def test_n_less_than_one(self):
        with self.assertRaises(ValueError):
            top_n(Counter({"a": 1}), 0)
        with self.assertRaises(ValueError):
            top_n(Counter({"a": 1}), -1)


class TestFormatRows(unittest.TestCase):
    ROWS = [("apple", 3), ("banana", 1)]

    def test_text(self):
        self.assertEqual(format_rows(self.ROWS, "text"), "apple\t3\nbanana\t1\n")

    def test_text_default(self):
        self.assertEqual(format_rows(self.ROWS), format_rows(self.ROWS, "text"))

    def test_csv(self):
        out = format_rows(self.ROWS, "csv")
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows, [["word", "count"], ["apple", "3"], ["banana", "1"]])

    def test_json(self):
        out = format_rows([("日本", 2)], "json")
        self.assertIn("日本", out)
        self.assertEqual(json.loads(out), [{"word": "日本", "count": 2}])

    def test_empty_text(self):
        self.assertEqual(format_rows([], "text"), "")

    def test_empty_csv_has_header(self):
        rows = list(csv.reader(io.StringIO(format_rows([], "csv"))))
        self.assertEqual(rows, [["word", "count"]])

    def test_empty_json(self):
        self.assertEqual(format_rows([], "json"), "[]")

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            format_rows(self.ROWS, "xml")


class TestLoadStopwords(unittest.TestCase):
    def test_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sw.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\nthe\n\n  and  \n# another\nの\n")
            self.assertEqual(load_stopwords(path), frozenset({"the", "and", "の"}))


if __name__ == "__main__":
    unittest.main()
