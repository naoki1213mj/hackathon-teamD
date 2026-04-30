"""Build travel_SM_v2 (Direct Lake semantic model) TMDL definition.

Generates all TMDL files locally for inspection, then deploys via Fabric REST API.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests

# ---- Constants -----------------------------------------------------------

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
LAKEHOUSE_V2_ID = "5e02348e-d2a4-47fb-b63d-257ed3be7731"
SEMANTIC_MODEL_NAME = "travel_SM_v2"
FABRIC_API = "https://api.fabric.microsoft.com"

OUT = Path(__file__).parent / "tmdl"
OUT.mkdir(exist_ok=True)


# ---- Schema (mirrors v2 lakehouse columns verified via INFORMATION_SCHEMA) -

# (column_name, dataType, summarizeBy, formatString, isHidden)
CUSTOMER_COLS = [
    ("customer_id", "string", "none", None, True),
    ("customer_code", "string", "none", None, False),
    ("last_name_kana", "string", "none", None, False),
    ("first_name_kana", "string", "none", None, False),
    ("gender", "string", "none", None, False),
    ("age_band", "string", "none", None, False),
    ("birth_year", "int64", "none", "0", False),
    ("customer_segment", "string", "none", None, False),
    ("loyalty_tier", "string", "none", None, False),
    ("acquisition_channel", "string", "none", None, False),
    ("prefecture", "string", "none", None, False),
    ("email_opt_in", "boolean", "none", None, False),
    ("created_at", "dateTime", "none", "General Date", False),
    ("updated_at", "dateTime", "none", "General Date", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

BOOKING_COLS = [
    ("booking_id", "string", "none", None, True),
    ("booking_code", "string", "none", None, False),
    ("customer_id", "string", "none", None, True),
    ("campaign_id", "string", "none", None, True),
    ("plan_name", "string", "none", None, False),
    ("product_type", "string", "none", None, False),
    ("destination_country", "string", "none", None, False),
    ("destination_region", "string", "none", None, False),
    ("destination_city", "string", "none", None, False),
    ("destination_type", "string", "none", None, False),
    ("season", "string", "none", None, False),
    ("departure_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("return_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("duration_days", "int64", "sum", "0", False),
    ("pax", "int64", "sum", "0", False),
    ("pax_adult", "int64", "sum", "0", False),
    ("pax_child", "int64", "sum", "0", False),
    ("total_revenue_jpy", "int64", "sum", "#,0", False),
    ("price_per_person_jpy", "int64", "average", "#,0", False),
    ("booking_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("lead_time_days", "int64", "average", "0", False),
    ("booking_status", "string", "none", None, False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

PAYMENT_COLS = [
    ("payment_id", "string", "none", None, True),
    ("booking_id", "string", "none", None, True),
    ("payment_method", "string", "none", None, False),
    ("payment_status", "string", "none", None, False),
    ("amount_jpy", "int64", "sum", "0", False),
    ("currency", "string", "none", None, False),
    ("exchange_rate_to_jpy", "double", "average", "0.0000", False),
    ("paid_at", "dateTime", "none", "General Date", False),
    ("installment_count", "int64", "sum", "0", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

CANCELLATION_COLS = [
    ("cancellation_id", "string", "none", None, True),
    ("booking_id", "string", "none", None, True),
    ("cancelled_at", "dateTime", "none", "General Date", False),
    ("cancellation_reason", "string", "none", None, False),
    ("cancellation_lead_days", "int64", "average", "0", False),
    ("cancellation_fee_jpy", "int64", "sum", "0", False),
    ("refund_amount_jpy", "int64", "sum", "0", False),
    ("refund_status", "string", "none", None, False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

ITINERARY_ITEM_COLS = [
    ("itinerary_item_id", "string", "none", None, True),
    ("booking_id", "string", "none", None, True),
    ("item_type", "string", "none", None, False),
    ("item_name", "string", "none", None, False),
    ("hotel_id", "string", "none", None, True),
    ("flight_id", "string", "none", None, True),
    ("start_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("end_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("nights", "double", "sum", "0", False),
    ("unit_price_jpy", "int64", "sum", "0", False),
    ("quantity", "int64", "sum", "0", False),
    ("total_price_jpy", "int64", "sum", "0", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

HOTEL_COLS = [
    ("hotel_id", "string", "none", None, True),
    ("hotel_code", "string", "none", None, False),
    ("name", "string", "none", None, False),
    ("country", "string", "none", None, False),
    ("region", "string", "none", None, False),
    ("city", "string", "none", None, False),
    ("category", "string", "none", None, False),
    ("star_rating", "int64", "average", "0", False),
    ("room_count", "int64", "sum", "0", False),
    ("avg_price_per_night_jpy", "int64", "average", "0", False),
    ("latitude", "double", "none", "0.0000", False),
    ("longitude", "double", "none", "0.0000", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

FLIGHT_COLS = [
    ("flight_id", "string", "none", None, True),
    ("airline_code", "string", "none", None, False),
    ("airline_name", "string", "none", None, False),
    ("departure_airport", "string", "none", None, False),
    ("arrival_airport", "string", "none", None, False),
    ("route_label", "string", "none", None, False),
    ("flight_class", "string", "none", None, False),
    ("distance_km", "int64", "sum", "0", False),
    ("avg_duration_min", "int64", "average", "0", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

TOUR_REVIEW_COLS = [
    ("review_id", "string", "none", None, True),
    ("booking_id", "string", "none", None, True),
    ("customer_id", "string", "none", None, True),
    ("plan_name", "string", "none", None, False),
    ("destination_region", "string", "none", None, False),
    ("rating", "int64", "average", "0", False),
    ("nps", "int64", "average", "0", False),
    ("comment", "string", "none", None, False),
    ("comment_summary", "int64", "none", "0", True),
    ("sentiment", "string", "none", None, False),
    ("review_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

CAMPAIGN_COLS = [
    ("campaign_id", "string", "none", None, True),
    ("campaign_code", "string", "none", None, False),
    ("campaign_name", "string", "none", None, False),
    ("campaign_type", "string", "none", None, False),
    ("target_segment", "string", "none", None, False),
    ("target_destination_type", "string", "none", None, False),
    ("start_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("end_date", "dateTime", "none", "yyyy-MM-dd", False),
    ("discount_percent", "double", "average", "0.00", False),
    ("total_budget_jpy", "int64", "sum", "0", False),
    ("total_redemptions", "int64", "sum", "0", False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

INQUIRY_COLS = [
    ("inquiry_id", "string", "none", None, True),
    ("customer_id", "string", "none", None, True),
    ("channel", "string", "none", None, False),
    ("inquiry_type", "string", "none", None, False),
    ("subject", "string", "none", None, False),
    ("body", "string", "none", None, False),
    ("received_at", "dateTime", "none", "General Date", False),
    ("resolved_at", "dateTime", "none", "General Date", False),
    ("resolution_minutes", "double", "average", "0", False),
    ("csat", "double", "average", "0.00", False),
    ("assigned_team", "string", "none", None, False),
    ("loaded_at", "dateTime", "none", "General Date", True),
]

TABLES = {
    "customer": CUSTOMER_COLS,
    "booking": BOOKING_COLS,
    "payment": PAYMENT_COLS,
    "cancellation": CANCELLATION_COLS,
    "itinerary_item": ITINERARY_ITEM_COLS,
    "hotel": HOTEL_COLS,
    "flight": FLIGHT_COLS,
    "tour_review": TOUR_REVIEW_COLS,
    "campaign": CAMPAIGN_COLS,
    "inquiry": INQUIRY_COLS,
}

# ---- Measures (12) - all on `booking` except AvgRating on tour_review -----

JPY_FMT = '"#,0"'
PCT_FMT = '"0.00%;-0.00%;0.00%"'

# (name, table, dax_lines, formatString, displayFolder)
MEASURES = [
    ("TotalRevenue", "booking",
     ['CALCULATE(',
      '\tSUM(booking[total_revenue_jpy]),',
      '\tbooking[booking_status] IN { "confirmed", "completed" }',
      ')'],
     JPY_FMT, "01_Revenue"),

    ("BookingCount", "booking",
     ['COUNTROWS(booking)'],
     "#,0", "02_Volume"),

    ("ActiveCustomerCount", "booking",
     ['DISTINCTCOUNT(booking[customer_id])'],
     "#,0", "02_Volume"),

    ("RepeatCustomerRate", "booking",
     ['VAR _BookingsPerCustomer =',
      '\tADDCOLUMNS(',
      '\t\tVALUES(booking[customer_id]),',
      '\t\t"BookingsForCustomer", CALCULATE(COUNTROWS(booking))',
      '\t)',
      'VAR _Repeat =',
      '\tCOUNTROWS(FILTER(_BookingsPerCustomer, [BookingsForCustomer] > 1))',
      'VAR _Total = DISTINCTCOUNT(booking[customer_id])',
      'RETURN DIVIDE(_Repeat, _Total)'],
     PCT_FMT, "03_Customer"),

    ("AvgPricePerPerson", "booking",
     ['AVERAGE(booking[price_per_person_jpy])'],
     JPY_FMT, "01_Revenue"),

    ("CancellationRate", "booking",
     ['DIVIDE(',
      '\tCALCULATE(COUNTROWS(booking), booking[booking_status] = "cancelled"),',
      '\tCOUNTROWS(booking)',
      ')'],
     PCT_FMT, "04_Operations"),

    ("ReviewRate", "booking",
     ['DIVIDE(',
      '\tDISTINCTCOUNT(tour_review[booking_id]),',
      '\tCOUNTROWS(booking)',
      ')'],
     PCT_FMT, "05_Quality"),

    ("AvgRating", "tour_review",
     ['AVERAGE(tour_review[rating])'],
     "0.00", "05_Quality"),

    ("InboundRevenueShare", "booking",
     ['DIVIDE(',
      '\tCALCULATE(SUM(booking[total_revenue_jpy]), booking[destination_type] = "inbound"),',
      '\tSUM(booking[total_revenue_jpy])',
      ')'],
     PCT_FMT, "06_Mix"),

    ("CampaignROI", "booking",
     ['VAR _Revenue =',
      '\tCALCULATE(',
      '\t\tSUM(booking[total_revenue_jpy]),',
      '\t\tNOT ISBLANK(booking[campaign_id])',
      '\t)',
      'VAR _Budget = SUM(campaign[total_budget_jpy])',
      'RETURN DIVIDE(_Revenue - _Budget, _Budget)'],
     PCT_FMT, "07_Campaign"),

    ("RevenueExchangeAdjustedJPY", "booking",
     ['SUMX(',
      '\tpayment,',
      '\tpayment[amount_jpy] * payment[exchange_rate_to_jpy]',
      ')'],
     JPY_FMT, "01_Revenue"),

    ("AvgLeadTimeDays", "booking",
     ['AVERAGE(booking[lead_time_days])'],
     "0.0", "04_Operations"),
]


# ---- Hierarchies (4) ------------------------------------------------------
# (name, table, levels=[(level_name, column_name)])
HIERARCHIES = [
    ("DateHierarchy", "booking",
     [("Year", "departure_date"),
      ("BookingDate", "booking_date")]),

    ("GeographyHierarchy", "booking",
     [("Country", "destination_country"),
      ("Region", "destination_region"),
      ("City", "destination_city")]),

    ("CustomerHierarchy", "customer",
     [("Segment", "customer_segment"),
      ("AgeBand", "age_band"),
      ("LoyaltyTier", "loyalty_tier")]),

    ("ProductHierarchy", "booking",
     [("ProductType", "product_type"),
      ("PlanName", "plan_name")]),
]


# ---- Relationships (9) ----------------------------------------------------
# (from_table.col, to_table.col, [optional_kwargs])  — single direction by default
RELATIONSHIPS = [
    ("customer.customer_id", "booking.customer_id", {}),
    ("campaign.campaign_id", "booking.campaign_id", {}),
    ("booking.booking_id", "payment.booking_id", {}),
    ("booking.booking_id", "cancellation.booking_id", {}),
    ("booking.booking_id", "tour_review.booking_id", {}),
    ("booking.booking_id", "itinerary_item.booking_id", {}),
    ("hotel.hotel_id", "itinerary_item.hotel_id", {}),
    ("flight.flight_id", "itinerary_item.flight_id", {}),
    ("customer.customer_id", "inquiry.customer_id", {}),
]


# ---- TMDL generation ------------------------------------------------------

def tmdl_table(table_name: str, cols, measures_for_table, hierarchies_for_table) -> str:
    """Generate one table's TMDL. Tab indented. Measures BEFORE columns."""
    lines = [f"table {table_name}"]
    lines.append(f"\tsourceLineageTag: [dbo].[{table_name}]")
    lines.append("")

    # Measures first
    for m_name, m_tbl, m_dax, m_fmt, m_folder in measures_for_table:
        lines.append(f"\tmeasure {m_name} = ```")
        for dl in m_dax:
            lines.append(f"\t\t{dl}")
        lines.append("\t\t```")
        if m_fmt:
            # Multi-line formatString needs special handling, but ours is single-line
            lines.append(f"\t\tformatString: {m_fmt}")
        if m_folder:
            lines.append(f"\t\tdisplayFolder: {m_folder}")
        lines.append("")

    # Columns
    for col_name, dtype, sumby, fmt, hidden in cols:
        is_key = col_name == f"{table_name}_id"
        lines.append(f"\tcolumn {col_name}")
        lines.append(f"\t\tdataType: {dtype}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        if is_key:
            lines.append("\t\tisKey")
        if hidden:
            lines.append("\t\tisHidden")
        lines.append(f"\t\tsummarizeBy: {sumby}")
        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append(f"\t\tsourceLineageTag: {col_name}")
        lines.append("")
        lines.append("\t\tannotation SummarizationSetBy = Automatic")
        lines.append("")

    # Hierarchies
    for h_name, h_tbl, h_levels in hierarchies_for_table:
        lines.append(f"\thierarchy '{h_name}'")
        for ix, (lvl_name, lvl_col) in enumerate(h_levels):
            lines.append(f"\t\tlevel {lvl_name}")
            lines.append(f"\t\t\tcolumn: {lvl_col}")
            if ix < len(h_levels) - 1:
                lines.append("")
        lines.append("")

    # Direct Lake partition
    lines.append(f"\tpartition {table_name} = entity")
    lines.append("\t\tmode: directLake")
    lines.append("\t\tsource")
    lines.append(f"\t\t\tentityName: {table_name}")
    lines.append("\t\t\tschemaName: dbo")
    lines.append("\t\t\texpressionSource: 'DL_Lakehouse'")
    lines.append("")

    return "\n".join(lines) + "\n"


def tmdl_relationships() -> str:
    """Generate relationships.tmdl. Single direction, m:1 (many on FK side)."""
    lines = []
    for from_ref, to_ref, kw in RELATIONSHIPS:
        rel_id = str(uuid.uuid4())
        # The FROM side carries the FK (many side); TO side is the PK (one side).
        # In TMDL: fromColumn = many.col, toColumn = one.col
        # Our spec is "one_side.pk -> many_side.fk" so swap to TMDL convention.
        # ie from_ref is the ONE side (PK), to_ref is the MANY side (FK)
        # TMDL relationship fromColumn must be the FK, toColumn must be the PK.
        many_table, many_col = to_ref.split(".")
        one_table, one_col = from_ref.split(".")
        lines.append(f"relationship {rel_id}")
        lines.append(f"\tfromColumn: {many_table}.{many_col}")
        lines.append(f"\ttoColumn: {one_table}.{one_col}")
        lines.append("")
    return "\n".join(lines) + "\n"


def tmdl_expressions() -> str:
    return f"""expression DL_Lakehouse =
\t\tlet
\t\t    Source = AzureStorage.DataLake("https://onelake.dfs.fabric.microsoft.com/{WORKSPACE_ID}/{LAKEHOUSE_V2_ID}", [HierarchicalNavigation=true])
\t\tin
\t\t    Source

\tannotation PBI_IncludeFutureArtifacts = False
"""


def tmdl_model() -> str:
    refs = "\n".join([f"ref table {t}" for t in TABLES])
    return f"""model Model
\tculture: ja-JP
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: ja-JP
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation PBI_QueryOrder = ["DL_Lakehouse"]

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = ["DirectLakeOnOneLakeInWeb","WebModelingEdit"]

{refs}
"""


def tmdl_database() -> str:
    return "database\n\tcompatibilityLevel: 1604\n"


def pbism_json() -> str:
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {
            "qnaEnabled": True
        }
    }, indent=2)


# ---- Build all files ------------------------------------------------------

def build():
    # Group measures and hierarchies per table
    measures_by_tbl = {t: [] for t in TABLES}
    for m in MEASURES:
        measures_by_tbl[m[1]].append(m)

    hier_by_tbl = {t: [] for t in TABLES}
    for h in HIERARCHIES:
        hier_by_tbl[h[1]].append(h)

    files: dict[str, str | bytes] = {}

    files["definition.pbism"] = pbism_json()
    files["definition/database.tmdl"] = tmdl_database()
    files["definition/model.tmdl"] = tmdl_model()
    files["definition/expressions.tmdl"] = tmdl_expressions()
    files["definition/relationships.tmdl"] = tmdl_relationships()

    for t, cols in TABLES.items():
        files[f"definition/tables/{t}.tmdl"] = tmdl_table(t, cols, measures_by_tbl[t], hier_by_tbl[t])

    # Write to disk for inspection
    for path, content in files.items():
        full = OUT / path
        full.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            full.write_text(content, encoding="utf-8", newline="\n")
        else:
            full.write_bytes(content)
    print(f"Wrote {len(files)} files to {OUT}")
    return files


# ---- Deploy ---------------------------------------------------------------

def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", FABRIC_API,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def deploy(files: dict[str, str | bytes], display_name: str) -> str:
    """createItemWithDefinition for SemanticModel. Returns the item id."""
    parts = []
    for path, content in files.items():
        if isinstance(content, str):
            content = content.encode("utf-8")
        parts.append({
            "path": path,
            "payload": base64.b64encode(content).decode("ascii"),
            "payloadType": "InlineBase64"
        })

    body = {
        "displayName": display_name,
        "type": "SemanticModel",
        "definition": {
            "parts": parts,
            "format": "TMDL"
        }
    }

    t = get_token()
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/items"
    print(f"POST {url} (parts={len(parts)})")
    r = requests.post(url, headers=h, json=body)
    print(f"  HTTP {r.status_code}")
    if r.status_code in (200, 201):
        item = r.json()
        return item["id"]
    elif r.status_code == 202:
        loc = r.headers.get("Location")
        print(f"  LRO Location: {loc}")
        return poll_lro(loc, t)
    else:
        print(f"  Body: {r.text[:2000]}")
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
                # GET on Location returns the item directly per Fabric LRO convention
                if "id" in d:
                    return d["id"]
                # else fetch /result
                rr = requests.get(loc + "/result", headers={"Authorization": f"Bearer {t}"})
                rj = rr.json()
                # createItemWithDefinition result has the item info
                return rj.get("id") or rj.get("itemId")
            if s in ("Failed", "Cancelled"):
                print(f"  body: {json.dumps(d, indent=2)[:2000]}")
                raise SystemExit(f"LRO terminal: {s}")
        time.sleep(3)
    raise SystemExit("LRO timeout")


def main():
    files = build()
    if "--build-only" in sys.argv:
        return
    item_id = deploy(files, SEMANTIC_MODEL_NAME)
    print(f"\n✅ Created semantic model {SEMANTIC_MODEL_NAME}: {item_id}")
    Path(OUT / "_id.txt").write_text(item_id, encoding="utf-8")


if __name__ == "__main__":
    main()
