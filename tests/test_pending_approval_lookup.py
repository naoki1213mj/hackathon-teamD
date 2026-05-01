"""approval context lookup の cross-owner 許容ロジックの単体テスト。"""
from __future__ import annotations

from src.api import chat as chat_module


def _setup_pending(conversation_id: str, owner_id: str, plan_text: str = "Test plan") -> None:
    chat_module._store_pending_approval_context(
        conversation_id,
        {
            "user_input": "test",
            "analysis_markdown": "analysis",
            "plan_markdown": plan_text,
            "model_settings": None,
            "workflow_settings": None,
            "approval_scope": "user",
            "manager_callback_token": None,
            "owner_id": owner_id,
            "conversation_settings": {"work_iq_enabled": False, "source_scope": []},
        },
    )


def test_can_access_pending_approval_exact_match() -> None:
    """両 owner_id が同一 → 許可"""
    assert chat_module._can_access_pending_approval("user-abc", "user-abc") is True


def test_can_access_pending_approval_either_empty() -> None:
    """片方が空 → 許可 (legacy 互換)"""
    assert chat_module._can_access_pending_approval("", "user-abc") is True
    assert chat_module._can_access_pending_approval("user-abc", "") is True
    assert chat_module._can_access_pending_approval("", "") is True


def test_can_access_pending_approval_anonymous_pair() -> None:
    """両方とも匿名 (anon-* prefix) → 許可 (fingerprint 揺らぎ吸収)"""
    assert chat_module._can_access_pending_approval("anon-aaaa", "anon-bbbb") is True


def test_can_access_pending_approval_real_user_mismatch() -> None:
    """実ユーザー間の cross-owner は禁止"""
    assert chat_module._can_access_pending_approval("user-abc", "user-xyz") is False


def test_can_access_pending_approval_anon_to_real_user() -> None:
    """匿名 → 実ユーザー所有の pending へのアクセスは禁止"""
    assert chat_module._can_access_pending_approval("user-abc", "anon-bbbb") is False
    assert chat_module._can_access_pending_approval("anon-bbbb", "user-abc") is False


def test_get_pending_from_memory_exact_match() -> None:
    """同じ owner_id で store→lookup は確実にヒット"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-1", "anon-aaaa")
    ctx = chat_module._get_pending_approval_context_from_memory("conv-1", "anon-aaaa")
    assert ctx is not None
    assert ctx["plan_markdown"] == "Test plan"
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_anonymous_drift() -> None:
    """匿名 owner の fingerprint 揺らぎ (anon-A → anon-B) でも lookup できる"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-2", "anon-original")
    # 異なる anon-* 値で lookup
    ctx = chat_module._get_pending_approval_context_from_memory("conv-2", "anon-different")
    assert ctx is not None, "匿名 fingerprint 揺らぎでも lookup できるべき"
    assert ctx["plan_markdown"] == "Test plan"
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_real_user_isolation() -> None:
    """実ユーザー (user-*) 間の cross-owner lookup は不可"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-3", "user-alice")
    ctx_other = chat_module._get_pending_approval_context_from_memory("conv-3", "user-mallory")
    assert ctx_other is None, "別実ユーザーは pending にアクセスできてはいけない"
    ctx_owner = chat_module._get_pending_approval_context_from_memory("conv-3", "user-alice")
    assert ctx_owner is not None
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_anon_to_real_blocked() -> None:
    """匿名 lookup から実ユーザー所有の pending には到達できない"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-4", "user-alice")
    ctx = chat_module._get_pending_approval_context_from_memory("conv-4", "anon-stranger")
    assert ctx is None, "匿名 lookup は実ユーザー pending にアクセス不可"
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_empty_lookup() -> None:
    """owner_id 未指定の lookup でも legacy 互換でヒット"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-5", "anon-aaaa")
    ctx = chat_module._get_pending_approval_context_from_memory("conv-5")
    assert ctx is not None
    chat_module._pending_approvals.clear()
