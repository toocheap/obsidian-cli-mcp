---
description: Team-based development with Planning, Implementation, and QA subagents
---

# Team Development Workflow

Leader（メインエージェント）が3つのサブエージェントチームを管理し、フィードバックループで品質を担保する。

## Roles

### Leader（メインエージェント）
- タスクを分割してサブエージェントに割り当て
- 各フェーズの成果物を確認・統合
- プロジェクト全体の進捗管理
- ブロッカー検出と対処

### Planning（計画サブエージェント）
- 実装仕様書の作成
- QAからのフィードバックを受けて仕様を再検討
- テストケース設計の方針策定

### Implementation（実装サブエージェント）
- テストファーストで実装
- 仕様書に基づきテストを先に書く
- テストが通るように実装コードを書く

### QA（品質管理サブエージェント）
- テストを実行
- 問題を特定・報告
- 計画チームにフィードバック

## Loop

```
Planning → 仕様書作成
    ↓
Implementation → テスト作成 → 実装
    ↓
QA → テスト実行 → 問題レポート
    ↓
Planning → 仕様再検討（必要な場合）
    ↓
(ループ繰り返し or 完了)
```

## Execution

// turbo-all

1. Leader: task.md でタスクを分割
2. Leader: browser_subagent で Planning を起動 → 仕様書を artifacts に出力
3. Leader: 仕様書を確認
4. Leader: browser_subagent で Implementation を起動 → テスト + 実装
5. Leader: 実装結果を確認
6. Leader: browser_subagent で QA を起動 → テスト実行 + レポート
7. Leader: QA レポートを確認 → 問題あれば 2 に戻る
8. Leader: 完了判定 → walkthrough 更新
