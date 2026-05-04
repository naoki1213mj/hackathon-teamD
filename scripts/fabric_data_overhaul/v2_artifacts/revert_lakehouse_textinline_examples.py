"""Phase 11d: Remove text-inline T-SQL example queries from lakehouse dataSourceInstructions.

This is the inverse of patch_lakehouse_examples.py (Phase 11b). Use after the
operator has manually populated the native Lakehouse `Example queries` UI in
Fabric and a 3-run post-UI smoke confirms no regression.

The reason for splitting: per user feedback (2026-05-04), text-inline NL+SQL
pairs in dataSourceInstructions duplicate the native exampleQueries field
(populated via Fabric UI) and create cognitive load on NL2Ontology. Native
field is preferred because Fabric uses vector similarity for retrieval rather
than passing the entire instructions block.

Idempotent via marker check. Saves backup before push.

Usage:
    uv run python scripts/fabric_data_overhaul/v2_artifacts/revert_lakehouse_textinline_examples.py --dry-run
    uv run python scripts/fabric_data_overhaul/v2_artifacts/revert_lakehouse_textinline_examples.py
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch_demo_few_shot as helpers  # noqa: E402

LAKEHOUSE_PATH_FRAGMENT = "lakehouse-tables-lh_travel_marketing_v2/datasource.json"
MARKER = "## T-SQL example queries (lakehouse-direct, limited use cases)"


def _strip_examples_block(instructions: str) -> tuple[str, bool]:
    """Remove the marker section + everything after it, plus trailing blank lines.

    Returns (new_instructions, was_modified).
    """
    idx = instructions.find(MARKER)
    if idx == -1:
        return instructions, False
    before = instructions[:idx].rstrip()
    return before + "\n", True


def patch_definition(definition: dict) -> tuple[dict, list[str]]:
    """Strip the text-inline examples section from both draft+published lakehouse parts."""
    parts = definition.get("definition", {}).get("parts", [])
    actions: list[str] = []
    for part in parts:
        path = part.get("path", "")
        if LAKEHOUSE_PATH_FRAGMENT not in path:
            continue
        if part.get("payloadType") != "InlineBase64":
            continue
        decoded = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
        old = decoded.get("dataSourceInstructions", "")
        new, modified = _strip_examples_block(old)
        if not modified:
            actions.append(f"SKIP: {path} (marker not present, already reverted)")
            continue
        decoded["dataSourceInstructions"] = new
        part["payload"] = base64.b64encode(
            json.dumps(decoded, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        actions.append(
            f"REVERTED: {path} -- dataSourceInstructions {len(old)} -> {len(new)} chars"
        )
    return definition, actions


def verify_post_push(client_factory) -> None:
    """Re-fetch live definition and assert MARKER is GONE in both lakehouse parts."""
    print("Re-fetching live definition for verification...")
    fresh = helpers.fetch_live_definition()
    parts = fresh.get("definition", {}).get("parts", [])
    found_count = 0
    verified_count = 0
    for part in parts:
        path = part.get("path", "")
        if LAKEHOUSE_PATH_FRAGMENT not in path:
            continue
        decoded = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
        instructions = decoded.get("dataSourceInstructions", "")
        if MARKER in instructions:
            found_count += 1
            print(f"  ❌ {path} ({len(instructions)} chars, MARKER STILL PRESENT)")
        else:
            verified_count += 1
            print(f"  ✅ {path} ({len(instructions)} chars, marker removed)")
    if found_count > 0:
        raise RuntimeError(
            f"VERIFICATION FAILED: marker still present in {found_count} lakehouse part(s)"
        )
    if verified_count != 2:
        raise RuntimeError(
            f"VERIFICATION FAILED: expected 2 lakehouse parts, got {verified_count}"
        )
    print("VERIFICATION OK")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Fetching live definition...")
    definition = helpers.fetch_live_definition()

    if args.dry_run:
        patched, actions = patch_definition(definition)
        print("=== DRY RUN ===")
        for a in actions:
            print(f"  {a}")
        out = (
            HERE
            / f"lakehouse_revert_dryrun_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        out.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  saved: {out.name}")
        return 0

    print("=== LIVE PUSH ===")
    backup_dir = HERE / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"agent_definition_pre_lakehouse_revert_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    (backup_dir / backup_name).write_text(
        json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  backup: {backup_name}")

    patched, actions = patch_definition(definition)
    for a in actions:
        print(f"  {a}")
    if not any("REVERTED" in a for a in actions):
        print("  ⏩ Nothing to revert (already in baseline state). Exiting.")
        return 0

    print(f"  pushing patch (modified {sum(1 for a in actions if 'REVERTED' in a)} parts)...")
    helpers.push_definition(patched)
    print("  push OK")

    verify_post_push(None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
