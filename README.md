# dev-factory showcase

Claude Code と OpenAI Codex で企画から納品までをつなぐ個人開発基盤 dev-factory を、文書と小さな CLI で紹介するポートフォリオです。役割分担、失敗時の引き継ぎ、品質を判断する基準を、検証の根拠と限界までたどれます。

**このリポジトリで確認できること**

- **判断と実装の分担**: Claude は判断・統合・レビューを担い、Codex を実装の第一候補にします。実装委譲は小規模な試行で確認しています。(検証ステータス: 実機検証済み / V02)
- **独立した品質確認**: reviewer の合格基準は加重平均 0.85 以上に加え、重大な誤りや必須条件の未達がないことなどです。(検証ステータス: 実機検証済み / V06) 不合格後は最大3回の再レビューとする規則で、修正後の合格は確認済みですが、上限未達で停止する経路は未確認です。(検証ステータス: 一部検証 / V07)
- **失敗後も作業を引き継ぐ運用**: Codex 失敗時のタスク単位のフォールバックに運用記録があります。(検証ステータス: 実機検証済み / V03) インフラ系失敗の連続を受けた circuit breaker の発動実績は1件です。(検証ステータス: 実機検証済み / V04)
- **検証範囲の明示と品質チェック**: [検証ステータス](docs/verification-status.md)で設計と動作確認を区別しています。たとえば完了条件の照合は設計段階です。(検証ステータス: 設計済み(未検証) / V11) リポジトリ内ファイルの自動検査と文書の静的検査には実行記録があります。(検証ステータス: 実機検証済み / P04)(検証ステータス: 実機検証済み / P05)

## 3分で分かる概要

**何を進めるか。** dev-factory は、企画から設計、実装、統合・デバッグ、検証、納品へ開発を進めるための個人用の基盤です。Web アプリや CLI など、対象に応じて構成を選ぶ方針で、成果物を案件ごとの領域にまとめます。小規模な試行では、納品後の学習記録まで確認されています。(検証ステータス: 実機検証済み / V01)

**どう分担するか。** リーダー(オーケストレーター)が工程をつなぎ、planner(企画)、architect(設計)、coder(実装)、debugger(デバッグ)、reviewer(検証)の5役を割り振ります。Claude は設計判断・統合・レビューに集中し、実装やデバッグ、大量の調査・集計は Codex-first とする方針です。実装委譲の確認範囲は小規模な試行です。(検証ステータス: 実機検証済み / V02)

**失敗をどう扱うか。** Codex の通常の失敗では、該当タスクを Claude の coder または debugger にフォールバックします。次の独立したタスクでは再び Codex を優先します。タスク単位での引き継ぎには実運用の記録があります。(検証ステータス: 実機検証済み / V03)

インフラ系の失敗は別に数え、同じフェーズで2回続けば circuit breaker により、そのフェーズの残りを Claude へ回します。発動を確認した実例は1件です。サンプルの通常の失敗は、この発動実績には含めません。(検証ステータス: 実機検証済み / V04)

**どう品質を確認するか。** テストの成功を確認した後、実装側から独立した reviewer が要件・テスト・コード品質・文書を採点します。加重平均 0.85 以上に加え、合否の整合、重大な誤りや必須条件の未達がないことを求めます。採点にはモデルの判断を含み、同じ点数の再現を保証するものではありません。(検証ステータス: 実機検証済み / V06)

不合格なら修正して再レビューし、最大3回でも条件が揃わない場合は `blocked` とする規則です。修正後の再レビューは確認されていますが、上限未達で停止する経路は未確認です。(検証ステータス: 一部検証 / V07)

**何をもって完了とするか。** PROJECT_STATE に依頼と進捗、検証の証拠を集め、GOAL_CONTRACT で完了条件を固定し、completion gate で成果物と照合する設計です。この gate が実案件で停止を判定した記録は確認できていません。(検証ステータス: 設計済み(未検証) / V11)

## 検証ステータス早見表

**実機検証済み**は記録のある範囲で動作を確認したもの、**一部検証**は確認できた経路が限られるもの、**設計済み(未検証)**は動作の裏付けが未確認のものです。設計の存在だけで検証済みとは扱いません。

| ID | 項目 | ステータス |
|---|---|---|
| V01 | 企画から納品・学習記録までのパイプライン完走 | 実機検証済み |
| V02 | Codex への実装委譲 | 実機検証済み |
| V03 | Codex 失敗後のタスク単位のフォールバック | 実機検証済み |
| V04 | インフラ系失敗の連続を受けた circuit breaker | 実機検証済み |
| V06 | reviewer による独立採点と合格判定 | 実機検証済み |
| V07 | 不合格後の修正・再レビューと未達時の blocked | 一部検証 |
| V11 | GOAL_CONTRACT と completion gate | 設計済み(未検証) |
| V12 | 監督付き自動再開 | 一部検証 |
| V13 | 無人の自動モードによる危険操作のブロック | 実機検証済み |
| V15 | 基盤の共有領域に対する書き込みの境界 | 実機検証済み |
| V17 | Codex の作業範囲の限定 | 一部検証 |
| V18 | 作業範囲などを人が事前に承認する仕組み | 設計済み(未検証) |
| V20 | LESSONS と学習のスキル化の承認 | 実機検証済み |

根拠・確認日・限界は [verification-status.md](docs/verification-status.md) を参照してください。安全装置にも未確認の経路や既知の課題があります。実機検証済みという分類は、完全な安全性や将来の同じ動作を保証しません。基盤の仕組み(V 系列)と、このリポジトリ自身の検査(P 系列)は詳細表で分けています。

## ドキュメント案内

採用担当・発注者の方は、まず全体構成と開発事例から、設計判断と成果物の対応を確認できます。検証の範囲を評価する際は、検証ステータスの根拠と限界も併せて参照してください。

| 文書 | 確認できること |
|---|---|
| [アーキテクチャ](docs/architecture.md) | 全体構成、基盤と案件の分離、Safety 層の概念、委譲の図 |
| [開発フロー](docs/development-flow.md) | 各工程の受け渡し、品質ゲート、やり直しと停止、完了条件 |
| [役割と分担](docs/roles.md) | リーダーと5役の責務・入力・出力・担当しないこと |
| [委譲と状態管理](docs/delegation-and-state.md) | Codex-first、失敗の分類、状態記録、中断・再開、学習の扱い |
| [検証ステータス](docs/verification-status.md) | 基盤と公開用成果物それぞれの検証結果、根拠、限界 |
| [開発事例](docs/case-study.md) | 小さな CLI を題材にした要件・実装・修正・採点の説明 |
| [権利と出典の方針](docs/rights-and-attribution.md) | 書き下ろし、再配布の範囲、商標とライセンスの扱い |

## 事例とサンプル

wordfreq のコードとテストは、このリポジトリを作った dev-factory の実行中に実装した実物です。Codex へ委譲した後、通常の失敗となり、Claude の coder へフォールバックして実装しました。  
一方、[開発事例](docs/case-study.md)の進行・修正履歴・スコア、およびサンプルの要件・状態・レビュー文書は**説明用の再構成**で、実際の実行記録ではありません。

[サンプルの README](examples/dummy-project/README.md)には、単語頻度カウンタの使い方と確認結果があります。[コード](examples/dummy-project/wordfreq/core.py)と[CLI](examples/dummy-project/wordfreq/__main__.py)、[集計処理のテスト](examples/dummy-project/tests/test_core.py)・[CLI のテスト](examples/dummy-project/tests/test_cli.py)も参照できます。Python の標準ライブラリだけを使い、日本語の形態素解析は行いません。

サンプルのテストは、このリポジトリのルートから実行します。

```sh
python3 -m unittest discover -s examples/dummy-project/tests -t examples/dummy-project
```

再構成した [spec](examples/dummy-project/spec.md)、[PROJECT_STATE](examples/dummy-project/PROJECT_STATE.md)、[REVIEW](examples/dummy-project/REVIEW.md) では、要件と完了条件、進捗と証拠、採点と指摘の対応をたどれます。説明用の点数を、このリポジトリの実レビュー結果には使いません。

## 品質チェックの自動化

Python 3.9 以上で、以下をリポジトリのルートから実行します。追加パッケージは不要です。履歴検査と git を使う自己テストには git も必要です。

```sh
python3 scripts/prepublish_check.py
python3 scripts/prepublish_check.py --history
python3 scripts/check_docs.py
```

[ファイル検査](scripts/prepublish_check.py)は個人情報・秘密情報などの混入の疑いを調べ、`--history` は既存コミットの差分、author・committer のメール、コミットメッセージも検査します。[文書検査](scripts/check_docs.py)は必須ファイル、相対リンク、Mermaid の静的構造、検証ステータスの整合などを確認します。外部 URL への接続は行いません。

自己テストは次のコマンドで実行します。サンプルのテストは前節のコマンドを使います。

```sh
python3 scripts/test_prepublish_check.py
python3 scripts/test_check_docs.py
```

終了コードは `0` が違反検出なし、`1` が違反検出、`2` が引数・入力などの実行エラーです。`PASS` でも警告や検査省略の内容を確認してください。照合資料を `--reference` で指定しない場合は長文一致の検査を省略します。ローカルの禁止語は `scripts/denylist.local.txt` または `--denylist`、外部スキル名は `scripts/skill-names.local.txt` または `--skill-names` で指定できます。これらのローカル専用リストは git の対象外です。

外部スキル名のリストが空なら名前に基づく検査は働きません。本文検出はハイフンを含む名前だけが対象で、ハイフンなしの名前はディレクトリ名でのみ検出します。モデル ID や内部の名前には汎用パターンがなく、禁止語リストに登録した語だけが検出対象です。自動検査は混入がないことの証明ではなく、内容や権利の判断、GitHub 上での Mermaid の表示確認を代替しません。

## リポジトリ構成

```text
.
├── README.md
├── LICENSE
├── LICENSE-docs.md
├── SECURITY.md
├── docs/
│   ├── architecture.md
│   ├── development-flow.md
│   ├── roles.md
│   ├── delegation-and-state.md
│   ├── verification-status.md
│   ├── case-study.md
│   └── rights-and-attribution.md
├── examples/
│   └── dummy-project/
│       ├── README.md
│       ├── spec.md
│       ├── PROJECT_STATE.md
│       ├── REVIEW.md
│       ├── wordfreq/
│       └── tests/
└── scripts/
    ├── prepublish_check.py
    ├── test_prepublish_check.py
    ├── check_docs.py
    ├── test_check_docs.py
    └── denylist.example.txt
```

## 免責

非公式の個人プロジェクトであり、Anthropic・OpenAI とは無関係です。各社が提供・承認するものではありません。製品名・商標の権利は各権利者に帰属します。

外部 skill は同梱・再配布しません。内部の実装・設定は掲載せず、公開向けに書き下ろした概念説明とサンプルを収録しています。基盤一式を導入するための配布物ではありません。

学習・ポートフォリオ用途の資料とサンプルであり、品質・安全性を保証するものではありません。脆弱性や秘密情報の混入の報告方法は [SECURITY.md](SECURITY.md) を参照してください。

## ライセンス

コードは **MIT License**、文書と自作 Mermaid 図は **CC BY 4.0** を採用しています。著作権者は **© 2026 satellite1105** です。

- **MIT License**: `scripts/` と `examples/dummy-project/` の Python ファイル、および `.gitignore`・`scripts/denylist.example.txt` などの設定・補助ファイル。
- **CC BY 4.0**: Markdown 文書 `*.md` と、その中の自作 Mermaid 図。ただし `LICENSE`・`LICENSE-docs.md` 自体は除きます。

MIT の全文は [LICENSE](LICENSE)、文書のライセンス宣言は [LICENSE-docs.md](LICENSE-docs.md) を参照してください。第三者の製品・商標・参照資料に関する権利は、このライセンスの許諾範囲には含みません。詳しくは[権利と出典の方針](docs/rights-and-attribution.md)を参照してください。
