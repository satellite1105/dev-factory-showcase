# wordfreq: 単語頻度カウンタ

> 記述時点: 2026-10。内容は非公開の内部概要資料(v2 系)から概念レベルで書き下ろしたもので、内部仕様は今後変わる可能性があります。
> wordfreq のコードとテストは、このリポジトリを作成した dev-factory の実行の中で実装したものです。Codex へ委譲しましたが通常の失敗となり、規則どおり Claude の coder(実装)にフォールバックして実装しました。
> spec.md・PROJECT_STATE.md・REVIEW.md は説明用の再構成で、実際の実行記録ではありません。以下の架空の依頼・進行・採点を、コードとテストの実際の作成経緯と区別してください。

公開状態: 確認完了まで Private 想定

## 概要

標準入力や UTF-8 のテキストファイルから語を拾い、出現回数を集計する小さな CLI です。標準ライブラリだけを使います。件数の多い順に並べ、同数なら語の昇順に並べます。

入力ファイルを複数指定すると合算し、ファイル指定がなければ標準入力を読みます。既定では `casefold()` で大文字小文字をまとめ、上位10語をタブ区切りで出力します。`-n` で表示数、`--format text|csv|json` で出力形式を選べます。`--stopwords FILE` は UTF-8 の1行1語を除外語として読み、空行と `#` で始まる行を飛ばします。

## 使い方

リポジトリのルートから移動します。以下の3例は、このディレクトリで実行した出力です。

```sh
cd examples/dummy-project
```

### 例1: 標準入力から上位2語

```sh
printf 'Apple banana apple cherry banana apple\n' | python3 -m wordfreq -n 2
```

```text
apple	3
banana	2
```

語と回数の間はタブです。

### 例2: 大文字小文字を保持して JSON 出力

```sh
printf 'Go go GO\n' | python3 -m wordfreq --no-lowercase --format json
```

```text
[{"word": "GO", "count": 1}, {"word": "Go", "count": 1}, {"word": "go", "count": 1}]
```

この JSON 出力の末尾には改行がありません。

### 例3: 空入力でも CSV の見出しを出力

```sh
printf '' | python3 -m wordfreq --format csv
```

```text
word,count
```

## テストの実行

次のコマンドはリポジトリのルートから実行します。上の使用例を実行した場所からは `cd ../..` で戻れます。

```sh
python3 -m unittest discover -s examples/dummy-project/tests -t examples/dummy-project
```

文書作成時に実行し、`Ran 37 tests` と `OK` を確認しました。所要時間は実行ごとに変わります。この実測結果は、再構成したレビューの点数の根拠ではありません。

## 文書の役割

| 文書 | 内容 |
| --- | --- |
| [README.md](README.md) | 実装の作成経緯、実行方法、実際に確認した使用例とテスト結果 |
| [spec.md](spec.md) | 架空の依頼から要件と完了条件を整理した例 |
| [PROJECT_STATE.md](PROJECT_STATE.md) | 完了条件、担当、進捗を記録する完了済みの架空の例 |
| [REVIEW.md](REVIEW.md) | 不合格から修正を経て合格する採点の架空の例 |

## 既知の制約

日本語の形態素解析はしません。たとえば「今日は晴れ」はひとまとまりとして扱います。数字やアンダースコアも語に含み、語中の半角アポストロフィを扱います。大きな入力を少しずつ処理する方式ではなく、入力全体をメモリに読み込みます。

除外語との照合は `--no-lowercase` を指定しても大文字小文字をまとめて行います。読めない入力は終了コード1、`-n 0` などの引数の誤りは終了コード2です。
