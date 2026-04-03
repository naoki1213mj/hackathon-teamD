"""外部の上司承認 workflow をローカルで再現する mock サービス。"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

_EMAIL_ADDRESS_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_REJECTION_COMMENT = "価格訴求を少し抑えて再確認してください。"


def _sanitize_text(value: str | None) -> str:
    """前後空白を除去した文字列を返す。"""
    return str(value or "").strip()


def _sanitize_email(value: str | None) -> str:
    """メールアドレスを正規化して返す。"""
    email = _sanitize_text(value).lower()
    if email and not _EMAIL_ADDRESS_RE.fullmatch(email):
        raise ValueError("メールアドレス形式が不正です")
    return email


class ManagerApprovalWorkflowRequest(BaseModel):
    """FastAPI 本体から受け取る上司承認 request。"""

    request_type: str = Field(..., max_length=100)
    plan_title: str = Field(..., min_length=1, max_length=200)
    plan_markdown: str = Field(..., min_length=1, max_length=200000)
    conversation_id: str = Field(..., min_length=1, max_length=100)
    manager_email: str = Field(..., min_length=3, max_length=320)
    manager_callback_url: str = Field(..., min_length=1, max_length=2000)
    manager_callback_token: str = Field(..., min_length=1, max_length=255)

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        """request_type を固定値で検証する。"""
        cleaned = _sanitize_text(value)
        if cleaned != "manager_approval":
            raise ValueError("request_type must be manager_approval")
        return cleaned

    @field_validator("plan_title", "plan_markdown", "conversation_id", "manager_callback_token")
    @classmethod
    def sanitize_required_text(cls, value: str) -> str:
        """必須文字列を正規化する。"""
        cleaned = _sanitize_text(value)
        if not cleaned:
            raise ValueError("empty value is not allowed")
        return cleaned

    @field_validator("manager_email")
    @classmethod
    def validate_manager_email(cls, value: str) -> str:
        """宛先メールアドレスを検証する。"""
        email = _sanitize_email(value)
        if not email:
            raise ValueError("manager_email is required")
        return email

    @field_validator("manager_callback_url")
    @classmethod
    def validate_manager_callback_url(cls, value: str) -> str:
        """callback URL を最小限検証する。"""
        cleaned = _sanitize_text(value)
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("manager_callback_url must start with http:// or https://")
        return cleaned


@dataclass(frozen=True)
class MockWorkflowSettings:
    """mock workflow の動作設定。"""

    decision: str
    comment: str
    approver_email: str | None
    delay_seconds: float


def _load_mock_workflow_settings() -> MockWorkflowSettings:
    """環境変数から mock workflow 設定を読み込む。"""
    raw_decision = _sanitize_text(os.getenv("MOCK_MANAGER_APPROVAL_DECISION", "approve")).lower()
    decision = raw_decision if raw_decision in {"approve", "reject"} else "approve"

    raw_delay_seconds = _sanitize_text(os.getenv("MOCK_MANAGER_APPROVAL_DELAY_SECONDS", str(_DEFAULT_DELAY_SECONDS)))
    try:
        delay_seconds = max(0.0, float(raw_delay_seconds))
    except ValueError:
        delay_seconds = _DEFAULT_DELAY_SECONDS

    comment = _sanitize_text(os.getenv("MOCK_MANAGER_APPROVAL_COMMENT"))
    approver_email = _sanitize_email(os.getenv("MOCK_MANAGER_APPROVAL_APPROVER_EMAIL")) or None
    if decision == "reject" and not comment:
        comment = DEFAULT_REJECTION_COMMENT

    return MockWorkflowSettings(
        decision=decision,
        comment=comment,
        approver_email=approver_email,
        delay_seconds=delay_seconds,
    )


def _build_callback_payload(
    request_body: ManagerApprovalWorkflowRequest,
    workflow_settings: MockWorkflowSettings,
) -> dict[str, object]:
    """callback 用 payload を組み立てる。"""
    approved = workflow_settings.decision == "approve"
    return {
        "conversation_id": request_body.conversation_id,
        "approved": approved,
        "comment": "" if approved else workflow_settings.comment,
        "approver_email": workflow_settings.approver_email or request_body.manager_email,
        "callback_token": request_body.manager_callback_token,
    }


async def _send_manager_callback(callback_url: str, callback_payload: dict[str, object]) -> None:
    """FastAPI 本体の callback endpoint へ承認結果を送る。"""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Manager-Approval-Token": str(callback_payload["callback_token"]),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(callback_url, json=callback_payload, headers=headers)
        response.raise_for_status()


async def _run_manager_callback(
    callback_url: str,
    callback_payload: dict[str, object],
    delay_seconds: float,
) -> None:
    """少し待ってから callback を送信する。"""
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    try:
        await _send_manager_callback(callback_url, callback_payload)
        logger.info(
            "Mock manager approval callback sent: conversation_id=%s approved=%s",
            callback_payload["conversation_id"],
            callback_payload["approved"],
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Mock manager approval callback failed: conversation_id=%s error=%s",
            callback_payload["conversation_id"],
            exc,
        )


app = FastAPI(title="Mock Manager Approval Workflow")


@app.get("/health")
async def health() -> dict[str, str]:
    """ヘルスチェックを返す。"""
    return {"status": "ok"}


@app.post("/manager-approval", status_code=202)
async def manager_approval(
    body: ManagerApprovalWorkflowRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    """上司承認 request を受け取り、遅延後に callback する。"""
    try:
        workflow_settings = _load_mock_workflow_settings()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    callback_payload = _build_callback_payload(body, workflow_settings)
    background_tasks.add_task(
        _run_manager_callback,
        body.manager_callback_url,
        callback_payload,
        workflow_settings.delay_seconds,
    )
    logger.info(
        "Mock manager approval queued: conversation_id=%s manager=%s decision=%s delay=%.1fs",
        body.conversation_id,
        body.manager_email,
        workflow_settings.decision,
        workflow_settings.delay_seconds,
    )
    return {
        "status": "accepted",
        "conversation_id": body.conversation_id,
        "decision": workflow_settings.decision,
    }
