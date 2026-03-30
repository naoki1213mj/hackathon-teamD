"""hosted_agent モジュールのテスト"""


from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_hosted_agent_main_creates_workflow():
    """main() がワークフローを構築し、KeyboardInterrupt で停止すること"""
    mock_workflow = MagicMock()

    with patch("src.hosted_agent.create_pipeline_workflow", return_value=mock_workflow) as mock_create, \
         patch("asyncio.sleep", side_effect=KeyboardInterrupt):
        from src.hosted_agent import main

        await main()
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_hosted_agent_main_logs_workflow_type():
    """main() がワークフロー型名をログ出力すること"""
    mock_workflow = MagicMock()

    with patch("src.hosted_agent.create_pipeline_workflow", return_value=mock_workflow), \
         patch("asyncio.sleep", side_effect=KeyboardInterrupt), \
         patch("src.hosted_agent.logger") as mock_logger:
        from src.hosted_agent import main

        await main()

        # ログ出力に型名が含まれること
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Workflow" in s or "構築完了" in s for s in log_calls)
