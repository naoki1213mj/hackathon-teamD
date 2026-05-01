# Ontology v2 (`travelIQ_v2`) 監査レポート

**実施日**: Phase 10 / Fabric Data Agent 信頼性向上タスク
**対象**: `ws-3iq-demo / 096ff72a-6174-4aba-8f0c-140454fa6c3f` 配下の `travelIQ_v2 / 10cd6675-405a-4366-b91b-d57242a28914`
**取得経路**: `POST https://api.fabric.microsoft.com/v1/workspaces/{ws}/ontologies/{id}/getDefinition` (LRO, audience `https://api.fabric.microsoft.com`)
**生成スクリプト**: `audit/fetch_ontology_v2.py`, `audit/summarize_ontology.py`
**出力**: `audit/ontology_v2_full.json` (raw 40 parts), `audit/ontology_v2_decoded.json` (decode 済), `audit/ontology_summary.txt`

---

## 1. サマリ

| 指標 | 値 |
|------|------|
| EntityType 数 | 10 |
| DataBinding 数 | 10 (entity 1:1) |
| RelationshipType 数 | 9 |
| Contextualization 数 | 9 |
| TimeSeries 化済み EntityType | 3 (`booking`, `payment`, `cancellation`) |
| `displayNamePropertyId` が設定されている EntityType | **0 / 10** ← 改善対象 |
| 値同義語 (synonyms) を保持できるフィールド | **存在しない** ← 後述 |

---

## 2. EntityType / プロパティ一覧

| ID | name | 通常 prop | TS prop | timestamp 列 | sourceTable |
|----|------|-----------|---------|--------------|-------------|
| 100000000001 | customer | 14 | 0 | — | `dbo.customer` |
| 100000000002 | booking | 15 | 7 | `departure_date` | `dbo.booking` |
| 100000000003 | payment | 6 | 3 | `paid_at` | `dbo.payment` |
| 100000000004 | cancellation | 5 | 3 | `cancelled_at` | `dbo.cancellation` |
| 100000000005 | itinerary_item | 12 | 0 | — | `dbo.itinerary_item` |
| 100000000006 | hotel | 12 | 0 | — | `dbo.hotel` |
| 100000000007 | flight | 9 | 0 | — | `dbo.flight` |
| 100000000008 | tour_review | 10 | 0 | — | `dbo.tour_review` |
| 100000000009 | campaign | 11 | 0 | — | `dbo.campaign` |
| 100000000010 | inquiry | 11 | 0 | — | `dbo.inquiry` |

`booking` の TS 化対象列: `duration_days, pax, pax_adult, pax_child, total_revenue_jpy, price_per_person_jpy, lead_time_days`。
`payment` の TS 化対象列: `amount_jpy, exchange_rate_to_jpy, installment_count`。
`cancellation` の TS 化対象列: `cancellation_lead_days, cancellation_fee_jpy, refund_amount_jpy`。

主要メトリクス列はすべて `BigInt` / `Double` で TS バインドされており、Direct Lake 経由で SUM/AVG が可能。

---

## 3. RelationshipType（9 本）

| Relationship 名 | source (FROM=many) | target (TO=one) | binding table | FK 列 |
|----------------|--------------------|-----------------|---------------|-------|
| `booking_has_customer` | booking | customer | dbo.booking | customer_id |
| `booking_has_campaign` | booking | campaign | dbo.booking | campaign_id |
| `payment_has_booking` | payment | booking | dbo.payment | booking_id |
| `cancellation_has_booking` | cancellation | booking | dbo.cancellation | booking_id |
| `tour_review_has_booking` | tour_review | booking | dbo.tour_review | booking_id |
| `itinerary_item_has_booking` | itinerary_item | booking | dbo.itinerary_item | booking_id |
| `itinerary_item_has_hotel` | itinerary_item | hotel | dbo.itinerary_item | hotel_id |
| `itinerary_item_has_flight` | itinerary_item | flight | dbo.itinerary_item | flight_id |
| `inquiry_has_customer` | inquiry | customer | dbo.inquiry | customer_id |

10 EntityType を網羅する基本リレーションは過不足なく宣言されている。

---

## 4. 同義語（synonyms） — スキーマ調査結果

公式の Fabric Ontology JSON Schema を確認した結果、**EntityType / EntityTypeProperty / RelationshipType / DataBinding のいずれにも synonyms / aliases / displayLabels / description フィールドは存在しない**。

確認したスキーマ:

- `https://developer.microsoft.com/json-schemas/fabric/item/ontology/entityType/1.0.0/schema.json`
- `https://developer.microsoft.com/json-schemas/fabric/item/ontology/dataBinding/1.0.0/schema.json`
- `https://developer.microsoft.com/json-schemas/fabric/item/ontology/relationshipType/1.0.0/schema.json`

`EntityTypeProperty` で許可される項目は `id`, `name`, `redefines`, `baseTypeNamespaceType`, `valueType` のみ。`name` はパターン `^[a-zA-Z][a-zA-Z0-9_-]{0,127}$` に制約されており、日本語ラベルや「春」などの値は格納できない。

**結論**: 「春→spring」「ファミリー→family」のような値同義語、および「売上→SUM(total_revenue_jpy)」のような語彙→GQL マッピングは Ontology 側に格納できない。これらは Microsoft の推奨どおり **Data Agent の `aiInstructions` / `dataSourceInstructions` / `example queries`** に集約する必要がある (参照: `data-agent-configuration-best-practices` §5)。

→ **Phase 10 / `da-agent-instructions-tune` 工程で対応する**。Ontology 側の更新ではない。

---

## 5. ギャップ分析（タスクで指定された観点）

| 観点 | Ontology 側のカバー | データ側 | アクションが必要か |
|------|----------------------|----------|---------------------|
| **season** (春/夏/秋/冬) | `booking.season` プロパティあり (String, NonTS prop)。値は `spring/summer/autumn/winter/gw/obon/new_year` で booking テーブルに格納 | 7 値すべて存在 (cnt: spring=12530, summer=11288, autumn=10684, winter=9782, gw=2371, obon=1821, new_year=1524) | Ontology 構造変更不要。値マッピング (春→spring 等) は aiInstructions 既存§A.5 に記載済 |
| **customer_segment** (ファミリー/シニア/学生/カップル) | `customer.customer_segment` プロパティあり | 7 値 (family=2731, couple=2102, solo=1843, group=1215, senior=985, student=607, business=517) | Ontology 構造変更不要。日本語マッピングは aiInstructions §A.8 に記載済 |
| **age_group** (20代/30代/...) | `customer.age_band` プロパティあり | 7 値 (10s/20s/30s/40s/50s/60s/70s+) | Ontology 構造変更不要。マッピングは §A.9 |
| **destination** (沖縄/北海道/京都/海外/国内) | `booking.destination_region` (region 30 値)、`destination_country` (英語 13 値)、`destination_type` (domestic/outbound/inbound) の 3 プロパティで覆う | region 30 値とも完全一致 (詳細は dataset audit) | 構造変更不要。「Hawaii→ハワイ」等の英⇄日マッピングは §A.1 / §D.1 |
| **metrics** (売上/予約数/単価/利益率) | `booking.total_revenue_jpy` / `booking.price_per_person_jpy` / `booking.pax` 等は TS prop として TimeSeries バインド済 | データ存在 | **利益率に該当する `cost / margin` 列はソースに存在しない**。「利益率」は構造的に算出不可 → aiInstructions §D.7 で「列に無い指標は代替指標へ」のフォールバック規則あり。問題なし |

---

## 6. 改善余地（Ontology 側で構造的に可能なもの）

`displayNamePropertyId` が **10 件すべて null**。これが NL2Ontology の出力品質に影響している。具体的には Phase 9.6 の smoke 結果 P01 で、`MATCH (booking_node:booking) ... RETURN booking_node.booking_id, SUM(...) GROUP BY booking_id` という GQL が生成され、PK でグルーピングして「集計でなく明細列」を返してしまう事故が起きていた。`displayNamePropertyId` を意味のある列に設定すれば、エージェントが「どの列で表示するか」を推論する手がかりが増える。

設定提案 (Phase 10 enrichment):

| EntityType | 推奨 displayNamePropertyId (列名) |
|-----------|-----------------------------------|
| customer | `customer_code` |
| booking | `plan_name` |
| payment | `payment_id` *(自然語ラベルなし)* |
| cancellation | `cancellation_id` *(同上)* |
| itinerary_item | `item_name` |
| hotel | `name` |
| flight | `route_label` |
| tour_review | `plan_name` |
| campaign | `campaign_name` |
| inquiry | `subject` |

これは **非破壊的** で、既存の DataBinding / Relationship / TS 設定に影響しない。

---

## 7. Phase 10 で実行する変更

1. **Ontology**: `displayNamePropertyId` を 10 entity に設定する非破壊パッチを `enrich_ontology_v2.py` で適用。
2. **値同義語**: スキーマ制約のため Ontology 側ではなく `aiInstructions`（既に §A に整備されているが軽微な改善余地あり）に維持する。
3. **`displayNamePropertyId` 反映後の SM refresh**: `POST /datasets/{sm_id}/refreshes` (audience `https://analysis.windows.net/powerbi/api`) で Direct Lake を再フレーム。
4. **smoke 検証**: 変更前後で `bestof_strict.py` を比較し、Grade A 件数の delta を `phase10_summary.md` に記載。

---

## 付録 A. 取得トレース

```text
POST https://api.fabric.microsoft.com/v1/workspaces/096ff72a-6174-4aba-8f0c-140454fa6c3f/ontologies/10cd6675-405a-4366-b91b-d57242a28914/getDefinition -> 202
  status=Running
  status=Succeeded
40 parts: 1 rootDefinition + 10 entityType + 10 dataBinding + 9 relationshipType + 9 contextualization + 1 .platform
```
