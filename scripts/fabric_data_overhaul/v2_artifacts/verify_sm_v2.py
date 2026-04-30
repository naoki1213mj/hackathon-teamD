"""Verify travel_SM_v2 by running EVALUATE DAX via Power BI executeQueries API."""
import json
import subprocess
import sys

import requests

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
SM_ID = "ce2bb828-d850-46aa-bc5e-224ea9a60667"
PBI = "https://api.powerbi.com"
PBI_AUDIENCE = "https://analysis.windows.net/powerbi/api"


def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", PBI_AUDIENCE,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def exec_dax(t, query: str):
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    body = {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}
    url = f"{PBI}/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{SM_ID}/executeQueries"
    r = requests.post(url, headers=h, json=body, timeout=120)
    return r


def main():
    t = get_token()
    queries = [
        ("TotalRevenue", "EVALUATE ROW(\"v\", [TotalRevenue])"),
        ("BookingCount", "EVALUATE ROW(\"v\", [BookingCount])"),
        ("ActiveCustomerCount", "EVALUATE ROW(\"v\", [ActiveCustomerCount])"),
        ("RepeatCustomerRate", "EVALUATE ROW(\"v\", [RepeatCustomerRate])"),
        ("AvgPricePerPerson", "EVALUATE ROW(\"v\", [AvgPricePerPerson])"),
        ("CancellationRate", "EVALUATE ROW(\"v\", [CancellationRate])"),
        ("ReviewRate", "EVALUATE ROW(\"v\", [ReviewRate])"),
        ("AvgRating", "EVALUATE ROW(\"v\", [AvgRating])"),
        ("InboundRevenueShare", "EVALUATE ROW(\"v\", [InboundRevenueShare])"),
        ("CampaignROI", "EVALUATE ROW(\"v\", [CampaignROI])"),
        ("RevenueExchangeAdjustedJPY", "EVALUATE ROW(\"v\", [RevenueExchangeAdjustedJPY])"),
        ("AvgLeadTimeDays", "EVALUATE ROW(\"v\", [AvgLeadTimeDays])"),
        # Hierarchy / relationship sanity
        ("RevenueByDestType",
         "EVALUATE SUMMARIZECOLUMNS(booking[destination_type], \"Revenue\", [TotalRevenue], \"Bookings\", [BookingCount])"),
        ("BookingsByYear",
         "EVALUATE SUMMARIZECOLUMNS(YEAR(booking[booking_date]), \"Bookings\", [BookingCount])"),
        ("ReviewRateByRegion",
         "EVALUATE TOPN(5, SUMMARIZECOLUMNS(booking[destination_region], \"Bookings\", [BookingCount], \"Revenue\", [TotalRevenue]), [Revenue], DESC)"),
    ]
    print(f"Running {len(queries)} DAX checks against travel_SM_v2…\n")
    fails = 0
    for name, q in queries:
        r = exec_dax(t, q)
        if r.status_code == 200:
            data = r.json()
            try:
                tables = data["results"][0]["tables"]
                rows = tables[0].get("rows", [])
                print(f"✅ {name}")
                for row in rows[:8]:
                    print(f"     {json.dumps(row, ensure_ascii=False)}")
            except Exception as ex:
                print(f"⚠️  {name}: parse error {ex} — {json.dumps(data)[:300]}")
                fails += 1
        else:
            fails += 1
            print(f"❌ {name}: HTTP {r.status_code} — {r.text[:600]}")
    print(f"\n{'PASS' if fails == 0 else 'FAIL'}: {len(queries) - fails}/{len(queries)} checks succeeded")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
