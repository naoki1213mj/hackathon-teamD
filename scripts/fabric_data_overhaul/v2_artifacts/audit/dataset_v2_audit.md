# Dataset v2 (`lh_travel_marketing_v2`) 監査レポート

**実施日**: Phase 10 / Fabric Data Agent 信頼性向上タスク
**対象**: SQL endpoint `pabkxzbptdhuzf2qxkx52ftsp4-fl3w6clumg5evdymcqcfj6tmh4.datawarehouse.fabric.microsoft.com` / Database `lh_travel_marketing_v2` / schema `dbo`
**接続経路**: `pyodbc + DefaultAzureCredential`、audience `https://database.windows.net`、`SQL_COPT_SS_ACCESS_TOKEN=1256`
**取得スクリプト**: `audit/fetch_dataset_v2.py` (uv run, 認証済 Service Principal)
**生成 raw JSON**: `audit/dataset_v2_audit_raw.json`

---

## 1. テーブル行数（10 テーブル）

| Table | rows |
|------|------|
| customer | 10,000 |
| booking | 50,000 |
| payment | 61,289 |
| cancellation | 5,135 |
| itinerary_item | 175,323 |
| hotel | 500 |
| flight | 2,000 |
| tour_review | 8,243 |
| campaign | 200 |
| inquiry | 20,000 |

`booking` と `cancellation` の比 = **10.27%**（生キャンセル率の参考値）。

---

## 2. ontology が参照する全カラムの DISTINCT 値（コア抜粋）

### 2.1 `booking.season`（7 値）

| value | bookings |
|------|---|
| spring | 12,530 |
| summer | 11,288 |
| autumn | 10,684 |
| winter | 9,782 |
| gw | 2,371 |
| obon | 1,821 |
| new_year | 1,524 |

### 2.2 `booking.destination_region`（30 値, 日本語）

すべて aiInstructions §A.1 の列挙と完全一致 — coverage diff `in_data_not_in_ontology = []`, `in_ontology_not_in_data = []`。

トップ 10: 沖縄(5,720) / 北海道(5,203) / その他(4,031) / 京都(3,735) / ハワイ(3,013) / 大阪(2,884) / 東京(2,833) / 韓国(2,393) / 台湾(1,882) / 福岡(1,517)。

### 2.3 `booking.destination_country`（13 値, 英語）

Japan(34,079) / USA(4,652) / South Korea(2,393) / Taiwan(1,882) / Thailand(1,379) / Singapore(1,014) / France(882) / Vietnam(815) / Italy(709) / Australia(694) / UK(516) / UAE(498) / China(487)。

### 2.4 `booking.destination_type`（3 値）

domestic = 31,038 / outbound = 16,877 / inbound = 2,085。

### 2.5 `booking.product_type`（5 値）

fit(18,001) / freeplan(10,457) / domestic_package(10,245) / outbound_package(5,734) / cruise(5,563)。

### 2.6 `booking.booking_status`（4 値）

completed(40,832) / cancelled(5,135) / confirmed(3,018) / no_show(1,015)。

→ 売上集計は `IN ('confirmed','completed')` で 43,850 件 (87.7%)。

### 2.7 `customer.customer_segment`（7 値）

family(2,731) / couple(2,102) / solo(1,843) / group(1,215) / senior(985) / student(607) / business(517)。

### 2.8 `customer.age_band`（7 値）

30s(2,207) / 40s(2,003) / 20s(1,833) / 50s(1,602) / 60s(1,169) / 70s+(785) / 10s(401)。

### 2.9 `customer.loyalty_tier`（4 値）

silver(3,996) / none / gold / platinum *(分布は raw JSON 参照)*

### 2.10 `payment.currency`（3 値）

JPY(59,203) / USD(1,364) / EUR(722)。

### 2.11 `tour_review.sentiment` / `rating`

3 値 (positive/neutral/negative)。avg_rating = **3.87**, avg_nps = **+46.3**, high_rating(rating≥4) = 5,725 件 / 8,243 件 = **69.5%**, low_rating(≤2) = 1,125 件 = **13.6%**。

### 2.12 `cancellation.cancellation_reason`（8 値）

8 reason codes に分散。詳細は raw JSON。

### 2.13 その他のフィールド

`hotel.category`(6: ryokan/budget/luxury/resort/midscale/upscale), `flight.flight_class`(4: economy/business/premium_economy/first), `inquiry.channel`(6: web_form/tel/email/chat/store/social), `inquiry.inquiry_type`(6: pre_booking_question/change_request/info_request/refund_request/complaint/lost_item) など、全カラムについて DISTINCT を取得済み。詳細は `dataset_v2_audit_raw.json`。

---

## 3. クロス分析（タスクで指定された分布観点）

### 3.1 `season × destination_type` 売上クロス

| season | type | bookings | revenue (¥) |
|--------|------|----------|-------------|
| spring | domestic | 6,813 | 3,003,805,477 |
| spring | outbound | 3,720 | 4,001,425,639 |
| spring | inbound | 465 | 337,993,653 |
| summer | domestic | 6,124 | 2,636,746,381 |
| summer | outbound | 3,362 | 3,575,574,786 |
| summer | inbound | 401 | 290,542,817 |
| autumn | domestic | 5,799 | 2,556,555,942 |
| autumn | outbound | 3,166 | 3,383,355,535 |
| autumn | inbound | 399 | 289,581,208 |
| winter | domestic | 5,337 | 2,284,813,895 |
| winter | outbound | 2,877 | 3,189,337,827 |
| winter | inbound | 355 | 282,984,624 |
| gw | domestic | 1,328 | 564,216,140 |
| gw | outbound | 688 | 763,162,558 |
| gw | inbound | 86 | 59,192,058 |
| obon | domestic | 986 | 422,452,776 |
| obon | outbound | 546 | 570,268,760 |
| obon | inbound | 65 | 42,621,506 |
| new_year | domestic | 829 | 354,671,336 |
| new_year | outbound | 459 | 481,365,818 |
| new_year | inbound | 45 | 24,344,558 |

### 3.2 `destination_region` 別売上 トップ 15

| region | bookings | revenue (¥) | avg pp price |
|---|---|---|---|
| ハワイ | 2,673 | 2,946,473,690 | 327,928 |
| 沖縄 | 5,018 | 2,328,083,134 | 136,682 |
| 韓国 | 2,063 | 2,185,670,920 | 333,499 |
| その他 | 3,530 | 2,124,163,337 | 176,668 |
| 北海道 | 4,566 | 1,975,104,183 | 135,599 |
| 台湾 | 1,638 | 1,714,608,104 | 321,271 |
| 京都 | 3,266 | 1,503,110,784 | 136,183 |
| タイ | 1,211 | 1,351,738,984 | 333,837 |
| 東京 | 2,471 | 1,299,554,490 | 154,889 |
| 大阪 | 2,513 | 1,197,384,345 | 144,194 |
| シンガポール | 898 | 1,005,464,384 | 326,193 |
| アメリカ西海岸 | 876 | 955,304,214 | 332,777 |
| パリ | 771 | 810,153,650 | 319,944 |
| ベトナム | 716 | 758,132,808 | 319,868 |
| オーストラリア | 609 | 657,581,402 | 332,023 |

### 3.3 `customer_segment × age_band` ブッキング数（抜粋）

| segment | age | bookings | revenue (¥) |
|---|---|---|---|
| couple | 30s | 1,930 | 875,547,917 |
| couple | 40s | 1,906 | 830,739,918 |
| couple | 20s | 1,833 | 758,291,530 |
| family | 40s | (next page) | … |
| business | 30s | 468 | 147,598,130 |
| senior | 70s+ | (raw 参照) | … |

詳細は `dataset_v2_audit_raw.json["cross"]["segment_x_ageband_bookings"]`。全 49 セルが埋まっており、HAVING ≥ 5 のサンプル稀薄問題なし。

### 3.4 `inbound` source market（destination_country = inbound 来訪先）

| dest country | dest region | bookings | revenue (¥) |
|---|---|---|---|
| Japan | 東京 | 636 | 478,145,461 |
| Japan | 京都 | 461 | 317,540,112 |
| Japan | 大阪 | 367 | 268,184,239 |
| Japan | 沖縄 | 175 | 135,430,388 |
| Japan | 北海道 | 177 | 127,960,224 |

> ※ inbound の **source_market** (発地国) は現状のスキーマには列が無い。`destination_country` は来訪先 (`Japan`) のみ。「source market」を区別したい場合は別カラムが必要 — Lakehouse 拡張要件。

### 3.5 `total_revenue_jpy` 帯域分布（confirmed+completed）

| band | bookings | total revenue (¥) |
|------|---------:|------------------:|
| A: <100k | 5,499 | 372,856,795 |
| B: 100k–300k | 13,700 | 2,612,831,290 |
| C: 300k–500k | 7,669 | 2,997,549,302 |
| D: 500k–1M | 8,801 | 6,204,983,392 |
| E: 1M–3M | 6,949 | 11,403,297,286 |
| F: ≥3M | 1,232 | 5,523,495,229 |

→ 高単価ロングテール (F) が件数 1,232 件で売上 19% を占める。

### 3.6 年別売上推移（出発日ベース）

| year | bookings | revenue (¥) | avg revenue (¥) |
|---|---:|---:|---:|
| 2022 | 6,019 | 3,771,651,514 | 626,624 |
| 2023 | 10,496 | 6,495,133,581 | 618,819 |
| 2024 | 12,587 | 8,615,398,257 | 684,467 |
| 2025 | 13,477 | 9,321,128,128 | 691,632 |
| 2026 | 1,271 | 911,701,814 | 717,310 ⚠ 1〜4 月のみ |

aiInstructions §B.1 のリファレンス値と完全一致。

---

## 4. Ontology 同義語カバレッジのクロスチェック

データ側の値 ⇄ aiInstructions §A の列挙値の差分:

| 列 | データに存在 / 列挙に無い | 列挙にある / データに無い |
|----|--------------------------|--------------------------|
| `booking.destination_region` | なし (30 値完全一致) | なし |
| `booking.destination_country` | なし (13 値完全一致) | なし |
| `booking.destination_type` | なし (3 値完全一致) | なし |
| `booking.season` | なし (7 値完全一致) | なし |
| `booking.product_type` | なし (5 値完全一致) | なし |
| `booking.booking_status` | なし (4 値完全一致) | なし |
| `customer.customer_segment` | なし (7 値完全一致) | なし |
| `customer.age_band` | なし (7 値完全一致) | なし |
| `customer.loyalty_tier` | なし (4 値完全一致) | なし |
| `payment.currency` | なし (3 値完全一致) | なし |
| `payment.payment_method` | (raw 参照) | (raw 参照) |
| `tour_review.sentiment` | なし (3 値完全一致) | なし |

**結論**: 値カバレッジは Phase 9.6 時点で完璧。aiInstructions §A の列挙が現実データを 100% 網羅しており、新たに追加すべき synonyms はない。

---

## 5. Phase 10 で改善すべき点（データ側ではなく Agent 側）

データ実態に問題は無く、ontology mapping もすべての列を捕捉している。残る gap は以下:

1. **`displayNamePropertyId` が 10 entity すべて null** → ontology enrichment 工程で対応 (`enrich_ontology_v2.py`).
2. **「source_market」列なし** — inbound の発地国を区別する列はソースに存在しない。aiInstructions で「source_market は現スキーマに無く `destination_country` で代替する」と明示する。
3. **「利益率 / 利益」列なし** — 同様に aiInstructions で「列に無い指標は代替指標へ」のフォールバックを徹底（既存 §D.7 のルール）。
4. **smoke 過去ログから判明した残課題**:
   - P01 「ハワイの売上」で `RETURN booking_id, SUM(...) GROUP BY booking_id` の誤生成 → aiInstructions §4 の「単一条件サマリは GROUP BY 禁止 / 集計のみ」ルールを GQL でも明確化。
   - P11 「リピート顧客比率」で「技術的制約」フォールバックが残存 → §C.1 / §D.4 の補強。
   - P13/P14 のタイムアウト → §D.6 のタイムアウト対策ルールを補強。

これらは `da-agent-instructions-tune` で対応する。

---

## 付録 A. 監査クエリの抜粋

```sql
-- 行数
SELECT 'booking' AS tbl, COUNT(*) FROM dbo.booking;

-- season distinct
SELECT season AS v, COUNT(*) AS cnt
FROM dbo.booking GROUP BY season ORDER BY cnt DESC;

-- season × destination_type cross
SELECT season, destination_type, COUNT(*), SUM(total_revenue_jpy)
FROM dbo.booking WHERE booking_status IN ('confirmed','completed')
GROUP BY season, destination_type ORDER BY season, destination_type;

-- revenue band distribution
SELECT
  CASE WHEN total_revenue_jpy < 100000 THEN 'A_<100k'
       WHEN total_revenue_jpy < 300000 THEN 'B_100k-300k'
       WHEN total_revenue_jpy < 500000 THEN 'C_300k-500k'
       WHEN total_revenue_jpy < 1000000 THEN 'D_500k-1M'
       WHEN total_revenue_jpy < 3000000 THEN 'E_1M-3M'
       ELSE 'F_>=3M' END AS band,
  COUNT(*), SUM(total_revenue_jpy)
FROM dbo.booking
WHERE booking_status IN ('confirmed','completed')
GROUP BY ... ORDER BY band;
```

すべての raw 結果は `dataset_v2_audit_raw.json` に保存。
