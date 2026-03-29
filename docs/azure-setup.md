# Azure セットアップガイド

旅行マーケティング AI マルチエージェントパイプラインに必要な Azure リソースの構築手順。

> **推奨リージョン**: East US 2（Code Interpreter のリージョン可用性による）

---

## 目次

1. [Foundry プロジェクト作成](#1-foundry-プロジェクト作成)
2. [gpt-5.4-mini モデルデプロイ](#2-gpt-54-mini-モデルデプロイ)
3. [GPT Image 1.5 デプロイ](#3-gpt-image-15-デプロイ)
4. [Content Safety リソース](#4-content-safety-リソース)
5. [Cosmos DB（Serverless）](#5-cosmos-dbserverless)
6. [APIM AI Gateway](#6-apim-ai-gateway)
7. [Fabric Lakehouse](#7-fabric-lakehouse)
8. [Foundry IQ Knowledge Base](#8-foundry-iq-knowledge-base)
9. [Azure Functions (Flex Consumption)](#9-azure-functions-flex-consumption)
10. [Hosted Agent 登録](#10-hosted-agent-登録)
11. [Evaluations セットアップ](#11-evaluations-セットアップ)
12. [Teams 公開](#12-teams-公開)
13. [Logic Apps コネクタ](#13-logic-apps-コネクタ)
14. [Application Insights](#14-application-insights)

---

## 1. Foundry プロジェクト作成

Microsoft Foundry のリソースモデル（`CognitiveServices/accounts` + `accounts/projects`）を使用する。

### Azure CLI

```bash
# リソースグループ作成
az group create --name rg-travel-marketing --location eastus2

# Foundry リソース（Cognitive Services Account with project management）
az cognitiveservices account create \
  --name travel-marketing-foundry \
  --resource-group rg-travel-marketing \
  --location eastus2 \
  --kind AIServices \
  --sku S0 \
  --custom-domain travel-marketing-foundry

# プロジェクト作成
az rest --method PUT \
  --uri "https://management.azure.com/subscriptions/{sub-id}/resourceGroups/rg-travel-marketing/providers/Microsoft.CognitiveServices/accounts/travel-marketing-foundry/projects/travel-agents?api-version=2025-06-01" \
  --body '{"location": "eastus2", "properties": {}}'
```

### ポータル

1. [Microsoft Foundry ポータル](https://ai.azure.com) にアクセス
2. 「新規プロジェクト」→ リージョン: East US 2 を選択
3. プロジェクト名を設定して作成

### 必要な権限

- `Cognitive Services OpenAI Contributor`（モデルデプロイ用）
- `Cognitive Services OpenAI User`（推論用）

### 確認

プロジェクトエンドポイントを `.env` に設定:

```env
AZURE_AI_PROJECT_ENDPOINT=https://travel-marketing-foundry.services.ai.azure.com/api/projects/travel-agents
```

---

## 2. gpt-5.4-mini モデルデプロイ

### Azure CLI

```bash
az cognitiveservices account deployment create \
  --name travel-marketing-foundry \
  --resource-group rg-travel-marketing \
  --deployment-name gpt-5-4-mini \
  --model-name gpt-5.4-mini \
  --model-version "2026-03-17" \
  --model-format OpenAI \
  --sku-capacity 30 \
  --sku-name GlobalStandard
```

### ポータル

1. Foundry ポータル → プロジェクト → 「モデルカタログ」
2. gpt-5.4-mini を選択 → 「デプロイ」
3. デプロイメント名: `gpt-5-4-mini`、SKU: Global Standard

### 確認

```env
MODEL_NAME=gpt-5-4-mini
```

---

## 3. GPT Image 1.5 デプロイ

> **注意**: GPT Image 1.5 はアクセス承認が必要です。事前に [アクセス申請フォーム](https://aka.ms/oai/access) から申請してください。

### Azure CLI

```bash
az cognitiveservices account deployment create \
  --name travel-marketing-foundry \
  --resource-group rg-travel-marketing \
  --deployment-name gpt-image-1-5 \
  --model-name gpt-image-1.5 \
  --model-format OpenAI \
  --sku-capacity 1 \
  --sku-name GlobalStandard
```

### ポータル

1. Foundry ポータル → モデルカタログ → GPT Image 1.5
2. 「デプロイ」→ アクセス承認済みであることを確認
3. デプロイメント名: `gpt-image-1-5`

### フォールバック

GPT Image 1.5 が未デプロイの場合、Agent4 は 1x1 透明 PNG プレースホルダーを返す。

---

## 4. Content Safety リソース

Content Safety は Foundry リソースに統合されている。Prompt Shield と Text Analysis を使用する。

### 確認

```bash
# Content Safety エンドポイントの確認
az cognitiveservices account show \
  --name travel-marketing-foundry \
  --resource-group rg-travel-marketing \
  --query "properties.endpoint" -o tsv
```

```env
CONTENT_SAFETY_ENDPOINT=https://travel-marketing-foundry.cognitiveservices.azure.com/
```

### Content Filter 設定

Foundry ポータルでモデルデプロイメントの Content Filter を有効化:

1. Foundry ポータル → デプロイメント → gpt-5-4-mini
2. 「Content Filter」タブ → フィルターレベルを設定
3. 推奨: 全カテゴリ（Hate / SelfHarm / Sexual / Violence）を Medium 以上に設定

---

## 5. Cosmos DB（Serverless）

会話履歴の永続化に使用。未設定時はインメモリストアにフォールバックする。

### Azure CLI

```bash
# Cosmos DB アカウント作成（Serverless）
az cosmosdb create \
  --name travel-marketing-cosmos \
  --resource-group rg-travel-marketing \
  --locations regionName=eastus2 \
  --capabilities EnableServerless \
  --default-consistency-level Session

# データベース作成
az cosmosdb sql database create \
  --account-name travel-marketing-cosmos \
  --resource-group rg-travel-marketing \
  --name travel-marketing

# コンテナ作成
az cosmosdb sql container create \
  --account-name travel-marketing-cosmos \
  --resource-group rg-travel-marketing \
  --database-name travel-marketing \
  --name conversations \
  --partition-key-path /id
```

### Managed Identity でのアクセス設定

```bash
# Container Apps の Managed Identity に Cosmos DB データ貢献者ロールを割り当て
az cosmosdb sql role assignment create \
  --account-name travel-marketing-cosmos \
  --resource-group rg-travel-marketing \
  --principal-id <container-app-identity-principal-id> \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --scope "/"
```

### 確認

```env
COSMOS_DB_ENDPOINT=https://travel-marketing-cosmos.documents.azure.com:443/
```

---

## 6. APIM AI Gateway

Azure API Management を AI Gateway として使用し、Foundry へのリクエストをプロキシする。

### Azure CLI

```bash
# APIM インスタンス作成（BasicV2 SKU）
az apim create \
  --name travel-marketing-apim \
  --resource-group rg-travel-marketing \
  --location eastus2 \
  --publisher-name "Travel Marketing" \
  --publisher-email admin@example.com \
  --sku-name BasicV2
```

### ポータル設定

1. APIM → API → 「Azure OpenAI Service API」をインポート
2. Inbound ポリシーに `llm-content-safety` を追加（追加フィルタリング）
3. Backend に Foundry エンドポイントを設定
4. Managed Identity で Foundry に認証

---

## 7. Fabric Lakehouse

売上データ・顧客レビューの分析に使用。未設定時は CSV フォールバック。

### 前提条件

- Microsoft Fabric 容量（F2 以上推奨）
- Fabric ワークスペースへのアクセス権

### セットアップ手順

1. **Fabric 容量の確認**
   - Azure ポータル → Microsoft Fabric → 容量が有効であることを確認

2. **Lakehouse 作成**
   - Fabric ポータル → ワークスペース → 「新しい Lakehouse」
   - 名前: `travel_marketing_lakehouse`

3. **Data Factory でデモデータロード**

   まずデモデータを生成:

   ```bash
   uv run python data/demo_data_generator.py
   # → data/sales_history.csv (800件)
   # → data/customer_reviews.csv (400件)
   # → data/plan_master.csv (20件)
   ```

   Data Factory のパイプラインで CSV → Delta テーブルに変換、または手動アップロード:

   - Fabric ポータル → Lakehouse → 「ファイルのアップロード」
   - テーブル: `sales_history`, `customer_reviews`, `plan_master`

4. **SQL エンドポイント確認**
   - Lakehouse → SQL 分析エンドポイント → エンドポイント URL をコピー

### 確認

```env
FABRIC_SQL_ENDPOINT=your-lakehouse.datawarehouse.fabric.microsoft.com
```

---

## 8. Foundry IQ Knowledge Base

規制チェック（Agent3）でレギュレーション文書を検索するために使用。

### 前提条件

- Azure AI Search リソース

### セットアップ手順

1. **AI Search リソース作成**

   ```bash
   az search service create \
     --name travel-marketing-search \
     --resource-group rg-travel-marketing \
     --location eastus2 \
     --sku basic
   ```

2. **Knowledge Base 作成**
   - Foundry ポータル → プロジェクト → 「ナレッジベース」
   - 名前: `regulations-kb`
   - AI Search リソースを接続

3. **ドキュメントアップロード**
   - `regulations/` ディレクトリ内の文書をアップロード
   - 対象: 旅行業法、景品表示法、社内ブランドガイドライン等

4. **インデックス確認**
   - インデックス作成が完了したことを確認
   - テストクエリ: 「景品表示法 有利誤認」

---

## 9. Azure Functions (Flex Consumption)

MCP サーバーとして外部ツール連携に使用。

> **注意**: Flex Consumption プランを使用。旧 Consumption プランはレガシーです。

### Azure CLI

```bash
# ストレージアカウント作成
az storage account create \
  --name travelmarketingfunc \
  --resource-group rg-travel-marketing \
  --location eastus2 \
  --sku Standard_LRS

# Function App 作成（Flex Consumption）
az functionapp create \
  --name travel-marketing-func \
  --resource-group rg-travel-marketing \
  --storage-account travelmarketingfunc \
  --runtime python \
  --runtime-version 3.12 \
  --flexconsumption-location eastus2
```

### デプロイ

```bash
cd functions
func azure functionapp publish travel-marketing-func
```

---

## 10. Hosted Agent 登録

Foundry Agent Service に Hosted Agent としてデプロイする。

### 手順

1. **ACR ビルド**

   ```bash
   az acr build \
     --registry <your-acr-name> \
     --image travel-agents-hosted:latest \
     --file Dockerfile.agent \
     .
   ```

2. **Foundry ポータルで Hosted Agent 作成**
   - Foundry ポータル → プロジェクト → 「エージェント」→ 「Hosted Agent」
   - コンテナイメージ: `<your-acr-name>.azurecr.io/travel-agents-hosted:latest`
   - エントリポイント: `src.hosted_agent` モジュール

3. **Managed Identity 設定**
   - Hosted Agent に System Managed Identity を割り当て
   - 必要なロール:
     - `Cognitive Services OpenAI User`（Foundry リソース）
     - `Key Vault Secrets User`（Key Vault）

> **制約**: Hosted Agent は現時点で private networking に未対応です。ネットワーク分離は Container Apps 層で実施。

---

## 11. Evaluations セットアップ

Foundry Evaluations で品質ダッシュボードを構築する。

### ポータル設定

1. Foundry ポータル → プロジェクト → 「評価」
2. 評価メトリクスを設定:
   - **Groundedness**: 生成テキストがデータに基づいているか
   - **Relevance**: ユーザーの質問に対する関連性
   - **ToolCallAccuracy**: ツール呼び出しの正確性
3. テストデータセットを作成して定期実行を設定

---

## 12. Teams 公開

Foundry Agent Service から Microsoft Teams に直接公開する。

### ポータル設定

1. Foundry ポータル → エージェント → 「公開」
2. 公開先: Microsoft Teams を選択
3. Teams 管理者の承認が必要（組織ポリシーによる）
4. Teams アプリとしてユーザーに配布

---

## 13. Logic Apps コネクタ

承認後の Teams 通知と SharePoint 保存を自動化する。

### ポータル設定

1. **Logic App 作成**（Consumption プラン）

   ```bash
   az logic workflow create \
     --name travel-marketing-logic \
     --resource-group rg-travel-marketing \
     --location eastus2
   ```

2. **ワークフロー設計**（ポータルのデザイナーで構築）
   - トリガー: HTTP リクエスト受信
   - アクション 1: Teams チャネルにメッセージ送信
   - アクション 2: SharePoint ドキュメントライブラリに成果物を保存

3. **コネクタ認証**
   - Teams コネクタ: 組織アカウントで認証
   - SharePoint コネクタ: 組織アカウントで認証

---

## 14. Application Insights

テレメトリ収集とパフォーマンスモニタリング。

### Azure CLI

```bash
# Application Insights 作成
az monitor app-insights component create \
  --app travel-marketing-insights \
  --resource-group rg-travel-marketing \
  --location eastus2 \
  --application-type web

# 接続文字列を取得
az monitor app-insights component show \
  --app travel-marketing-insights \
  --resource-group rg-travel-marketing \
  --query "connectionString" -o tsv
```

### 確認

```env
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=...
```

---

## リソース構成図

```
rg-travel-marketing/
├── travel-marketing-foundry        # Foundry (CognitiveServices)
│   └── travel-agents               # Project
│       ├── gpt-5-4-mini            # Model deployment
│       └── gpt-image-1-5           # Image model deployment
├── travel-marketing-cosmos         # Cosmos DB (Serverless)
├── travel-marketing-apim           # API Management (BasicV2)
├── travel-marketing-search         # AI Search (Basic)
├── travel-marketing-func           # Functions (Flex Consumption)
├── travel-marketing-logic          # Logic Apps (Consumption)
├── travel-marketing-insights       # Application Insights
├── travel-marketing-acr            # Container Registry
├── travel-marketing-ca             # Container Apps
├── travel-marketing-kv             # Key Vault
└── travel-marketing-vnet           # Virtual Network
    ├── snet-container-apps         # Container Apps サブネット
    └── snet-private-endpoints      # Private Endpoint サブネット
```

---

## 必要なロール割り当て一覧

| プリンシパル | リソース | ロール |
|------------|---------|-------|
| Container Apps MI | Foundry | `Cognitive Services OpenAI User` |
| Container Apps MI | Key Vault | `Key Vault Secrets User` |
| Container Apps MI | Cosmos DB | `Cosmos DB Built-in Data Contributor` |
| Container Apps MI | ACR | `AcrPull` |
| APIM MI | Foundry | `Cognitive Services OpenAI User` |
| GitHub Actions SP | ACR | `AcrPush` |
| GitHub Actions SP | Container Apps | `Contributor` |
| Hosted Agent MI | Foundry | `Cognitive Services OpenAI User` |
| Hosted Agent MI | Key Vault | `Key Vault Secrets User` |

> **注意**: 全ての認証は `DefaultAzureCredential` / Managed Identity を使用。API キーのハードコードは禁止。
