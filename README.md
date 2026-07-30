# 会議スカウター / Meeting Scouter

[![CI](https://github.com/Fumiya-Matsumoto/meeting-scouter/actions/workflows/ci.yml/badge.svg)](https://github.com/Fumiya-Matsumoto/meeting-scouter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

> 議事録を読み、横文字・曖昧表現・未決定・責任の所在を検出して、会議の「空中戦指数」をTUI風に診断するAgent Skill。

Claude Code と Codex で動きます。議事録本文のコピペだけでなく、ローカルのファイルパスも渡せます。

```text
╭────────────────────────────────────────────────────────────╮
│                  会議スカウター                            │
│          この会議、本当に必要でしたか？                    │
│                                                            │
│  空中戦指数   87/100  █████████████████████░░░             │
│  ランク       S  — 地上との通信が途絶えています            │
│  会議戦闘力   9,700                                        │
│                                                            │
│  診断: 認識は揃いましたが、担当者と期限は置き去りです。    │
╰────────────────────────────────────────────────────────────╯
```

## 特徴

- **本文またはファイルパスを入力**: Markdown、テキスト、PDF、DOCXなど、利用中のエージェントが読める形式に対応。
- **固定辞書＋意味判定**: 既知の会議用語を決定論的に数え、未知の曖昧表現はAIが文脈から発見。
- **育つ候補辞書**: 新語を `~/.meeting-scouter/` に蓄積。本文そのものは保存しません。
- **分かりやすい0〜100点**: 横文字、曖昧さ、未決定、責任不明の4軸。
- **依存パッケージなし**: Python 3.10以上の標準ライブラリだけで動作。

## インストール

### リポジトリから一括インストール

```bash
git clone https://github.com/Fumiya-Matsumoto/meeting-scouter.git
cd meeting-scouter
./install.sh --all
```

個別に入れる場合:

```bash
./install.sh --claude       # ~/.claude/skills/meeting-scouter
./install.sh --codex        # ~/.agents/skills/meeting-scouter
./install.sh --codex-legacy # ~/.codex/skills/meeting-scouter
```

既存インストールを上書きする場合は `--force` を付けます。

### Codex の skill-installer から

Codexで次を依頼します。

```text
$skill-installer install https://github.com/Fumiya-Matsumoto/meeting-scouter/tree/main/meeting-scouter
```

インストール後、必要に応じてCodexを再起動してください。

## 使い方

### Claude Code

```text
/meeting-scouter ./docs/weekly-meeting.md
```

または、スキルを呼び出して議事録をそのまま貼り付けます。

```text
/meeting-scouter
本日のアジェンダですが、まず関係者と認識をアラインして……
```

### Codex

```text
$meeting-scouter ./docs/weekly-meeting.md
```

自然文でも利用できます。

```text
この議事録を会議スカウターで診断して: ./meeting-notes.txt
```

## スコア

| 空中戦指数 | ランク | 診断 |
|---:|:---:|---|
| 0–19 | 健全 | 仕事が進んでいます |
| 20–39 | C | 少し足元が浮いています |
| 40–59 | B | 会議らしくフワついています |
| 60–79 | A | かなり空中です |
| 80–94 | S | 地上との通信が途絶えています |
| 95–100 | SSS | 会議そのものが目的です |

「一般的な定例会議の約○倍」は、実測統計ではなく**当スカウター内の演出用基準**です。

## 新語学習とプライバシー

AIが未知の曖昧表現を見つけると、次の情報だけを `~/.meeting-scouter/` に保存します。

- 発見した短いフレーズ
- カテゴリ、出現回数、平均信頼度
- 元文書を復元できない短いSHA-256フィンガープリント
- ソースラベル

議事録本文は保存しません。学習を止めたい場合は、スキルの実行コマンドに `--no-learn` を付けるようエージェントへ指示できます。保存先は `MEETING_SCOUTER_HOME` で変更できます。

候補一覧:

```bash
python3 meeting-scouter/scripts/meeting_scouter.py candidates
```

## 開発

```bash
make validate
make test
make demo
```

テストはPython標準ライブラリの `unittest` のみを使用します。

## コントリビューション

会議語辞書、新しい診断パターン、他言語対応、スコア改善のPull Requestを歓迎します。詳しくは [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## ライセンス

MIT License
