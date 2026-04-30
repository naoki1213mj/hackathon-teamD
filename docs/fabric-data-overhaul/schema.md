# Travel Marketing v2: ER スキーマ設計

## 設計目的

Phase 9 で構築する `lh_travel_marketing_v2` Lakehouse の 10 テーブル ER 設計。  
NL2Ontology の翻訳先となる **物理スキーマの Source of Truth**。

## 設計方針

- **5 年分** (`2022-01-01` 〜 `2026-04-30`) のデータを格納する
- 既存の `travel_sales` / `travel_review` (旧 ws-3iq-demo) は **不変** で残し、本 v2 と並列で動かす
- すべての顧客 / 予約 / 決済は **synthetic**。PII は混入させない (氏名は `Faker(jp)` の dummy)
- 売上は **税込円**。為替影響は `payment.exchange_rate_to_jpy` で吸収する
- すべての日付は **JST** (UTC+9 を仮定)
- すべてのキーは **GUID 文字列** (Lakehouse Delta との親和性、Fabric Direct Lake への影響を最小化)
- すべてのテーブルに `loaded_at` (UTC TIMESTAMP) を追加し、ETL 観測性を確保

## ER Diagram (高レベル)

```text
                                 ┌─────────────┐
                                 │  customer   │
                                 └──┬──────────┘
                                    │ 1:N
                                    ▼
                       ┌──────────────────────┐
                       │       booking        │ ◀────── campaign (1:N)
                       └──┬─────┬─────────────┘
                          │     │
            1:N           │     │  1:N
                          ▼     ▼
                  ┌──────────┐ ┌──────────┐
                  │ payment  │ │itinerary_│
                  │          │ │   item   │
                  └──────────┘ └────┬─────┘
                                    │ N:1
                                    ▼
                           ┌────────────────┐
                           │ hotel | flight │
                           └────────────────┘
                          
                       ┌──────────────────────┐
                       │       booking        │
                       └─────┬────────┬───────┘
                             │        │
                   1:N       │        │  1:1 (option)
                             ▼        ▼
                    ┌──────────────┐ ┌──────────────┐
                    │ tour_review  │ │ cancellation │
                    └──────────────┘ └──────────────┘

                              ┌──────────────┐
                              │   inquiry    │ (お問い合わせ、独立ファクト)
                              └──────────────┘
```

## テーブル定義

### 1. `customer` (顧客マスタ)

| カラム | 型 | 説明 |
|---|---|---|
| `customer_id` | STRING (GUID) | PK。SCD Type 1 で更新時は overwrite。 |
| `customer_code` | STRING | 顧客番号 `C-2022-000123` 形式。`Y-Y-N` の範囲 1 万 |
| `last_name_kana` | STRING | カナ氏名 (姓)。Faker で生成 |
| `first_name_kana` | STRING | カナ氏名 (名) |
| `gender` | STRING | `male` / `female` / `other` (公的統計分布で seed) |
| `age_band` | STRING | `10s`, `20s`, `30s`, `40s`, `50s`, `60s`, `70s+` |
| `birth_year` | INT | 年齢計算用 |
| `customer_segment` | STRING | `family` / `couple` / `solo` / `group` / `senior` / `student` / `business` |
| `loyalty_tier` | STRING | `none` / `silver` / `gold` / `platinum` |
| `acquisition_channel` | STRING | `web` / `agent_store` / `tel` / `referral` / `corporate` |
| `prefecture` | STRING | 居住都道府県 (47 都道府県) |
| `email_opt_in` | BOOLEAN | メール配信同意 |
| `created_at` | TIMESTAMP | 登録日 |
| `updated_at` | TIMESTAMP | 最終更新日 |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 10,000 行。年ごとに新規 1,500-2,500 加入する想定。

---

### 2. `booking` (予約ファクト)

| カラム | 型 | 説明 |
|---|---|---|
| `booking_id` | STRING | PK |
| `booking_code` | STRING | `BK-2025-000123` 形式 |
| `customer_id` | STRING | FK → customer |
| `campaign_id` | STRING | FK → campaign (NULL 可) |
| `plan_name` | STRING | 例: `沖縄3泊4日ファミリープラン` |
| `product_type` | STRING | `domestic_package` / `outbound_package` / `freeplan` / `cruise` / `fit` |
| `destination_country` | STRING | 例: `Japan` / `USA` / `France` |
| `destination_region` | STRING | 例: `沖縄` / `ハワイ` / `パリ` |
| `destination_city` | STRING | 例: `那覇` / `Honolulu` / `Paris` |
| `destination_type` | STRING | `domestic` / `outbound` / `inbound` |
| `season` | STRING | `spring`, `summer`, `autumn`, `winter`, `gw`, `obon`, `new_year` |
| `departure_date` | DATE | 出発日 |
| `return_date` | DATE | 帰着日 |
| `duration_days` | INT | 日程 |
| `pax` | INT | 旅行者数 |
| `pax_adult` | INT | 成人 |
| `pax_child` | INT | 子供 |
| `total_revenue_jpy` | DECIMAL(12,0) | 税込売上 (円) |
| `price_per_person_jpy` | DECIMAL(12,0) | 1人あたり単価 |
| `booking_date` | DATE | 予約日 |
| `lead_time_days` | INT | 出発までの日数 (departure - booking) |
| `booking_status` | STRING | `confirmed` / `cancelled` / `completed` / `no_show` |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 50,000 行。月平均 ~830 件、ピーク (GW・お盆・年末年始) で 2,500 件/月程度。  
**季節性**: GW (4月後半-5月初旬) / お盆 (8月中旬) / 年末年始 / 紅葉 (10-11月) / 桜 (3月後半-4月初旬) / 春節 (1月後半-2月初旬、インバウンド) を強くする。  
**コロナリバウンド**: 2022 H1 = 通常の 40%、2022 H2 = 60%、2023 = 90%、2024+ = 110% (補正後正常)。  
**円安効果**: 2024 以降 outbound の `price_per_person_jpy` を +20% 補正。  
**インデックス推奨**: `(destination_region, season, booking_date)`。

---

### 3. `payment` (決済ファクト)

| カラム | 型 | 説明 |
|---|---|---|
| `payment_id` | STRING | PK |
| `booking_id` | STRING | FK → booking |
| `payment_method` | STRING | `credit_card` / `bank_transfer` / `pay_at_store` / `point` / `voucher` |
| `payment_status` | STRING | `pending` / `succeeded` / `failed` / `refunded` |
| `amount_jpy` | DECIMAL(12,0) | 決済額 |
| `currency` | STRING | `JPY` / `USD` / `EUR` (海外現地払いがある場合) |
| `exchange_rate_to_jpy` | DECIMAL(10,4) | 当時の換算レート (`USD->JPY` など) |
| `paid_at` | TIMESTAMP | 決済成立時刻 |
| `installment_count` | INT | 分割回数 (1 = 一括) |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 50,000-55,000 行 (1 booking に対して 1 payment が基本、稀に 2-3 分割)。

---

### 4. `itinerary_item` (旅程明細)

| カラム | 型 | 説明 |
|---|---|---|
| `itinerary_item_id` | STRING | PK |
| `booking_id` | STRING | FK → booking |
| `item_type` | STRING | `flight` / `hotel` / `transfer` / `activity` / `meal` / `insurance` |
| `item_name` | STRING | 例: `美ら海水族館入場券`, `ハワイ→東京 ANA850便` |
| `hotel_id` | STRING | FK → hotel (item_type=hotel のみ) |
| `flight_id` | STRING | FK → flight (item_type=flight のみ) |
| `start_date` | DATE | 開始日 |
| `end_date` | DATE | 終了日 |
| `nights` | INT | 宿泊日数 (hotel のみ) |
| `unit_price_jpy` | DECIMAL(10,0) | 単価 |
| `quantity` | INT | 数量 |
| `total_price_jpy` | DECIMAL(12,0) | 合計 |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 150,000 行。1 booking あたり 2-5 アイテム (フライト + ホテル + 数アクティビティ)。

---

### 5. `hotel` (宿泊施設マスタ)

| カラム | 型 | 説明 |
|---|---|---|
| `hotel_id` | STRING | PK |
| `hotel_code` | STRING | 内部コード |
| `name` | STRING | 例: `ザ・ブセナテラス` |
| `country` | STRING | 例: `Japan` |
| `region` | STRING | 例: `沖縄` |
| `city` | STRING | 例: `名護市` |
| `category` | STRING | `luxury` / `upscale` / `midscale` / `budget` / `ryokan` / `resort` |
| `star_rating` | INT | 1-5 |
| `room_count` | INT | 客室数 |
| `avg_price_per_night_jpy` | DECIMAL(10,0) | 平均一泊料金 |
| `latitude` | DOUBLE | 地理空間検索用 |
| `longitude` | DOUBLE | 地理空間検索用 |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 500 行 (国内 300 + 海外 200)。

---

### 6. `flight` (フライト商品マスタ)

| カラム | 型 | 説明 |
|---|---|---|
| `flight_id` | STRING | PK |
| `airline_code` | STRING | `ANA` / `JAL` / `UAL` / `DEL` 等 |
| `airline_name` | STRING | 例: `全日本空輸` |
| `departure_airport` | STRING | IATA 例: `HND` |
| `arrival_airport` | STRING | IATA |
| `route_label` | STRING | `HND-HNL` 形式 |
| `flight_class` | STRING | `economy` / `premium_economy` / `business` / `first` |
| `distance_km` | INT | 距離 |
| `avg_duration_min` | INT | 平均所要時間 |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 2,000 行 (ルート × クラス × 主要キャリア)。

---

### 7. `tour_review` (顧客レビュー)

| カラム | 型 | 説明 |
|---|---|---|
| `review_id` | STRING | PK |
| `booking_id` | STRING | FK → booking |
| `customer_id` | STRING | FK → customer (denormalized for query speed) |
| `plan_name` | STRING | denormalized |
| `destination_region` | STRING | denormalized |
| `rating` | INT | 1-5 |
| `nps` | INT | -100 〜 +100 (NPS 計算用) |
| `comment` | STRING | 例: `子供が大喜び。ガイドさんが親切` |
| `comment_summary` | STRING | LLM 生成の 1 行サマリ (オプション、null 可) |
| `sentiment` | STRING | `positive` / `neutral` / `negative` |
| `review_date` | DATE | レビュー投稿日 |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 10,000 行 (booking 50,000 のうち約 20% が投稿)。

---

### 8. `campaign` (販促キャンペーン)

| カラム | 型 | 説明 |
|---|---|---|
| `campaign_id` | STRING | PK |
| `campaign_code` | STRING | `CMP-2025-Q2-001` |
| `campaign_name` | STRING | 例: `早期予約30%OFF` |
| `campaign_type` | STRING | `early_bird` / `last_minute` / `loyalty` / `seasonal` / `regional_partner` / `corporate` |
| `target_segment` | STRING | `family` / `couple` / etc., null=全顧客 |
| `target_destination_type` | STRING | `domestic` / `outbound` / null |
| `start_date` | DATE | 開始日 |
| `end_date` | DATE | 終了日 |
| `discount_percent` | DECIMAL(5,2) | 値引き率 |
| `total_budget_jpy` | DECIMAL(14,0) | 投下予算 |
| `total_redemptions` | INT | 利用件数 (集計値) |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 200 行 (5 年 × Q4 × 主要キャンペーン 10 種前後)。

---

### 9. `inquiry` (問い合わせ・コンタクト履歴)

| カラム | 型 | 説明 |
|---|---|---|
| `inquiry_id` | STRING | PK |
| `customer_id` | STRING | FK → customer (NULL 可、未登録顧客の問い合わせ) |
| `channel` | STRING | `web_form` / `tel` / `email` / `chat` / `store` / `social` |
| `inquiry_type` | STRING | `pre_booking_question` / `change_request` / `complaint` / `lost_item` / `refund_request` / `info_request` |
| `subject` | STRING | 件名 |
| `body` | STRING | 内容 (匿名化済み) |
| `received_at` | TIMESTAMP | 受信時刻 |
| `resolved_at` | TIMESTAMP | クローズ時刻 (NULL=未解決) |
| `resolution_minutes` | INT | 解決所要分 |
| `csat` | INT | 1-5 (顧客満足度、NULL 可) |
| `assigned_team` | STRING | `cs_domestic` / `cs_outbound` / `cs_corp` |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 20,000 行。

---

### 10. `cancellation` (キャンセル詳細)

| カラム | 型 | 説明 |
|---|---|---|
| `cancellation_id` | STRING | PK |
| `booking_id` | STRING | FK → booking (1:1, booking_status=cancelled のみ) |
| `cancelled_at` | TIMESTAMP | キャンセル時刻 |
| `cancellation_reason` | STRING | `personal` / `weather` / `health` / `change_of_plan` / `price_dissatisfaction` / `force_majeure` / `airline_cancel` / `other` |
| `cancellation_lead_days` | INT | 出発の何日前にキャンセルしたか (負数=出発後) |
| `cancellation_fee_jpy` | DECIMAL(12,0) | キャンセル料 |
| `refund_amount_jpy` | DECIMAL(12,0) | 返金額 |
| `refund_status` | STRING | `pending` / `processed` / `denied` |
| `loaded_at` | TIMESTAMP | ETL ロード時刻 |

**規模**: 約 5,000 行 (booking 50,000 のうち約 10%)。

---

## 主要な集計指標 (semantic measures)

下記は Phase 9.4 で Fabric semantic model に measure として実装する候補:

| 指標 | 計算式 | 用途 |
|---|---|---|
| `total_revenue_jpy` | `SUM(booking.total_revenue_jpy WHERE status IN (confirmed,completed))` | 売上 |
| `gross_booking_count` | `COUNT(booking)` | 予約件数 |
| `net_booking_count` | `COUNT(booking WHERE status != cancelled)` | 確定予約件数 |
| `cancellation_rate` | `cancelled_count / gross_booking_count` | キャンセル率 |
| `avg_price_per_person_jpy` | `AVG(price_per_person_jpy)` | 平均単価 |
| `repeat_customer_rate` | `repeat_customers / unique_customers` | リピート率 |
| `avg_lead_time_days` | `AVG(lead_time_days)` | 平均リードタイム |
| `nps` | `pct(promoters) - pct(detractors)` | NPS |
| `csat_avg` | `AVG(inquiry.csat)` | 顧客満足度 |
| `outbound_revenue_share` | `outbound_revenue / total_revenue` | 海外比率 |
| `campaign_roi` | `(revenue_with_campaign - budget) / budget` | キャンペーン ROI |
| `inbound_revenue_share` | `inbound_revenue / total_revenue` | インバウンド比率 |

## 階層 (semantic hierarchies)

| 階層 | 構造 |
|---|---|
| `destination_geo` | `destination_country` -> `destination_region` -> `destination_city` |
| `customer_segment` | `customer_segment` -> `age_band` -> `loyalty_tier` |
| `time` | `year` -> `quarter` -> `month` -> `week` -> `date` |
| `season` | `season_group` (high/shoulder/low) -> `season_label` (spring/summer/...) |

## 分布シード方針 (Phase 9.2)

下記の公的統計から **集計分布** を seed として抽出する (個別行は使用しない、PII 不混入):

- 観光庁「主要旅行業者の旅行取扱状況」(月次): 国内・海外・外国人旅行の取扱額シェア、年同月比 → `total_revenue_jpy` の seasonality と yoy growth に反映
- e-Stat「宿泊旅行統計調査」: 都道府県別宿泊者数 → `destination_region` の頻度分布に反映
- 為替: 日銀「為替相場 月中平均」(USD/JPY, EUR/JPY) → `payment.exchange_rate_to_jpy` に反映

抽出した seed は `scripts/fabric_data_overhaul/seed_distributions.json` に固定する。  
本物のレコード行は使わない。これにより PII を避け、分布のみを保つ "hybrid seeded synthetic" になる。

## ロールバック戦略

- v2 がうまく動かなかった場合の rollback は env だけで完了する: `FABRIC_DATA_AGENT_RUNTIME_VERSION=v1`
- 既存の `travel_sales` / `travel_review` テーブルと `Travel_Ontology_DA` (v1) は不変
- v2 専用 lakehouse `lh_travel_marketing_v2` は workspace 内に独立しているため、削除も独立して可能
- semantic model / Knowledge / Data Agent も v2 専用名で作成し、v1 と名前衝突しない (`Travel_Ontology_DA_v2`)
