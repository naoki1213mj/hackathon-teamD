<!-- Phase 11d source — see session-state/.../fabric-da-instructions-improved-draft.md for rationale -->

`lh_travel_marketing_v2` は dbo schema 配下に Delta テーブルとして保持された旅行マーケティング運用データソース。Fabric SQL endpoint 経由で T-SQL クエリ可能。**個票照会 (指定 ID / コードのレコード取得) / 最新 N 件のヘッドライン / `SELECT COUNT(*)` の存在確認** に限定して使う。KPI 集計・ランキング・期間集計は同じテーブル群を参照する `travelIQ_v2` ontology を使う (こちらにビジネス制約と関係定義が入っている)。

主要テーブル (10 件、すべて dbo schema):
- `booking`: 予約ファクト (約 50,000 行、2022-01〜2026-04)。`booking_id` (PK, UUID), `booking_code` (人間可読: `BK-2026-000123` 形式)
- `customer`: 顧客マスタ (約 10,000 行)。`customer_id` (UUID), `customer_code` (`C-2025-000456` 形式)
- `payment`: 決済 (約 60,000 行)。`payment_id` (UUID), `booking_id` (FK)
- `cancellation`: キャンセル詳細 (約 5,000 行)。`booking_id` (FK 1:1)
- `itinerary_item`: 旅程明細 (約 175,000 行)。`booking_id` (FK)
- `tour_review`: ツアーレビュー (約 8,000 行)。`review_id` (UUID), `booking_id` (FK 1:1)
- `campaign`: 販促キャンペーン (200 行)。`campaign_id` (UUID), `campaign_code` (`CMP-2026-Q1-007` 形式)
- `inquiry`: 問い合わせ (約 20,000 行)
- `hotel`: 宿泊マスタ (500 行) / `flight`: 航空便商品 (2,000 行)

命名規約:
- `*_id` は UUID (機械的キー、回答に出さない)
- `*_code` は人間可読コード (回答可)
- `*_jpy` は円・税込整数 (例: `total_revenue_jpy`)
- `*_status` は英語コード (例: `payment_status` は `succeeded` / `refunded` のみ)
- 目的地は 3 階層: `destination_country` (英語: `Japan` / `USA` …) / `destination_region` (日本語: `沖縄` / `北海道` / `京都` / `ハワイ` …) / `destination_city` (国内は日本語: `那覇` `札幌`、海外は英語: `Honolulu` `Paris`)。**`沖縄` `北海道` `ハワイ` は region であって city ではない。**
