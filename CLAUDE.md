# CLAUDE.md - Obsidian CLI MCP サーバー

## プロジェクト概要

Obsidian Vault 操作のための Python MCP サーバー。2つのサーバーバックエンドを提供:

- **server.py** (CLI版) — Obsidian 1.12+ の公式 CLI バイナリ経由
- **fs_server.py** (FS版) — ファイルシステムへの直接アクセス（CLI不要）

## アーキテクチャ

- **言語**: Python (FastMCP)
- **トランスポート**: stdio (ローカル実行)
- **CLI実行**: ノンブロッキングなCLI呼び出しのために `asyncio.to_thread(subprocess.run(...))` を使用
- **FSアクセス**: Vault ディレクトリに対する直接の `Path` 操作
- **ターゲットクライアント**: Claude Desktop, Claude Code

## ファイル構成

```
obsidian-cli-mcp/
├── CLAUDE.md              # このファイル - エージェントへの指示書
├── server.py              # CLIベースの FastMCP サーバー
├── fs_server.py           # ファイルシステムベースの FastMCP サーバー
├── cli.py                 # 低レベル CLI ラッパー (サブプロセス呼び出し)
├── pyproject.toml         # 依存関係とメタデータ
└── README.md              # ユーザー向けセットアップ手順
```

## モジュールの責務

### `cli.py` - CLI ラッパー
- `run_obsidian(*args) -> str` — Obsidian CLI への同期サブプロセス呼び出し
- `run_obsidian_async(*args) -> str` — `asyncio.to_thread` 経由の非同期ラッパー
- エンコーディング、タイムアウト、エラー捕捉を処理
- stdout を文字列として返す。失敗時は `ObsidianCLIError` を発生させる

### `server.py` - CLI MCP サーバー
- `obsidian_mcp` という名前の FastMCP サーバー
- Obsidian CLI コマンドをラップする8つのツール
- 入力検証のための Pydantic モデル
- エントリーポイント: `main()`

### `fs_server.py` - ファイルシステム MCP サーバー
- `obsidian_fs_mcp` という名前の FastMCP サーバー
- Vault ファイルを直接操作する9つのツール
- `OBSIDIAN_VAULT_PATH` 環境変数が必要
- バックリンク分析、タグ抽出、検索機能を含む
- エントリーポイント: `main()`

## ツール一覧

### CLI版 (`server.py`) — 8ツール

| ツール | CLI コマンド | 読み書き |
|------|------------|-----|
| `obsidian_daily_read` | `daily:read` | R |
| `obsidian_daily_append` | `daily:append content=...` | W |
| `obsidian_tasks_list` | `tasks [filters]` | R |
| `obsidian_task_toggle` | `task ref=... toggle` | W |
| `obsidian_search` | `search query=...` | R |
| `obsidian_tags_list` | `tags all counts` | R |
| `obsidian_tag_info` | `tag name=...` | R |
| `obsidian_vault_info` | `vault` | R |

### FS版 (`fs_server.py`) — 9ツール + ユニバーサルエイリアス

Obsidian アプリが起動していない状態でも、以下の標準的なツール名でファイルシステムを直接操作できます (`server.py` の代わりとして機能します)。

| ツール | エイリアス (CLI互換) | 説明 |
|--------|---------------------|------|
| `obsidian_fs_search` | `obsidian_search` | ファイル名・コンテンツ検索 |
| `obsidian_fs_read` | `obsidian_read` | ノート読み取り（メタデータ付き） |
| `obsidian_fs_create` | `obsidian_create` | ノート作成 |
| `obsidian_fs_edit` | `obsidian_edit` | ノート編集 |
| `obsidian_fs_delete` | `obsidian_delete` | ノート削除 |
| `obsidian_fs_list_folder` | `obsidian_list_folder` | フォルダ構造表示 |
| `obsidian_fs_get_tags` | `obsidian_tags_list` | 全タグ一覧 |
| `obsidian_fs_get_backlinks` | `obsidian_backlinks` | バックリンク解析 |
| `obsidian_fs_daily_note` | `obsidian_daily_read` | デイリーノート読み取り（作成） |
| `obsidian_fs_daily_note` + edit | `obsidian_daily_append` | デイリーノート追記 |

FS版を使用することで、Obsidian アプリを常駐させずにすべての操作が可能になります。

## コーディング規約

- コメントは英語で統一（※注: 日本語翻訳版のためここは矛盾しますが、コード内のコメントは英語のままが望ましいです）
- すべての関数に型ヒントを記述（制約付き文字列には `Literal` を使用）
- すべてのツール入力に Pydantic `BaseModel` を使用し、`ConfigDict(extra="forbid")` を設定
- すべてのツール関数は `async def` とする
- `@mcp.tool(name="tool_name")` デコレータを使用（`annotations` 引数は使用しない）
- エラーメッセージは具体的なアクションを示唆するものにする
- ファイルI/Oは `OSError` を捕捉するために try/except でラップする
- `Path.is_relative_to()` を使用してパストラバーサルを防止する

## CLIコマンドのパターン

すべての Obsidian CLI コマンドは以下のパターンに従います:
```
obsidian [vault=<n>] <command> [param=value ...] [flags]
```

- パラメータ: `key=value` (スペースを含む値は引用符で囲む)
- フラグ: ブールスイッチ (単語のみ、例: `silent`, `todo`)
- 複数行: 改行には `\n` を使用

## テスト方法

```bash
# 構文チェック
python -m py_compile server.py
python -m py_compile fs_server.py

# CLI サーバーの実行 (Obsidian がローカルで起動している必要あり)
python server.py

# FS サーバーの実行 (OBSIDIAN_VAULT_PATH が必要)
OBSIDIAN_VAULT_PATH=/path/to/vault python fs_server.py
```

## 依存関係

- `mcp[cli]` (FastMCP を含む)
- `pydantic>=2.0.0`
- `python-frontmatter>=1.0.0`
- Python 3.10+
