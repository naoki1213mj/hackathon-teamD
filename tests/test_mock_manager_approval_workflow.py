"""mock_manager_approval_workflow のテスト。"""

from fastapi.testclient import TestClient

from scripts import mock_manager_approval_workflow as mock_workflow

client = TestClient(mock_workflow.app)


def test_mock_workflow_approve_callback(monkeypatch):
    """approve 設定なら承認 callback を送る。"""
    captured: dict[str, object] = {}

    async def fake_send_manager_callback(callback_url: str, callback_payload: dict[str, object]) -> None:
        captured["callback_url"] = callback_url
        captured["callback_payload"] = callback_payload

    monkeypatch.setenv("MOCK_MANAGER_APPROVAL_DECISION", "approve")
    monkeypatch.setenv("MOCK_MANAGER_APPROVAL_DELAY_SECONDS", "0")
    monkeypatch.delenv("MOCK_MANAGER_APPROVAL_COMMENT", raising=False)
    monkeypatch.delenv("MOCK_MANAGER_APPROVAL_APPROVER_EMAIL", raising=False)
    monkeypatch.setattr(mock_workflow, "_send_manager_callback", fake_send_manager_callback)

    response = client.post(
        "/manager-approval",
        json={
            "request_type": "manager_approval",
            "plan_title": "春の沖縄ファミリーキャンペーン",
            "plan_markdown": "# 春の沖縄ファミリーキャンペーン",
            "conversation_id": "conv-approve",
            "manager_email": "manager@example.com",
            "manager_callback_url": "https://example.com/api/chat/conv-approve/manager-approval-callback",
            "manager_callback_token": "token-approve",
        },
    )

    assert response.status_code == 202
    assert response.json()["decision"] == "approve"
    assert captured["callback_url"] == "https://example.com/api/chat/conv-approve/manager-approval-callback"
    assert captured["callback_payload"] == {
        "conversation_id": "conv-approve",
        "approved": True,
        "comment": "",
        "approver_email": "manager@example.com",
        "callback_token": "token-approve",
    }


def test_mock_workflow_reject_callback_uses_defaults(monkeypatch):
    """reject 設定なら既定コメント付きで差し戻し callback を送る。"""
    captured: dict[str, object] = {}

    async def fake_send_manager_callback(callback_url: str, callback_payload: dict[str, object]) -> None:
        captured["callback_url"] = callback_url
        captured["callback_payload"] = callback_payload

    monkeypatch.setenv("MOCK_MANAGER_APPROVAL_DECISION", "reject")
    monkeypatch.setenv("MOCK_MANAGER_APPROVAL_DELAY_SECONDS", "0")
    monkeypatch.delenv("MOCK_MANAGER_APPROVAL_COMMENT", raising=False)
    monkeypatch.setenv("MOCK_MANAGER_APPROVAL_APPROVER_EMAIL", "director@example.com")
    monkeypatch.setattr(mock_workflow, "_send_manager_callback", fake_send_manager_callback)

    response = client.post(
        "/manager-approval",
        json={
            "request_type": "manager_approval",
            "plan_title": "京都プレミアムツアー",
            "plan_markdown": "# 京都プレミアムツアー",
            "conversation_id": "conv-reject",
            "manager_email": "manager@example.com",
            "manager_callback_url": "https://example.com/api/chat/conv-reject/manager-approval-callback",
            "manager_callback_token": "token-reject",
        },
    )

    assert response.status_code == 202
    assert response.json()["decision"] == "reject"
    assert captured["callback_url"] == "https://example.com/api/chat/conv-reject/manager-approval-callback"
    assert captured["callback_payload"] == {
        "conversation_id": "conv-reject",
        "approved": False,
        "comment": mock_workflow.DEFAULT_REJECTION_COMMENT,
        "approver_email": "director@example.com",
        "callback_token": "token-reject",
    }
