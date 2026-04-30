# Travel Marketing v2: Semantic Ontology 設計

## 設計目的

Phase 9.4 で構築する **新規 Fabric semantic model + Fabric IQ Knowledge** の concept / synonym /  hierarchy 定義の Source of Truth。

NL2Ontology が日本語マーケティング質問を v2 物理スキーマに翻訳する際の意味境界をここに定める。  
Phase 9.6 の SDK enrichment はこのドキュメントに沿って programmatic に同期する。

## ベースライン: 既存 travelIQ ontology の不足点

実機 9-prompt 検証 (`files/nl2ontology-condition-matrix.json`) と過去の trace 分析から、現状の `travelIQ` ontology が苦手なのは以下:

| カテゴリ | 苦手なクエリ | 理由仮説 |
|---|---|---|
| 季節 | `春のパリ` (内部の仕組み上エラー) | `春` -> `month IN (3,4,5)` のような展開が不安定 |
| 顧客タイプ | `20代の学生` | `Customer_Segment = student` と `Age_Band` の AND 合成が ontology 上未定義 |
| 為替影響 | `円安後の海外売上` | `payment.exchange_rate_to_jpy` を使う集計概念が無い |
| ROI / リピート | `リピート率上位` / `キャンペーンの ROI` | measure として未定義 |
| インバウンド | `インバウンド比率` | `destination_type` のディメンションが travelIQ には無い |

**v2 ontology はこれらをすべて concept として明示する**。

## Concepts (semantic 概念定義)

### 1. 期間概念

| Concept | 物理マッピング | Synonyms (日本語) | Synonyms (英語) |
|---|---|---|---|
| `Spring` | `MONTH(booking.departure_date) IN (3,4,5)` | `春`, `春先`, `春シーズン` | `spring` |
| `Summer` | `MONTH(booking.departure_date) IN (6,7,8)` | `夏`, `夏休み`, `夏季`, `サマー` | `summer` |
| `Autumn` | `MONTH(booking.departure_date) IN (9,10,11)` | `秋`, `紅葉`, `秋シーズン` | `autumn`, `fall` |
| `Winter` | `MONTH(booking.departure_date) IN (12,1,2)` | `冬`, `冬休み`, `ウィンター` | `winter` |
| `GoldenWeek` | `season = 'gw'` | `GW`, `ゴールデンウィーク`, `大型連休` | `golden week` |
| `Obon` | `season = 'obon'` | `お盆`, `お盆休み`, `盆休み` | `obon` |
| `NewYear` | `season = 'new_year'` | `年末年始`, `お正月`, `年末` | `new year holiday` |
| `Cherry` | `MONTH IN (3,4) AND ...` | `桜`, `お花見`, `桜シーズン` | `cherry blossom` |

### 2. 顧客セグメント

| Concept | 物理マッピング | Synonyms |
|---|---|---|
| `Family` | `customer_segment = 'family'` | `ファミリー`, `家族旅行`, `家族連れ` |
| `Couple` | `customer_segment = 'couple'` | `カップル`, `ご夫婦`, `2 人旅` |
| `Solo` | `customer_segment = 'solo'` | `一人旅`, `おひとり様`, `ソロ旅` |
| `Group` | `customer_segment = 'group'` | `グループ`, `団体`, `団体旅行` |
| `Senior` | `customer_segment = 'senior' OR age_band IN ('60s','70s+')` | `シニア`, `シニア層`, `年配` |
| `Student` | `customer_segment = 'student' OR (age_band IN ('10s','20s') AND ...)` | `学生`, `大学生`, `若者層` |
| `Business` | `customer_segment = 'business'` | `ビジネス`, `出張`, `企業旅行`, `法人` |

### 3. 年齢層

| Concept | 物理マッピング | Synonyms |
|---|---|---|
| `Age10s` | `age_band = '10s'` | `10代`, `ティーン` |
| `Age20s` | `age_band = '20s'` | `20代`, `若年層` |
| `Age30s` | `age_band = '30s'` | `30代` |
| `Age40s` | `age_band = '40s'` | `40代` |
| `Age50s` | `age_band = '50s'` | `50代` |
| `Age60s` | `age_band = '60s'` | `60代` |
| `Age70Plus` | `age_band = '70s+'` | `70代以上`, `高齢層` |

### 4. 目的地ディメンション

| Concept | 物理マッピング | Synonyms |
|---|---|---|
| `DomesticTrip` | `destination_type = 'domestic'` | `国内旅行`, `国内` |
| `OutboundTrip` | `destination_type = 'outbound'` | `海外旅行`, `海外`, `アウトバウンド` |
| `InboundTrip` | `destination_type = 'inbound'` | `インバウンド`, `訪日`, `外国人旅行` |
| `Hawaii` | `destination_region = 'ハワイ' OR destination_country = 'USA' AND city LIKE '%Honolulu%'` | `ハワイ`, `Hawaii`, `ホノルル` |
| `Okinawa` | `destination_region = '沖縄'` | `沖縄`, `おきなわ`, `Okinawa` |
| `Paris` | `destination_region = 'パリ' OR destination_city = 'Paris'` | `パリ`, `Paris`, `フランス首都` |
| `NewYork` | `destination_region = 'ニューヨーク' OR destination_city LIKE '%New York%'` | `ニューヨーク`, `NY`, `New York`, `マンハッタン` |
| ... (他主要 destination) |

### 5. 商品タイプ

| Concept | 物理マッピング | Synonyms |
|---|---|---|
| `DomesticPackage` | `product_type = 'domestic_package'` | `国内パッケージ`, `国内ツアー` |
| `OutboundPackage` | `product_type = 'outbound_package'` | `海外パッケージ`, `海外ツアー` |
| `FreePlan` | `product_type = 'freeplan'` | `フリープラン`, `自由旅行` |
| `Cruise` | `product_type = 'cruise'` | `クルーズ`, `船旅` |
| `FIT` | `product_type = 'fit'` | `FIT`, `個人手配` |

### 6. ステータス

| Concept | 物理マッピング | Synonyms |
|---|---|---|
| `Confirmed` | `booking_status IN ('confirmed','completed')` | `確定`, `成約` |
| `Cancelled` | `booking_status = 'cancelled'` | `キャンセル`, `取消` |
| `NoShow` | `booking_status = 'no_show'` | `ノーショー`, `当日キャンセル` |

## Measures (集計指標)

NL2Ontology が「合計売上」「リピート率」のような自然言語を直接マップできるよう、以下を semantic measure として登録する。

| Measure | DAX (semantic model 用) | Synonyms |
|---|---|---|
| `TotalRevenue` | `SUM(booking[total_revenue_jpy])` filter `Confirmed` | `売上`, `合計売上`, `総売上`, `revenue`, `gross sales` |
| `GrossBookingCount` | `COUNT(booking[booking_id])` | `予約件数`, `予約数`, `bookings` |
| `NetBookingCount` | `Confirmed` filter `COUNT` | `成約件数`, `確定予約数` |
| `CancellationRate` | `DIVIDE(CancelledCount, GrossBookingCount)` | `キャンセル率`, `cancel rate` |
| `AvgPricePerPerson` | `AVERAGE(booking[price_per_person_jpy])` | `平均単価`, `1人あたり単価`, `avg unit price` |
| `RepeatCustomerRate` | `DIVIDE(CountRepeatCustomer, CountUniqueCustomer)` | `リピート率`, `repeat rate` |
| `AvgLeadTimeDays` | `AVERAGE(booking[lead_time_days])` | `平均リードタイム`, `予約までの日数` |
| `NPS` | `(promoters - detractors) / total_responses * 100` | `NPS`, `ネット・プロモーター・スコア` |
| `OutboundRevenueShare` | `DIVIDE(OutboundRevenue, TotalRevenue)` | `海外比率`, `outbound share` |
| `InboundRevenueShare` | `DIVIDE(InboundRevenue, TotalRevenue)` | `インバウンド比率`, `inbound share` |
| `CampaignROI` | `DIVIDE(RevenueWithCampaign - TotalCampaignBudget, TotalCampaignBudget)` | `キャンペーン ROI`, `ROI`, `投資収益率` |
| `CSATAvg` | `AVERAGE(inquiry[csat])` | `CSAT`, `顧客満足度` |
| `RevenueExchangeAdjustedJPY` | `SUM(booking[total_revenue_jpy]) * AVG(payment[exchange_rate_to_jpy])` | `為替調整後売上`, `currency adjusted revenue` |

## Hierarchies (階層)

| Hierarchy | Levels |
|---|---|
| `DestinationGeo` | `destination_country` -> `destination_region` -> `destination_city` |
| `CustomerSegment` | `customer_segment` -> `age_band` |
| `LoyaltyTier` | `loyalty_tier` (none -> silver -> gold -> platinum) |
| `Time` | `year` -> `quarter` -> `month_name` -> `month` -> `date` |
| `Season` | `season_group` (high/shoulder/low) -> `season` (spring/summer/.../gw/obon/new_year) |
| `Product` | `product_type` -> `plan_name` |

## Relations (関連定義)

| Relation | From | To | 説明 |
|---|---|---|---|
| `customer_owns_bookings` | `customer.customer_id` | `booking.customer_id` | 1:N |
| `booking_has_payments` | `booking.booking_id` | `payment.booking_id` | 1:N |
| `booking_has_itinerary` | `booking.booking_id` | `itinerary_item.booking_id` | 1:N |
| `itinerary_at_hotel` | `itinerary_item.hotel_id` | `hotel.hotel_id` | N:1 |
| `itinerary_uses_flight` | `itinerary_item.flight_id` | `flight.flight_id` | N:1 |
| `booking_has_review` | `booking.booking_id` | `tour_review.booking_id` | 1:1 (optional) |
| `booking_in_campaign` | `booking.campaign_id` | `campaign.campaign_id` | N:1 (optional) |
| `customer_made_inquiry` | `customer.customer_id` | `inquiry.customer_id` | 1:N (optional) |
| `booking_has_cancellation` | `booking.booking_id` | `cancellation.booking_id` | 1:1 (cancelled のみ) |

## NL2Ontology テストケース (Phase 9.5 / 9.6 のスモーク)

### 既存 9-prompt (互換性確認)

新 ontology でもすべて成功する必要がある:
1. `ハワイの売上を教えてください` (single condition)
2. `夏のハワイの売上を教えてください` (season + region)
3. `ハワイで20代の旅行者の売上を教えてください` (region + age)
4. `夏のハワイで20代の旅行者の売上を教えてください` (season + region + age)
5. `夏のハワイで20代の旅行者の売上、予約数、平均評価を教えてください` (multi-metric)
6. `ハワイのレビュー評価分布を教えてください` (rating distribution)
7. `夏の沖縄でファミリー向けの売上を教えてください` (season + region + segment)
8. `春のパリの売上を教えてください` (Paris + spring 修正対象)
9. `旅行先別の売上ランキングを教えてください` (ranking)

### 新規 5-prompt (richer dataset の威力を見せる)

10. `年別の売上トレンドを教えてください` (Time hierarchy + TotalRevenue)
11. `リピート顧客の比率を教えてください` (RepeatCustomerRate)
12. `キャンセル率が高いプラン上位5位は？` (CancellationRate ranking by Plan)
13. `円安後の海外売上回復の度合いを教えてください` (Time + ExchangeRate + OutboundTrip)
14. `インバウンド比率の四半期推移を教えてください` (InboundRevenueShare + Quarter)

## Phase 9.6 SDK enrichment 候補リスト

Fabric IQ Knowledge の自動生成では入らない可能性が高い概念 (SDK で programmatic に追加):

| 優先度 | 追加対象 | 理由 |
|---|---|---|
| 高 | `Spring` / `Summer` / `Autumn` / `Winter` の synonym 拡張 | 自動生成は英単語のみカバーする可能性。日本語の異表記を網羅。 |
| 高 | `Hawaii` / `Okinawa` の城市表記揺れ (Honolulu / 那覇 / おきなわ) | NL2Ontology が漢字とカタカナの両方を扱える保証無し |
| 高 | `RepeatCustomerRate` measure | Auto-generation が repeat という概念を生成しない事が多い |
| 高 | `InboundRevenueShare` / `OutboundRevenueShare` | destination_type の dimension が autogen に含まれない可能性 |
| 中 | `Family` / `Couple` / `Senior` / `Student` の synonym 強化 | 顧客セグメントの日本語ペルソナ表現はカスタムが必要 |
| 中 | `Cancellation rate by plan` 用の cross-table relation | rare query path |
| 低 | `CampaignROI` measure | KPI の定義が会社ごとに揺れるため optional |

## ロールバック戦略

- 新 ontology / Knowledge / semantic model はすべて `*_v2` 接尾辞で命名
- 既存 `travelIQ` には変更を加えない
- v2 ontology が壊れた場合は v2 の semantic model / Knowledge / Data Agent ごと削除すれば v1 は不変のまま動作
