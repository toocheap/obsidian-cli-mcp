# obsidian-cli-mcp

Obsidian を Claude Desktop / Claude Code から操作するための MCP サーバー。

2つのバックエンドを提供：

- **server.py** (CLI版) — Obsidian 1.12+ の公式 CLI 経由
- **fs_server.py** (FS版) — Vault のファイルシステムを直接操作（CLI 不要）

## 前提条件

### CLI版 (`server.py`)
- Obsidian 1.12+ がインストール・起動済み
- CLI が有効 (Settings → General → Command line interface)
- Catalyst ライセンス（Early Access 期間中）
- Python 3.10+, `uv`

### FS版 (`fs_server.py`)
- `OBSIDIAN_VAULT_PATH` 環境変数の設定のみ
- Python 3.10+, `uv`

## セットアップ

```bash
# リポジトリから直接インストール
pip install git+https://github.com/toocheap/obsidian-cli-mcp.git

# または uv を使用
uv tool install git+https://github.com/toocheap/obsidian-cli-mcp.git
```

## 開発用セットアップ

```bash
cd ~/src/obsidian-cli-mcp
uv sync
```

## Claude Desktop で使う

`~/Library/Application Support/Claude/claude_desktop_config.json` に追加：

### CLI版のみ
```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": ["run", "--directory", "~/src/obsidian-cli-mcp", "server.py"]
    }
  }
}
```

### FS版のみ
```json
{
  "mcpServers": {
    "obsidian_fs": {
      "command": "uv",
      "args": ["run", "--directory", "~/src/obsidian-cli-mcp", "fs_server.py"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/too/Obsidian/too"
      }
    }
  }
}
```

### 両方同時（ツール名プレフィックスが異なるため衝突しない）
```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": ["run", "--directory", "~/src/obsidian-cli-mcp", "server.py"]
    },
    "obsidian_fs": {
      "command": "uv",
      "args": ["run", "--directory", "~/src/obsidian-cli-mcp", "fs_server.py"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/too/Obsidian/too"
      }
    }
  }
}
```

Claude Desktop を再起動。

## Claude Code で使う

```bash
# CLI版
claude mcp add obsidian -- uvx --from git+https://github.com/toocheap/obsidian-cli-mcp.git obsidian-mcp

# FS版
claude mcp add obsidian_fs -e OBSIDIAN_VAULT_PATH=/Users/too/Obsidian/too -- uvx --from git+https://github.com/toocheap/obsidian-cli-mcp.git obsidian-fs-mcp
```

## CLI版ツール一覧

| ツール | CLI コマンド | 説明 |
|--------|-------------|------|
| `obsidian_daily_read` | `daily:read` | デイリーノートを読む |
| `obsidian_daily_append` | `daily:append` | デイリーノートに追記 |
| `obsidian_tasks_list` | `tasks` | タスク一覧（フィルタ対応） |
| `obsidian_task_toggle` | `task ref=... toggle` | タスク完了/未完了切り替え |
| `obsidian_search` | `search` | Vault 内テキスト検索 |
| `obsidian_tags_list` | `tags all counts` | タグ一覧（カウント付き） |
| `obsidian_tag_info` | `tag name=...` | 特定タグの詳細 |
| `obsidian_vault_info` | `vault` | Vault 情報 |

## FS版ツール一覧

| ツール | 説明 |
|--------|------|
| `obsidian_fs_search` | ファイル名・コンテンツ検索 |
| `obsidian_fs_read` | ノート読み取り（メタデータ付き） |
| `obsidian_fs_create` | ノート作成 |
| `obsidian_fs_edit` | ノート編集（append/prepend/replace） |
| `obsidian_fs_delete` | ノート削除 |
| `obsidian_fs_list_folder` | フォルダ構造表示 |
| `obsidian_fs_get_tags` | 全タグ一覧（カウント付き） |
| `obsidian_fs_get_backlinks` | バックリンク解析 |
| `obsidian_fs_daily_note` | デイリーノート作成 |

## 拡張

`CLAUDE.md` を参照。CLI コマンド一覧: https://help.obsidian.md/cli
