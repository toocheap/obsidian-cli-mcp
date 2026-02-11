# Antigravity Handoff: obsidian-cli-mcp

## プロジェクト概要

Obsidian vault を操作する MCP サーバー。2つのバックエンドを提供：

1. **server.py** (CLI版) — Obsidian 1.12+ の CLI バイナリを subprocess 経由で呼び出し
2. **fs_server.py** (FS版) — vault のファイルシステムを直接操作（CLI 不要）

## ファイル構成

```
obsidian-cli-mcp/
├── CLAUDE.md              # エージェント向け指示書（CLI版のコンテキスト）
├── server.py              # CLI版 MCPサーバー（obsidian コマンド経由）
├── cli.py                 # subprocess ラッパー
├── fs_server.py           # FS版 MCPサーバー（ファイルシステム直接操作）★NEW
├── pyproject.toml         # 依存パッケージ & メタデータ
├── README.md              # ユーザー向けセットアップガイド
└── HANDOFF.md             # このファイル
```

## 2つのサーバーの比較

| 項目 | server.py (CLI版) | fs_server.py (FS版) |
|---|---|---|
| 前提条件 | Obsidian 1.12+ 起動中 + CLI有効 | `OBSIDIAN_VAULT_PATH` 環境変数のみ |
| ツールプレフィックス | `obsidian_` | `obsidian_fs_` |
| Daily Notes | ✅ read/append | ✅ create (テンプレート対応) |
| Tasks | ✅ list/toggle | ❌ 未実装 |
| Search | ✅ (CLI経由) | ✅ (ファイル名+コンテンツ) |
| Tags | ✅ list/info | ✅ (全タグカウント付き) |
| Backlinks | ❌ | ✅ [[wikilink]] 解析 |
| Note CRUD | ❌ | ✅ create/read/edit/delete |
| Folder listing | ❌ | ✅ ツリー表示 |
| Vault info | ✅ | ❌ |

**両方を同時に登録可能**（ツール名プレフィックスが異なるため衝突しない）

## MCP クライアント設定例

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

### 両方同時
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

## ユーザー環境情報

- **Vault 名**: `too`
- **Vault パス**: `/Users/too/Obsidian/too/` (要確認)
  - 以前 iCloud パスでエラーが出ていたためローカルパス推奨
- **OS**: macOS
- **パッケージマネージャ**: uv

## 現在のステータス

- **server.py (CLI版)**: 実装済み・未テスト（Obsidian CLI の Early Access が必要）
- **fs_server.py (FS版)**: 実装済み・未テスト（サンドボックスで作成）

## 次のステップ (TODO)

### 優先度: 高
1. **vault パスの確認** — `ls /Users/too/Obsidian/too/` で存在を確認
2. **fs_server.py の構文確認** — `python -m py_compile fs_server.py`
3. **pyproject.toml の更新** — fs_server.py のエントリポイント追加
4. **基本動作テスト** — MCP Inspector で各ツールをテスト
5. **README.md の更新** — FS版の説明を追加

### 優先度: 中
6. **CLI版のテスト** — Obsidian 1.12+ CLI が利用可能か確認
7. **Tasks サポート (FS版)** — `- [ ]` チェックボックスの解析・トグル機能
8. **フロントマッター完全パース** — YAML frontmatter の全フィールド対応
9. **移動/リネームツール** — `obsidian_fs_move` の追加

### 優先度: 低
10. **2サーバー統合** — CLI利用可能時はCLI、不可時はFS、のフォールバック
11. **キャッシュ機構** — 大きな vault での検索パフォーマンス改善
12. **Dataview 互換クエリ** — Dataview プラグイン風のクエリサポート

## 既知の問題

- iCloud 同期パスのスペース問題（ローカルパス推奨）
- 大規模 vault (数千ノート) では全文検索が遅い可能性
- UTF-8 以外のファイルはスキップされる
