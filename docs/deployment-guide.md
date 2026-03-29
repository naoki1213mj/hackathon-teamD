# デプロイガイド

旅行マーケティング AI マルチエージェントパイプラインのデプロイ手順。

---

## 前提条件チェックリスト

### ツール

- [ ] Python 3.14+
- [ ] Node.js 22+
- [ ] [uv](https://docs.astral.sh/uv/)（Python パッケージマネージャー）
- [ ] [Azure Developer CLI (azd)](https://learn.microsoft.com/ja-jp/azure/developer/azure-developer-cli/install-azd)
- [ ] [Azure CLI (az)](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli)
- [ ] Git

### Azure リソース

- [ ] Azure サブスクリプション
- [ ] Microsoft Foundry プロジェクト（East US 2 推奨）
- [ ] gpt-5.4-mini モデルデプロイメント
- [ ] Azure Container Registry (ACR)
- [ ] Content Safety リソース（本番環境で必須）

> **注**: Docker Desktop は不要です。コンテナビルドは `az acr build` でリモート実行されます。

---

## ローカル開発セットアップ

### 1. リポジトリクローン

```bash
git clone https://github.com/naoki1213mj/hackathon-teamD.git
cd hackathon-teamD
```

### 2. Python 依存インストール

```bash
uv sync
```

### 3. フロントエンド依存インストール

```bash
cd frontend && npm ci && cd ..
```

### 4. 環境変数設定

```bash
cp .env.example .env
```

`.env` を編集して Azure リソースの情報を設定:

```env
# 最低限必要（Azure 接続する場合）
AZURE_AI_PROJECT_ENDPOINT=https://your-foundry.services.ai.azure.com/api/projects/your-project

# Azure 未接続でもデモモードで動作可能（全項目未設定でOK）
```

> **重要**: `.env` ファイルは `.gitignore` に含まれているため、Git にコミットされません。

### 5. ローカル起動

```bash
# バックエンド起動（ターミナル 1）
uv run uvicorn src.main:app --reload --port 8000

# フロントエンド起動（ターミナル 2）
cd frontend && npm run dev
```

ブラウザで http://localhost:5173 にアクセス。`/api` パスは Vite proxy により `:8000` に転送される。

### 6. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/api/health
# → {"status": "ok"}

# レディネスチェック
curl http://localhost:8000/api/ready
# → {"status": "ready", "missing": []}

# チャット（SSE ストリーミング）
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "沖縄のファミリー向け春キャンペーンを企画して"}'
```

---

## テスト

```bash
# バックエンドテスト
uv run pytest

# カバレッジ付き
uv run pytest --cov=src

# Python リント
uv run ruff check src/

# TypeScript 型チェック
cd frontend && npx tsc --noEmit
```

---

## Docker ビルド

### ローカルビルド（動作確認用）

```bash
docker build -t travel-agents .
docker run -p 8000:8000 --env-file .env travel-agents
```

### ACR リモートビルド（推奨）

Docker Desktop 不要。Azure Container Registry 上でビルドが実行される。

```bash
# ACR にログイン
az acr login --name <your-acr-name>

# リモートビルド
az acr build \
  --registry <your-acr-name> \
  --image travel-agents:latest \
  --file Dockerfile \
  .
```

### Dockerfile の構成

マルチステージビルド:

1. **Stage 1 (Node.js)**: フロントエンドビルド（`npm ci && npm run build`）
2. **Stage 2 (Python 3.14-slim)**: FastAPI + 静的ファイル配信

ヘルスチェックが Dockerfile 内に定義されており、`/api/health` をチェックする。

---

## Azure デプロイ（azd）

### 初回デプロイ

```bash
# Azure にログイン
azd auth login

# 環境を作成してデプロイ
azd up
```

`azd up` は以下を実行する:
1. Bicep テンプレートで Azure リソースをプロビジョニング
2. ACR リモートビルドでコンテナイメージをビルド
3. Container Apps にデプロイ
4. 環境変数を Container Apps に設定

### 2 回目以降のデプロイ

```bash
# コードのみデプロイ（インフラ変更なし）
azd deploy
```

### 環境変数の設定

```bash
# azd 環境変数を設定
azd env set AZURE_AI_PROJECT_ENDPOINT "https://..."
azd env set CONTENT_SAFETY_ENDPOINT "https://..."
azd env set COSMOS_DB_ENDPOINT "https://..."
```

---

## 環境変数リファレンス

### 必須（本番環境）

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `AZURE_AI_PROJECT_ENDPOINT` | Foundry プロジェクトエンドポイント | `https://your-foundry.services.ai.azure.com/api/projects/your-project` |
| `CONTENT_SAFETY_ENDPOINT` | Content Safety エンドポイント | `https://your-foundry.cognitiveservices.azure.com/` |

### オプション（デフォルト値あり）

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `MODEL_NAME` | 推論モデル名 | `gpt-5-4-mini` |
| `ENVIRONMENT` | 環境名 | `development` |
| `ALLOWED_ORIGINS` | CORS 許可オリジン（カンマ区切り） | `http://localhost:5173` |
| `SERVE_STATIC` | 静的ファイル配信（本番のみ `true`） | `false` |

### オプション（未設定時はフォールバック）

| 変数名 | 説明 | フォールバック動作 |
|--------|------|------------------|
| `COSMOS_DB_ENDPOINT` | Cosmos DB エンドポイント | インメモリストアに切替 |
| `FABRIC_SQL_ENDPOINT` | Fabric Lakehouse SQL EP | CSV ファイルから読み込み |
| `CONTENT_UNDERSTANDING_ENDPOINT` | Content Understanding EP | PDF 解析をスキップ |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights 接続文字列 | テレメトリ無効 |

---

## ヘルスチェック検証

デプロイ後、以下のエンドポイントで正常性を確認する:

```bash
# ライブネスプローブ
curl https://<your-app>.azurecontainerapps.io/api/health
# 期待値: {"status": "ok"}

# レディネスプローブ（本番設定の検証）
curl https://<your-app>.azurecontainerapps.io/api/ready
# 期待値: {"status": "ready", "missing": []}
```

`/api/ready` が `503` を返す場合、`missing` フィールドで不足している環境変数を確認する。

---

## CI/CD パイプライン

GitHub Actions で 3 つのワークフローが定義されている:

### ci.yml — 継続的インテグレーション

- Ruff lint → pytest → `tsc --noEmit` → `npm run build`
- プルリクエストおよび `main` ブランチへの push でトリガー

### deploy.yml — デプロイ

- OIDC Login → `az acr build` → `az containerapp update` → ヘルスチェック
- CI 成功後にのみ実行される
- 認証は OIDC Workload Identity Federation（シークレット不要）

### security.yml — セキュリティスキャン

- Trivy（コンテナ脆弱性） → Gitleaks（シークレット検出） → npm audit + pip-audit
- 失敗時はパイプラインをブロックする

---

## トラブルシューティング FAQ

### Q: `AZURE_AI_PROJECT_ENDPOINT` を設定していないがアプリは動くのか？

**A:** はい。未設定の場合はモックデモモードで動作し、ハードコードされたサンプルデータで SSE イベントを返します。本番環境では必須です。

### Q: `/api/ready` が `503 degraded` を返す

**A:** 本番環境（`ENVIRONMENT=production`）で `AZURE_AI_PROJECT_ENDPOINT` または `CONTENT_SAFETY_ENDPOINT` が未設定です。`azd env set` で設定してください。

### Q: Fabric Lakehouse に接続できない

**A:** `FABRIC_SQL_ENDPOINT` を確認してください。接続には `pyodbc` と Azure AD トークン認証が必要です。接続失敗時は自動的に `data/sales_history.csv` 等の CSV ファイルにフォールバックします。

### Q: 画像生成が失敗する

**A:** GPT Image 1.5 にはアクセス承認が必要です。Foundry ポータルでモデルデプロイメントを確認してください。失敗時は 1x1 の透明 PNG プレースホルダーが返されます。

### Q: Docker ビルドが失敗する

**A:** ローカルで `docker build` する場合は Docker Desktop が必要ですが、推奨は `az acr build` によるリモートビルドです。`frontend/package-lock.json` がコミットされていることを確認してください。

### Q: SSE ストリームが途中で切れる

**A:** リバースプロキシ（nginx 等）がバッファリングしている可能性があります。`X-Accel-Buffering: no` ヘッダが設定されていることを確認してください。Container Apps のイングレスタイムアウト設定も確認してください。

### Q: `429 Too Many Requests` が返される

**A:** レート制限（10 リクエスト/分）に達しています。1 分間待ってからリトライしてください。

### Q: Content Safety が `fail-close` でリクエストを拒否する

**A:** 本番環境では `CONTENT_SAFETY_ENDPOINT` が必須です。設定を確認するか、開発環境では `ENVIRONMENT=development` にしてください。
