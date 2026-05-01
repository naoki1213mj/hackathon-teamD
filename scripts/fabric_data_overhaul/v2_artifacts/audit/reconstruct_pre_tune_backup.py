"""pre-tune の Travel_Ontology_DA_v2 definition を復元する補助スクリプト。

監査時に取得した audit/current_aiinstructions.txt (元の aiInstructions テキスト) と、
本ファイルにベタ書きした OLD_DS_INSTRUCTIONS (元の dataSourceInstructions テキスト)
を使って、現在の (post-tune) full definition から pre-tune バックアップを再構成する。

この再構成スクリプトは、もし backup を上書きしてしまった事故時のリカバリ用。
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ARTIFACT_DIR = Path(__file__).parent.parent
RAW_PATH = ARTIFACT_DIR / "audit" / "agent_definition_v2_full.json"   # 現在 (post-tune)
BACKUP_PATH = ARTIFACT_DIR / "backups" / "agent_definition_pre_tune.json"
OLD_AI_TXT_PATH = ARTIFACT_DIR / "audit" / "current_aiinstructions.txt"

# 監査時の console dump から復元した元 dataSourceInstructions
OLD_DS_INSTRUCTIONS = """travelIQ_v2 は lh_travel_marketing_v2 の travel marketing 用 Fabric IQ ontology です。

利用可能 entity (10 種類):
- customer: 顧客マスタ (customer_id, age_band, customer_segment, loyalty_tier, prefecture, gender, acquisition_channel)
- booking: 予約ファクト (約 50,000 件、2022〜2026/4)。booking_id, customer_id, campaign_id, destination_country/region/city/type, season, departure_date, total_revenue_jpy, price_per_person_jpy, pax, lead_time_days, booking_status
- payment: 決済 (payment_id, booking_id, payment_method, amount_jpy, currency, exchange_rate_to_jpy, paid_at)
- cancellation: キャンセル詳細 (booking_id, cancelled_at, cancellation_reason, cancellation_lead_days, refund_amount_jpy)
- itinerary_item: 旅程明細 (booking_id, item_type, hotel_id, flight_id)
- hotel: 宿泊マスタ (region, city, category, star_rating)
- flight: フライト商品 (airline_code, route_label, flight_class)
- tour_review: レビュー (booking_id, customer_id, rating, nps, sentiment, comment)
- campaign: 販促キャンペーン (campaign_id, campaign_type, target_segment, total_budget_jpy)
- inquiry: 問い合わせ (customer_id, channel, inquiry_type, csat)

## 値マッピング (CRITICAL)
- destination_region は **日本語** (ハワイ / 沖縄 / 北海道 / パリ / ニューヨーク 等)。
  「Hawaii」は `destination_region='ハワイ'` で検索。`destination_country='Hawaii'` は存在しない。
- destination_country は **英語** (Japan / USA / South Korea / France / 等)。
- destination_type は domestic / outbound / inbound (英語コード)。
- season は spring / summer / autumn / winter / gw / obon / new_year (英語コード)。
- age_band は 10s / 20s / 30s / 40s / 50s / 60s / 70s+。
- customer_segment は family / couple / solo / group / senior / student / business。
- booking_status は confirmed / completed / cancelled / no_show。

## 集計戦略
- 単一条件サマリ (「ハワイの売上」) は明細表でなく `destination_region='ハワイ'` の SUM/COUNT/AVG 一行。
- 目的地別ランキングは destination_region で集約し重複行禁止。
- 売上 + レビューは booking で先に絞り、tour_review を booking_id で結合。
- cancellation_rate は `COUNT(WHERE booking_status='cancelled') / COUNT(*)` を使い、HAVING COUNT(*) >= 30 で疎データを除外。
- 為替: payment.exchange_rate_to_jpy で USD/EUR の年次レート上昇を確認。
- リピート率: `customer_id ごとの予約数 >=2` の比率。SM 計算メジャーが見えなくても SQL で必ず計算可能。

## 0 件の前に DISTINCT 確認
WHERE 句で 0 件が返った場合は、必ず `SELECT DISTINCT <column>` で値一覧を確認し、ユーザーの語との一致 (LIKE / 編集距離) を試してから再クエリする。「データなし」「ツール側制限」を回答する前に必ず実施。

## 自動緩和
複数条件で 0 件のときは自動緩和: season → age_band → customer_segment → region→country。緩和したら明示する。

## 失敗時のフォールバック
- 「技術的なエラー」「システム的な制約」「取得できませんでした」「ツール側制限」「SM計算列が見えない」を最終回答にしないこと。
- 複合 JOIN が失敗したら単一テーブルクエリに分解 (booking → review → cancellation を独立に取得し並列表示)。
- 列にない指標 (利益・天気・流入元) は説明だけで終わらず total_revenue_jpy / pax / price_per_person_jpy / rating で代替ランキングを作成。
"""


def main() -> int:
    # 元 aiInstructions テキストを current_aiinstructions.txt から復元
    raw_lines = OLD_AI_TXT_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    # 1 行目に "--- aiInstructions length: 19172" が入っているので捨てる
    if raw_lines and raw_lines[0].startswith("--- aiInstructions length"):
        raw_lines = raw_lines[1:]
    old_ai = "".join(raw_lines)
    # ファイル末尾の改行は trim しない (元テキストに合わせる)
    print(f"old aiInstructions length: {len(old_ai)}")

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    new_parts: list[dict] = []
    for part in raw.get("definition", {}).get("parts", []):
        path = part.get("path") or ""
        payload_b64 = part["payload"]
        payload_text = base64.b64decode(payload_b64).decode("utf-8")
        if path.endswith("stage_config.json"):
            obj = json.loads(payload_text)
            obj["aiInstructions"] = old_ai
            payload_text = json.dumps(obj, ensure_ascii=False)
        elif path.endswith("ontology-travelIQ_v2/datasource.json"):
            obj = json.loads(payload_text)
            obj["dataSourceInstructions"] = OLD_DS_INSTRUCTIONS
            payload_text = json.dumps(obj, ensure_ascii=False)
        new_payload = base64.b64encode(payload_text.encode("utf-8")).decode("ascii")
        new_parts.append({
            "path": path,
            "payload": new_payload,
            "payloadType": part.get("payloadType", "InlineBase64"),
        })
    body = {"definition": {"parts": new_parts}}
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_PATH.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"reconstructed pre-tune backup -> {BACKUP_PATH}")
    print("注意: backups/agent_definition_pre_tune.json は監査時の現状から再構成された pre-tune スナップショット")
    return 0


if __name__ == "__main__":
    sys.exit(main())
