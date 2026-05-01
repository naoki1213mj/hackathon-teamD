"""Travel_Ontology_DA_v2 の現行 definition を取得し、JSON / 各 part を decode して保存する。

Phase 10 の monstre tune の前にバックアップを取得することが目的。
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
DA_ID = "b85b67a4-bac4-4852-95e1-443c02032844"
FABRIC_API = "https://api.fabric.microsoft.com"

OUT_DIR = Path(__file__).parent
RAW_PATH = OUT_DIR / "agent_definition_v2_full.json"
DECODED_PATH = OUT_DIR / "agent_definition_v2_decoded.json"
BACKUP_PATH = (OUT_DIR / ".." / "backups" / "agent_definition_pre_tune.json").resolve()


def get_token() -> str:
    r = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", FABRIC_API,
            "--query", "accessToken", "-o", "tsv",
        ],
        capture_output=True, text=True, shell=True, check=True,
    )
    return r.stdout.strip()


def fetch_definition(token: str) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    url = f"{FABRIC_API}/v1/workspaces/{WORKSPACE_ID}/dataAgents/{DA_ID}/getDefinition"
    r = requests.post(url, headers=h, timeout=60)
    print(f"POST {url} -> {r.status_code}")
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code != 202:
        raise SystemExit(f"unexpected: {r.status_code} body={r.text[:500]}")
    location = r.headers["Location"]
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(2)
        rr = requests.get(location, headers=h, timeout=60)
        if rr.status_code == 200:
            body = rr.json()
            st = body.get("status")
            print(f"  status={st}")
            if st == "Succeeded":
                rrr = requests.get(location + "/result", headers=h, timeout=60)
                rrr.raise_for_status()
                return rrr.json()
            if st in ("Failed", "Cancelled"):
                raise SystemExit(f"LRO terminal: {body}")
    raise SystemExit("LRO timeout")


def decode_parts(raw: dict) -> list[dict]:
    decoded: list[dict] = []
    for part in raw.get("definition", {}).get("parts", []):
        path = part.get("path")
        payload_b64 = part.get("payload", "")
        text = ""
        try:
            payload_bytes = base64.b64decode(payload_b64)
            text = payload_bytes.decode("utf-8") if payload_bytes else ""
        except (UnicodeDecodeError, ValueError) as ex:
            decoded.append({"path": path, "payload_decode_error": str(ex)})
            continue
        # JSON だったら parse、そうでなければ生 text を残す
        payload_obj: object
        if text.lstrip().startswith(("{", "[")):
            try:
                payload_obj = json.loads(text)
            except json.JSONDecodeError:
                payload_obj = {"_text": text}
        else:
            payload_obj = {"_text": text}
        decoded.append({"path": path, "payload": payload_obj, "byte_size": len(text)})
    return decoded


def main() -> int:
    token = get_token()
    raw = fetch_definition(token)
    RAW_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"raw -> {RAW_PATH}")
    decoded = decode_parts(raw)
    DECODED_PATH.write_text(json.dumps(decoded, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"decoded -> {DECODED_PATH}")
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP_PATH.exists():
        print(f"backup already exists, leaving as-is: {BACKUP_PATH}")
    else:
        BACKUP_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"backup -> {BACKUP_PATH}")
    print("\nparts:")
    for p in decoded:
        print(f"  - {p.get('path')}  size={p.get('byte_size')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
