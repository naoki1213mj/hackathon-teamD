"""Inspect schema URL + elements + sample dataSourceInstructions head from lakehouse data part."""
import base64
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_lakehouse_schema.py BACKUP_FILE")
        return 1
    backup_path = Path(sys.argv[1])
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    parts = data.get("definition", {}).get("parts", [])
    lh = next((p for p in parts if "draft/lakehouse" in p["path"]), None)
    if not lh:
        print("ERROR: draft lakehouse part not found")
        return 1
    decoded = json.loads(base64.b64decode(lh["payload"]).decode("utf-8"))
    print(f"schema URL: {decoded.get('$schema')}")
    print(f"type: {decoded.get('type')}")
    print(f"displayName: {decoded.get('displayName')}")
    print("\n=== elements ===")
    print(json.dumps(decoded.get("elements"), ensure_ascii=False, indent=2)[:3000])
    print("\n=== dataSourceInstructions head (first 800 chars) ===")
    print(decoded.get("dataSourceInstructions", "")[:800])
    print("\n=== dataSourceInstructions tail (last 400 chars) ===")
    print(decoded.get("dataSourceInstructions", "")[-400:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
