"""travelIQ_v2 が参照する Lakehouse v2 のデータ実態を監査する。

- booking / tour_review を中心に、各カラムの DISTINCT 件数・上位値・カバレッジを抽出する。
- season / customer_segment / age_band / destination 系 / total_revenue_jpy 帯域の分布を計測する。
- 結果は dataset_v2_audit_raw.json に書き出し、Markdown レポートはレビュー側で別途生成する。
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import pyodbc

ENDPOINT = "pabkxzbptdhuzf2qxkx52ftsp4-fl3w6clumg5evdymcqcfj6tmh4.datawarehouse.fabric.microsoft.com"
DATABASE = "lh_travel_marketing_v2"
SQL_COPT_SS_ACCESS_TOKEN = 1256

TABLE_ROWCOUNT_QUERIES: list[tuple[str, str]] = [
    ("rowcount", """
        SELECT 'customer' AS tbl, COUNT(*) AS row_count FROM dbo.customer
        UNION ALL SELECT 'booking', COUNT(*) FROM dbo.booking
        UNION ALL SELECT 'payment', COUNT(*) FROM dbo.payment
        UNION ALL SELECT 'cancellation', COUNT(*) FROM dbo.cancellation
        UNION ALL SELECT 'itinerary_item', COUNT(*) FROM dbo.itinerary_item
        UNION ALL SELECT 'hotel', COUNT(*) FROM dbo.hotel
        UNION ALL SELECT 'flight', COUNT(*) FROM dbo.flight
        UNION ALL SELECT 'tour_review', COUNT(*) FROM dbo.tour_review
        UNION ALL SELECT 'campaign', COUNT(*) FROM dbo.campaign
        UNION ALL SELECT 'inquiry', COUNT(*) FROM dbo.inquiry
        ORDER BY tbl
    """),
]

# ontology が参照する全カラムについて DISTINCT 値カウントを取得
COLUMN_QUERIES: list[tuple[str, str]] = [
    ("booking.season", "SELECT season AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY season ORDER BY cnt DESC"),
    ("booking.destination_region",
     "SELECT destination_region AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY destination_region ORDER BY cnt DESC"),
    ("booking.destination_country",
     "SELECT destination_country AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY destination_country ORDER BY cnt DESC"),
    ("booking.destination_city",
     "SELECT destination_city AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY destination_city ORDER BY cnt DESC"),
    ("booking.destination_type",
     "SELECT destination_type AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY destination_type ORDER BY cnt DESC"),
    ("booking.product_type",
     "SELECT product_type AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY product_type ORDER BY cnt DESC"),
    ("booking.booking_status",
     "SELECT booking_status AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY booking_status ORDER BY cnt DESC"),
    ("booking.plan_name_top30",
     "SELECT TOP 30 plan_name AS v, COUNT(*) AS cnt FROM dbo.booking GROUP BY plan_name ORDER BY cnt DESC"),
    ("customer.customer_segment",
     "SELECT customer_segment AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY customer_segment ORDER BY cnt DESC"),
    ("customer.age_band",
     "SELECT age_band AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY age_band ORDER BY cnt DESC"),
    ("customer.loyalty_tier",
     "SELECT loyalty_tier AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY loyalty_tier ORDER BY cnt DESC"),
    ("customer.acquisition_channel",
     "SELECT acquisition_channel AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY acquisition_channel ORDER BY cnt DESC"),
    ("customer.gender",
     "SELECT gender AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY gender ORDER BY cnt DESC"),
    ("customer.prefecture_top25",
     "SELECT TOP 25 prefecture AS v, COUNT(*) AS cnt FROM dbo.customer GROUP BY prefecture ORDER BY cnt DESC"),
    ("payment.payment_method",
     "SELECT payment_method AS v, COUNT(*) AS cnt FROM dbo.payment GROUP BY payment_method ORDER BY cnt DESC"),
    ("payment.payment_status",
     "SELECT payment_status AS v, COUNT(*) AS cnt FROM dbo.payment GROUP BY payment_status ORDER BY cnt DESC"),
    ("payment.currency",
     "SELECT currency AS v, COUNT(*) AS cnt FROM dbo.payment GROUP BY currency ORDER BY cnt DESC"),
    ("cancellation.cancellation_reason",
     "SELECT cancellation_reason AS v, COUNT(*) AS cnt FROM dbo.cancellation GROUP BY cancellation_reason ORDER BY cnt DESC"),
    ("cancellation.refund_status",
     "SELECT refund_status AS v, COUNT(*) AS cnt FROM dbo.cancellation GROUP BY refund_status ORDER BY cnt DESC"),
    ("itinerary_item.item_type",
     "SELECT item_type AS v, COUNT(*) AS cnt FROM dbo.itinerary_item GROUP BY item_type ORDER BY cnt DESC"),
    ("hotel.category",
     "SELECT category AS v, COUNT(*) AS cnt FROM dbo.hotel GROUP BY category ORDER BY cnt DESC"),
    ("flight.flight_class",
     "SELECT flight_class AS v, COUNT(*) AS cnt FROM dbo.flight GROUP BY flight_class ORDER BY cnt DESC"),
    ("flight.airline_top15",
     "SELECT TOP 15 airline_code AS v, COUNT(*) AS cnt FROM dbo.flight GROUP BY airline_code ORDER BY cnt DESC"),
    ("tour_review.sentiment",
     "SELECT sentiment AS v, COUNT(*) AS cnt FROM dbo.tour_review GROUP BY sentiment ORDER BY cnt DESC"),
    ("tour_review.rating",
     "SELECT rating AS v, COUNT(*) AS cnt FROM dbo.tour_review GROUP BY rating ORDER BY cnt DESC"),
    ("tour_review.destination_region",
     "SELECT destination_region AS v, COUNT(*) AS cnt FROM dbo.tour_review GROUP BY destination_region ORDER BY cnt DESC"),
    ("campaign.campaign_type",
     "SELECT campaign_type AS v, COUNT(*) AS cnt FROM dbo.campaign GROUP BY campaign_type ORDER BY cnt DESC"),
    ("campaign.target_segment",
     "SELECT target_segment AS v, COUNT(*) AS cnt FROM dbo.campaign GROUP BY target_segment ORDER BY cnt DESC"),
    ("inquiry.channel",
     "SELECT channel AS v, COUNT(*) AS cnt FROM dbo.inquiry GROUP BY channel ORDER BY cnt DESC"),
    ("inquiry.inquiry_type",
     "SELECT inquiry_type AS v, COUNT(*) AS cnt FROM dbo.inquiry GROUP BY inquiry_type ORDER BY cnt DESC"),
]

CROSS_QUERIES: list[tuple[str, str]] = [
    # season × destination_type 売上クロス
    ("season_x_destination_type_revenue", """
        SELECT season, destination_type,
               COUNT(*) AS bookings,
               SUM(total_revenue_jpy) AS revenue_jpy
        FROM dbo.booking
        WHERE booking_status IN ('confirmed','completed')
        GROUP BY season, destination_type
        ORDER BY season, destination_type
    """),
    # destination_region 別売上 (TOP15)
    ("destination_region_revenue_top15", """
        SELECT TOP 15 destination_region,
               COUNT(*) AS bookings,
               SUM(total_revenue_jpy) AS revenue_jpy,
               AVG(price_per_person_jpy) AS avg_unit_price_jpy
        FROM dbo.booking
        WHERE booking_status IN ('confirmed','completed')
        GROUP BY destination_region
        ORDER BY revenue_jpy DESC
    """),
    # customer_segment × age_band クロス (booking ベースで人気セグメントを抽出)
    ("segment_x_ageband_bookings", """
        SELECT c.customer_segment, c.age_band, COUNT(b.booking_id) AS bookings,
               SUM(b.total_revenue_jpy) AS revenue_jpy
        FROM dbo.booking b
        JOIN dbo.customer c ON c.customer_id = b.customer_id
        WHERE b.booking_status IN ('confirmed','completed')
        GROUP BY c.customer_segment, c.age_band
        ORDER BY c.customer_segment, c.age_band
    """),
    # source_market: 訪日 (inbound) の destination_country / destination_region 内訳
    ("inbound_source_market", """
        SELECT destination_country, destination_region, COUNT(*) AS bookings,
               SUM(total_revenue_jpy) AS revenue_jpy
        FROM dbo.booking
        WHERE destination_type = 'inbound'
          AND booking_status IN ('confirmed','completed')
        GROUP BY destination_country, destination_region
        ORDER BY revenue_jpy DESC
    """),
    # total_revenue_jpy 帯域分布
    ("revenue_band_distribution", """
        SELECT
            CASE
                WHEN total_revenue_jpy < 100000 THEN 'A_<100k'
                WHEN total_revenue_jpy < 300000 THEN 'B_100k-300k'
                WHEN total_revenue_jpy < 500000 THEN 'C_300k-500k'
                WHEN total_revenue_jpy < 1000000 THEN 'D_500k-1M'
                WHEN total_revenue_jpy < 3000000 THEN 'E_1M-3M'
                ELSE 'F_>=3M'
            END AS band,
            COUNT(*) AS bookings,
            SUM(total_revenue_jpy) AS revenue_jpy
        FROM dbo.booking
        WHERE booking_status IN ('confirmed','completed')
        GROUP BY
            CASE
                WHEN total_revenue_jpy < 100000 THEN 'A_<100k'
                WHEN total_revenue_jpy < 300000 THEN 'B_100k-300k'
                WHEN total_revenue_jpy < 500000 THEN 'C_300k-500k'
                WHEN total_revenue_jpy < 1000000 THEN 'D_500k-1M'
                WHEN total_revenue_jpy < 3000000 THEN 'E_1M-3M'
                ELSE 'F_>=3M'
            END
        ORDER BY band
    """),
    # 年別 booking
    ("revenue_by_year", """
        SELECT YEAR(departure_date) AS yr,
               COUNT(*) AS bookings,
               SUM(total_revenue_jpy) AS revenue_jpy,
               AVG(total_revenue_jpy) AS avg_revenue_jpy
        FROM dbo.booking
        WHERE booking_status IN ('confirmed','completed')
        GROUP BY YEAR(departure_date)
        ORDER BY yr
    """),
    # tour_review 統計
    ("tour_review_aggregates", """
        SELECT COUNT(*) AS reviews,
               AVG(CAST(rating AS FLOAT)) AS avg_rating,
               AVG(CAST(nps AS FLOAT)) AS avg_nps,
               SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) AS high_rating,
               SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) AS low_rating
        FROM dbo.tour_review
    """),
]

# データ→ ontology 表記マッピングのカバレッジを確認するため、aiInstructions §A.1 で
# 列挙されている region 値が実データに存在するかをチェックする
ONTOLOGY_REGION_VALUES = [
    "沖縄", "北海道", "京都", "ハワイ", "大阪", "東京", "韓国", "台湾", "福岡", "タイ",
    "静岡", "長野", "シンガポール", "アメリカ西海岸", "広島", "愛知", "石川", "鹿児島",
    "パリ", "ベトナム", "イタリア", "オーストラリア", "三重", "ニューヨーク", "青森",
    "宮城", "ロンドン", "ドバイ", "中国", "その他",
]


def get_token() -> str:
    r = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", "https://database.windows.net",
            "--query", "accessToken", "-o", "tsv",
        ],
        capture_output=True, text=True, shell=True, check=True,
    )
    return r.stdout.strip()


def make_conn() -> pyodbc.Connection:
    token = get_token()
    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={ENDPOINT},1433;"
        f"Database={DATABASE};"
        "Encrypt=yes;TrustServerCertificate=no;"
        "Connection Timeout=60;"
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})


def fetch(cur: pyodbc.Cursor, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out: list[dict] = []
    for r in rows:
        item: dict = {}
        for c, v in zip(cols, r):
            if isinstance(v, (int, float)) or v is None:
                item[c] = v
            else:
                item[c] = str(v)
        out.append(item)
    return out


def main() -> int:
    out_path = Path(__file__).parent / "dataset_v2_audit_raw.json"
    with make_conn() as conn:
        cur = conn.cursor()
        result: dict = {"row_counts": {}, "columns": {}, "cross": {}, "coverage": {}}
        for name, sql in TABLE_ROWCOUNT_QUERIES:
            print(f"[rowcount] {name}")
            data = fetch(cur, sql)
            result["row_counts"] = {row["tbl"]: row["row_count"] for row in data}
            print("  ", result["row_counts"])
        for name, sql in COLUMN_QUERIES:
            print(f"[col] {name}")
            try:
                result["columns"][name] = fetch(cur, sql)
            except pyodbc.Error as ex:
                result["columns"][name] = [{"_error": str(ex)}]
                print(f"  ERROR {ex}")
        for name, sql in CROSS_QUERIES:
            print(f"[cross] {name}")
            try:
                result["cross"][name] = fetch(cur, sql)
            except pyodbc.Error as ex:
                result["cross"][name] = [{"_error": str(ex)}]
                print(f"  ERROR {ex}")

        # region coverage
        actual_regions = {row["v"] for row in result["columns"].get("booking.destination_region", []) if row.get("v")}
        ontology_regions = set(ONTOLOGY_REGION_VALUES)
        result["coverage"]["region"] = {
            "ontology_listed": sorted(ontology_regions),
            "actual": sorted(actual_regions),
            "in_ontology_not_in_data": sorted(ontology_regions - actual_regions),
            "in_data_not_in_ontology": sorted(actual_regions - ontology_regions),
        }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
