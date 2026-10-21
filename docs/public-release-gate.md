# 公開ゲート

> 記述時点: 2026-10(現在の状態は2026-10-21時点)。公開の判断と操作は作者が行います。

## 現在の状態

公開用リポジトリは、旧履歴を引き継がない新しい履歴で作り直し、GitHub の **Private** リポジトリへ通常の push で登録済みです(履歴は1コミット)。旧リポジトリは非公開のまま、別名で保管しています。

P07 の根拠は作者の目視確認(2026-10-21、修正前の版 70a3335)です。GitHub 上で Mermaid 図4つが表示されたとの作者の申告を記録しています。図を修正した後の版の表示は未確認。Public 化前に作者が再確認します。(検証ステータス: 一部検証 / P07)

Public 化と報告窓口の有効化は未実施です。Private vulnerability reporting は、作者の決定により Public 化の直後に有効化します。

## Public 化までの手順(作者自身が行う)

[公開前チェックリスト](prepublish-checklist.md)の「確認済み」は自動検査と独立レビューの記録であり、作者の承認ではありません。残る確認と判断を次の順序で行います。

1. **未確認**: 修正後の版の Mermaid 図4つを GitHub 上で目視し、版・日付・結果を記録します。Public に切り替える直前に、公開する版で下記の自動検査一式(--history 含む)を再実行します。公開版を更新した場合はコミット後に --history を再実行し、影響する目視確認もやり直します。ローカル専用リストと長文一致の指定・検査の限界はチェックリストを参照してください。
2. **本人判断**: 公開名、コミットのモデル名と検査用の標準パス等の語、リスト外の実案件名・関係者名・所属、第三者の権利、内部運用の事実・数値について、チェックリストの「本人の判断が必要」を確認します。
3. **最終承認**: 公開する版について未確認・本人判断の項目を確認し、チェックリストの最終承認欄に承認・日付・承認者を記録します。問題や未確認事項があれば Private のまま止め、修正・再確認します。承認後に版が変わった場合も影響する確認と必要な承認を取り直します。
4. 作者が承認した版を GitHub 上で **Public** に切り替えます。

```sh
python3 scripts/test_prepublish_check.py
python3 scripts/test_check_docs.py
python3 -m unittest discover -s examples/dummy-project/tests -t examples/dummy-project
python3 scripts/check_docs.py
python3 scripts/prepublish_check.py
python3 scripts/prepublish_check.py --history
```

## Public 化後

Public 化の直後に GitHub のリポジトリ設定で **Private vulnerability reporting** を有効にし、[SECURITY.md](../SECURITY.md) の案内どおり Security タブの Report a vulnerability から非公開報告が使えることを確認します。公開ゲートと README に古い記述がないことも確認します。

## エージェントの実行範囲

文書の整備とローカル検査を担当し、作者の判断・承認や GitHub 上の目視・設定操作は代行しません。履歴の変更、コミット、remote の変更、push、Public 化、報告窓口の有効化はこの作業に含めません。未実施の結果を先取りして検証済みと記載しません。

## 関連ドキュメント

- [README に戻る](../README.md)
- [公開前チェックリスト](prepublish-checklist.md)
- [権利と出典の方針](rights-and-attribution.md)
- [検証ステータス](verification-status.md)
