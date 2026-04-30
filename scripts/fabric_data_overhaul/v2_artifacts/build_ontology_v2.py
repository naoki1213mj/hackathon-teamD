"""Build travelIQ_v2 (Fabric IQ Ontology) and deploy via Fabric REST API.

Ontology JSON schema mirrors the v1 templates we extracted via getDefinition.
- Each EntityType has a numeric id and a list of properties (each with stable property id)
- Each EntityType has a DataBinding mapping the source column -> property id
- Each RelationshipType references source + target EntityType ids
- Each Contextualization binds the source/target keys to a Lakehouse table
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
LAKEHOUSE_V2_ID = "5e02348e-d2a4-47fb-b63d-257ed3be7731"
ONTOLOGY_NAME = "travelIQ_v2"
FABRIC_API = "https://api.fabric.microsoft.com"

OUT = Path(__file__).parent / "ontology"
OUT.mkdir(exist_ok=True)

# (id_offset, name, type, columns) — column type: 'String' / 'BigInt' / 'Double' / 'Boolean' / 'DateTime'
ENTITIES = [
    ("100000000001", "customer", [
        ("customer_id", "String"),
        ("customer_code", "String"),
        ("last_name_kana", "String"),
        ("first_name_kana", "String"),
        ("gender", "String"),
        ("age_band", "String"),
        ("birth_year", "BigInt"),
        ("customer_segment", "String"),
        ("loyalty_tier", "String"),
        ("acquisition_channel", "String"),
        ("prefecture", "String"),
        ("email_opt_in", "Boolean"),
        ("created_at", "DateTime"),
        ("updated_at", "DateTime"),
    ]),
    ("100000000002", "booking", [
        ("booking_id", "String"),
        ("booking_code", "String"),
        ("customer_id", "String"),
        ("campaign_id", "String"),
        ("plan_name", "String"),
        ("product_type", "String"),
        ("destination_country", "String"),
        ("destination_region", "String"),
        ("destination_city", "String"),
        ("destination_type", "String"),
        ("season", "String"),
        ("departure_date", "DateTime"),
        ("return_date", "DateTime"),
        ("duration_days", "BigInt"),
        ("pax", "BigInt"),
        ("pax_adult", "BigInt"),
        ("pax_child", "BigInt"),
        ("total_revenue_jpy", "BigInt"),
        ("price_per_person_jpy", "BigInt"),
        ("booking_date", "DateTime"),
        ("lead_time_days", "BigInt"),
        ("booking_status", "String"),
    ]),
    ("100000000003", "payment", [
        ("payment_id", "String"),
        ("booking_id", "String"),
        ("payment_method", "String"),
        ("payment_status", "String"),
        ("amount_jpy", "BigInt"),
        ("currency", "String"),
        ("exchange_rate_to_jpy", "Double"),
        ("paid_at", "DateTime"),
        ("installment_count", "BigInt"),
    ]),
    ("100000000004", "cancellation", [
        ("cancellation_id", "String"),
        ("booking_id", "String"),
        ("cancelled_at", "DateTime"),
        ("cancellation_reason", "String"),
        ("cancellation_lead_days", "BigInt"),
        ("cancellation_fee_jpy", "BigInt"),
        ("refund_amount_jpy", "BigInt"),
        ("refund_status", "String"),
    ]),
    ("100000000005", "itinerary_item", [
        ("itinerary_item_id", "String"),
        ("booking_id", "String"),
        ("item_type", "String"),
        ("item_name", "String"),
        ("hotel_id", "String"),
        ("flight_id", "String"),
        ("start_date", "DateTime"),
        ("end_date", "DateTime"),
        ("nights", "Double"),
        ("unit_price_jpy", "BigInt"),
        ("quantity", "BigInt"),
        ("total_price_jpy", "BigInt"),
    ]),
    ("100000000006", "hotel", [
        ("hotel_id", "String"),
        ("hotel_code", "String"),
        ("name", "String"),
        ("country", "String"),
        ("region", "String"),
        ("city", "String"),
        ("category", "String"),
        ("star_rating", "BigInt"),
        ("room_count", "BigInt"),
        ("avg_price_per_night_jpy", "BigInt"),
        ("latitude", "Double"),
        ("longitude", "Double"),
    ]),
    ("100000000007", "flight", [
        ("flight_id", "String"),
        ("airline_code", "String"),
        ("airline_name", "String"),
        ("departure_airport", "String"),
        ("arrival_airport", "String"),
        ("route_label", "String"),
        ("flight_class", "String"),
        ("distance_km", "BigInt"),
        ("avg_duration_min", "BigInt"),
    ]),
    ("100000000008", "tour_review", [
        ("review_id", "String"),
        ("booking_id", "String"),
        ("customer_id", "String"),
        ("plan_name", "String"),
        ("destination_region", "String"),
        ("rating", "BigInt"),
        ("nps", "BigInt"),
        ("comment", "String"),
        ("sentiment", "String"),
        ("review_date", "DateTime"),
    ]),
    ("100000000009", "campaign", [
        ("campaign_id", "String"),
        ("campaign_code", "String"),
        ("campaign_name", "String"),
        ("campaign_type", "String"),
        ("target_segment", "String"),
        ("target_destination_type", "String"),
        ("start_date", "DateTime"),
        ("end_date", "DateTime"),
        ("discount_percent", "Double"),
        ("total_budget_jpy", "BigInt"),
        ("total_redemptions", "BigInt"),
    ]),
    ("100000000010", "inquiry", [
        ("inquiry_id", "String"),
        ("customer_id", "String"),
        ("channel", "String"),
        ("inquiry_type", "String"),
        ("subject", "String"),
        ("body", "String"),
        ("received_at", "DateTime"),
        ("resolved_at", "DateTime"),
        ("resolution_minutes", "Double"),
        ("csat", "Double"),
        ("assigned_team", "String"),
    ]),
]

# Relationships: (from_entity_table, to_entity_table, name, source_key_col, target_key_col)
# Direction: from = MANY side, to = ONE side (e.g. booking_has_customer reads booking → customer)
RELATIONSHIPS = [
    ("booking", "customer", "booking_has_customer", "customer_id", "customer_id"),
    ("booking", "campaign", "booking_has_campaign", "campaign_id", "campaign_id"),
    ("payment", "booking", "payment_has_booking", "booking_id", "booking_id"),
    ("cancellation", "booking", "cancellation_has_booking", "booking_id", "booking_id"),
    ("tour_review", "booking", "tour_review_has_booking", "booking_id", "booking_id"),
    ("itinerary_item", "booking", "itinerary_item_has_booking", "booking_id", "booking_id"),
    ("itinerary_item", "hotel", "itinerary_item_has_hotel", "hotel_id", "hotel_id"),
    ("itinerary_item", "flight", "itinerary_item_has_flight", "flight_id", "flight_id"),
    ("inquiry", "customer", "inquiry_has_customer", "customer_id", "customer_id"),
]


def make_property_id(entity_id: str, idx: int) -> str:
    """Stable property id for an entity column. Format: <entity_id>_<idx> as a long-looking string."""
    return f"3{entity_id[1:]}{idx:04d}"


def collect_id_parts() -> dict[str, set[str]]:
    """Each entity's entityIdParts = its PK only. Relationships are encoded in
    contextualizations via dataBindingTable + source/target key columns in that table."""
    by_table = {name: cols for (_id, name, cols) in ENTITIES}
    return {n: {by_table[n][0][0]} for n in by_table}


def build_entity_files() -> dict[str, dict]:
    files: dict[str, dict] = {}
    entity_meta: dict[str, dict] = {}
    id_parts_by_table = collect_id_parts()

    for entity_id, name, cols in ENTITIES:
        # Property definitions
        properties = []
        prop_ids = {}
        for idx, (col_name, dtype) in enumerate(cols):
            pid = make_property_id(entity_id, idx)
            properties.append({
                "id": pid,
                "name": col_name,
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": dtype,
            })
            prop_ids[col_name] = pid
        # entityIdParts = PK + every FK col referenced by any relationship touching this entity
        id_part_cols = id_parts_by_table[name]
        # Maintain stable order: PK first, then by column position
        ordered = [c for c, _ in cols if c in id_part_cols]
        entity_id_parts = [prop_ids[c] for c in ordered]
        entity_def = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/entityType/1.0.0/schema.json",
            "id": entity_id,
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": name,
            "entityIdParts": entity_id_parts,
            "displayNamePropertyId": None,
            "namespaceType": "Imported",
            "visibility": "Visible",
            "properties": properties,
            "timeseriesProperties": [],
        }
        files[f"EntityTypes/{entity_id}/definition.json"] = entity_def

        # DataBinding
        binding_id = str(uuid.uuid4())
        prop_bindings = []
        for col_name, _dtype in cols:
            prop_bindings.append({
                "sourceColumnName": col_name,
                "targetPropertyId": prop_ids[col_name],
            })
        binding = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/dataBinding/1.0.0/schema.json",
            "id": binding_id,
            "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries",
                "propertyBindings": prop_bindings,
                "sourceTableProperties": {
                    "sourceType": "LakehouseTable",
                    "workspaceId": WORKSPACE_ID,
                    "itemId": LAKEHOUSE_V2_ID,
                    "sourceTableName": name,
                    "sourceSchema": "dbo",
                },
            },
        }
        files[f"EntityTypes/{entity_id}/DataBindings/{binding_id}.json"] = binding

        entity_meta[name] = {
            "id": entity_id,
            "prop_ids": prop_ids,
        }

    return files, entity_meta


def build_relationship_files(entity_meta) -> dict[str, dict]:
    files: dict[str, dict] = {}
    by_table = {name: cols for (_id, name, cols) in ENTITIES}

    for ix, (from_tbl, to_tbl, rel_name, src_col, tgt_col) in enumerate(RELATIONSHIPS):
        rel_id = f"31764998130711715{ix:02d}"  # stable-ish
        ctx_id = str(uuid.uuid4())

        from_meta = entity_meta[from_tbl]
        to_meta = entity_meta[to_tbl]

        # The FROM entity is the MANY side (e.g. booking → customer means a booking links to one customer).
        # dataBindingTable = FROM entity's physical table (contains both PK and FK columns).
        # sourceKeyRefBindings: from_table's own PK column → from entity's PK propId
        # targetKeyRefBindings: the FK column in from_table → target entity's PK propId
        from_pk = by_table[from_tbl][0][0]
        to_pk = by_table[to_tbl][0][0]

        rel_def = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/relationshipType/1.0.0/schema.json",
            "namespace": "usertypes",
            "id": rel_id,
            "name": rel_name,
            "namespaceType": "Imported",
            "source": {"entityTypeId": from_meta["id"]},
            "target": {"entityTypeId": to_meta["id"]},
        }
        files[f"RelationshipTypes/{rel_id}/definition.json"] = rel_def

        ctx = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/ontology/contextualization/1.0.0/schema.json",
            "id": ctx_id,
            "dataBindingTable": {
                "workspaceId": WORKSPACE_ID,
                "itemId": LAKEHOUSE_V2_ID,
                "sourceTableName": from_tbl,
                "sourceSchema": "dbo",
                "sourceType": "LakehouseTable",
            },
            "sourceKeyRefBindings": [{
                "sourceColumnName": from_pk,
                "targetPropertyId": from_meta["prop_ids"][from_pk],
            }],
            "targetKeyRefBindings": [{
                "sourceColumnName": src_col,  # the FK column in from_table
                "targetPropertyId": to_meta["prop_ids"][to_pk],
            }],
        }
        files[f"RelationshipTypes/{rel_id}/Contextualizations/{ctx_id}.json"] = ctx

    return files


def platform_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {
            "type": "Ontology",
            "displayName": ONTOLOGY_NAME,
        },
        "config": {
            "version": "2.0",
            "logicalId": "00000000-0000-0000-0000-000000000000",
        },
    }


def build_all() -> dict[str, str]:
    """Returns dict[path] -> JSON-string content."""
    entity_files, entity_meta = build_entity_files()
    rel_files = build_relationship_files(entity_meta)
    files = {**entity_files, **rel_files}
    files["definition.json"] = {}
    files[".platform"] = platform_json()

    out_strs: dict[str, str] = {}
    for path, payload in files.items():
        s = json.dumps(payload, indent=2, ensure_ascii=False)
        full = OUT / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(s, encoding="utf-8", newline="\n")
        out_strs[path] = s
    return out_strs


def get_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", FABRIC_API,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True, check=True
    )
    return r.stdout.strip()


def deploy(files: dict[str, str]) -> str:
    parts = []
    # Skip .platform — Fabric injects it from displayName/type during create
    for path, content in files.items():
        if path == ".platform":
            continue
        parts.append({
            "path": path,
            "payload": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "payloadType": "InlineBase64",
        })
    body = {
        "displayName": ONTOLOGY_NAME,
        "definition": {
            "parts": parts,
        },
    }
    t = get_token()
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/ontologies"
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
    files = build_all()
    print(f"Wrote {len(files)} files to {OUT}")
    if "--build-only" in sys.argv:
        return
    ont_id = deploy(files)
    print(f"\n✅ Created ontology {ONTOLOGY_NAME}: {ont_id}")
    Path(OUT / "_id.txt").write_text(ont_id, encoding="utf-8")


if __name__ == "__main__":
    main()
