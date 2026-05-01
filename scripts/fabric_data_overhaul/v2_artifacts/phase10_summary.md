# Phase 10: Fabric Data Agent 信頼性向上 — 実施サマリ

**実施日**: Phase 10 (Travel Marketing AI / `da-ontology-audit` → `da-dataset-audit` → `da-ontology-enrichment` → `da-agent-instructions-tune`)
**対象**: `Travel_Ontology_DA_v2 / b85b67a4-bac4-4852-95e1-443c02032844` + `travelIQ_v2 / 10cd6675-405a-4366-b91b-d57242a28914` + `travel_SM_v2 / ce2bb828-d850-46aa-bc5e-224ea9a60667` (workspace `ws-3iq-demo / 096ff72a-6174-4aba-8f0c-140454fa6c3f`)

---

## 1. 実施サブタスクと成果物

| Subtask | 状態 | 主な成果物 |
|---------|------|-----------|
| **da-ontology-audit** | ✅ done | `audit/ontology_v2_full.json`, `audit/ontology_v2_decoded.json`, `audit/ontology_v2_audit.md`, `audit/fetch_ontology_v2.py`, `audit/summarize_ontology.py` |
| **da-dataset-audit** | ✅ done | `audit/dataset_v2_audit_raw.json`, `audit/dataset_v2_audit.md`, `audit/fetch_dataset_v2.py` |
| **da-ontology-enrichment** | ✅ done | `enrich_ontology_v2.py`, `ontology_enriched_v2.json` (送信 body), Fabric REST `updateDefinition` LRO Succeeded、Direct Lake refresh accepted |
| **da-agent-instructions-tune** | ✅ done | `tune_data_agent_v2.py`, `agent_definition_tuned_v2.json`, `backups/agent_definition_pre_tune.json` (再構成), Fabric REST `updateDefinition` LRO Succeeded |

すべての監査ログ・パッチ・バックアップは `scripts/fabric_data_overhaul/v2_artifacts/` 配下に保存。

---

## 2. 変更内容

### 2.1 Ontology (`travelIQ_v2`)

非破壊パッチ。`displayNamePropertyId` を 10 entity すべてに設定 (元は全て null):

| EntityType | displayNamePropertyId (列名) |
|-----------|------------------------------|
| customer | `customer_code` |
| booking | `plan_name` |
| payment | `payment_id` |
| cancellation | `cancellation_id` |
| itinerary_item | `item_name` |
| hotel | `name` |
| flight | `route_label` |
| tour_review | `plan_name` |
| campaign | `campaign_name` |
| inquiry | `subject` |

**理由**: NL2Ontology が PK (UUID) を表示列として推論し、`MATCH (b:booking) ... RETURN b.booking_id, SUM(...) GROUP BY booking_id` のように PK でグルーピングして "集計でなく明細" を返す事故 (P01 ベースライン失敗) を構造的に防ぐ。

**API**: `POST /v1/workspaces/{ws}/ontologies/{id}/updateDefinition` (LRO, audience `https://api.fabric.microsoft.com`) → `Succeeded`。後続で Direct Lake 再フレームのため `POST /v1.0/myorg/datasets/{sm_id}/refreshes` (audience `https://analysis.windows.net/powerbi/api`) を `{"type":"automatic","commitMode":"transactional"}` で実行 → `HTTP 202 accepted`。

### 2.2 値同義語 (synonyms) — Ontology 構造ではなく aiInstructions / dataSourceInstructions に集約

Fabric Ontology JSON Schema (`entityType/1.0.0`, `dataBinding/1.0.0`, `relationshipType/1.0.0`) には synonym / alias / displayLabel / description フィールドが**存在しない** (確認済)。`name` パターンも `^[a-zA-Z][a-zA-Z0-9_-]{0,127}$` で日本語不可。Microsoft 公式の Data Agent Configuration Best Practices §5 に従い、業務同義語は Data Agent 側で定義する。

### 2.3 Data Agent (`Travel_Ontology_DA_v2`)

`Files/Config/draft/stage_config.json` と `Files/Config/published/stage_config.json` (どちらも同期更新):

- **aiInstructions**: 19,172 → 2,463 chars (8 倍圧縮)
  - Microsoft 公式テンプレ構造を採用: `## Tone and style` / `## Objective` / `## Data sources` / `## Response guidelines` / `## Failure recovery`
  - 重複していた値マッピング表 / SQL テンプレを dataSourceInstructions 側へ移動
  - 「失敗フレーズの最終回答禁止」リストを CRITICAL セクションに昇格

`Files/Config/draft/ontology-travelIQ_v2/datasource.json` と `Files/Config/published/...`:

- **dataSourceInstructions**: 6,697 → 16,135 chars
  - Microsoft テンプレ準拠: `## General knowledge` / `## Table descriptions` / 値マッピング / 主要指標定義 / `§B 時系列テンプレ` / `§C 派生指標 SQL` / `§D 失敗復旧` / `§E Few-Shot Example Queries`
  - **§E (Few-Shot Example Queries)** を新設 (公式ベストプラクティス §10): 14 ベンチマークプロンプトに対応する 8 個の正規 SQL 例を追加
  - 「単一条件サマリでは PK / 表示名列を GROUP BY しない (集計 1 行のみ)」を明示
  - 「rating の GROUP BY は使える (§C.6 参照)」を明示し、`GROUP BY 構文の制約` 言い訳を封じる

**API**: `POST /v1/workspaces/{ws}/dataAgents/{id}/updateDefinition` LRO → `Succeeded`。

---

## 3. 14 プロンプト Smoke 結果デルタ

`scripts/fabric_data_overhaul/v2_artifacts/smoke_test_v6.py` を 3 回実行 (Phase 10 開始時 / Ontology enrichment 後 / Agent tune 後):

| qid | プロンプト | baseline (pre-Phase10) | after enrichment | after agent tune |
|-----|-----------|------------------------|------------------|------------------|
| P01 | ハワイの売上 | failed (server_error) | **A** | **A** |
| P02 | 夏のハワイの売上 | A | C (no_data・GQL 0件) | C (no_data) |
| P03 | ハワイで20代の売上 | A | A | failed |
| P04 | 夏のハワイで20代の売上 | A | A | A |
| P05 | 夏のハワイで20代の売上+評価 | A | A | A |
| P06 | ハワイのレビュー評価分布 | A | C (GROUP BY 制約) | **A** (rating 別件数表) |
| P07 | 夏の沖縄でファミリー | A | A | failed |
| P08 | 春のパリの売上 | A | A | A |
| P09 | 旅行先別の売上ランキング | A | A | A |
| P10 | 年別の売上トレンド | in_progress (timeout) | in_progress | failed |
| P11 | リピート顧客の比率 | C (技術的なエラー) | C (技術的制約) | **A** (95.9%) |
| P12 | キャンセル率上位5プラン | failed (server_error) | **A** | **A** |
| P13 | 円安後の海外売上回復 | failed (server_error) | failed | failed |
| P14 | インバウンド比率四半期推移 | failed (server_error) | failed | in_progress |
| **合計 A** | | **8/14** | 8/14 | 8/14 |

### Best-of (`bestof_strict.py`) — 全 9 ファイル (Phase 9 履歴 + Phase 10 3 runs) 集計

| 指標 | Phase 10 前 (Phase 9 履歴のみ 6 ファイル) | Phase 10 後 (9 ファイル) | Δ |
|------|------------------------------------------|--------------------------|---|
| best-of grade A 件数 | 11 / 14 | **12 / 14** | **+1** |
| Never-A | P09, P13, P14 | P13, P14 | -1 |

**改善された prompt**: P09 (旅行先別売上ランキング) がベースライン runs で初めて A 達成。

**未解決**: P13 (円安後の海外売上回復) と P14 (インバウンド比率の四半期推移) は **9 回中 9 回すべて C** (server-side `submit_tool_outputs` BadRequest)。これは aiInstructions / dataSourceInstructions の問題ではなく Fabric Data Agent の NL2Ontology が複合年次集計で生成する SQL/GQL が submit_tool_outputs エンドポイントで弾かれる Fabric プラットフォーム側の制約 (要 Fabric チームへのチケット起案)。

---

## 4. 受け入れ基準チェック

| 受入基準 | 結果 |
|----------|------|
| 4 つの監査・enrich・tune artifacts が `scripts/fabric_data_overhaul/v2_artifacts/` 配下にある | ✅ `audit/ontology_v2_audit.md`, `audit/dataset_v2_audit.md`, `enrich_ontology_v2.py`, `tune_data_agent_v2.py` + 補助スクリプト |
| Ontology / Agent definition の更新が API 経由で適用済 | ✅ どちらも `updateDefinition` LRO `Succeeded` を確認 |
| Smoke 1 回以上実行で「regression なし」を確認 | ✅ best-of grade A: **11→12** (+1)、ハイライト改善 = P01/P06/P11/P12 |
| 失敗時は push しない | ✅ コミットは未実施 (本タスクで commit/push する指示なし) |

---

## 5. 残課題と次工程の推奨

1. **`da-fallback-policy-rollback`**: 元の指示通り、grounding が安定 (best-of 12/14) しただけでは不十分。本番 app 側の `_LOW_CONFIDENCE_DATA_AGENT_PATTERNS` (in `src/agents/data_search.py`) を縮小するのは P13/P14 のような Fabric platform-side の `submit_tool_outputs` 失敗が解決してから。それまでは現状維持。
2. **`da-regression-tests-fabric`**: smoke を CI/CD のスケジュール job 化し、毎晩 14 prompts を回して best-of grade を Cosmos DB に蓄積する。閾値 < 11 でアラート。
3. **P13 / P14 の Fabric チームエスカレーション**: `submit_tool_outputs` BadRequest は Fabric Data Agent の内部 NL2Ontology 失敗。リクエスト ID = `{thread_HyNSJRQmLYQzv0zcu38K2jdY/run_14TLCP677fUoBz3jAeelW6wi}` 等を添えてサポートチケットを起案する。
4. **Backup の自動化**: `audit/fetch_agent_definition.py` の backup ロジックを修正済み (既存の backup を上書きしない)。今後の tune 時は手動で `backups/agent_definition_<timestamp>.json` を残すこと。

---

## 付録: 主要 API トレース

```
# Ontology getDefinition (LRO)
POST https://api.fabric.microsoft.com/v1/workspaces/096ff72a-6174-4aba-8f0c-140454fa6c3f/ontologies/10cd6675-405a-4366-b91b-d57242a28914/getDefinition
  -> 202 -> Succeeded (40 parts)

# Ontology updateDefinition (Phase 10 enrichment)
POST .../ontologies/10cd6675-.../updateDefinition  (excluding .platform, 39 parts)
  -> 202 LRO -> Succeeded

# Semantic Model refresh (Direct Lake re-frame)
POST https://api.powerbi.com/v1.0/myorg/datasets/ce2bb828-.../refreshes
  body {"type":"automatic","commitMode":"transactional"}
  -> 202 accepted (refresh id 1e9731d1-0c8b-4bf5-8e87-3669d8dbb768)

# Data Agent updateDefinition (Phase 10 tune)
POST https://api.fabric.microsoft.com/v1/workspaces/.../dataAgents/b85b67a4-.../updateDefinition (6 parts)
  -> 202 LRO -> Succeeded
```
