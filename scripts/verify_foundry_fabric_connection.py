"""Foundry の Fabric Data Agent connection を検証するスクリプト (PR 3)。

使い方:
    # 通常モード: FOUNDRY_FABRIC_CONNECTION_ID 環境変数を検証
    uv run python scripts/verify_foundry_fabric_connection.py

    # ポータル作成直後モード: 接続名を指定して resource ID を取得 (env var 未設定でも OK)
    uv run python scripts/verify_foundry_fabric_connection.py --connection-name travel-fabric-da

確認項目:
1. AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_FABRIC_CONNECTION_ID が設定されているか
   (--connection-name 指定時は env var 不要)
2. connection_id 形式が `/subscriptions/.../connections/{name}` を満たすか
3. Foundry Project に接続でき、connection が存在するか (DefaultAzureCredential)
4. category が Fabric 系で target に dataagents path を含むか (false-green 防止)

idempotent — 何度でも安全に実行できる。

成功時は最後に `gh variable set -e production FOUNDRY_FABRIC_CONNECTION_ID ...` を提示する。
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("verify_foundry_fabric_connection")


_CONNECTION_ID_PATTERN = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.CognitiveServices/"
    r"accounts/[^/]+/projects/[^/]+/connections/[^/]+$"
)


def _print_check(label: str, status: str, detail: str = "") -> None:
    """[OK] / [WARN] / [FAIL] 形式の進捗を stdout に出す。"""
    icon = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}.get(status, "[INFO]")
    line = f"{icon} {label}"
    if detail:
        line += f" — {detail}"
    print(line)


def _read_env(name: str) -> str:
    """環境変数を読む（空文字含めて常に str を返す）。"""
    return os.environ.get(name, "").strip()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Foundry の Fabric Data Agent connection を検証",
    )
    parser.add_argument(
        "--connection-name",
        default="",
        help=(
            "ポータル作成直後モード: 接続名 (例: travel-fabric-da) を指定すると "
            "FOUNDRY_FABRIC_CONNECTION_ID env var なしで lookup + 推奨 gh コマンドを表示。"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_endpoint = _read_env("AZURE_AI_PROJECT_ENDPOINT")
    connection_id = _read_env("FOUNDRY_FABRIC_CONNECTION_ID")
    explicit_connection_name = (args.connection_name or "").strip()

    has_error = False

    if not project_endpoint:
        _print_check(
            "AZURE_AI_PROJECT_ENDPOINT",
            "fail",
            "未設定。`.env.local` または GitHub Actions Variables に設定してください。",
        )
        return 1
    _print_check("AZURE_AI_PROJECT_ENDPOINT", "ok", project_endpoint)

    # ポータル作成直後モード: env var 不要、connection 名で lookup + ID を提示
    if explicit_connection_name:
        _print_check(
            "Mode",
            "ok",
            f"ポータル作成直後モード — connection_name=`{explicit_connection_name}`",
        )
        connection_id = ""  # env var ではなく lookup 結果から ID を構成
    else:
        if not connection_id:
            _print_check(
                "FOUNDRY_FABRIC_CONNECTION_ID",
                "fail",
                "未設定。Foundry Portal で Fabric DA connection を作成し、"
                "`--connection-name` か env var で指定してください。",
            )
            return 1
        _print_check("FOUNDRY_FABRIC_CONNECTION_ID set", "ok", connection_id)

        if not _CONNECTION_ID_PATTERN.match(connection_id):
            _print_check(
                "FOUNDRY_FABRIC_CONNECTION_ID 形式",
                "fail",
                "`/subscriptions/.../connections/{name}` 形式ではありません",
            )
            return 1
        _print_check("FOUNDRY_FABRIC_CONNECTION_ID 形式", "ok")

    # Live check (best-effort) — connection をリスト/取得して存在を確認する
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        _print_check(
            "azure-ai-projects SDK",
            "warn",
            f"import 失敗: {exc}。`uv sync` で依存をインストールしてください。",
        )
        return 0  # オフライン検証は終わっているので 0 を返す

    try:
        client = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    except Exception as exc:  # noqa: BLE001
        _print_check(
            "AIProjectClient 初期化",
            "warn",
            f"認証/接続失敗: {exc}",
        )
        return 0

    try:
        connections = getattr(client, "connections", None)
        if connections is None:
            _print_check(
                "Foundry connection 取得",
                "warn",
                "AIProjectClient.connections が未公開の SDK バージョンです",
            )
            return 0

        connection_name = explicit_connection_name or connection_id.rsplit("/", 1)[-1]
        try:
            conn = connections.get(connection_name)
            target = getattr(conn, "target", "") or ""
            category = getattr(conn, "category", None) or getattr(conn, "type", None) or ""
            auth_type = getattr(conn, "auth_type", None) or ""
            resolved_id = getattr(conn, "id", "") or ""
            _print_check(
                f"connection `{connection_name}` 取得",
                "ok",
                f"target={target[:80]}",
            )
            # Fabric Data Agent 専用 sanity check (false-green 防止)
            category_str = str(category).lower()
            target_str = str(target).lower()
            shape_ok = False
            if category_str and "fabric" not in category_str:
                _print_check(
                    "connection.category",
                    "warn",
                    f"category=`{category}` (Fabric ではない可能性。MicrosoftFabricPreviewTool が消費できないかも)",
                )
            elif "/dataagents/" not in target_str and "fabric" not in target_str:
                _print_check(
                    "connection.target",
                    "warn",
                    f"target に `/dataagents/` が含まれない: {target[:120]}",
                )
            else:
                _print_check(
                    "Fabric DA shape 検証",
                    "ok",
                    f"category={category} auth={auth_type}",
                )
                shape_ok = True

            # ポータル作成直後モード: shape OK + resolved resource ID 検証 OK のときだけ
            # 推奨コマンドを表示する (fail-closed; rubber-duck pr3-portal-followup-impl-review blocking #2)
            if explicit_connection_name:
                if not resolved_id:
                    _print_check(
                        "resolved resource ID",
                        "fail",
                        "connection.id が取得できませんでした",
                    )
                    has_error = True
                elif not _CONNECTION_ID_PATTERN.match(resolved_id):
                    _print_check(
                        "resolved resource ID 形式",
                        "fail",
                        f"`{resolved_id}` は標準パターンと異なります",
                    )
                    has_error = True
                elif not shape_ok:
                    _print_check(
                        "Fabric shape 検証",
                        "fail",
                        "category / target が Fabric Data Agent の shape を満たさないため、"
                        "production への昇格コマンドは表示しません。"
                        "別の connection 名を指定するか、ポータルで connection を作り直してください。",
                    )
                    has_error = True
                else:
                    _print_check("resolved resource ID 形式", "ok")
                    print()
                    print("=" * 72)
                    print("FOUNDRY_FABRIC_CONNECTION_ID:")
                    print(resolved_id)
                    print()
                    print("次に実行するコマンド (production env scope):")
                    print(f'  gh variable set FOUNDRY_FABRIC_CONNECTION_ID --env production --body "{resolved_id}"')
                    print('  gh variable set DATA_SEARCH_RUNTIME --env production --body "foundry_preprovisioned"')
                    print()
                    print("接続が反映されたら、Prompt Agent 定義に Fabric tool を attach するため再同期:")
                    print('  uv run python -m scripts.sync_data_search_agent')
                    print()
                    print("もしくは新しい revision を作って反映を待たない (一行):")
                    print(
                        f'  az containerapp update -n ca-wmbvhdhcsuyb2-pn -g rg-workiq-dev '
                        f'--set-env-vars FOUNDRY_FABRIC_CONNECTION_ID="{resolved_id}" '
                        f'DATA_SEARCH_RUNTIME=foundry_preprovisioned'
                    )
                    print("(注: --set-env-vars は新 revision を作成するため即時ではないが、deploy.yml を待つよりは早い)")
                    print("=" * 72)
        except Exception as exc:  # noqa: BLE001
            _print_check(
                f"connection `{connection_name}` 取得",
                "fail",
                f"connection が見つからないか権限不足: {exc}",
            )
            has_error = True
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
