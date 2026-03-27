"""デモデータ生成スクリプト。Faker でリアルな旅行業務データを生成する。

使い方:
  uv run python data/demo_data_generator.py

出力:
  data/sales_history.csv
  data/customer_reviews.csv
  data/plan_master.csv
"""

import csv
import os
import random
from datetime import date, timedelta

# シード固定で再現性を確保
random.seed(42)

OUTPUT_DIR = os.path.dirname(__file__)

# --- プランマスタ ---
PLANS = [
    {
        "plan_id": "PLN001",
        "plan_name": "沖縄3泊4日ファミリープラン",
        "region": "沖縄",
        "season": "spring",
        "price_range": "80,000〜120,000",
        "category": "ファミリー",
        "duration_days": 4,
        "itinerary": "那覇→美ら海水族館→古宇利島→国際通り",
    },
    {
        "plan_id": "PLN002",
        "plan_name": "沖縄リゾートステイ",
        "region": "沖縄",
        "season": "summer",
        "price_range": "60,000〜100,000",
        "category": "カップル",
        "duration_days": 3,
        "itinerary": "恩納村リゾート→青の洞窟シュノーケリング→アメリカンビレッジ",
    },
    {
        "plan_id": "PLN003",
        "plan_name": "北海道ラベンダー畑ツアー",
        "region": "北海道",
        "season": "summer",
        "price_range": "70,000〜110,000",
        "category": "ファミリー",
        "duration_days": 4,
        "itinerary": "札幌→富良野ラベンダー畑→旭山動物園→小樽運河",
    },
    {
        "plan_id": "PLN004",
        "plan_name": "京都紅葉めぐり",
        "region": "京都",
        "season": "autumn",
        "price_range": "50,000〜80,000",
        "category": "シニア",
        "duration_days": 3,
        "itinerary": "東福寺→嵐山→金閣寺→清水寺",
    },
    {
        "plan_id": "PLN005",
        "plan_name": "箱根温泉週末プラン",
        "region": "箱根",
        "season": "winter",
        "price_range": "30,000〜50,000",
        "category": "カップル",
        "duration_days": 2,
        "itinerary": "箱根湯本→大涌谷→芦ノ湖遊覧→箱根神社",
    },
    {
        "plan_id": "PLN006",
        "plan_name": "石垣島ダイビング",
        "region": "沖縄",
        "season": "summer",
        "price_range": "90,000〜140,000",
        "category": "アクティブ",
        "duration_days": 4,
        "itinerary": "石垣島→竹富島→マンタスクランブル→川平湾",
    },
    {
        "plan_id": "PLN007",
        "plan_name": "東北温泉巡り",
        "region": "東北",
        "season": "winter",
        "price_range": "40,000〜70,000",
        "category": "シニア",
        "duration_days": 3,
        "itinerary": "銀山温泉→蔵王温泉→鳴子温泉",
    },
    {
        "plan_id": "PLN008",
        "plan_name": "九州グルメツアー",
        "region": "九州",
        "season": "autumn",
        "price_range": "55,000〜85,000",
        "category": "グループ",
        "duration_days": 3,
        "itinerary": "博多→長崎→熊本→別府",
    },
    {
        "plan_id": "PLN009",
        "plan_name": "北海道スキーリゾート",
        "region": "北海道",
        "season": "winter",
        "price_range": "80,000〜130,000",
        "category": "ファミリー",
        "duration_days": 4,
        "itinerary": "新千歳→ニセコ→ルスツ→小樽",
    },
    {
        "plan_id": "PLN010",
        "plan_name": "奄美大島ネイチャー",
        "region": "鹿児島",
        "season": "spring",
        "price_range": "65,000〜95,000",
        "category": "カップル",
        "duration_days": 3,
        "itinerary": "奄美空港→マングローブカヌー→加計呂麻島→あやまる岬",
    },
    {
        "plan_id": "PLN011",
        "plan_name": "四国お遍路ウォーキング",
        "region": "四国",
        "season": "spring",
        "price_range": "45,000〜75,000",
        "category": "シニア",
        "duration_days": 4,
        "itinerary": "高松→金刀比羅宮→道後温泉→桂浜",
    },
    {
        "plan_id": "PLN012",
        "plan_name": "長野高原リトリート",
        "region": "長野",
        "season": "summer",
        "price_range": "35,000〜60,000",
        "category": "カップル",
        "duration_days": 2,
        "itinerary": "軽井沢→白糸の滝→旧軽井沢銀座→ハルニレテラス",
    },
    {
        "plan_id": "PLN013",
        "plan_name": "広島・宮島歴史探訪",
        "region": "広島",
        "season": "autumn",
        "price_range": "50,000〜80,000",
        "category": "グループ",
        "duration_days": 3,
        "itinerary": "広島平和記念公園→宮島厳島神社→尾道",
    },
    {
        "plan_id": "PLN014",
        "plan_name": "伊豆半島ドライブ",
        "region": "静岡",
        "season": "spring",
        "price_range": "25,000〜45,000",
        "category": "カップル",
        "duration_days": 2,
        "itinerary": "熱海→伊豆高原→城ヶ崎海岸→修善寺",
    },
    {
        "plan_id": "PLN015",
        "plan_name": "屋久島トレッキング",
        "region": "鹿児島",
        "season": "summer",
        "price_range": "85,000〜120,000",
        "category": "アクティブ",
        "duration_days": 4,
        "itinerary": "屋久島空港→白谷雲水峡→縄文杉→ウミガメ産卵地",
    },
    {
        "plan_id": "PLN016",
        "plan_name": "金沢文化体験",
        "region": "石川",
        "season": "autumn",
        "price_range": "45,000〜70,000",
        "category": "グループ",
        "duration_days": 3,
        "itinerary": "兼六園→ひがし茶屋街→近江町市場→21世紀美術館",
    },
    {
        "plan_id": "PLN017",
        "plan_name": "日光・鬼怒川温泉",
        "region": "栃木",
        "season": "autumn",
        "price_range": "30,000〜55,000",
        "category": "ファミリー",
        "duration_days": 2,
        "itinerary": "日光東照宮→華厳の滝→鬼怒川温泉→江戸ワンダーランド",
    },
    {
        "plan_id": "PLN018",
        "plan_name": "函館ロマンチック旅",
        "region": "北海道",
        "season": "winter",
        "price_range": "55,000〜85,000",
        "category": "カップル",
        "duration_days": 3,
        "itinerary": "函館山夜景→五稜郭→朝市→大沼公園",
    },
    {
        "plan_id": "PLN019",
        "plan_name": "宮古島絶景ビーチ",
        "region": "沖縄",
        "season": "summer",
        "price_range": "95,000〜150,000",
        "category": "カップル",
        "duration_days": 4,
        "itinerary": "宮古島→伊良部大橋→与那覇前浜→シギラビーチ",
    },
    {
        "plan_id": "PLN020",
        "plan_name": "信州そば巡り",
        "region": "長野",
        "season": "autumn",
        "price_range": "28,000〜48,000",
        "category": "シニア",
        "duration_days": 2,
        "itinerary": "松本城→安曇野→戸隠神社→善光寺",
    },
]

SEGMENTS = ["ファミリー", "カップル", "シニア", "グループ", "一人旅", "アクティブ"]
SEASONS = ["spring", "summer", "autumn", "winter"]
SEASON_MONTHS = {"spring": [3, 4, 5], "summer": [6, 7, 8], "autumn": [9, 10, 11], "winter": [12, 1, 2]}

# 季節係数（需要の重み）
SEASON_WEIGHT = {"spring": 1.2, "summer": 1.5, "autumn": 1.0, "winter": 0.8}

REVIEW_POSITIVE = [
    "最高の旅行でした！景色が素晴らしい",
    "スタッフの対応が丁寧で安心できました",
    "子どもが大喜びでした。また行きたい",
    "食事が美味しくて大満足",
    "コスパが良く、友人にもおすすめしたい",
    "ガイドさんが親切で楽しい旅になりました",
    "ホテルが清潔で快適でした",
    "写真映えスポットが多くて嬉しかった",
]

REVIEW_NEUTRAL = [
    "全体的に満足だが、移動時間が長かった",
    "観光スポットは良かったが、食事が普通",
    "天候に恵まれず少し残念",
    "もう少し自由時間が欲しかった",
    "ホテルは普通。立地は良い",
]

REVIEW_NEGATIVE = [
    "価格に対して食事の質がイマイチ",
    "混雑していてゆっくりできなかった",
    "バスの移動時間が長すぎる",
    "Wi-Fi が使えなくて不便だった",
    "予約の変更がしにくかった",
]


def generate_sales_history(n: int = 800) -> list[dict]:
    """販売履歴データを生成する"""
    records = []
    base_date = date(2025, 4, 1)

    for i in range(n):
        plan = random.choice(PLANS)
        season = plan["season"]
        weight = SEASON_WEIGHT[season]

        # 予約日: 過去1年分（季節で重み付け）
        days_ago = random.randint(0, 365)
        booking_date = base_date - timedelta(days=days_ago)

        # 出発日: 予約日から1〜90日後
        departure_offset = random.randint(7, 90)
        departure_date = booking_date + timedelta(days=departure_offset)

        # 人数・売上（季節とカテゴリで変動）
        pax = random.choices([1, 2, 3, 4, 5, 6], weights=[5, 30, 20, 25, 10, 10])[0]
        base_revenue = random.randint(30000, 150000) * pax
        revenue = int(base_revenue * weight * random.uniform(0.8, 1.2))

        segment = plan["category"] if random.random() < 0.7 else random.choice(SEGMENTS)

        records.append(
            {
                "booking_id": f"BK{i + 1:05d}",
                "plan_name": plan["plan_name"],
                "destination": plan["region"],
                "departure_date": departure_date.isoformat(),
                "pax": pax,
                "revenue": revenue,
                "customer_segment": segment,
                "booking_date": booking_date.isoformat(),
            }
        )

    return records


def generate_customer_reviews(n: int = 400) -> list[dict]:
    """顧客レビューデータを生成する"""
    records = []
    base_date = date(2025, 4, 1)

    for i in range(n):
        plan = random.choice(PLANS)
        rating = random.choices([1, 2, 3, 4, 5], weights=[3, 7, 15, 35, 40])[0]

        if rating >= 4:
            comment = random.choice(REVIEW_POSITIVE)
        elif rating == 3:
            comment = random.choice(REVIEW_NEUTRAL)
        else:
            comment = random.choice(REVIEW_NEGATIVE)

        review_date = base_date - timedelta(days=random.randint(0, 365))

        records.append(
            {
                "review_id": f"RV{i + 1:05d}",
                "plan_name": plan["plan_name"],
                "rating": rating,
                "comment": comment,
                "review_date": review_date.isoformat(),
            }
        )

    return records


def write_csv(filename: str, records: list[dict]) -> None:
    """CSV ファイルに書き出す"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    print(f"  {filepath} ({len(records)} 件)")


def main() -> None:
    """全デモデータを生成する"""
    print("デモデータ生成中...")

    # plan_master
    write_csv("plan_master.csv", PLANS)

    # sales_history
    sales = generate_sales_history(800)
    write_csv("sales_history.csv", sales)

    # customer_reviews
    reviews = generate_customer_reviews(400)
    write_csv("customer_reviews.csv", reviews)

    print("完了！")


if __name__ == "__main__":
    main()
