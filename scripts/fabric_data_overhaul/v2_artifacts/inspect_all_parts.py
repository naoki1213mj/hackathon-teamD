"""Inspect stage_config + data_agent.json for any 'example' field locations."""
import base64
import json
import sys
from pathlib import Path


def find_example_keys(obj: object, path: str = "") -> list[str]:
    """Walk JSON-like obj, return paths where keys contain 'example' (case-insensitive)."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            if "example" in k.lower() or "fewshot" in k.lower() or "few_shot" in k.lower():
                size = len(v) if hasattr(v, "__len__") else "N/A"
                found.append(f"{sub}  (type={type(v).__name__}, size={size})")
            found.extend(find_example_keys(v, sub))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(find_example_keys(item, f"{path}[{i}]"))
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_all_parts.py BACKUP_FILE")
        return 1
    backup_path = Path(sys.argv[1])
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    parts = data.get("definition", {}).get("parts", [])

    print("=== Parts inventory ===")
    for part in parts:
        path = part.get("path", "")
        ptype = part.get("payloadType", "")
        size = len(part.get("payload", ""))
        print(f"  {path}  ({ptype}, base64 len={size})")

    print("\n=== Searching for 'example' / 'fewshot' / 'few_shot' keys (anywhere) ===")
    for part in parts:
        path = part.get("path", "")
        if part.get("payloadType") != "InlineBase64":
            continue
        try:
            payload = base64.b64decode(part["payload"]).decode("utf-8")
            decoded = json.loads(payload)
        except (ValueError, json.JSONDecodeError):
            continue
        matches = find_example_keys(decoded)
        if matches:
            print(f"\n--- {path} ---")
            for m in matches:
                print(f"  {m}")

    print("\n=== stage_config.json (draft) full content (truncated to 4000 chars) ===")
    sc = next((p for p in parts if "draft/stage_config" in p["path"]), None)
    if sc:
        decoded = json.loads(base64.b64decode(sc["payload"]).decode("utf-8"))
        print(f"top-level keys: {list(decoded.keys())}")
        print(json.dumps(decoded, ensure_ascii=False, indent=2)[:4000])

    print("\n=== data_agent.json full content (truncated to 2000 chars) ===")
    da = next((p for p in parts if p["path"] == "Files/Config/data_agent.json"), None)
    if da:
        decoded = json.loads(base64.b64decode(da["payload"]).decode("utf-8"))
        print(json.dumps(decoded, ensure_ascii=False, indent=2)[:2000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
