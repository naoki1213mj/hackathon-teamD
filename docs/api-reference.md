# API リファレンス

旅行マーケティング AI マルチエージェントパイプラインの REST API 仕様。

## ベース URL

- ローカル開発: `http://localhost:8000`
- 本番: Container Apps の FQDN（`https://<app-name>.<region>.azurecontainerapps.io`）

---

## エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| `GET` | `/api/health` | ライブネスプローブ |
| `GET` | `/api/ready` | レディネスプローブ |
| `POST` | `/api/chat` | メインチャット（SSE ストリーミング） |
| `POST` | `/api/chat/{thread_id}/approve` | 承認/修正エンドポイント |
| `GET` | `/api/conversations` | 会話一覧取得 |
| `GET` | `/api/conversations/{id}` | 会話詳細取得 |
| `GET` | `/api/replay/{id}` | SSE イベントリプレイ |

---

## ヘルスチェック

### `GET /api/health`

ライブネスプローブ用。常に `200 OK` を返す。

**レスポンス**

```json
{"status": "ok"}
```

### `GET /api/ready`

レディネスプローブ用。本番環境で必須設定（`AZURE_AI_PROJECT_ENDPOINT`、`CONTENT_SAFETY_ENDPOINT`）が揃っているかを検証する。

**レスポンス（正常時: 200）**

```json
{"status": "ready", "missing": []}
```

**レスポンス（設定不足時: 503）**

```json
{
  "status": "degraded",
  "missing": ["AZURE_AI_PROJECT_ENDPOINT", "CONTENT_SAFETY_ENDPOINT"]
}
```

> **注**: `ENVIRONMENT` が `development` の場合、必須チェックはスキップされ常に `ready` を返す。

---

## チャット API

### `POST /api/chat`

ユーザーのメッセージを受け取り、マルチエージェントパイプラインを実行する。結果は SSE（Server-Sent Events）ストリームで返却される。

- レート制限: **10 リクエスト/分**（IP アドレスベース）
- 入力制御文字は自動除去される

**リクエストボディ**

```json
{
  "message": "沖縄のファミリー向け春キャンペーンを企画してください",
  "conversation_id": null
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `message` | `string` | ✅ | ユーザーメッセージ（1〜5000 文字） |
| `conversation_id` | `string \| null` | — | 既存の会話 ID を指定するとマルチターン修正として処理される |

**レスポンス**

`Content-Type: text/event-stream`

SSE イベントが順次ストリーミングされる。各イベントの形式は後述の「SSE イベント仕様」を参照。

**動作フロー**

```
conversation_id なし（新規会話）:
  Azure 接続あり → Workflow 実行（Agent1→2→[承認]→3→4）
  Azure 接続なし → モックデモイベント

conversation_id あり（マルチターン修正）:
  修正内容のキーワードに応じて適切なエージェントを再実行
  - 画像/バナー関連 → brochure-gen-agent
  - 規制/法令関連 → regulation-check-agent
  - その他 → marketing-plan-agent
```

**cURL の例**

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "沖縄のファミリー向け春キャンペーンを企画して"}'
```

### `POST /api/chat/{thread_id}/approve`

承認ステップに対するユーザーの応答を処理する。承認キーワード（`承認`、`approve`、`ok` 等）を検出すると後続の Agent3→Agent4 を実行し、それ以外は修正として Agent2 を再実行する。

- レート制限: **10 リクエスト/分**
- Content Safety チェック（Prompt Shield）が承認レスポンスにも適用される

**パスパラメータ**

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `thread_id` | `string` | 会話のスレッド ID |

**リクエストボディ**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "承認"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `conversation_id` | `string` | ✅ | 会話 ID（最大 100 文字） |
| `response` | `string` | ✅ | 承認キーワードまたは修正指示（1〜5000 文字） |

**承認キーワード一覧**

以下のキーワード（大文字小文字不問、部分一致）が含まれると承認として処理される:

| 日本語 | 英語 | 中国語 |
|--------|------|--------|
| `承認` | `approve` / `approved` | `批准` |
| `了承` | `go` / `ok` / `yes` | `同意` |
| `進めて` | | |

**レスポンス**

`Content-Type: text/event-stream`

- 承認時: Agent3（規制チェック）→ Agent4（販促物生成）の SSE イベント
- 修正時: 対象エージェントの再実行 → 再度 `approval_request` イベント

---

## 会話 API

### `GET /api/conversations`

保存済みの会話一覧を取得する。Cosmos DB が設定されていない場合はインメモリストアから取得される。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `limit` | `int` | `20` | 取得する最大件数 |

**レスポンス**

```json
{
  "conversations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_message": "沖縄のファミリー向け春キャンペーン",
      "created_at": "2026-03-20T10:30:00Z",
      "event_count": 12
    }
  ]
}
```

### `GET /api/conversations/{conversation_id}`

特定の会話の詳細を取得する。

**パスパラメータ**

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `conversation_id` | `string` | 会話 ID |

**レスポンス（正常時: 200）**

会話ドキュメント全体が JSON で返される。

**レスポンス（未存在時: 404）**

```json
{"error": "conversation not found"}
```

### `GET /api/replay/{conversation_id}`

録画済みの SSE イベントを高速リプレイする。デモ用途で使用。

**パスパラメータ**

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `conversation_id` | `string` | リプレイする会話 ID |

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `speed` | `float` | `5.0` | リプレイ速度の倍率（5.0 = 5倍速） |

**レスポンス**

`Content-Type: text/event-stream`

保存されたイベントが `speed` 倍速で再生される。データが見つからない場合は `error` イベントが返される。

---

## SSE イベント仕様

全エンドポイントの SSE レスポンスは以下の形式に従う:

```
event: {イベント種別}\ndata: {JSON データ}\n\n
```

### イベント種別一覧（8 種）

#### 1. `agent_progress` — エージェント進捗

エージェントの開始・完了をフロントエンドに通知する。プログレスバーや状態表示に使用。

```json
{
  "agent": "data-search-agent",
  "status": "running",
  "step": 1,
  "total_steps": 4
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `agent` | `string` | エージェント名（`data-search-agent` / `marketing-plan-agent` / `regulation-check-agent` / `brochure-gen-agent` / `quality-review-agent` / `pipeline`） |
| `status` | `string` | `"running"` または `"completed"` |
| `step` | `int` | 現在のステップ番号（1〜5） |
| `total_steps` | `int` | 総ステップ数（通常 4、品質レビュー含む場合 5） |

#### 2. `tool_event` — ツール呼び出し

エージェントが使用したツールの実行状況を通知する。

```json
{
  "tool": "web_search",
  "status": "completed",
  "agent": "marketing-plan-agent"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `tool` | `string` | ツール名（`search_sales_history` / `search_customer_reviews` / `web_search` / `search_market_trends` / `check_ng_expressions` / `check_travel_law_compliance` / `search_knowledge_base` / `search_safety_info` / `generate_hero_image` / `generate_banner_image`） |
| `status` | `string` | `"completed"` |
| `agent` | `string` | ツールを呼び出したエージェント名 |

#### 3. `text` — テキスト出力

エージェントが生成したテキストコンテンツ。Markdown 形式の企画書や HTML ブローシャを含む。

```json
{
  "content": "## データ分析サマリ\n\n沖縄エリアの春季売上は前年比 **+12%** で推移。",
  "agent": "data-search-agent"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `content` | `string` | テキストコンテンツ（Markdown / HTML） |
| `agent` | `string` | 出力元エージェント名 |
| `content_type` | `string?` | `"html"` の場合はブローシャ HTML として処理 |

#### 4. `image` — 画像出力

エージェントが生成した画像。Base64 エンコードの data URI または SVG data URI で提供される。

```json
{
  "url": "data:image/png;base64,iVBORw0KGgo...",
  "alt": "沖縄の美ら海をイメージしたヒーロー画像",
  "agent": "brochure-gen-agent"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `url` | `string` | 画像の data URI（`data:image/png;base64,...` または `data:image/svg+xml;...`） |
| `alt` | `string` | 代替テキスト |
| `agent` | `string` | 出力元エージェント名 |

#### 5. `approval_request` — 承認リクエスト

Agent2（施策生成）完了後にフロントエンドに承認 UI の表示を要求する。ユーザーが承認すると `/api/chat/{thread_id}/approve` が呼ばれる。

```json
{
  "prompt": "上記の企画書を確認してください。承認する場合は「承認」、修正したい場合は修正内容を入力してください。",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "plan_markdown": "# 春の沖縄ファミリープラン 企画書\n\n..."
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `prompt` | `string` | ユーザーへの承認依頼メッセージ |
| `conversation_id` | `string` | この会話の ID（approve エンドポイントに渡す） |
| `plan_markdown` | `string` | 承認対象の企画書 Markdown |

#### 6. `safety` — Content Safety 結果

Content Safety（Text Analysis）による出力スキャン結果。4 カテゴリのスコアを返す。

```json
{
  "hate": 0,
  "self_harm": 0,
  "sexual": 0,
  "violence": 0,
  "status": "safe"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `hate` | `int` | ヘイトスコア（0 = 安全、1〜6 = 段階的に危険） |
| `self_harm` | `int` | 自傷行為スコア |
| `sexual` | `int` | 性的コンテンツスコア |
| `violence` | `int` | 暴力スコア |
| `status` | `string` | `"safe"` / `"warning"` / `"error"` |

#### 7. `error` — エラー

処理中に発生したエラーを通知する。

```json
{
  "message": "入力が安全性チェックに失敗しました",
  "code": "PROMPT_SHIELD_BLOCKED"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `message` | `string` | エラーメッセージ（日本語） |
| `code` | `string` | エラーコード |

**エラーコード一覧**

| コード | 説明 |
|--------|------|
| `PROMPT_SHIELD_BLOCKED` | Prompt Shield がプロンプトインジェクションを検出 |
| `WORKFLOW_BUILD_ERROR` | Workflow の構築に失敗 |
| `WORKFLOW_RUNTIME_ERROR` | Workflow の実行中にエラー |
| `AGENT_RUNTIME_ERROR` | 個別エージェントの実行に失敗 |
| `REPLAY_NOT_FOUND` | リプレイデータが見つからない |

#### 8. `done` — 完了

パイプライン全体の処理完了を通知する。メトリクスを含む。

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "metrics": {
    "latency_seconds": 4.8,
    "tool_calls": 6,
    "total_tokens": 3200
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `conversation_id` | `string` | 会話 ID |
| `metrics.latency_seconds` | `float` | 処理時間（秒） |
| `metrics.tool_calls` | `int` | ツール呼び出し回数 |
| `metrics.total_tokens` | `int` | 使用トークン数 |

---

## SSE イベントの典型的なフロー

### 新規会話（承認あり）

```
1. agent_progress  (data-search-agent, running, step=1)
2. tool_event       (search_sales_history, completed)
3. text             (データ分析サマリ)
4. agent_progress  (data-search-agent, completed, step=1)
5. agent_progress  (marketing-plan-agent, running, step=2)
6. tool_event       (web_search, completed)
7. text             (企画書 Markdown)
8. agent_progress  (marketing-plan-agent, completed, step=2)
9. approval_request (承認待ち)
--- ここで SSE ストリームが一旦終了 ---

--- ユーザーが承認 → POST /api/chat/{thread_id}/approve ---
10. agent_progress  (regulation-check-agent, running, step=3)
11. tool_event       (check_ng_expressions, completed)
12. tool_event       (check_travel_law_compliance, completed)
13. text             (レギュレーションチェック結果)
14. agent_progress  (regulation-check-agent, completed, step=3)
15. agent_progress  (brochure-gen-agent, running, step=4)
16. tool_event       (generate_hero_image, completed)
17. text             (HTML ブローシャ)
18. image            (ヒーロー画像)
19. tool_event       (generate_banner_image, completed)
20. image            (SNS バナー画像)
21. agent_progress  (brochure-gen-agent, completed, step=4)
22. safety           (Content Safety 結果)
23. done             (メトリクス)
```

---

## Content Safety

全ての入力は Prompt Shield でスキャンされ、プロンプトインジェクション攻撃を検出する。全ての出力は Text Analysis で 4 カテゴリ（Hate / SelfHarm / Sexual / Violence）のスキャンが行われる。

本番環境（`ENVIRONMENT=production`）では Content Safety が必須であり、未設定の場合は fail-close（リクエスト拒否）となる。開発環境ではスキップされる。

---

## レート制限

| エンドポイント | 制限 |
|--------------|------|
| `POST /api/chat` | 10 リクエスト/分（IP ベース） |
| `POST /api/chat/{thread_id}/approve` | 10 リクエスト/分（IP ベース） |

レート制限超過時は `429 Too Many Requests` が返される。
