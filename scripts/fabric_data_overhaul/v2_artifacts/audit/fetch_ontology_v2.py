"""travelIQ_v2 の getDefinition を呼び出し、全パートを decode してダンプする監査用スクリプト。

- 出力1: ontology_v2_full.json (Fabric REST のレスポンスそのもの, base64 含む)
- 出力2: ontology_v2_decoded.json (各 part を decode して構造解析しやすい形へ整形)
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
ONTOLOGY_ID = "10cd6675-405a-4366-b91b-d57242a28914"
FABRIC_API = "https://api.fabric.microsoft.com"

OUT_DIR = Path(__file__).parent
RAW_PATH = OUT_DIR / "ontology_v2_full.json"
DECODED_PATH = OUT_DIR / "ontology_v2_decoded.json"


def get_token() -> str:
    """az CLI から Fabric API 用の AAD トークンを取得する。"""
    r = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", FABRIC_API,
            "--query", "accessToken",
            "-o", "tsv",
        ],
        capture_output=True, text=True, shell=True, check=True,
    )
    return r.stdout.strip()


def call_get_definition(token: str) -> dict:
    """LRO 形式の getDefinition を呼んで結果を返す。"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/ontologies/{ONTOLOGY_ID}/getDefinition"
    r = requests.post(url, headers=headers, timeout=60)
    print(f"POST {url} -> {r.status_code}")
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code != 202:
        raise SystemExit(f"unexpected status: {r.status_code} body={r.text[:500]}")
    location = r.headers["Location"]
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(2)
        rr = requests.get(location, headers=headers, timeout=60)
        if rr.status_code != 200:
            print(f"  poll status={rr.status_code} body={rr.text[:200]}")
            continue
        body = rr.json()
        st = body.get("status")
        print(f"  status={st}")
        if st == "Succeeded":
            rrr = requests.get(location + "/result", headers=headers, timeout=60)
            rrr.raise_for_status()
            return rrr.json()
        if st in ("Failed", "Cancelled"):
            raise SystemExit(f"LRO terminal: {body}")
    raise SystemExit("LRO timeout")


def decode_parts(raw: dict) -> list[dict]:
    """definition.parts を decode して [path, kind, payload(parsed)] 形式に変換する。"""
    decoded: list[dict] = []
    for part in raw.get("definition", {}).get("parts", []):
        path = part.get("path")
        payload_b64 = part.get("payload", "")
        try:
            payload_bytes = base64.b64decode(payload_b64)
            payload_text = payload_bytes.decode("utf-8") if payload_bytes else ""
            payload_obj: object = json.loads(payload_text) if payload_text else {}
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as ex:
            payload_obj = {"_decode_error": str(ex), "_raw_b64_head": payload_b64[:80]}
        kind = "unknown"
        if "/EntityTypes/" in (path or "") and (path or "").endswith("/definition.json"):
            kind = "entityType"
        elif "/DataBindings/" in (path or ""):
            kind = "dataBinding"
        elif "/RelationshipTypes/" in (path or "") and (path or "").endswith("/definition.json"):
            kind = "relationshipType"
        elif "/Contextualizations/" in (path or ""):
            kind = "contextualization"
        elif path == "definition.json":
            kind = "rootDefinition"
        elif path == ".platform":
            kind = "platform"
        decoded.append({"path": path, "kind": kind, "payload": payload_obj})
    return decoded


def main() -> int:
    token = get_token()
    raw = call_get_definition(token)
    RAW_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"raw definition saved -> {RAW_PATH}")
    decoded = decode_parts(raw)
    DECODED_PATH.write_text(
        json.dumps(decoded, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"decoded {len(decoded)} parts -> {DECODED_PATH}")
    counts: dict[str, int] = {}
    for p in decoded:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
    print("part kinds:")
    for k, v in sorted(counts.items()):
        print(f"  {k:24s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
