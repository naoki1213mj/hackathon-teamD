"""marketing-plan 用 Foundry Prompt Agent の narrow re-sync (Phase 12)。

使い方 (Foundry Portal で Work IQ MCP connection を作成し、
適切な env vars を設定した *後* に実行):

    AZURE_AI_PROJECT_ENDPOINT=https://aiswmbvhdhcsuyb2.services.ai.azure.com/api/projects/aip-wmbvhdhcsuyb2 \
    uv run python -m scripts.sync_marketing_plan_agent

(`python scripts/sync_marketing_plan_agent.py` 形式でも動作する — sys.path shim あり)

理由:
  scripts/postprovision.py:sync_marketing_plan_agent は postprovision の途中で実行されるが、
  INSTRUCTIONS を tune した場合 (Phase 12 等) は postprovision を全部回さずに
  marketing-plan Prompt Agent だけを再同期したい。本スクリプトはそれを行う。

idempotent — `create_version` を呼ぶので何度実行しても新しい version が作成されるだけ。

Phase 12 rubber-duck 指摘 #2 (live Foundry agent re-sync gap) 対応:
  data-search 用 sync script (`scripts/sync_data_search_agent.py`) と対称な
  narrow sync script を marketing-plan 側にも追加する。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# `python scripts/sync_marketing_plan_agent.py` 形式で実行された場合に repo root を
# sys.path に追加して `from scripts.postprovision import ...` を解決可能にする。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sync_marketing_plan_agent")


def main() -> int:
    """marketing-plan 用 Prompt Agent を再同期する。"""
    project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not project_endpoint:
        logger.error("AZURE_AI_PROJECT_ENDPOINT が未設定です")
        return 1

    # postprovision の同期ロジックをそのまま再利用する (drift 防止)
    from scripts.postprovision import sync_marketing_plan_agent

    success = sync_marketing_plan_agent(project_endpoint)
    if success:
        logger.info("marketing-plan Prompt Agent の再同期に成功しました。")
        return 0
    logger.error("marketing-plan Prompt Agent の再同期に失敗しました。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
