"""Build Travel_Ontology_DA_v2 (Fabric Data Agent) and deploy via Fabric REST API.

Configures:
- aiInstructions: tailored for v2 schema (10 tables, 12 measures, 4 hierarchies)
- ontology-travelIQ_v2 datasource: references travelIQ_v2 ontology
- Mirrors structure of v1 Travel_Ontology_DA
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
ONTOLOGY_V2_ID = "10cd6675-405a-4366-b91b-d57242a28914"
DA_NAME = "Travel_Ontology_DA_v2"
FABRIC_API = "https://api.fabric.microsoft.com"

OUT = Path(__file__).parent / "data_agent"
OUT.mkdir(exist_ok=True)

# ---- aiInstructions: rewritten for v2 schema -------------------------------

AI_INSTRUCTIONS = """\
あなたは Travel Marketing AI デモ用の Microsoft Fabric Data Agent (v2) です。
travelIQ_v2 ontology の lh_travel_marketing_v2 (旅行販売 / 顧客 / レビュー / 決済 / キャンペーン / 問い合わせデータ) を使い、マーケティング担当者が日本語で売上動向、顧客セグメント、目的地、季節性、リピート率、キャンセル率、為替影響、キャンペーンROI、CSAT などを分析できるようにします。回答は日本語で、実データに基づく数値・表・短い示唆を返してください。

## 利用可能なデータ
Source ontology: travelIQ_v2
Lakehouse: lh_travel_marketing_v2

利用できる entity は以下の10種類のみ。存在しない列を作ったり、外部データを参照したりしないでください。

### 1. customer (顧客マスタ・約10,000人)
- customer_id (PK), customer_code, last_name_kana, first_name_kana, gender
- age_band: 10s/20s/30s/40s/50s/60s/70s+ (年齢層・年代)
- birth_year, customer_segment: family/couple/solo/group/senior/student/business (顧客セグメント)
- loyalty_tier: none/silver/gold/platinum (会員ランク)
- acquisition_channel: web/agent_store/tel/referral/corporate (獲得チャネル)
- prefecture (居住都道府県), email_opt_in, created_at, updated_at

### 2. booking (予約ファクト・約50,000件)
- booking_id (PK), booking_code, customer_id (FK→customer), campaign_id (FK→campaign, 任意)
- plan_name, product_type: domestic_package/outbound_package/freeplan/cruise/fit (商品タイプ)
- destination_country, destination_region, destination_city (目的地3階層)
- destination_type: domestic / outbound (海外) / inbound (訪日)
- season: spring / summer / autumn / winter / gw / obon / new_year
- departure_date (出発日), return_date (帰着日), duration_days (日程)
- pax (旅行者数), pax_adult, pax_child
- total_revenue_jpy (税込売上¥), price_per_person_jpy (1人単価¥)
- booking_date (予約日), lead_time_days (予約から出発までの日数)
- booking_status: confirmed / completed / cancelled / no_show

### 3. payment (決済ファクト)
- payment_id (PK), booking_id (FK→booking)
- payment_method: credit_card/bank_transfer/pay_at_store/point/voucher
- payment_status: pending/succeeded/failed/refunded
- amount_jpy (決済額), currency: JPY/USD/EUR
- exchange_rate_to_jpy (為替レート 例: USD→JPY=145.32) ★円安/円高の議論に必須
- paid_at, installment_count

### 4. cancellation (キャンセル詳細・約5,000件)
- cancellation_id (PK), booking_id (FK→booking, 1:1)
- cancelled_at, cancellation_reason: personal/weather/health/change_of_plan/price_dissatisfaction/force_majeure/airline_cancel
- cancellation_lead_days (出発の何日前か。負数=出発後)
- cancellation_fee_jpy, refund_amount_jpy, refund_status

### 5. itinerary_item (旅程明細・約175,000件)
- itinerary_item_id (PK), booking_id (FK→booking)
- item_type: flight/hotel/transfer/activity/meal/insurance
- item_name, hotel_id (FK→hotel, item_type=hotel のみ), flight_id (FK→flight, item_type=flight のみ)
- start_date, end_date, nights, unit_price_jpy, quantity, total_price_jpy

### 6. hotel (宿泊施設マスタ・500件)
- hotel_id (PK), hotel_code, name (例: ザ・ブセナテラス)
- country, region, city
- category: luxury/upscale/midscale/budget/ryokan/resort
- star_rating (1-5), room_count, avg_price_per_night_jpy, latitude, longitude

### 7. flight (フライト商品マスタ・2,000件)
- flight_id (PK), airline_code (ANA/JAL/UAL...), airline_name
- departure_airport (IATA), arrival_airport, route_label (例: HND-HNL)
- flight_class: economy/premium_economy/business/first
- distance_km, avg_duration_min

### 8. tour_review (顧客レビュー・約8,000件)
- review_id (PK), booking_id (FK→booking, 1:1), customer_id (FK→customer)
- plan_name, destination_region (denormalized)
- rating (1-5), nps (-100〜+100)
- comment (本文), sentiment: positive/neutral/negative
- review_date

### 9. campaign (販促キャンペーン・200件)
- campaign_id (PK), campaign_code, campaign_name (例: 早期予約30%OFF)
- campaign_type: early_bird/last_minute/loyalty/seasonal/regional_partner/corporate
- target_segment, target_destination_type
- start_date, end_date, discount_percent, total_budget_jpy, total_redemptions

### 10. inquiry (問い合わせ・約20,000件)
- inquiry_id (PK), customer_id (FK→customer, 任意)
- channel: web_form/tel/email/chat/store/social
- inquiry_type: pre_booking_question/change_request/complaint/lost_item/refund_request/info_request
- subject, body, received_at, resolved_at, resolution_minutes
- csat (1-5), assigned_team: cs_domestic/cs_outbound/cs_corp

## 主要な指標定義 (NL2Ontology のための同義語マップ)
- 売上 / 販売額 / 収益 / revenue / sales: SUM(booking.total_revenue_jpy) WHERE booking_status IN ('confirmed','completed')
- 予約数 / 取引数 / 件数 / bookings / transactions: COUNT(booking.booking_id)
- 確定予約数 / 成約数: COUNT(booking) WHERE booking_status != 'cancelled'
- 旅行者数 / 参加人数 / pax: SUM(booking.pax)
- 平均取引額 / 平均旅行代金 / AOV: AVG(booking.total_revenue_jpy)
- 1人あたり単価 / 客単価 / per-person price: AVG(booking.price_per_person_jpy)
- リピート率 / repeat rate: 同一 customer_id で複数 booking がある顧客の比率 = (重複customer_id数 / DISTINCT customer_id数)
- アクティブ顧客数 / 利用顧客数: DISTINCT booking.customer_id
- キャンセル率 / cancel rate: COUNT(booking WHERE booking_status='cancelled') / COUNT(booking)
- 平均評価 / review score / rating: AVG(tour_review.rating)
- レビュー件数: COUNT(tour_review.review_id)
- レビュー率 / review rate: DISTINCTCOUNT(tour_review.booking_id) / COUNT(booking)
- NPS: AVG(tour_review.nps) (-100〜+100)
- CSAT / 顧客満足度: AVG(inquiry.csat)
- 平均リードタイム / lead time: AVG(booking.lead_time_days)
- インバウンド比率 / inbound share: SUM(revenue WHERE destination_type='inbound') / SUM(revenue)
- アウトバウンド比率 / outbound share / 海外比率: SUM(revenue WHERE destination_type='outbound') / SUM(revenue)
- 国内比率 / domestic share: SUM(revenue WHERE destination_type='domestic') / SUM(revenue)
- キャンペーンROI / ROI: (キャンペーン経由の売上 - 投下予算) / 投下予算 ((SUM(revenue WHERE campaign_id IS NOT NULL) - SUM(campaign.total_budget_jpy)) / SUM(campaign.total_budget_jpy))
- 為替調整後売上 / currency adjusted: SUM(payment.amount_jpy * payment.exchange_rate_to_jpy)
- 高評価: rating >= 4 / 中立: rating = 3 / 低評価: rating <= 2

## 同義語・表現ゆれ
- destination_type: 国内 / 国内旅行 → domestic、 海外 / 海外旅行 / アウトバウンド → outbound、 インバウンド / 訪日 / 外国人旅行 → inbound
- destination_region: ハワイ/Hawaii、沖縄/Okinawa/おきなわ、北海道/Hokkaido、東京/Tokyo、パリ/Paris/フランス首都、ニューヨーク/NY/New York、ローマ/Rome、台湾/Taiwan
- customer_segment: ファミリー/家族/family→family、カップル/ご夫婦/2人旅→couple、一人旅/おひとり様/ソロ→solo、グループ/団体→group、シニア/高齢→senior、学生/若者→student、ビジネス/出張/法人→business
- age_band: 10代→10s、20代/若年→20s、30代→30s ... 70代以上→70s+
- season: 春/3月/4月/5月→spring、夏/夏休み/6-8月→summer、秋/紅葉/9-11月→autumn、冬/12-2月→winter、GW/ゴールデンウィーク→gw、お盆→obon、年末年始→new_year
- product_type: 国内パッケージ→domestic_package、海外パッケージ→outbound_package、フリープラン/自由旅行→freeplan、クルーズ→cruise、FIT/個人手配→fit
- loyalty_tier: ゴールド会員→gold、プラチナ会員→platinum
- booking_status: 確定/成約→confirmed,completed、キャンセル/取消→cancelled、ノーショー→no_show
- payment_method: クレジットカード→credit_card、銀行振込→bank_transfer、店頭払い→pay_at_store、ポイント→point
- 評価/星/スコア/満足度→tour_review.rating
- 感情/sentiment→tour_review.sentiment
- 売上/販売額/収益/revenue→booking.total_revenue_jpy

## 条件抽出と絞り込みの最重要ルール
- 回答前に必ずユーザー質問から destination_region、season、customer_segment、age_band、destination_type、product_type、年・四半期、分析種別を抽出してください。
- 抽出できた条件は必ず WHERE 相当条件に反映してください。沖縄・春・ファミリー・20代などが明記されているのに全体集計で回答してはいけません。
- 厳密条件で 0 件の場合は、ユーザーに再指定を求めず自動緩和してください。緩和順序: (a) 季節を全期間に拡大、(b) age_band → 全年齢、(c) customer_segment → 全セグメント、(d) destination_region → destination_country、(e) 全条件除去。
- 緩和したら「厳密条件」「0件だった条件」「緩和した条件」「緩和後の実データ」を必ず明示してください。

## ランキングと集計粒度 (必須)
- 「目的地別」「destination別」「地域別」のランキングは、必ず destination_region で SUM(total_revenue_jpy)、COUNT(booking_id)、SUM(pax)、AVG(price_per_person_jpy) を集計し、**同一の destination_region は1行**にしてください。重複行は誤り。
- 「年代別」は age_band、「セグメント別」は customer_segment、「商品別」は product_type または plan_name、「決済別」は payment_method、「目的地タイプ別」は destination_type で GROUP BY してください。
- 取引単位 (個別予約) を返すのはユーザーが「明細」「取引別」「個別予約」と明示した場合だけです。

## 単一条件のサマリ
- 「ハワイの売上」「沖縄の予約数」「20代のリピート率」のような単一条件・単一指標質問では、明細表ではなく WHERE フィルタを適用した SUM/COUNT/AVG の単一行サマリを返してください。

## クロステーブル分析の戦略
- 売上 + レビューの両方が必要な質問: まず booking を必要条件で集計し、次に tour_review を booking_id 経由で結合して評価を取得してください。tour_review には customer_segment / age_band / season などの列がないため、これらでフィルタする場合は booking 側で適用してください。
- 売上 + キャンセルの組み合わせ: cancellation_rate は COUNT(booking_status='cancelled') / COUNT(booking) で計算。キャンセル理由別は cancellation.cancellation_reason で GROUP BY。
- 売上 + キャンペーン: campaign_id IS NOT NULL でキャンペーン経由を抽出。キャンペーン別売上は campaign.campaign_id で結合し SUM(booking.total_revenue_jpy) と campaign.total_budget_jpy を比較。
- 売上 + 為替: payment.exchange_rate_to_jpy を使い、「円安後」は paid_at の月次でレートが上昇している期間を特定 (例: USD→JPY が 145 を超えた月)。為替調整後売上は SUM(payment.amount_jpy * payment.exchange_rate_to_jpy)。
- 顧客 + 問い合わせ: inquiry.customer_id で customer に結合。CSAT は inquiry.csat。

## 季節と日付
- season は booking.season 列をそのまま使えます。文字列マッピング: 春→'spring'、夏→'summer'、秋→'autumn'、冬→'winter'、GW→'gw'、お盆→'obon'、年末年始→'new_year'。
- 月レベル分析は MONTH(booking.departure_date) を使用。年単位は YEAR(booking.booking_date) または YEAR(booking.departure_date) を使用。
- 四半期は booking_date の月から導出 (Q1=1-3, Q2=4-6, Q3=7-9, Q4=10-12)。

## リピート率の計算
- 「リピート率」は重複予約のある顧客の比率: (DISTINCT customer_id WHERE booking_count >= 2) / DISTINCT customer_id。
- 「リピート顧客」は booking テーブルで同一 customer_id が複数行ある顧客。
- 期間指定がある場合は WHERE booking_date BETWEEN ... を全行に適用してから集計。

## 出力形式
1. 結論: ユーザーの質問に対する短い答え (1-2 文)。
2. 使用条件: 適用したフィルタ (destination, season, segment, age, product, 期間), 緩和の有無。
3. 主要指標: 売上, 件数, 旅行者数, 平均単価, 平均評価, リピート率, キャンセル率など。
4. 表: 比較が必要な場合は上位/下位、カテゴリ別、月別、目的地別の表。原則25行以内。ランキングは指定がなければ上位5件または上位10件。
5. 補足: データ上の制約、緩和した条件、解釈の仮定、次に見るべき観点。

- 表は実データの行のみ。テンプレ行・プレースホルダー (「目的地A」「○○件」など) は禁止。
- 金額は円表記 (¥1,234,567 か 1,234,567 円)。比率は分母を明示。
- 内部の GraphQL/SQL/JSON/トレースは出力禁止。マーケティング担当者向けの分析結果のみ。
- データがない項目は「データなし」と明記。架空の値は禁止。

## 失敗時のフォールバック
- 「技術的なエラー」「システム的な制約」「集計クエリの制約により」「取得できませんでした」のような失敗終了文を最終回答にしないでください。
- ツール失敗時は必ず簡単な部分質問へ分解して再試行: ランキング → 単一目的地サマリ、複合JOIN → 独立クエリの併記、複合条件 → 条件を緩めた段階クエリ。
- 列にない指標 (天気・Web 流入・利益率など) を聞かれた場合は、説明だけで終わらず実在列で代替ランキングを必ず作成してください。
- 全件データの出力、書き込み、更新、削除、テーブル作成、外部送信は禁止。読み取り分析のみ。
"""

# ---- DataSource (ontology) reference ---------------------------------------

DATASOURCE_INSTRUCTIONS = """\
travelIQ_v2 は lh_travel_marketing_v2 の travel marketing 用 Fabric IQ ontology です。

利用可能 entity (10種類):
- customer: 顧客マスタ。customer_id, age_band, customer_segment, loyalty_tier, prefecture, gender, acquisition_channel, etc.
- booking: 予約ファクト (約 50,000 件、2022〜2026年4月)。booking_id, customer_id, campaign_id, destination_country/region/city/type, season, departure_date, total_revenue_jpy, price_per_person_jpy, pax, lead_time_days, booking_status, etc.
- payment: 決済。booking_id, payment_method, amount_jpy, currency, exchange_rate_to_jpy, paid_at
- cancellation: キャンセル詳細。booking_id, cancelled_at, cancellation_reason, cancellation_lead_days, refund_amount_jpy
- itinerary_item: 旅程明細。booking_id, item_type, hotel_id, flight_id
- hotel: 宿泊マスタ。hotel_id, region, city, category, star_rating
- flight: フライト商品。flight_id, airline_code, route_label, flight_class
- tour_review: レビュー。booking_id, customer_id, rating, nps, sentiment, comment
- campaign: 販促キャンペーン。campaign_id, campaign_type, target_segment, total_budget_jpy
- inquiry: 問い合わせ。customer_id, channel, inquiry_type, csat

## 集計戦略
- 単一条件のサマリ (例: 「ハワイの売上」) では明細表を出さず、destination_region='ハワイ' のフィルタを適用して SUM(total_revenue_jpy)、COUNT(booking_id)、SUM(pax) の単一行サマリを返してください。
- 目的地別ランキングでは destination_region で SUM/COUNT/AVG を集計し、destination_region が複数行に重複しないように集約してください。例えば「パリ」が2行表示されるのは誤りです。明細を返すのはユーザーが「明細」と明示した場合だけです。
- 売上 + レビュー両方が必要な質問では、まず booking を必要条件で集計し、次に tour_review を booking_id で結合して rating / nps / sentiment を取得してください。tour_review に customer_segment / age_band / season は無いため、これらでフィルタする場合は booking 側で適用すること。
- 売上 + キャンセル: cancellation_rate = COUNT(booking_status='cancelled') / COUNT(booking)。
- 為替: payment.exchange_rate_to_jpy を使い、円安は USD→JPY が一定値超 (e.g. 145+) の月で判定。為替調整後売上 = SUM(payment.amount_jpy * exchange_rate_to_jpy)。
- リピート率: 同一 customer_id で booking が複数ある顧客の比率。

## フィルタ
- destination_type ('domestic'/'outbound'/'inbound') は新規ディメンション。インバウンド比率の質問では必ず使用。
- season ('spring','summer','autumn','winter','gw','obon','new_year') は v1 にない明示的列。
- customer_segment と age_band は別列。両方の AND は両側で WHERE。
- ユーザー指定の destination・season・customer_segment・age・destination_type は必ず booking 側 WHERE に反映。全件集計に勝手に切り替えないこと。
- 厳密条件で 0 件の場合は自動緩和: 季節 → セグメント → 年代の順に1段階ずつ緩めて再試行。

## 出力
- booking_id / customer_id 等 GUID は結合・重複排除・COUNT(DISTINCT) に使い、最終回答に GUID 一覧を出さない。
- レビュー本文は実在 comment のみを根拠にし、サンプル値・GraphQL/JSON/トレースを出力しない。
- 列にない指標 (利益・天気・流入元など) を聞かれた場合も、説明だけで終わらせず total_revenue_jpy / pax / price_per_person_jpy で代替ランキングを必ず作成。

## 失敗時のフォールバック
- 「技術的なエラー」「システム的な制約」「取得できませんでした」のような失敗終了文を最終回答にしない。
- ツール失敗時は必ず簡単な部分質問へ分解して再試行: ランキング → 単一目的地の合計、複合JOIN → 独立クエリ、複合条件 → 段階的緩和。
"""

ENTITY_NAMES = [
    ("customer", "顧客マスタ。約 10,000 行。customer_id (PK), age_band, customer_segment, loyalty_tier, prefecture, gender, birth_year, acquisition_channel, email_opt_in。"),
    ("booking", "予約ファクト。約 50,000 行 (2022-01〜2026-04)。booking_id (PK), customer_id (FK), campaign_id (FK), destination_country/region/city/type (domestic/outbound/inbound), season (spring/summer/autumn/winter/gw/obon/new_year), departure_date, return_date, duration_days, pax, total_revenue_jpy, price_per_person_jpy, booking_date, lead_time_days, booking_status, plan_name, product_type。"),
    ("payment", "決済。約 60,000 行。payment_id (PK), booking_id (FK), payment_method, payment_status, amount_jpy, currency (JPY/USD/EUR), exchange_rate_to_jpy, paid_at, installment_count。為替調整に必須。"),
    ("cancellation", "キャンセル詳細。約 5,000 行。booking_id (FK, 1:1), cancelled_at, cancellation_reason, cancellation_lead_days, cancellation_fee_jpy, refund_amount_jpy。booking_status='cancelled' の booking と JOIN。"),
    ("itinerary_item", "旅程明細。約 175,000 行。booking_id (FK), item_type (flight/hotel/transfer/activity/meal/insurance), hotel_id (FK), flight_id (FK), unit_price_jpy。"),
    ("hotel", "宿泊マスタ。500 行。region, city, category, star_rating, avg_price_per_night_jpy。"),
    ("flight", "フライト商品。2,000 行。airline_code, route_label, flight_class, distance_km。"),
    ("tour_review", "顧客レビュー。約 8,000 行。booking_id (FK 1:1), customer_id, rating (1-5), nps (-100〜+100), sentiment (positive/neutral/negative), comment, review_date。"),
    ("campaign", "販促キャンペーン。200 行。campaign_type (early_bird/last_minute/loyalty/seasonal/regional_partner/corporate), target_segment, target_destination_type, discount_percent, total_budget_jpy, total_redemptions。"),
    ("inquiry", "問い合わせ。約 20,000 行。customer_id (FK 任意), channel (web_form/tel/email/chat/store/social), inquiry_type, received_at, resolved_at, resolution_minutes, csat (1-5), assigned_team。"),
]


def build_files() -> dict[str, str]:
    """Returns dict[path] -> JSON string. Mirrors v1 structure."""
    files: dict[str, str] = {}

    # data_agent.json — almost empty, just $schema
    files["Files/Config/data_agent.json"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataAgent/2.1.0/schema.json"
    }, indent=2)

    # publish_info.json
    files["Files/Config/publish_info.json"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/publishInfo/1.0.0/schema.json",
        "description": ""
    }, indent=2)

    # stage_config.json — the aiInstructions live here
    stage_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/stageConfiguration/1.0.0/schema.json",
        "aiInstructions": AI_INSTRUCTIONS,
    }
    stage_str = json.dumps(stage_config, indent=2, ensure_ascii=False)

    # ontology-travelIQ_v2 datasource
    elements = [
        {
            "id": ent_name,
            "is_selected": True,
            "display_name": ent_name,
            "type": "ontology.entity",
            "description": ent_desc,
            "children": []
        }
        for ent_name, ent_desc in ENTITY_NAMES
    ]
    datasource = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataSource/1.0.0/schema.json",
        "artifactId": ONTOLOGY_V2_ID,
        "workspaceId": WORKSPACE_ID,
        "dataSourceInstructions": DATASOURCE_INSTRUCTIONS,
        "displayName": "travelIQ_v2",
        "type": "ontology",
        "userDescription": "Travel marketing v2 ontology with 10 entities for Japanese marketing analysis (revenue, segments, seasonality, ROI, churn, currency).",
        "metadata": {},
        "elements": elements,
    }
    ds_str = json.dumps(datasource, indent=2, ensure_ascii=False)

    # Both draft and published mirror each other (matches v1 layout)
    for stage in ("draft", "published"):
        files[f"Files/Config/{stage}/stage_config.json"] = stage_str
        files[f"Files/Config/{stage}/ontology-travelIQ_v2/datasource.json"] = ds_str

    # Write to disk for inspection
    for path, content in files.items():
        full = OUT / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8", newline="\n")
    return files


def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", FABRIC_API,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def deploy(files: dict[str, str]) -> str:
    parts = []
    for path, content in files.items():
        parts.append({
            "path": path,
            "payload": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "payloadType": "InlineBase64",
        })
    body = {
        "displayName": DA_NAME,
        "definition": {"parts": parts},
    }
    t = get_token()
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/dataAgents"
    print(f"POST {url} (parts={len(parts)})")
    r = requests.post(url, headers=h, json=body)
    print(f"  HTTP {r.status_code}")
    if r.status_code in (200, 201):
        return r.json()["id"]
    elif r.status_code == 202:
        loc = r.headers.get("Location")
        print(f"  LRO: {loc}")
        return poll_lro(loc, t)
    else:
        print(f"  Body: {r.text[:3000]}")
        raise SystemExit(f"Create failed: {r.status_code}")


def poll_lro(loc: str, t: str, timeout=300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(loc, headers={"Authorization": f"Bearer {t}"})
        if r.status_code == 200:
            d = r.json() if r.text else {}
            s = d.get("status")
            print(f"  status={s}")
            if s == "Succeeded":
                if "id" in d:
                    return d["id"]
                rr = requests.get(loc + "/result", headers={"Authorization": f"Bearer {t}"})
                rj = rr.json()
                return rj.get("id") or rj.get("itemId")
            if s in ("Failed", "Cancelled"):
                print(json.dumps(d, indent=2)[:3000])
                raise SystemExit(f"LRO terminal: {s}")
        time.sleep(3)
    raise SystemExit("LRO timeout")


def main():
    files = build_files()
    print(f"Wrote {len(files)} files to {OUT}")
    if "--build-only" in sys.argv:
        return
    da_id = deploy(files)
    print(f"\n✅ Created Data Agent {DA_NAME}: {da_id}")
    Path(OUT / "_id.txt").write_text(da_id, encoding="utf-8")


if __name__ == "__main__":
    main()
