# 公開ゲート

> 記述時点: 2026-10(現在の状態は2026-10-21時点)。公開の判断と操作は作者が行います。

## 現在の状態

公開用リポジトリは、旧履歴を引き継がない新しい履歴(原則1コミット)で作り直しました。GitHub の **Private** リポジトリへ通常の push で登録しています(履歴は1コミット)。

旧リポジトリは非公開のまま、別名で保管しています。

GitHub 上の Mermaid 描画の目視確認(P07)、Public 化、報告窓口の有効化は未実施です。(検証ステータス: 設計済み(未検証) / P07) Private vulnerability reporting は、作者の決定により Public 化の直後に有効化します。

## ゲートの条件

[公開前チェックリスト](prepublish-checklist.md)の Public 化前の人手確認を作者が完了し、最終承認欄に Public 化を明示的に承認した記録を残すことが、Public 化の条件です。決定済みのライセンス(コード MIT / 文書 CC BY 4.0)と著作権者(2026 satellite1105)が [LICENSE](../LICENSE)・[LICENSE-docs.md](../LICENSE-docs.md)・本文で一致すること、および公開用コミットの author / committer の名前とメールを確認します。コミットメールには GitHub の noreply アドレスを使い、正しいアドレスが確認できない場合は仮設定しません。author と committer のメールは、最初のコミットも含めて両方とも許可ドメインで検査します。

承認は、公開する版について以降の再確認でも問題がないことを前提とします。不備や未確認事項があれば Private のまま止め、修正・再確認し、必要な承認を取り直します。自動チェックの成功や文書の完成だけではゲートを通過しません。

## 残りの手順(作者自身が行う)

1. 公開用の新しい履歴をコミット後に検査し、`python3 scripts/prepublish_check.py --history` が `PASS` することを確認します。コミットメッセージ本文のセッション URL・内部 URL なども検査対象です。パターンに一致しない情報は人手でも確認し、GitHub の Private リポジトリへ通常の push を行います。
2. GitHub 上で README と各ドキュメントを開き、Mermaid の図が意図どおり描画されるかを目視します。これが P07 の確認です。静的検査の成功で代替せず、確認した版と結果を記録します。
3. [公開前チェックリスト](prepublish-checklist.md)の Public 化前の人手確認を完了し、作者が最終承認を記録します。
4. 公開する版について、下記のチェック一式をリポジトリのルートから再実行します。ローカルの検査リストと、権限のある手元の資料との長文一致検査も、チェックリストに従って確認します。失敗、警告、検査省略を確認し、検査、目視、承認の記録が公開する版と一致することを確かめます。修正した場合は Private のまま反映し、影響するチェックと目視確認をやり直し、必要な承認を取り直します。
5. 未解決の問題がないことを作者が確認し、GitHub 上で **Public** に切り替えます。
6. Public 化の直後に、GitHub のリポジトリ設定で **Private vulnerability reporting** を有効にします。[SECURITY.md](../SECURITY.md) の案内どおり、Security タブの Report a vulnerability から非公開報告が使えることを確認します。
7. Public 化後、本ファイルの「現在の状態」と README の記述に古い内容が残っていないか確認し、公開してよい範囲で更新します。

```sh
python3 scripts/prepublish_check.py
python3 scripts/prepublish_check.py --history
python3 scripts/check_docs.py
python3 scripts/test_prepublish_check.py
python3 scripts/test_check_docs.py
```

## エージェントの実行範囲

エージェントは上記の残りの手順を実行しません。履歴の変更、GitHub 上の目視・設定操作、Public 化、非公開報告の有効化・動作確認を代行せず、実行結果を先取りして検証済みと記載しません。リポジトリ作成、コミット、remote の変更、push もこの文書の整備には含めません。

## 関連ドキュメント

- [README に戻る](../README.md)
- [公開前チェックリスト](prepublish-checklist.md)
- [権利と出典の方針](rights-and-attribution.md)
- [検証ステータス](verification-status.md)
