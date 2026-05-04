"""Phase 11d: Push improved instruction blocks to Travel_Ontology_DA_v2.

verifier verdict 反映後の rubber-duck 修正済 4 ブロックを `agent_definition` に
適用する。各ブロックの本文は同階層の `phase11d_blocks/*.md` に保管されており、
本スクリプトはそこから読み込んでテキストを置換する。

各ブロックの適用先:

- **Block 1** (`agent_instructions.md`): `Files/Config/draft/stage_config.json`
  と `Files/Config/published/stage_config.json` の `aiInstructions` を完全置換。
  Phase 11a で append された "## When asked about" routing rule もまとめて
  Block 1 に再構成済 (verdict 反映の master 集約版)。
- **Block 2** (`lakehouse_description.md`): lakehouse `lh_travel_marketing_v2`
  の `userDescription` を完全置換 (現行 96 chars → ~1,369 chars)。
- **Block 3** (`lakehouse_instructions.md`): lakehouse の
  `dataSourceInstructions` を完全置換。Phase 11a の routing 部 + Phase 11b の
  text-inline T-SQL example queries を一括撤去 (Phase 11c の native
  `exampleQueries` 15 件で代替)。
- **Block 4** (`ontology_description.md`): `--include-ontology-desc` 指定時のみ
  ontology `travelIQ_v2` の `userDescription` を置換。MS Learn の supported
  matrix 上 ontology の `userDescription` は ✅ supported だが、現行 133 chars の
  英語要約も問題なく動作しているため Block 4 は opt-in にし default では
  触らない (changes 範囲を最小化)。
- **Ontology `dataSourceInstructions`** (現行 21,653 chars) は Phase 11d-2
  scope。本スクリプトでは触らない。

Idempotency: 4 (or 6) targets path × field の全 string equality check で判定。
draft/published の stage_config.aiInstructions、lakehouse の userDescription /
dataSourceInstructions、(opt-in 時は) ontology の userDescription、すべての
field 内容が対応する block と完全一致すれば Phase 11d 適用済とみなして no-op
success。一部だけ適用済の half-applied 状態は patch して合わせ込む。

Usage:
    # ドライラン (payload diff を JSON で出力、live は変えない)
    uv run python scripts/fabric_data_overhaul/v2_artifacts/patch_phase11d_instructions.py --dry-run

    # ライブ適用 (Block 1 + 2 + 3、ontology userDescription は触らない)
    uv run python scripts/fabric_data_overhaul/v2_artifacts/patch_phase11d_instructions.py

    # ライブ適用 (Block 4 も含めて ontology userDescription を置換)
    uv run python scripts/fabric_data_overhaul/v2_artifacts/patch_phase11d_instructions.py --include-ontology-desc

Rollback:
    uv run python scripts/fabric_data_overhaul/v2_artifacts/rollback_to_backup.py \\
        agent_definition_pre_phase11d_<timestamp>.json
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ARTIFACTS_DIR))
import patch_demo_few_shot as helpers  # noqa: E402

BACKUP_DIR = ARTIFACTS_DIR / "backups"
BLOCKS_DIR = ARTIFACTS_DIR / "phase11d_blocks"

DRAFT_STAGE_PATH = "Files/Config/draft/stage_config.json"
PUBLISHED_STAGE_PATH = "Files/Config/published/stage_config.json"
DRAFT_LAKEHOUSE_PATH = (
    "Files/Config/draft/lakehouse-tables-lh_travel_marketing_v2/datasource.json"
)
PUBLISHED_LAKEHOUSE_PATH = (
    "Files/Config/published/lakehouse-tables-lh_travel_marketing_v2/datasource.json"
)
DRAFT_ONTOLOGY_PATH = "Files/Config/draft/ontology-travelIQ_v2/datasource.json"
PUBLISHED_ONTOLOGY_PATH = "Files/Config/published/ontology-travelIQ_v2/datasource.json"


def _load_block(filename: str) -> str:
    """phase11d_blocks/<filename> を読み込み、先頭の HTML コメントを取り除く。

    .md ファイルの先頭には `<!-- Phase 11d source — ... -->` のヒトのための
    コメント行が付与されているが、それは Fabric DA に送らない。
    """
    raw = (BLOCKS_DIR / filename).read_text(encoding="utf-8")
    # 先頭の HTML コメント (1 つだけ) を取り除く。直後の空行も併せて除去。
    cleaned = re.sub(r"\A<!--.*?-->\s*\n+", "", raw, count=1, flags=re.DOTALL)
    # 末尾の改行統一 (trailing single newline を維持)
    cleaned = cleaned.rstrip("\n") + "\n"
    return cleaned


def _replace_part(
    parts: list[dict],
    target_path: str,
    field_updates: dict[str, str],
) -> tuple[dict, str, dict[str, tuple[int, int]]]:
    """指定 path の part を見つけ、payload (base64 inline JSON) 内の field を置換する。

    Returns:
        (new_part, original_payload_text, char_diffs)
        char_diffs は {field_name: (before_len, after_len)} の dict。

    Raises:
        SystemExit: 対象 path が見つからない場合。
    """
    part = next((p for p in parts if p["path"] == target_path), None)
    if part is None:
        raise SystemExit(f"❌ live definition missing expected path: {target_path}")

    payload_text = base64.b64decode(part["payload"]).decode("utf-8")
    obj = json.loads(payload_text)
    char_diffs: dict[str, tuple[int, int]] = {}
    for field, new_value in field_updates.items():
        before = obj.get(field, "") or ""
        char_diffs[field] = (len(before), len(new_value))
        obj[field] = new_value

    new_payload_bytes = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    new_part = {
        "path": part["path"],
        "payload": base64.b64encode(new_payload_bytes).decode("ascii"),
        "payloadType": part.get("payloadType", "InlineBase64"),
    }
    return new_part, payload_text, char_diffs


def _build_expected_field_map(
    *,
    block1: str,
    block2: str,
    block3: str,
    block4: str | None,
    include_ontology_desc: bool,
) -> dict[str, dict[str, str]]:
    """Phase 11d 適用後に各 target path で期待される field 値の dict を返す。

    idempotency check と post-push verify の両方で使われ、source-of-truth を
    1 か所にまとめる。
    """
    expected: dict[str, dict[str, str]] = {
        DRAFT_STAGE_PATH: {"aiInstructions": block1},
        PUBLISHED_STAGE_PATH: {"aiInstructions": block1},
        DRAFT_LAKEHOUSE_PATH: {
            "userDescription": block2,
            "dataSourceInstructions": block3,
        },
        PUBLISHED_LAKEHOUSE_PATH: {
            "userDescription": block2,
            "dataSourceInstructions": block3,
        },
    }
    if include_ontology_desc:
        if block4 is None:
            raise SystemExit(
                "❌ internal: include_ontology_desc=True but block4 not loaded"
            )
        expected[DRAFT_ONTOLOGY_PATH] = {"userDescription": block4}
        expected[PUBLISHED_ONTOLOGY_PATH] = {"userDescription": block4}
    return expected


def _all_fields_match(
    parts: list[dict], expected: dict[str, dict[str, str]]
) -> bool:
    """expected の全 (path, field, value) が live parts と string equality で一致するか。

    一部でも一致しなければ False を返す。path 自体が見つからない場合は
    SystemExit (live definition の構造異常)。
    """
    for path, field_map in expected.items():
        part = next((p for p in parts if p["path"] == path), None)
        if part is None:
            raise SystemExit(f"❌ live definition missing expected path: {path}")
        decoded = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
        for field, expected_value in field_map.items():
            actual = decoded.get(field, "") or ""
            if actual != expected_value:
                return False
    return True


def patch_definition(
    definition: dict, *, include_ontology_desc: bool
) -> tuple[dict, bool, dict[str, dict[str, tuple[int, int]]]]:
    """4 ブロックを適用した新しい definition を返す。

    Args:
        definition: live `getDefinition` で取得した dict。
        include_ontology_desc: Block 4 (ontology `userDescription`) を適用するか。

    Returns:
        (new_definition, changed, summary)
        - changed=False は idempotent no-op (全 target field が期待値と完全一致)。
        - summary は {target_path: {field: (before_len, after_len)}} の dict。
    """
    parts: list[dict] = list(definition.get("definition", {}).get("parts", []))
    if not parts:
        raise SystemExit("❌ live definition has no parts")

    block1 = _load_block("agent_instructions.md")
    block2 = _load_block("lakehouse_description.md")
    block3 = _load_block("lakehouse_instructions.md")
    block4 = _load_block("ontology_description.md") if include_ontology_desc else None

    expected = _build_expected_field_map(
        block1=block1,
        block2=block2,
        block3=block3,
        block4=block4,
        include_ontology_desc=include_ontology_desc,
    )

    # Idempotency: 4 (or 6) targets path × field の全 string equality check。
    # 一部 target が未適用 (half-applied) ならば patch して合わせ込む。
    if _all_fields_match(parts, expected):
        scope = (
            "all 6 target fields"
            if include_ontology_desc
            else "all 4 target fields"
        )
        print(
            f"  no-op: {scope} (stage_config × 2, lakehouse × 2"
            + (", ontology × 2" if include_ontology_desc else "")
            + ") already match Phase 11d expected content"
        )
        return definition, False, {}

    summary: dict[str, dict[str, tuple[int, int]]] = {}
    new_parts: list[dict] = []
    target_paths = {DRAFT_STAGE_PATH, PUBLISHED_STAGE_PATH, DRAFT_LAKEHOUSE_PATH, PUBLISHED_LAKEHOUSE_PATH}
    if include_ontology_desc:
        target_paths.update({DRAFT_ONTOLOGY_PATH, PUBLISHED_ONTOLOGY_PATH})

    for part in parts:
        path = part["path"]
        if path in (DRAFT_STAGE_PATH, PUBLISHED_STAGE_PATH):
            new_part, _, diffs = _replace_part(
                parts, path, {"aiInstructions": block1}
            )
            new_parts.append(new_part)
            summary[path] = diffs
            print(
                f"  + {path}: aiInstructions "
                f"{diffs['aiInstructions'][0]} → {diffs['aiInstructions'][1]} chars"
            )
        elif path in (DRAFT_LAKEHOUSE_PATH, PUBLISHED_LAKEHOUSE_PATH):
            new_part, _, diffs = _replace_part(
                parts,
                path,
                {"userDescription": block2, "dataSourceInstructions": block3},
            )
            new_parts.append(new_part)
            summary[path] = diffs
            print(
                f"  + {path}: userDescription "
                f"{diffs['userDescription'][0]} → {diffs['userDescription'][1]} chars, "
                f"dataSourceInstructions "
                f"{diffs['dataSourceInstructions'][0]} → {diffs['dataSourceInstructions'][1]} chars"
            )
        elif include_ontology_desc and path in (
            DRAFT_ONTOLOGY_PATH,
            PUBLISHED_ONTOLOGY_PATH,
        ):
            assert block4 is not None  # include_ontology_desc=True で読み込み済
            new_part, _, diffs = _replace_part(
                parts, path, {"userDescription": block4}
            )
            new_parts.append(new_part)
            summary[path] = diffs
            print(
                f"  + {path}: userDescription "
                f"{diffs['userDescription'][0]} → {diffs['userDescription'][1]} chars"
            )
        else:
            new_parts.append(part)

    # 想定 path がすべて見つかったか確認
    found_paths = set(summary.keys())
    missing = target_paths - found_paths
    if missing:
        raise SystemExit(f"❌ live definition missing expected paths: {sorted(missing)}")

    new_definition = {"definition": {"parts": new_parts}}
    return new_definition, True, summary


def verify_post_push(
    *,
    block1: str,
    block2: str,
    block3: str,
    block4: str | None,
    include_ontology_desc: bool,
) -> None:
    """live を再 fetch して、Phase 11d 対象の全 (path, field) が期待値と完全一致するか
    厳密 assert する。一致しない (path 不在 / 異なる長さ / content drift) 場合は
    SystemExit で fail loud。"""
    print("Re-fetching live definition for read-back verification...")
    live = helpers.fetch_live_definition()
    parts = live.get("definition", {}).get("parts", [])
    expected = _build_expected_field_map(
        block1=block1,
        block2=block2,
        block3=block3,
        block4=block4,
        include_ontology_desc=include_ontology_desc,
    )
    failures: list[str] = []
    for path, field_map in expected.items():
        part = next((p for p in parts if p["path"] == path), None)
        if part is None:
            failures.append(f"{path}: part missing")
            continue
        decoded = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
        for field, expected_value in field_map.items():
            actual = decoded.get(field, "") or ""
            if actual == expected_value:
                print(
                    f"  ✅ {path} {field}: {len(actual)} chars exact match"
                )
            else:
                failures.append(
                    f"{path} {field}: expected {len(expected_value)} chars, "
                    f"got {len(actual)} chars (content mismatch)"
                )
    if failures:
        raise SystemExit(
            "❌ read-back verification failed:\n  - " + "\n  - ".join(failures)
        )


def _format_summary(summary: dict[str, dict[str, tuple[int, int]]]) -> str:
    """ターミナル表示用の char count delta サマリ。"""
    lines = []
    for path, diffs in summary.items():
        for field, (before, after) in diffs.items():
            delta = after - before
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"  {path} {field}: {before} → {after} chars ({sign}{delta})"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Patch in memory のみ。live は変更せず payload diff を JSON 出力する。",
    )
    parser.add_argument(
        "--include-ontology-desc",
        action="store_true",
        help=(
            "ontology travelIQ_v2 の userDescription を Block 4 で置換する。"
            "default では触らない (現行 133 chars でも動作実績あり、"
            "Phase 11d-2 cleanup と分離するため opt-in にしている)。"
        ),
    )
    args = parser.parse_args()

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print("Fetching live definition...")
    definition = helpers.fetch_live_definition()
    pre_size = sum(len(p.get("payload", "")) for p in definition["definition"]["parts"])
    print(
        f"  live parts={len(definition['definition']['parts'])} "
        f"pre_payload_size={pre_size} bytes (base64)"
    )

    backup_path = BACKUP_DIR / f"agent_definition_pre_phase11d_{timestamp}.json"
    backup_path.write_text(
        json.dumps(definition, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  backup saved to {backup_path.name}")

    new_definition, changed, summary = patch_definition(
        definition, include_ontology_desc=args.include_ontology_desc
    )
    if not changed:
        print("Phase 11d already applied — no-op success")
        return 0

    print("\nChar count delta:")
    print(_format_summary(summary))

    if args.dry_run:
        diff_path = ARTIFACTS_DIR / f"phase11d_dryrun_{timestamp}.json"
        diff_path.write_text(
            json.dumps(new_definition, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nDRY RUN: payload written to {diff_path.name}, NOT pushed")
        print(f"  include_ontology_desc={args.include_ontology_desc}")
        return 0

    print("\nPushing updateDefinition LRO...")
    helpers.push_definition(new_definition)
    print("✅ updateDefinition succeeded")

    block1 = _load_block("agent_instructions.md")
    block2 = _load_block("lakehouse_description.md")
    block3 = _load_block("lakehouse_instructions.md")
    block4 = (
        _load_block("ontology_description.md")
        if args.include_ontology_desc
        else None
    )
    verify_post_push(
        block1=block1,
        block2=block2,
        block3=block3,
        block4=block4,
        include_ontology_desc=args.include_ontology_desc,
    )

    print("\n" + "=" * 70)
    print("✅ Phase 11d instructions pushed to Travel_Ontology_DA_v2")
    print("=" * 70)
    print("\nNext: smoke regression check (run 2-3x for variance averaging):")
    print("  uv run python scripts/fabric_data_overhaul/v2_artifacts/smoke_demo_prompts.py")
    print("  uv run python scripts/fabric_data_overhaul/v2_artifacts/smoke_test_v6.py")
    print("\nIf regression detected (best-of grade A < 12/14), rollback with:")
    print(
        "  uv run python scripts/fabric_data_overhaul/v2_artifacts/rollback_to_backup.py "
        f"{backup_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
