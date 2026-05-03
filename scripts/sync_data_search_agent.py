"""data-search 用 Foundry Prompt Agent の narrow re-sync (PR 3)。

使い方 (Foundry Portal で Fabric DA connection を作成し、
FOUNDRY_FABRIC_CONNECTION_ID を設定した *後* に実行):

    AZURE_AI_PROJECT_ENDPOINT=https://aiswmbvhdhcsuyb2.services.ai.azure.com/api/projects/aip-wmbvhdhcsuyb2 \
    FOUNDRY_FABRIC_CONNECTION_ID=/subscriptions/.../connections/travel-fabric-da \
    uv run python -m scripts.sync_data_search_agent

(`python scripts/sync_data_search_agent.py` 形式でも動作する — sys.path shim あり)

理由:
  scripts/postprovision.py:sync_data_search_agent は postprovision の途中で実行されるが、
  Fabric connection を後から portal で作成した場合、Prompt Agent 定義に
  MicrosoftFabricPreviewTool が attach されていない。本スクリプトは
  postprovision を全部回さずに data-search Agent だけを再同期する。

idempotent — `create_version` を呼ぶので何度実行しても新しい version が作成されるだけ。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# `python scripts/sync_data_search_agent.py` 形式で実行された場合に repo root を
# sys.path に追加して `from scripts.postprovision import ...` を解決可能にする。
# `python -m scripts.sync_data_search_agent` 形式は repo root が cwd なら不要だが
# 重複追加しても害は無い。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sync_data_search_agent")


def main() -> int:
    project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not project_endpoint:
        logger.error("AZURE_AI_PROJECT_ENDPOINT が未設定です")
        return 1

    fabric_connection_id = os.environ.get("FOUNDRY_FABRIC_CONNECTION_ID", "").strip()
    if not fabric_connection_id:
        logger.warning(
            "FOUNDRY_FABRIC_CONNECTION_ID が未設定です。Fabric tool 抜きで同期されます。"
        )

    # postprovision の同期ロジックをそのまま再利用する (drift 防止)
    from scripts.postprovision import sync_data_search_agent

    success = sync_data_search_agent(project_endpoint)
    if success:
        logger.info("data-search Prompt Agent の再同期に成功しました。")
        return 0
    logger.error("data-search Prompt Agent の再同期に失敗しました。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
