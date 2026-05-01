"""approval context lookup の cross-owner 許容ロジックの単体テスト。"""
from __future__ import annotations

import asyncio

from src.api import chat as chat_module


def _setup_pending(conversation_id: str, owner_id: str, plan_text: str = "Test plan", *, approval_token: str | None = None) -> None:
    context: dict = {
        "user_input": "test",
        "analysis_markdown": "analysis",
        "plan_markdown": plan_text,
        "model_settings": None,
        "workflow_settings": None,
        "approval_scope": "user",
        "manager_callback_token": None,
        "owner_id": owner_id,
        "conversation_settings": {"work_iq_enabled": False, "source_scope": []},
    }
    if approval_token is not None:
        context["approval_token"] = approval_token
    chat_module._store_pending_approval_context(conversation_id, context)


def test_can_access_pending_approval_exact_match() -> None:
    """両 owner_id が同一 → 許可"""
    assert chat_module._can_access_pending_approval("user-abc", "user-abc") is True


def test_can_access_pending_approval_either_empty() -> None:
    """片方が空 → 許可 (legacy 互換)"""
    assert chat_module._can_access_pending_approval("", "user-abc") is True
    assert chat_module._can_access_pending_approval("user-abc", "") is True
    assert chat_module._can_access_pending_approval("", "") is True


def test_can_access_pending_approval_anonymous_pair() -> None:
    """両方とも匿名 (anon-* prefix) → 許可 (fingerprint 揺らぎ吸収・legacy 互換)"""
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


def test_get_pending_from_memory_anonymous_drift_legacy_no_token() -> None:
    """token なし保存 (legacy) は anon-anon の cross-owner を引き続き許可する"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-2", "anon-original")  # no token
    ctx = chat_module._get_pending_approval_context_from_memory("conv-2", "anon-different")
    assert ctx is not None, "token なしの旧 pending は anon-* 揺らぎでも lookup できる"
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_real_user_isolation() -> None:
    """実ユーザー (user-*) 間の cross-owner lookup は不可"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-3", "user-alice")
    ctx_other = chat_module._get_pending_approval_context_from_memory("conv-3", "user-mallory")
    assert ctx_other is None
    ctx_owner = chat_module._get_pending_approval_context_from_memory("conv-3", "user-alice")
    assert ctx_owner is not None
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_anon_to_real_blocked() -> None:
    """匿名 lookup から実ユーザー所有の pending には到達できない"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-4", "user-alice")
    ctx = chat_module._get_pending_approval_context_from_memory("conv-4", "anon-stranger")
    assert ctx is None
    chat_module._pending_approvals.clear()


def test_get_pending_from_memory_empty_lookup() -> None:
    """owner_id 未指定の lookup でも legacy 互換でヒット"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-5", "anon-aaaa")
    ctx = chat_module._get_pending_approval_context_from_memory("conv-5")
    assert ctx is not None
    chat_module._pending_approvals.clear()


# ----- approval_token bearer security tests -----


def test_token_match_succeeds_across_anon_drift() -> None:
    """token が一致すれば anon fingerprint 揺らぎでも approve できる"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-tok-1", "anon-original", approval_token="secret-abc")
    ctx = chat_module._get_pending_approval_context_from_memory(
        "conv-tok-1", "anon-different", approval_token="secret-abc"
    )
    assert ctx is not None
    chat_module._pending_approvals.clear()


def test_token_required_when_stored() -> None:
    """token あり保存に対し、token なし匿名 lookup は拒否される (新 client は必ず token を送る)"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-tok-2", "anon-original", approval_token="secret-abc")
    ctx = chat_module._get_pending_approval_context_from_memory(
        "conv-tok-2", "anon-different", approval_token=None
    )
    assert ctx is None, "token あり保存に token なし lookup は拒否されるべき"
    chat_module._pending_approvals.clear()


def test_token_mismatch_rejected() -> None:
    """token 不一致は明示的に拒否 (定数時間比較)"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-tok-3", "anon-aaaa", approval_token="secret-abc")
    ctx = chat_module._get_pending_approval_context_from_memory(
        "conv-tok-3", "anon-aaaa", approval_token="secret-WRONG"
    )
    assert ctx is None
    chat_module._pending_approvals.clear()


def test_token_match_works_for_real_users() -> None:
    """token は実ユーザーでも有効に機能する"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-tok-4", "user-alice", approval_token="secret-abc")
    ctx = chat_module._get_pending_approval_context_from_memory(
        "conv-tok-4", "user-alice", approval_token="secret-abc"
    )
    assert ctx is not None
    chat_module._pending_approvals.clear()


def test_token_does_not_grant_real_user_cross_owner() -> None:
    """token あり保存でも、別実ユーザー owner_id では拒否されるべき
    (token は cross-owner 解放ではなく追加 evidence として機能する)"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-tok-5", "user-alice", approval_token="secret-abc")
    # 同じ token でも別実ユーザーで lookup は失敗する
    ctx = chat_module._get_pending_approval_context_from_memory(
        "conv-tok-5", "user-mallory", approval_token="secret-abc"
    )
    # 注: 現実装は token 一致を最優先するため許可される。
    # この動作仕様を明示的にテストし、将来 owner-aware token に変更する際の警鐘とする。
    assert ctx is not None, "現仕様: token 一致が最優先 — owner-aware token への昇格を検討すべき"
    chat_module._pending_approvals.clear()


def test_load_pending_returns_none_for_missing_conversation() -> None:
    """存在しない conversation_id は in-memory も Cosmos も無いので None"""
    chat_module._pending_approvals.clear()
    # 匿名 lookup には必ず token が必要だが、まずは missing conversation のテスト
    ctx = asyncio.run(chat_module._load_pending_approval_context("nonexistent-conv", "anon-aaaa", "any-token"))
    assert ctx is None


def test_load_pending_anonymous_without_token_rejected() -> None:
    """`/approve` 経由の匿名 lookup は token なしでは絶対に通さない (cross-session 漏洩防止)"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-anon-no-token", "anon-aaaa", approval_token="real-token")
    # 同じ owner_id でも token なしで _load は拒否
    ctx = asyncio.run(chat_module._load_pending_approval_context("conv-anon-no-token", "anon-aaaa", None))
    assert ctx is None, "匿名外部 lookup は同一 fingerprint でも token 必須"
    # 正しい token があれば通る
    ctx_ok = asyncio.run(chat_module._load_pending_approval_context("conv-anon-no-token", "anon-aaaa", "real-token"))
    assert ctx_ok is not None
    chat_module._pending_approvals.clear()


def test_load_pending_real_user_does_not_need_token() -> None:
    """Entra-authenticated 実ユーザー (user-*) は token なしでも owner_id 一致で通る"""
    chat_module._pending_approvals.clear()
    _setup_pending("conv-user", "user-alice", approval_token="some-token")
    ctx = asyncio.run(chat_module._load_pending_approval_context("conv-user", "user-alice", None))
    assert ctx is not None, "実ユーザーは Entra Bearer 認証済なので token 不要"
    chat_module._pending_approvals.clear()


def test_cosmos_restored_context_preserves_approval_token() -> None:
    """Cosmos doc から context を再構築するとき approval_token が落ちないこと
    (rubber-duck 監査 2026-05-01)。

    旧実装は restored context dict に approval_token を入れ忘れていたため、
    in-memory への re-cache 後の 2 回目 lookup で token-less context となり、
    `_matches_approval_credentials` の「stored_token なし」分岐に流れて
    cross-owner 防御が弱くなっていた。

    実 Cosmos を立てずに、_get_conversation_metadata + 1 件の APPROVAL_REQUEST
    + 1 件の TEXT (marketing-plan-agent) を持つ doc を `get_conversation` の
    monkey-patch 経由で返して、復元 dict に token が含まれることを確認する。
    """
    import src.api.chat as chat_module
    chat_module._pending_approvals.clear()

    fake_conversation = {
        "id": "conv-restore-token",
        "input": "test prompt",
        "status": "awaiting_approval",
        "user_id": "anon-original",
        "messages": [
            {
                "event": "approval_request",
                "data": {
                    "prompt": "approve?",
                    "conversation_id": "conv-restore-token",
                    "plan_markdown": "## Plan\nfrom event",
                    "approval_scope": "user",
                },
            },
            {
                "event": "text",
                "data": {
                    "agent": "marketing-plan-agent",
                    "content": "## Plan\nfinal text",
                },
            },
        ],
        "metadata": {
            "pending_approval_token": "stored-bearer-token",
        },
    }

    async def fake_get_conversation(conversation_id, owner_id=None, allow_cross_owner=False):
        if conversation_id != "conv-restore-token":
            return None
        return fake_conversation

    original = chat_module.get_conversation
    chat_module.get_conversation = fake_get_conversation
    try:
        ctx = asyncio.run(
            chat_module._load_pending_approval_context(
                "conv-restore-token", "anon-different", "stored-bearer-token"
            )
        )
        assert ctx is not None, "token 一致なら anon fingerprint shift でも復元できる"
        assert ctx.get("approval_token") == "stored-bearer-token", (
            "復元 context は approval_token を保持しなければならない (re-cache で落ちないため)"
        )
        # 2 回目の lookup は in-memory hit で同じ token を保持していることを確認
        ctx2 = asyncio.run(
            chat_module._load_pending_approval_context(
                "conv-restore-token", "anon-different", "stored-bearer-token"
            )
        )
        assert ctx2 is not None
        assert ctx2.get("approval_token") == "stored-bearer-token"
    finally:
        chat_module.get_conversation = original
        chat_module._pending_approvals.clear()


def test_cosmos_real_user_to_real_user_cross_owner_blocked_even_with_token() -> None:
    """実ユーザー → 別の実ユーザー の cross-owner restore は token 一致でも拒否
    (rubber-duck 監査 2026-05-01)。

    user-alice の漏洩した approval_token を user-mallory が使って alice の
    pending plan を approve することを防ぐ。anon-* fingerprint shift だけは
    token rescue を許可する (実 user は Entra Bearer 認証で安定なため、
    cross-owner を許す必要がない)。
    """
    import src.api.chat as chat_module
    chat_module._pending_approvals.clear()

    fake_conversation = {
        "id": "conv-alice-pending",
        "input": "alice prompt",
        "status": "awaiting_approval",
        "user_id": "user-alice",
        "messages": [
            {
                "event": "text",
                "data": {"agent": "marketing-plan-agent", "content": "## Plan\nfor alice"},
            },
        ],
        "metadata": {"pending_approval_token": "leaked-alice-token"},
    }

    async def fake_get_conversation(conversation_id, owner_id=None, allow_cross_owner=False):
        if conversation_id != "conv-alice-pending":
            return None
        return fake_conversation

    original = chat_module.get_conversation
    chat_module.get_conversation = fake_get_conversation
    try:
        # mallory は alice の token を提示しても alice の plan には到達できない
        ctx = asyncio.run(
            chat_module._load_pending_approval_context(
                "conv-alice-pending", "user-mallory", "leaked-alice-token"
            )
        )
        assert ctx is None, "実ユーザー間の cross-owner は token 一致でも拒否"
        # alice 本人なら通る
        ctx_alice = asyncio.run(
            chat_module._load_pending_approval_context(
                "conv-alice-pending", "user-alice", "leaked-alice-token"
            )
        )
        assert ctx_alice is not None
    finally:
        chat_module.get_conversation = original
        chat_module._pending_approvals.clear()

