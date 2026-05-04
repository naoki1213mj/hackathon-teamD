<!-- Phase 11d source — see session-state/.../fabric-da-instructions-improved-draft.md for rationale -->

`travelIQ_v2` は `lh_travel_marketing_v2` (Fabric Lakehouse, dbo schema) を裏付けにした旅行マーケティング用 Fabric IQ ontology。**KPI 集計・期間推移・ランキング・関係横断 (顧客 → 予約 → レビュー → 決済 → キャンペーン) のセマンティック推論** に最適化。データ期間は 2022 年〜 2026 年 4 月 (2026 は 1〜4 月のみの部分年)。

10 entities:
- `customer` 顧客マスタ (約 10,000 行) / `booking` 予約ファクト (約 50,000 行) / `payment` 決済 (約 60,000 行) / `cancellation` キャンセル (約 5,000 行) / `itinerary_item` 旅程明細 (約 175,000 行) / `hotel` 宿泊 (500 行) / `flight` 航空便 (2,000 行) / `tour_review` レビュー (約 8,000 行) / `campaign` 販促 (200 行) / `inquiry` 問い合わせ (約 20,000 行)

主要リレーション: `customer → booking`, `booking → payment` / `cancellation` (1:1) / `itinerary_item` / `tour_review` (1:1), `booking → campaign` (任意), `itinerary_item → hotel` / `flight`, `customer → inquiry` (任意)。各 entity には `displayNamePropertyId` (`booking.plan_name`, `customer.customer_code`, `campaign.campaign_name` など) が設定済で、PK の UUID ではなく人間可読列が表示用デフォルトになる。

詳細な値マッピング・KPI 計算ルール・失敗復旧テンプレ・GQL ヒントは **Agent Instructions** に集約 (本欄では繰り返さない)。集計・ランキング・期間 KPI・関係横断はすべて本データソースに routing する。個票照会 / 最新 N 件 / 存在確認だけは `lh_travel_marketing_v2` lakehouse 経由を使う。
