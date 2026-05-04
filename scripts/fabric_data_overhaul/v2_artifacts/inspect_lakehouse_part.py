"""Inspect lakehouse data parts in a backup to find native exampleQueries field."""
import base64
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_lakehouse_part.py BACKUP_FILE")
        return 1
    backup_path = Path(sys.argv[1])
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    parts = data.get("definition", {}).get("parts", [])
    print(f"total parts: {len(parts)}")
    for part in parts:
        path = part.get("path", "")
        ptype = part.get("payloadType", "")
        print(f"  - {path}  ({ptype})")

    print("\n=== lakehouse data parts (decoded) ===")
    for part in parts:
        path = part.get("path", "")
        if "lakehouse" not in path.lower():
            continue
        if part.get("payloadType") == "InlineBase64":
            payload = base64.b64decode(part["payload"]).decode("utf-8")
            try:
                decoded = json.loads(payload)
                print(f"\n--- {path} ---")
                print(f"  top-level keys: {list(decoded.keys())}")
                if "exampleQueries" in decoded:
                    eqs = decoded["exampleQueries"]
                    print(f"  exampleQueries: type={type(eqs).__name__}, len={len(eqs) if hasattr(eqs, '__len__') else 'N/A'}")
                    if eqs:
                        print(f"  first item keys: {list(eqs[0].keys()) if isinstance(eqs[0], dict) else 'non-dict'}")
                        print(f"  first item: {json.dumps(eqs[0], ensure_ascii=False, indent=2)[:500]}")
                else:
                    print("  exampleQueries: <NOT PRESENT>")
                # Show all top-level fields with their types/lengths
                for k, v in decoded.items():
                    if isinstance(v, str):
                        print(f"  .{k}: str ({len(v)} chars)")
                    elif isinstance(v, list):
                        print(f"  .{k}: list (len={len(v)})")
                    elif isinstance(v, dict):
                        print(f"  .{k}: dict (keys={list(v.keys())[:5]})")
                    else:
                        print(f"  .{k}: {type(v).__name__}={v!r}")
            except Exception as exc:
                print(f"\n--- {path} (RAW, decode failed: {exc}) ---")
                print(payload[:1000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
