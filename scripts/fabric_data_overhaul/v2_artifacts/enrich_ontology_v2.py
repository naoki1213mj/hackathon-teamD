"""travelIQ_v2 を非破壊的に強化するパッチ。

変更内容（Phase 10 / `da-ontology-enrichment`）:
- 全 10 EntityType に対して `displayNamePropertyId` を意味のある列の id に設定する。
  これは null のままだと NL2Ontology が PK (UUID) を表示列として推定してしまい、
  P01「ハワイの売上」で `RETURN booking_id, SUM(...) GROUP BY booking_id` のように
  PK でグルーピングする事故を起こしていた問題への構造的対策。

非変更:
- properties / timeseriesProperties / DataBindings / RelationshipTypes は手付かず。
- .platform は updateDefinition では送らない (LRO 規約)。

API:
- `POST /v1/workspaces/{ws}/ontologies/{id}/getDefinition` (既に audit/ 側で取得済)
- `POST /v1/workspaces/{ws}/ontologies/{id}/updateDefinition` で adopt
- 完了後、Direct Lake を再フレームするため `POST /datasets/{sm_id}/refreshes` を呼ぶ
  (audience: `https://analysis.windows.net/powerbi/api`)
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

WORKSPACE_ID = "096ff72a-6174-4aba-8f0c-140454fa6c3f"
ONTOLOGY_ID = "10cd6675-405a-4366-b91b-d57242a28914"
SEMANTIC_MODEL_ID = "ce2bb828-d850-46aa-bc5e-224ea9a60667"
FABRIC_API = "https://api.fabric.microsoft.com"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"

# (entity_id, entity_name) -> 表示用に最も自然な列名
DISPLAY_NAME_TARGETS: dict[str, tuple[str, str]] = {
    "100000000001": ("customer", "customer_code"),
    "100000000002": ("booking", "plan_name"),
    "100000000003": ("payment", "payment_id"),
    "100000000004": ("cancellation", "cancellation_id"),
    "100000000005": ("itinerary_item", "item_name"),
    "100000000006": ("hotel", "name"),
    "100000000007": ("flight", "route_label"),
    "100000000008": ("tour_review", "plan_name"),
    "100000000009": ("campaign", "campaign_name"),
    "100000000010": ("inquiry", "subject"),
}

ARTIFACT_DIR = Path(__file__).parent
SOURCE_FULL = ARTIFACT_DIR / "audit" / "ontology_v2_full.json"
PATCHED_PATH = ARTIFACT_DIR / "ontology_enriched_v2.json"


def get_token(resource: str) -> str:
    r = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", resource,
            "--query", "accessToken",
            "-o", "tsv",
        ],
        capture_output=True, text=True, shell=True, check=True,
    )
    return r.stdout.strip()


def build_patched_definition() -> dict:
    """元の definition の各 EntityType part を decode → displayNamePropertyId 設定 → encode しなおす。"""
    if not SOURCE_FULL.exists():
        raise SystemExit(f"missing source: {SOURCE_FULL}. Run audit/fetch_ontology_v2.py first.")
    raw = json.loads(SOURCE_FULL.read_text(encoding="utf-8"))
    new_parts: list[dict] = []
    modified: list[tuple[str, str, str]] = []
    for part in raw.get("definition", {}).get("parts", []):
        path = part.get("path") or ""
        # .platform は updateDefinition では送らない
        if path == ".platform":
            continue
        # 既存ルール: EntityType definition だけ書き換え
        if "EntityTypes/" in path and path.endswith("/definition.json"):
            payload_text = base64.b64decode(part["payload"]).decode("utf-8")
            obj = json.loads(payload_text)
            entity_id = obj.get("id")
            target = DISPLAY_NAME_TARGETS.get(entity_id)
            if target is not None:
                _name, target_col = target
                # 該当列の property id を探す (properties / timeseriesProperties 両方をスキャン)
                all_props = list(obj.get("properties") or []) + list(obj.get("timeseriesProperties") or [])
                match = next((p for p in all_props if p.get("name") == target_col), None)
                if match is None:
                    raise SystemExit(
                        f"{entity_id}: target column {target_col!r} not found among {[p.get('name') for p in all_props]}"
                    )
                old_display = obj.get("displayNamePropertyId")
                obj["displayNamePropertyId"] = match["id"]
                modified.append((entity_id, target_col, str(old_display)))
                payload_text = json.dumps(obj, ensure_ascii=False)
            new_payload = base64.b64encode(payload_text.encode("utf-8")).decode("ascii")
            new_parts.append({"path": path, "payload": new_payload, "payloadType": part.get("payloadType", "InlineBase64")})
            continue
        # それ以外はそのまま追加
        new_parts.append({"path": path, "payload": part["payload"], "payloadType": part.get("payloadType", "InlineBase64")})

    body = {"definition": {"parts": new_parts}}
    PATCHED_PATH.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"patched body -> {PATCHED_PATH}")
    print(f"modified entities ({len(modified)}):")
    for eid, col, old in modified:
        print(f"  {eid} displayNamePropertyId: {old} -> {col}")
    if len(modified) != len(DISPLAY_NAME_TARGETS):
        raise SystemExit(f"expected {len(DISPLAY_NAME_TARGETS)} updates, got {len(modified)}")
    return body


def update_ontology(body: dict) -> None:
    token = get_token(FABRIC_API)
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/ontologies/{ONTOLOGY_ID}/updateDefinition"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"POST {url}")
    r = requests.post(url, headers=headers, json=body, timeout=120)
    print(f"  HTTP {r.status_code}")
    if r.status_code in (200, 201):
        print("  immediate success")
        return
    if r.status_code != 202:
        raise SystemExit(f"updateDefinition failed: {r.status_code} body={r.text[:1000]}")
    location = r.headers["Location"]
    print(f"  LRO: {location}")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        rr = requests.get(location, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if rr.status_code != 200:
            print(f"  poll status={rr.status_code} body={rr.text[:200]}")
            continue
        body_resp = rr.json()
        st = body_resp.get("status")
        print(f"  status={st}")
        if st == "Succeeded":
            return
        if st in ("Failed", "Cancelled"):
            raise SystemExit(f"LRO terminal: {body_resp}")
    raise SystemExit("LRO timeout")


def refresh_semantic_model() -> None:
    """Direct Lake 再フレームのため SM を transactional refresh する。"""
    token = get_token("https://analysis.windows.net/powerbi/api")
    url = f"{POWERBI_API}/datasets/{SEMANTIC_MODEL_ID}/refreshes"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"type": "automatic", "commitMode": "transactional"}
    print(f"POST {url}")
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"  HTTP {r.status_code}")
    if r.status_code in (200, 202):
        loc = r.headers.get("Location") or r.headers.get("RequestId")
        print(f"  refresh accepted (location/id={loc})")
        return
    print(f"  body: {r.text[:1000]}")
    raise SystemExit(f"refresh failed: {r.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true", help="生成のみで API 呼び出しはしない")
    parser.add_argument("--skip-refresh", action="store_true", help="SM refresh をスキップ")
    args = parser.parse_args()

    body = build_patched_definition()
    if args.build_only:
        return 0
    update_ontology(body)
    print("\n✅ ontology updateDefinition succeeded")
    if not args.skip_refresh:
        try:
            refresh_semantic_model()
        except SystemExit as ex:
            # Refresh は ベストエフォート: ログだけ残して終了コード 0 にする
            print(f"⚠️ semantic model refresh failed: {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
