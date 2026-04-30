"""Travel Marketing v2 hybrid seeded synthetic dataset generator.

Phase 9.2 のメインエントリポイント。`seed_distributions.json` から公的統計の集計分布を
読み込み、Faker + numpy でレコードを合成して 10 個の Parquet ファイルを書き出す。

設計詳細: docs/fabric-data-overhaul/schema.md
オントロジー: docs/fabric-data-overhaul/ontology.md
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = Path(__file__).resolve().parent / "seed_distributions.json"

START_DATE = date(2022, 1, 1)
END_DATE = date(2026, 4, 30)


@dataclass
class GenerationConfig:
    """医療規模 (medium) のデフォルト件数。"""

    customers: int = 10_000
    bookings: int = 50_000
    payments_per_booking_max: int = 3
    review_rate: float = 0.20
    cancellation_rate: float = 0.10
    inquiry_count: int = 20_000
    hotels: int = 500
    flights: int = 2_000
    campaigns: int = 200
    seed: int = 42


def _load_seeds() -> dict[str, Any]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _weighted_choice(rng: np.random.Generator, distribution: dict[str, float], size: int) -> np.ndarray:
    keys = [k for k in distribution if not k.startswith("_")]
    weights = np.array([distribution[k] for k in keys], dtype=float)
    weights = weights / weights.sum()
    return rng.choice(keys, size=size, p=weights)


def _utc_now_ts() -> datetime:
    return datetime.now(timezone.utc)


def _ts_str(d: datetime | None) -> datetime | None:
    return d


def _midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# customer
# ---------------------------------------------------------------------------


def generate_customers(config: GenerationConfig, seeds: dict[str, Any], rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    n = config.customers
    age_band = _weighted_choice(rng, seeds["age_band_distribution"], n)
    band_to_birth_offset = {"10s": 15, "20s": 25, "30s": 35, "40s": 45, "50s": 55, "60s": 65, "70s+": 75}
    today_year = END_DATE.year
    birth_year = np.array([today_year - band_to_birth_offset[band] - rng.integers(-3, 3) for band in age_band])

    rows = {
        "customer_id": [str(uuid.uuid4()) for _ in range(n)],
        "customer_code": [f"C-{rng.integers(2018, 2027):04d}-{i:06d}" for i in range(n)],
        "last_name_kana": [fake.last_kana_name() for _ in range(n)],
        "first_name_kana": [fake.first_kana_name() for _ in range(n)],
        "gender": _weighted_choice(rng, {"male": 0.48, "female": 0.50, "other": 0.02}, n),
        "age_band": age_band,
        "birth_year": birth_year,
        "customer_segment": _weighted_choice(rng, seeds["customer_segment_distribution"], n),
        "loyalty_tier": _weighted_choice(rng, seeds["loyalty_tier_distribution"], n),
        "acquisition_channel": _weighted_choice(rng, seeds["acquisition_channel_distribution"], n),
        "prefecture": _weighted_choice(rng, seeds["prefecture_share"], n),
        "email_opt_in": rng.random(n) < 0.60,
    }
    created_dates: list[datetime] = []
    for _ in range(n):
        days_ago = int(rng.integers(0, (END_DATE - date(2018, 1, 1)).days))
        created_dates.append(_midnight(END_DATE - timedelta(days=days_ago)))
    rows["created_at"] = created_dates
    rows["updated_at"] = created_dates
    rows["loaded_at"] = [_utc_now_ts()] * n
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# hotel
# ---------------------------------------------------------------------------


def generate_hotels(config: GenerationConfig, seeds: dict[str, Any], rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    n = config.hotels
    domestic_keys = list(seeds["destination_share_domestic"].keys())
    outbound_keys = list(seeds["destination_share_outbound"].keys())
    domestic_keys = [k for k in domestic_keys if k != "その他"]
    outbound_keys = [k for k in outbound_keys if k != "その他"]
    country_map = seeds["destination_country_map"]
    rows = []
    for i in range(n):
        is_domestic = rng.random() < 0.6
        region = rng.choice(domestic_keys) if is_domestic else rng.choice(outbound_keys)
        meta = country_map.get(region, {"country": "Japan", "city": region})
        category = rng.choice(["luxury", "upscale", "midscale", "budget", "ryokan", "resort"])
        star_rating = {"luxury": 5, "upscale": 4, "midscale": 3, "budget": 2, "ryokan": 4, "resort": 4}[category]
        avg_price = {"luxury": 60_000, "upscale": 30_000, "midscale": 15_000, "budget": 8_000, "ryokan": 28_000, "resort": 35_000}[category]
        avg_price = int(avg_price * float(rng.normal(1.0, 0.15)))
        avg_price = max(5_000, avg_price)
        rows.append(
            {
                "hotel_id": str(uuid.uuid4()),
                "hotel_code": f"HOT-{i:05d}",
                "name": _make_hotel_name(rng, region, category),
                "country": meta["country"],
                "region": region,
                "city": meta["city"],
                "category": category,
                "star_rating": star_rating,
                "room_count": int(rng.integers(20, 600)),
                "avg_price_per_night_jpy": avg_price,
                "latitude": float(rng.uniform(24, 46)) if is_domestic else float(rng.uniform(-40, 60)),
                "longitude": float(rng.uniform(123, 146)) if is_domestic else float(rng.uniform(-180, 180)),
                "loaded_at": _utc_now_ts(),
            }
        )
    return pd.DataFrame(rows)


def _make_hotel_name(rng: np.random.Generator, region: str, category: str) -> str:
    suffixes = {
        "luxury": ["パレスホテル", "ザ・リッツ", "リゾート＆スパ"],
        "upscale": ["プリンスホテル", "グランドホテル", "プラザホテル"],
        "midscale": ["シティホテル", "ホテル"],
        "budget": ["インバウンドイン", "ビジネスホテル"],
        "ryokan": ["温泉旅館", "別邸"],
        "resort": ["ビーチリゾート", "オーシャンリゾート"],
    }
    return f"{region} {rng.choice(suffixes[category])}"


# ---------------------------------------------------------------------------
# flight
# ---------------------------------------------------------------------------


def generate_flights(config: GenerationConfig, seeds: dict[str, Any], rng: np.random.Generator) -> pd.DataFrame:
    n = config.flights
    airlines = [
        ("ANA", "全日本空輸"), ("JAL", "日本航空"), ("UAL", "ユナイテッド航空"),
        ("DAL", "デルタ航空"), ("AAL", "アメリカン航空"), ("AFR", "エールフランス"),
        ("LH", "ルフトハンザ"), ("BAW", "ブリティッシュ・エアウェイズ"),
        ("KAL", "大韓航空"), ("CAL", "チャイナエアライン"), ("THA", "タイ国際航空"),
        ("SIA", "シンガポール航空"), ("EK", "エミレーツ"), ("QF", "カンタス航空"),
    ]
    airports_jp = ["HND", "NRT", "KIX", "NGO", "FUK", "CTS", "OKA"]
    airports_intl = ["HNL", "JFK", "LAX", "CDG", "LHR", "FCO", "FRA", "SIN", "BKK", "ICN", "TPE", "DXB", "SYD"]
    classes = ["economy", "premium_economy", "business", "first"]
    class_weights = [0.78, 0.10, 0.10, 0.02]

    rows = []
    seen_routes: set[tuple[str, str, str]] = set()
    while len(rows) < n:
        is_domestic = rng.random() < 0.4
        if is_domestic:
            dep, arr = rng.choice(airports_jp, size=2, replace=False)
            distance = int(rng.integers(300, 2_000))
            duration = int(distance / 8 + rng.integers(20, 60))
        else:
            dep = rng.choice(airports_jp)
            arr = rng.choice(airports_intl)
            distance = int(rng.integers(2_500, 13_000))
            duration = int(distance / 9 + rng.integers(60, 180))
        airline = airlines[int(rng.integers(0, len(airlines)))]
        flight_class = rng.choice(classes, p=class_weights)
        route_key = (airline[0], dep, arr, flight_class)
        if route_key in seen_routes:
            continue
        seen_routes.add(route_key)  # type: ignore[arg-type]
        rows.append(
            {
                "flight_id": str(uuid.uuid4()),
                "airline_code": airline[0],
                "airline_name": airline[1],
                "departure_airport": str(dep),
                "arrival_airport": str(arr),
                "route_label": f"{dep}-{arr}",
                "flight_class": flight_class,
                "distance_km": distance,
                "avg_duration_min": duration,
                "loaded_at": _utc_now_ts(),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# campaign
# ---------------------------------------------------------------------------


def generate_campaigns(config: GenerationConfig, seeds: dict[str, Any], rng: np.random.Generator) -> pd.DataFrame:
    types = ["early_bird", "last_minute", "loyalty", "seasonal", "regional_partner", "corporate"]
    rows = []
    for i in range(config.campaigns):
        start = START_DATE + timedelta(days=int(rng.integers(0, (END_DATE - START_DATE).days - 60)))
        end = start + timedelta(days=int(rng.integers(14, 90)))
        campaign_type = str(rng.choice(types))
        target_segment = str(rng.choice([None, "family", "couple", "solo", "group", "senior", "student"], p=[0.45, 0.18, 0.13, 0.07, 0.07, 0.05, 0.05]))
        target_dest_type = str(rng.choice([None, "domestic", "outbound", "inbound"], p=[0.55, 0.30, 0.13, 0.02]))
        rows.append(
            {
                "campaign_id": str(uuid.uuid4()),
                "campaign_code": f"CMP-{start.year}-Q{(start.month - 1) // 3 + 1}-{i:03d}",
                "campaign_name": _make_campaign_name(rng, campaign_type),
                "campaign_type": campaign_type,
                "target_segment": target_segment if target_segment != "None" else None,
                "target_destination_type": target_dest_type if target_dest_type != "None" else None,
                "start_date": start,
                "end_date": end,
                "discount_percent": float(round(rng.uniform(5, 35), 1)),
                "total_budget_jpy": int(rng.integers(2_000_000, 25_000_000)),
                "total_redemptions": 0,
                "loaded_at": _utc_now_ts(),
            }
        )
    return pd.DataFrame(rows)


def _make_campaign_name(rng: np.random.Generator, campaign_type: str) -> str:
    table = {
        "early_bird": ["早期予約30%OFF", "夏旅早割キャンペーン", "海外早期予約特典"],
        "last_minute": ["週末出発限定セール", "直前割引", "ラストミニッツSALE"],
        "loyalty": ["プレミアム会員限定優待", "ゴールドメンバー感謝祭", "リピーター割引"],
        "seasonal": ["紅葉キャンペーン", "桜シーズン限定", "夏休み応援セール", "GW特別企画"],
        "regional_partner": ["沖縄観光協会タイアップ", "北海道道産品付きプラン", "京都伝統工芸体験付き"],
        "corporate": ["法人MICEプラン", "社員旅行特別レート"],
    }
    return str(rng.choice(table[campaign_type]))


# ---------------------------------------------------------------------------
# booking + payment + cancellation + itinerary_item + tour_review
# ---------------------------------------------------------------------------


def _yearly_factor(seeds: dict[str, Any], yr: int) -> float:
    idx = seeds["yearly_revenue_index"]
    if yr == 2026:
        return float(idx["2026_partial"]) / 100.0
    return float(idx[str(yr)]) / 100.0


def _is_special_period(d: date, seeds: dict[str, Any], key: str) -> bool:
    for s, e in seeds["special_period_dates"][key]:
        s_d = date.fromisoformat(s)
        e_d = date.fromisoformat(e)
        if s_d <= d <= e_d:
            return True
    return False


def _resolve_season(d: date, seeds: dict[str, Any]) -> str:
    if _is_special_period(d, seeds, "gw"):
        return "gw"
    if _is_special_period(d, seeds, "obon"):
        return "obon"
    if _is_special_period(d, seeds, "new_year"):
        return "new_year"
    for season, months in seeds["season_to_months"].items():
        if d.month in months:
            return season
    return "winter"


def _sample_departure_dates(rng: np.random.Generator, seeds: dict[str, Any], n: int) -> np.ndarray:
    """年×月の重みを公的統計の seasonality と yearly index から構築し、出発日を一気にサンプリング。"""
    weights: list[tuple[date, float]] = []
    cur = START_DATE
    monthly = seeds["monthly_seasonality"]
    while cur <= END_DATE:
        yr = cur.year
        mo = cur.month
        days_in_month = (date(yr + (mo == 12), mo % 12 + 1, 1) - date(yr, mo, 1)).days
        for d_idx in range(days_in_month):
            d = date(yr, mo, 1) + timedelta(days=d_idx)
            if d > END_DATE:
                break
            w = _yearly_factor(seeds, yr) * float(monthly[str(mo)])
            if _is_special_period(d, seeds, "gw") or _is_special_period(d, seeds, "obon") or _is_special_period(d, seeds, "new_year"):
                w *= 1.6
            weights.append((d, w))
        cur = date(yr + (mo == 12), mo % 12 + 1, 1)
    dates = [w[0] for w in weights]
    ws = np.array([w[1] for w in weights], dtype=float)
    ws = ws / ws.sum()
    return rng.choice(dates, size=n, p=ws)


def _sample_destination(rng: np.random.Generator, seeds: dict[str, Any], dest_type: str) -> str:
    if dest_type == "domestic":
        share = seeds["destination_share_domestic"]
    elif dest_type == "outbound":
        share = seeds["destination_share_outbound"]
    else:
        # inbound: simulated as Japanese popular cities seen by foreign travelers
        share = {"東京": 0.35, "京都": 0.25, "大阪": 0.20, "沖縄": 0.10, "北海道": 0.10}
    return str(_weighted_choice(rng, share, 1)[0])


def generate_bookings_and_dependents(
    config: GenerationConfig,
    seeds: dict[str, Any],
    rng: np.random.Generator,
    customers_df: pd.DataFrame,
    campaigns_df: pd.DataFrame,
    hotels_df: pd.DataFrame,
    flights_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = config.bookings
    departures = _sample_departure_dates(rng, seeds, n)

    # Derive dest type per booking from inbound/outbound/domestic share
    dest_type_arr = _weighted_choice(rng, seeds["destination_type_share"], n)

    product_type_for_domestic = ["domestic_package", "freeplan", "fit"]
    product_type_for_outbound = ["outbound_package", "cruise", "fit"]

    booking_rows: list[dict[str, Any]] = []
    payment_rows: list[dict[str, Any]] = []
    cancellation_rows: list[dict[str, Any]] = []
    itinerary_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    customer_ids = customers_df["customer_id"].to_numpy()
    customer_segments = customers_df["customer_segment"].to_numpy()
    customer_age_bands = customers_df["age_band"].to_numpy()
    customer_index_map = {cid: idx for idx, cid in enumerate(customer_ids)}

    campaign_ids = campaigns_df["campaign_id"].to_numpy()
    campaign_starts = campaigns_df["start_date"].to_numpy()
    campaign_ends = campaigns_df["end_date"].to_numpy()

    hotels_by_region = defaultdict(list)
    for _, row in hotels_df.iterrows():
        hotels_by_region[row["region"]].append(row)
    flights_jp_to_intl = flights_df[flights_df["arrival_airport"].isin(["HNL", "JFK", "LAX", "CDG", "LHR", "FCO", "FRA", "SIN", "BKK", "ICN", "TPE", "DXB", "SYD"])]
    flights_jp_dom = flights_df[flights_df["departure_airport"].isin(["HND", "NRT", "KIX", "NGO", "FUK", "CTS", "OKA"]) & flights_df["arrival_airport"].isin(["HND", "NRT", "KIX", "NGO", "FUK", "CTS", "OKA"])]

    repeat_targets = rng.choice(customer_ids, size=int(n * 0.65), replace=True)
    primary_customer_picks = list(repeat_targets) + list(rng.choice(customer_ids, size=n - len(repeat_targets), replace=True))
    rng.shuffle(primary_customer_picks)

    country_map = seeds["destination_country_map"]
    seed_prices = seeds["price_per_person_jpy"]
    seed_durations = seeds["duration_days_distribution"]
    rating_dist = seeds["rating_distribution"]
    cancel_reason_dist = seeds["cancellation_reason_distribution"]
    booking_status_dist = seeds["booking_status_distribution"]

    redemption_count = defaultdict(int)

    for i in range(n):
        dep_date = pd.to_datetime(departures[i]).date()
        dest_type = str(dest_type_arr[i])
        region = _sample_destination(rng, seeds, dest_type)
        meta = country_map.get(region, {"country": "Japan", "city": region})
        season = _resolve_season(dep_date, seeds)

        product_pool = product_type_for_domestic if dest_type == "domestic" else product_type_for_outbound
        product_type = str(rng.choice(product_pool))
        if dest_type == "inbound":
            product_type = "fit"

        cust_id = primary_customer_picks[i]
        cust_idx = customer_index_map[cust_id]
        seg = str(customer_segments[cust_idx])
        _age_band = str(customer_age_bands[cust_idx])

        pax_seed_lambda = {"family": 4.2, "couple": 2.0, "solo": 1.0, "group": 8.0, "senior": 2.0, "student": 3.0, "business": 1.5}[seg]
        pax = int(max(1, rng.poisson(pax_seed_lambda)))
        pax_child = int(rng.binomial(pax, 0.35)) if seg == "family" else 0
        pax_adult = pax - pax_child
        if pax_adult < 1:
            pax_adult = 1
            pax = pax_adult + pax_child

        dur_seed = seed_durations[product_type]
        duration = int(max(dur_seed["min"], min(dur_seed["max"], rng.poisson(dur_seed["mean"]))))
        return_date_v = dep_date + timedelta(days=duration - 1)

        price_seed = seed_prices[product_type]
        median_price_thousand = float(price_seed["median"])
        sigma = float(price_seed["stdev_log"])
        ppp = int(rng.lognormal(mean=math.log(median_price_thousand * 1000), sigma=sigma))
        # 円安効果 (海外のみ、2024 以降 +20%)
        if dest_type == "outbound" and dep_date.year >= 2024:
            ppp = int(ppp * 1.2)
        # シニア / luxury 補正
        if seg == "senior" and product_type in ("cruise", "outbound_package"):
            ppp = int(ppp * 1.15)
        revenue = ppp * pax

        lead_time_log_med = math.log(seeds["lead_time_days_distribution"]["median"])
        lead_time_sigma = seeds["lead_time_days_distribution"]["stdev_log"]
        lead_days = int(min(365, max(0, rng.lognormal(mean=lead_time_log_med, sigma=lead_time_sigma))))
        booking_date_v = dep_date - timedelta(days=lead_days)
        if booking_date_v < START_DATE:
            booking_date_v = START_DATE

        # campaign join: 30% chance, must overlap with booking date
        campaign_id_assigned: str | None = None
        if rng.random() < 0.3 and len(campaign_ids) > 0:
            for _ in range(3):
                k = int(rng.integers(0, len(campaign_ids)))
                cs = pd.to_datetime(campaign_starts[k]).date()
                ce = pd.to_datetime(campaign_ends[k]).date()
                if cs <= booking_date_v <= ce:
                    campaign_id_assigned = str(campaign_ids[k])
                    redemption_count[campaign_id_assigned] += 1
                    break

        status = str(_weighted_choice(rng, booking_status_dist, 1)[0])
        booking_id = str(uuid.uuid4())
        booking_rows.append(
            {
                "booking_id": booking_id,
                "booking_code": f"BK-{dep_date.year}-{i:06d}",
                "customer_id": cust_id,
                "campaign_id": campaign_id_assigned,
                "plan_name": _make_plan_name(rng, region, season, seg, dest_type),
                "product_type": product_type,
                "destination_country": meta["country"],
                "destination_region": region,
                "destination_city": meta["city"],
                "destination_type": dest_type,
                "season": season,
                "departure_date": dep_date,
                "return_date": return_date_v,
                "duration_days": duration,
                "pax": pax,
                "pax_adult": pax_adult,
                "pax_child": pax_child,
                "total_revenue_jpy": revenue,
                "price_per_person_jpy": ppp,
                "booking_date": booking_date_v,
                "lead_time_days": lead_days,
                "booking_status": status,
                "loaded_at": _utc_now_ts(),
            }
        )

        # payment(s)
        installments = 1 if rng.random() < 0.85 else int(rng.integers(2, 4))
        per_amount = revenue // installments
        for inst_idx in range(installments):
            paid_at = datetime.combine(booking_date_v + timedelta(days=int(rng.integers(0, max(1, lead_days)))), datetime.min.time(), tzinfo=timezone.utc)
            currency = "JPY"
            rate = 1.0
            if dest_type == "outbound" and rng.random() < 0.10:
                currency = "USD" if rng.random() < 0.65 else "EUR"
                yr = str(dep_date.year)
                if currency == "USD":
                    rate = float(seeds["exchange_rate_usd_jpy"].get(yr, 150.0))
                else:
                    rate = float(seeds["exchange_rate_eur_jpy"].get(yr, 162.0))
            payment_status = "succeeded"
            if status in ("cancelled", "no_show") and rng.random() < 0.6:
                payment_status = rng.choice(["refunded", "succeeded"])
            payment_rows.append(
                {
                    "payment_id": str(uuid.uuid4()),
                    "booking_id": booking_id,
                    "payment_method": str(rng.choice(["credit_card", "bank_transfer", "pay_at_store", "point", "voucher"], p=[0.62, 0.18, 0.10, 0.05, 0.05])),
                    "payment_status": str(payment_status),
                    "amount_jpy": per_amount if inst_idx < installments - 1 else revenue - per_amount * (installments - 1),
                    "currency": currency,
                    "exchange_rate_to_jpy": rate,
                    "paid_at": paid_at,
                    "installment_count": installments,
                    "loaded_at": _utc_now_ts(),
                }
            )

        # cancellation
        if status == "cancelled":
            cancelled_at = datetime.combine(booking_date_v + timedelta(days=int(rng.integers(0, max(1, lead_days)))), datetime.min.time(), tzinfo=timezone.utc)
            cancel_lead = (dep_date - cancelled_at.date()).days
            fee_pct = 0.0
            if cancel_lead < 7:
                fee_pct = 0.5 if cancel_lead >= 3 else 1.0
            elif cancel_lead < 30:
                fee_pct = 0.2
            else:
                fee_pct = 0.0
            fee = int(revenue * fee_pct)
            refund = revenue - fee
            cancellation_rows.append(
                {
                    "cancellation_id": str(uuid.uuid4()),
                    "booking_id": booking_id,
                    "cancelled_at": cancelled_at,
                    "cancellation_reason": str(_weighted_choice(rng, cancel_reason_dist, 1)[0]),
                    "cancellation_lead_days": cancel_lead,
                    "cancellation_fee_jpy": fee,
                    "refund_amount_jpy": refund,
                    "refund_status": str(rng.choice(["processed", "pending", "denied"], p=[0.85, 0.12, 0.03])),
                    "loaded_at": _utc_now_ts(),
                }
            )

        # itinerary items
        # flights (1 outbound, 1 return for outbound bookings; 1 round for domestic if bigger)
        flight_pool = flights_jp_to_intl if dest_type == "outbound" else flights_jp_dom
        if not flight_pool.empty:
            flight_pick_count = 2 if dest_type == "outbound" else int(rng.integers(0, 2))
            for _ in range(flight_pick_count):
                f_row = flight_pool.iloc[int(rng.integers(0, len(flight_pool)))]
                itinerary_rows.append(
                    {
                        "itinerary_item_id": str(uuid.uuid4()),
                        "booking_id": booking_id,
                        "item_type": "flight",
                        "item_name": f"{f_row['airline_name']} {f_row['route_label']} ({f_row['flight_class']})",
                        "hotel_id": None,
                        "flight_id": f_row["flight_id"],
                        "start_date": dep_date,
                        "end_date": return_date_v,
                        "nights": None,
                        "unit_price_jpy": int(rng.integers(20_000, 250_000) if dest_type == "outbound" else rng.integers(15_000, 60_000)),
                        "quantity": pax,
                        "total_price_jpy": 0,
                        "loaded_at": _utc_now_ts(),
                    }
                )

        hotels_in_region = hotels_by_region.get(region) or list(hotels_df.itertuples())[:5]
        if hotels_in_region:
            h_row = hotels_in_region[int(rng.integers(0, len(hotels_in_region)))]
            h_row = h_row if isinstance(h_row, pd.Series) else hotels_df.iloc[int(rng.integers(0, len(hotels_df)))]
            nights = max(1, duration - 1)
            unit = int(h_row["avg_price_per_night_jpy"])
            itinerary_rows.append(
                {
                    "itinerary_item_id": str(uuid.uuid4()),
                    "booking_id": booking_id,
                    "item_type": "hotel",
                    "item_name": str(h_row["name"]),
                    "hotel_id": str(h_row["hotel_id"]),
                    "flight_id": None,
                    "start_date": dep_date,
                    "end_date": return_date_v,
                    "nights": nights,
                    "unit_price_jpy": unit,
                    "quantity": nights,
                    "total_price_jpy": unit * nights,
                    "loaded_at": _utc_now_ts(),
                }
            )

        # 1-3 activities
        activity_count = int(rng.integers(0, 4))
        for _ in range(activity_count):
            itinerary_rows.append(
                {
                    "itinerary_item_id": str(uuid.uuid4()),
                    "booking_id": booking_id,
                    "item_type": "activity",
                    "item_name": _make_activity_name(rng, region),
                    "hotel_id": None,
                    "flight_id": None,
                    "start_date": dep_date + timedelta(days=int(rng.integers(0, max(1, duration - 1)))),
                    "end_date": dep_date + timedelta(days=int(rng.integers(0, max(1, duration - 1)))),
                    "nights": None,
                    "unit_price_jpy": int(rng.integers(2_000, 25_000)),
                    "quantity": pax,
                    "total_price_jpy": 0,
                    "loaded_at": _utc_now_ts(),
                }
            )

        # tour_review
        if status == "completed" and rng.random() < seeds["review_rate"]["rate"]:
            rating = int(_weighted_choice(rng, rating_dist, 1)[0])
            sentiment = "positive" if rating >= 4 else ("neutral" if rating == 3 else "negative")
            comment = _make_review_comment(rng, region, sentiment)
            review_rows.append(
                {
                    "review_id": str(uuid.uuid4()),
                    "booking_id": booking_id,
                    "customer_id": cust_id,
                    "plan_name": booking_rows[-1]["plan_name"],
                    "destination_region": region,
                    "rating": rating,
                    "nps": _rating_to_nps(rating, rng),
                    "comment": comment,
                    "comment_summary": None,
                    "sentiment": sentiment,
                    "review_date": min(END_DATE, return_date_v + timedelta(days=int(rng.integers(1, 30)))),
                    "loaded_at": _utc_now_ts(),
                }
            )

    # write back redemption counts onto campaigns
    if "total_redemptions" in campaigns_df.columns:
        campaigns_df["total_redemptions"] = campaigns_df["campaign_id"].map(lambda c: redemption_count.get(c, 0)).astype(int)

    # finalize itinerary total_price
    itin_df = pd.DataFrame(itinerary_rows)
    if not itin_df.empty:
        itin_df["total_price_jpy"] = (itin_df["unit_price_jpy"].fillna(0).astype(int) * itin_df["quantity"].fillna(0).astype(int)).astype(int)
        itin_df.loc[itin_df["item_type"] == "hotel", "total_price_jpy"] = (
            itin_df.loc[itin_df["item_type"] == "hotel", "unit_price_jpy"].astype(int)
            * itin_df.loc[itin_df["item_type"] == "hotel", "nights"].fillna(1).astype(int)
        )

    return (
        pd.DataFrame(booking_rows),
        pd.DataFrame(payment_rows),
        pd.DataFrame(cancellation_rows),
        itin_df,
        pd.DataFrame(review_rows),
    )


def _rating_to_nps(rating: int, rng: np.random.Generator) -> int:
    if rating >= 5:
        return int(rng.integers(80, 101))
    if rating == 4:
        return int(rng.integers(40, 80))
    if rating == 3:
        return int(rng.integers(-20, 40))
    if rating == 2:
        return int(rng.integers(-60, -20))
    return int(rng.integers(-100, -60))


def _make_plan_name(rng: np.random.Generator, region: str, season: str, segment: str, dest_type: str) -> str:
    season_label = {
        "spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬",
        "gw": "GW", "obon": "夏休み", "new_year": "年末年始",
    }[season]
    seg_label = {
        "family": "ファミリー", "couple": "カップル", "solo": "ひとり旅", "group": "グループ",
        "senior": "シニア", "student": "学生", "business": "ビジネス",
    }[segment]
    nights = int(rng.integers(2, 7))
    if dest_type == "domestic":
        return f"{region}{nights}泊{nights + 1}日{seg_label}プラン ({season_label})"
    if dest_type == "outbound":
        return f"{region}周遊{nights}泊{nights + 1}日{seg_label}向け ({season_label})"
    return f"訪日{region}体験{nights}泊{nights + 1}日 ({season_label})"


def _make_activity_name(rng: np.random.Generator, region: str) -> str:
    activities = {
        "沖縄": ["美ら海水族館", "シュノーケリング", "古宇利島ドライブ", "国際通り散策"],
        "北海道": ["小樽運河クルーズ", "アイヌ文化体験", "ファーム見学", "ウィンターアクティビティ"],
        "京都": ["金閣寺拝観", "嵐山竹林散策", "和菓子作り体験", "舞妓見学"],
        "ハワイ": ["ダイヤモンドヘッド登山", "ノースショアサーフィン", "ルアウディナー", "サンセットクルーズ"],
        "パリ": ["ルーヴル美術館", "セーヌ川クルーズ", "モンマルトル散策", "エッフェル塔展望"],
    }
    options = activities.get(region, ["市内観光ツアー", "現地ガイドツアー", "ローカル料理体験"])
    return str(rng.choice(options))


def _make_review_comment(rng: np.random.Generator, region: str, sentiment: str) -> str:
    pos = [
        f"{region}は本当に素晴らしかったです。スタッフの対応も丁寧で安心して楽しめました。",
        "子どもが大はしゃぎ。家族の思い出に最高のプランでした。",
        "ガイドさんが親切で現地のおすすめスポットも教えてくれました。",
        f"{region}のホテルが特に良かったです。また利用したい。",
    ]
    neu = [
        "概ね満足ですが、移動が少し慌ただしかったです。",
        "良い旅行でしたが、食事のバリエーションがもう少しあると嬉しいです。",
    ]
    neg = [
        "予約の変更がしにくかった点が残念。",
        "ホテルの設備が古く、写真と少しイメージが違いました。",
        "現地スタッフとの連絡が取りづらく、不安になりました。",
    ]
    pool = {"positive": pos, "neutral": neu, "negative": neg}[sentiment]
    return str(rng.choice(pool))


# ---------------------------------------------------------------------------
# inquiry
# ---------------------------------------------------------------------------


def generate_inquiries(config: GenerationConfig, seeds: dict[str, Any], rng: np.random.Generator, customers_df: pd.DataFrame, fake: Faker) -> pd.DataFrame:
    n = config.inquiry_count
    customer_ids = customers_df["customer_id"].to_numpy()
    rows = []
    for i in range(n):
        cust_id = str(rng.choice(customer_ids)) if rng.random() < 0.85 else None
        received = datetime.combine(START_DATE + timedelta(days=int(rng.integers(0, (END_DATE - START_DATE).days))), datetime.min.time(), tzinfo=timezone.utc)
        resolved = received + timedelta(minutes=int(rng.integers(5, 1500))) if rng.random() < 0.92 else None
        rows.append(
            {
                "inquiry_id": str(uuid.uuid4()),
                "customer_id": cust_id,
                "channel": str(rng.choice(["web_form", "tel", "email", "chat", "store", "social"], p=[0.30, 0.25, 0.18, 0.12, 0.10, 0.05])),
                "inquiry_type": str(rng.choice(["pre_booking_question", "change_request", "complaint", "lost_item", "refund_request", "info_request"], p=[0.32, 0.22, 0.10, 0.04, 0.12, 0.20])),
                "subject": fake.sentence(nb_words=6).replace(".", "")[:120],
                "body": fake.paragraph(nb_sentences=3)[:500],
                "received_at": received,
                "resolved_at": resolved,
                "resolution_minutes": int((resolved - received).total_seconds() / 60) if resolved else None,
                "csat": int(_weighted_choice(rng, seeds["csat_distribution"], 1)[0]) if resolved else None,
                "assigned_team": str(rng.choice(["cs_domestic", "cs_outbound", "cs_corp"], p=[0.55, 0.35, 0.10])),
                "loaded_at": _utc_now_ts(),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------


def generate_all(config: GenerationConfig, output_dir: Path, sample_dir: Path) -> None:
    seeds = _load_seeds()
    rng = np.random.default_rng(config.seed)
    fake = Faker("ja_JP")
    Faker.seed(config.seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating customers (%d rows)...", config.customers)
    customers_df = generate_customers(config, seeds, rng, fake)

    logger.info("Generating hotels (%d rows)...", config.hotels)
    hotels_df = generate_hotels(config, seeds, rng, fake)

    logger.info("Generating flights (%d rows)...", config.flights)
    flights_df = generate_flights(config, seeds, rng)

    logger.info("Generating campaigns (%d rows)...", config.campaigns)
    campaigns_df = generate_campaigns(config, seeds, rng)

    logger.info("Generating bookings + payments + cancellations + itinerary + reviews (%d bookings)...", config.bookings)
    bookings_df, payments_df, cancellations_df, itinerary_df, reviews_df = generate_bookings_and_dependents(
        config, seeds, rng, customers_df, campaigns_df, hotels_df, flights_df
    )

    logger.info("Generating inquiries (%d rows)...", config.inquiry_count)
    inquiries_df = generate_inquiries(config, seeds, rng, customers_df, fake)

    tables: dict[str, pd.DataFrame] = {
        "customer": customers_df,
        "hotel": hotels_df,
        "flight": flights_df,
        "campaign": campaigns_df,
        "booking": bookings_df,
        "payment": payments_df,
        "cancellation": cancellations_df,
        "itinerary_item": itinerary_df,
        "tour_review": reviews_df,
        "inquiry": inquiries_df,
    }

    summary: list[dict[str, Any]] = []
    for name, df in tables.items():
        out = output_dir / f"{name}.parquet"
        df.to_parquet(out, index=False, engine="pyarrow")
        sample_path = sample_dir / f"{name}_sample.csv"
        df.head(50).to_csv(sample_path, index=False, encoding="utf-8-sig")
        summary.append({"table": name, "rows": len(df), "parquet": str(out.resolve()), "sample": str(sample_path.resolve())})
        logger.info("  -> %s: %d rows -> %s", name, len(df), out)

    summary_path = output_dir / "generation_summary.json"
    summary_path.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "config": config.__dict__, "tables": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Summary -> %s", summary_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate hybrid seeded synthetic travel marketing dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--sample-dir", type=Path, default=Path(__file__).resolve().parent / "samples")
    parser.add_argument("--customers", type=int, default=10_000)
    parser.add_argument("--bookings", type=int, default=50_000)
    parser.add_argument("--inquiries", type=int, default=20_000)
    parser.add_argument("--hotels", type=int, default=500)
    parser.add_argument("--flights", type=int, default=2_000)
    parser.add_argument("--campaigns", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = GenerationConfig(
        customers=args.customers,
        bookings=args.bookings,
        inquiry_count=args.inquiries,
        hotels=args.hotels,
        flights=args.flights,
        campaigns=args.campaigns,
        seed=args.seed,
    )
    generate_all(config, args.output_dir, args.sample_dir)


if __name__ == "__main__":
    main()
