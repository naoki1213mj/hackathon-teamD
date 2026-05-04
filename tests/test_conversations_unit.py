"""conversations モジュールのユニットテスト（インメモリストア）"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.conversations as _conv_mod
from src.conversations import (
    _build_memory_key,
    _get_container,
    _get_cosmos_client,
    _memory_store,
    append_conversation_events,
    get_conversation,
    get_replay_data,
    list_conversations,
    replace_conversation_metadata,
    save_conversation,
    save_replay_data,
)


@pytest.fixture(autouse=True)
def _clear_memory_store(monkeypatch):
    """各テスト前にインメモリストアをクリアし、Cosmos DB シングルトンをリセットする"""
    _memory_store.clear()
    _conv_mod._conversation_locks.clear()
    monkeypatch.delenv("COSMOS_DB_ENDPOINT", raising=False)
    # シングルトンをリセットして各テストが独立して初期化できるようにする
    _conv_mod._cosmos_client = None
    _conv_mod._cosmos_initialized = False
    _conv_mod._cosmos_retry_after_monotonic = 0.0
    yield
    _memory_store.clear()
    _conv_mod._conversation_locks.clear()
    _conv_mod._cosmos_client = None
    _conv_mod._cosmos_initialized = False
    _conv_mod._cosmos_retry_after_monotonic = 0.0


# --- 既存テスト ---


async def test_save_conversation_to_memory():
    """インメモリストアに会話を保存できる"""
    await save_conversation(
        conversation_id="test-conv-1",
        user_input="沖縄プラン作って",
        events=[{"event": "text", "data": "ok"}],
    )
    assert _build_memory_key("anonymous", "test-conv-1") in _memory_store
    assert _memory_store[_build_memory_key("anonymous", "test-conv-1")]["input"] == "沖縄プラン作って"


async def test_save_conversation_preserves_status():
    """明示した status が保存される"""
    await save_conversation(
        conversation_id="test-conv-status",
        user_input="承認待ちプラン",
        events=[],
        status="awaiting_approval",
    )
    assert _memory_store[_build_memory_key("anonymous", "test-conv-status")]["status"] == "awaiting_approval"


async def test_save_conversation_preserves_created_at_on_update():
    """同一 conversation_id の更新でも created_at は維持される"""
    await save_conversation(
        conversation_id="test-conv-update",
        user_input="初回",
        events=[],
        status="awaiting_approval",
    )
    created_at = _memory_store[_build_memory_key("anonymous", "test-conv-update")]["created_at"]

    await save_conversation(
        conversation_id="test-conv-update",
        user_input="更新後",
        events=[{"event": "done", "data": {}}],
        status="completed",
    )

    assert _memory_store[_build_memory_key("anonymous", "test-conv-update")]["created_at"] == created_at
    assert _memory_store[_build_memory_key("anonymous", "test-conv-update")]["status"] == "completed"


async def test_append_conversation_events_preserves_existing_messages():
    """append 保存は既存メッセージを消さずに新規イベントだけを追記する"""
    await save_conversation(
        conversation_id="test-conv-append",
        user_input="初回入力",
        events=[{"event": "text", "data": {"content": "# Plan v1"}}],
        metrics={"user_messages": ["初回入力"]},
    )

    await append_conversation_events(
        conversation_id="test-conv-append",
        user_input=None,
        new_events=[{"event": "evaluation_result", "data": {"version": 1, "round": 1, "result": {"builtin": {}}}}],
        metrics={"background_updates_pending": False},
        status="completed",
    )

    doc = _memory_store[_build_memory_key("anonymous", "test-conv-append")]
    assert [event["event"] for event in doc["messages"]] == ["text", "evaluation_result"]
    assert doc["metadata"]["user_messages"] == ["初回入力"]
    assert doc["metadata"]["background_updates_pending"] is False


async def test_append_conversation_events_replaces_metadata_when_requested():
    """明示 replace 時は消したい metadata キーを残さない"""
    await save_conversation(
        conversation_id="test-conv-metadata-replace",
        user_input="初回入力",
        events=[{"event": "text", "data": {"content": "# Plan v1"}}],
        metrics={
            "user_messages": ["初回入力"],
            "background_updates_pending": True,
            "manager_approval_callback_token": "secret-token",
        },
    )

    await append_conversation_events(
        conversation_id="test-conv-metadata-replace",
        user_input=None,
        new_events=[],
        metrics=replace_conversation_metadata({"user_messages": ["初回入力"]}),
        status="completed",
    )

    doc = _memory_store[_build_memory_key("anonymous", "test-conv-metadata-replace")]
    assert doc["metadata"] == {"user_messages": ["初回入力"]}


async def test_get_conversation_from_memory():
    """保存した会話をインメモリストアから取得できる"""
    await save_conversation(
        conversation_id="test-conv-2",
        user_input="春プランを企画",
        events=[],
    )
    result = await get_conversation("test-conv-2")
    assert result is not None
    assert result["id"] == "test-conv-2"
    assert result["input"] == "春プランを企画"


async def test_list_conversations_from_memory():
    """limit 付きで会話一覧を取得できる"""
    for i in range(5):
        await save_conversation(
            conversation_id=f"list-conv-{i}",
            user_input=f"query {i}",
            events=[],
        )
    result = await list_conversations(limit=3)
    assert len(result) == 3


async def test_get_replay_data_fallback_to_json():
    """Cosmos DB 未設定・インメモリにもない場合、demo-replay.json にフォールバックする"""
    replay_file = Path(__file__).resolve().parent.parent / "data" / "demo-replay.json"
    if not replay_file.exists():
        pytest.skip("demo-replay.json が見つからない")

    result = await get_replay_data("demo-replay-001")
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0


# --- 大きな画像の永続化向け切り詰め (Bug 4 root-cause fix) ---


class TestImageTruncationForPersistence:
    """`_truncate_large_images_for_persistence` のテスト。

    Cosmos 2MB 制限を超えないよう、image event の大きな data URL を
    SVG プレースホルダで置換するヘルパの不変条件を検証する。
    Bug 4 root cause: brochure-gen の base64 PNG (1 枚 ~1MB) が複数
    保存されると Cosmos が 413 で拒否し in-memory フォールバック
    → polling restoreConversation が古い `awaiting_approval` を読んで
    UI が承認画面に戻る。
    """

    def test_truncates_large_base64_image_url(self):
        from src.conversations import _truncate_large_images_for_persistence

        large_payload = "A" * 300_000  # 300KB > 256KB threshold
        events = [
            {"event": "image", "data": {"url": f"data:image/png;base64,{large_payload}", "alt": "hero", "agent": "brochure-gen-agent"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert len(result) == 1
        assert result[0]["event"] == "image"
        assert result[0]["data"]["url"].startswith("data:image/svg+xml")
        assert result[0]["data"]["truncated"] is True
        assert result[0]["data"]["original_size_bytes"] >= 300_000
        assert result[0]["data"]["alt"] == "hero"
        assert result[0]["data"]["agent"] == "brochure-gen-agent"
        # original event は破壊されない (引数 list の元 dict は不変)
        assert events[0]["data"]["url"].startswith("data:image/png;base64,")

    def test_keeps_small_data_url_untouched(self):
        from src.conversations import _truncate_large_images_for_persistence

        small_svg = "data:image/svg+xml;charset=utf-8,%3Csvg/%3E"
        events = [
            {"event": "image", "data": {"url": small_svg, "alt": "fallback"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["url"] == small_svg
        assert "truncated" not in result[0]["data"]

    def test_keeps_http_url_untouched(self):
        from src.conversations import _truncate_large_images_for_persistence

        events = [
            {"event": "image", "data": {"url": "https://example.com/img.png", "alt": "remote"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["url"] == "https://example.com/img.png"
        assert "truncated" not in result[0]["data"]

    def test_keeps_text_and_tool_events_untouched(self):
        from src.conversations import _truncate_large_images_for_persistence

        large_text = "B" * 300_000
        events = [
            {"event": "text", "data": {"content": large_text, "agent": "brochure-gen-agent"}},
            {"event": "tool_event", "data": {"tools": ["search"], "agent": "data-search-agent"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["content"] == large_text
        assert result[1]["data"]["tools"] == ["search"]

    def test_truncates_multiple_images_independently(self):
        from src.conversations import _truncate_large_images_for_persistence

        large_payload = "A" * 300_000
        events = [
            {"event": "image", "data": {"url": f"data:image/png;base64,{large_payload}", "alt": "hero"}},
            {"event": "text", "data": {"content": "ok"}},
            {"event": "image", "data": {"url": f"data:image/png;base64,{large_payload}", "alt": "banner"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["truncated"] is True
        assert result[0]["data"]["alt"] == "hero"
        assert result[1]["data"]["content"] == "ok"
        assert result[2]["data"]["truncated"] is True
        assert result[2]["data"]["alt"] == "banner"

    def test_handles_non_list_input(self):
        from src.conversations import _truncate_large_images_for_persistence

        assert _truncate_large_images_for_persistence(None) == []
        assert _truncate_large_images_for_persistence("not a list") == []
        assert _truncate_large_images_for_persistence({}) == []

    def test_handles_malformed_event_entries(self):
        from src.conversations import _truncate_large_images_for_persistence

        events = [
            "not a dict",
            {"event": "image", "data": "not a dict"},
            {"event": "image", "data": {"url": 12345}},
            {"event": "image"},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result == events

    async def test_save_conversation_truncates_large_images_in_cosmos_doc(self):
        """save_conversation 経由で Cosmos doc 上の大きな画像が切り詰められる (E2E)."""
        large_payload = "A" * 300_000
        await save_conversation(
            conversation_id="test-truncation-e2e",
            user_input="ハワイプラン",
            events=[
                {"event": "text", "data": {"content": "# プラン", "agent": "marketing-plan-agent"}},
                {"event": "image", "data": {"url": f"data:image/png;base64,{large_payload}", "alt": "hero", "agent": "brochure-gen-agent"}},
            ],
            status="completed",
        )

        doc = _memory_store[_build_memory_key("anonymous", "test-truncation-e2e")]
        assert doc["messages"][0]["data"]["content"] == "# プラン"
        assert doc["messages"][1]["data"]["url"].startswith("data:image/svg+xml")
        assert doc["messages"][1]["data"]["truncated"] is True
        assert doc["messages"][1]["data"]["alt"] == "hero"

    def test_truncates_inline_data_url_in_brochure_html_text_event(self):
        """rubber-duck blocking #1: brochure HTML の inline `<img src="data:...">` も切り詰める。"""
        from src.conversations import _truncate_large_images_for_persistence

        large_payload = "A" * 300_000
        html = (
            "<section class='brochure'>"
            f'<img src="data:image/png;base64,{large_payload}" alt="hero" />'
            f"<img src='data:image/png;base64,{large_payload}' alt='banner' />"
            '<img src="https://example.com/small.png" alt="ok" />'
            "</section>"
        )
        events = [
            {"event": "text", "data": {"content": html, "content_type": "html", "agent": "brochure-gen-agent"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        new_html = result[0]["data"]["content"]
        assert f"base64,{large_payload}" not in new_html
        assert "data:image/svg+xml" in new_html
        assert "https://example.com/small.png" in new_html
        assert result[0]["data"]["truncated_inline_images"] == 2
        assert result[0]["data"]["agent"] == "brochure-gen-agent"

    def test_keeps_small_inline_data_url_in_html_untouched(self):
        from src.conversations import _truncate_large_images_for_persistence

        small_svg = "data:image/svg+xml;charset=utf-8,%3Csvg/%3E"
        html = f'<div><img src="{small_svg}" alt="ok"/></div>'
        events = [
            {"event": "text", "data": {"content": html, "content_type": "html"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["content"] == html
        assert "truncated_inline_images" not in result[0]["data"]

    def test_html_truncation_skipped_when_content_type_not_html(self):
        from src.conversations import _truncate_large_images_for_persistence

        large_payload = "A" * 300_000
        text_with_data_uri = f'see <img src="data:image/png;base64,{large_payload}">'
        events = [
            # content_type missing or != 'html' → text event must NOT be HTML-scanned
            {"event": "text", "data": {"content": text_with_data_uri, "agent": "marketing-plan-agent"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        # plain markdown / LLM text 内に偶然 data: URI があっても触らない。
        assert result[0]["data"]["content"] == text_with_data_uri

    def test_truncates_html_img_with_whitespace_around_equals(self):
        """rubber-duck pr1-final-review blocking #1: `src = "data:..."` も切り詰める。"""
        from src.conversations import _truncate_inline_data_urls_in_html

        large_payload = "A" * 300_000
        html = f'<img src = "data:image/png;base64,{large_payload}" alt="hero">'

        truncated, count = _truncate_inline_data_urls_in_html(html)

        assert count == 1
        assert f"base64,{large_payload}" not in truncated
        assert "data:image/svg+xml" in truncated

    def test_truncates_html_img_unquoted_data_url(self):
        """rubber-duck pr1-final-review blocking #1: `src=data:...` (no quotes) も切り詰める。"""
        from src.conversations import _truncate_inline_data_urls_in_html

        large_payload = "A" * 300_000
        # Note: large payload contains no whitespace / quotes so unquoted is parser-valid
        html = f'<img src=data:image/png;base64,{large_payload} alt="hero">'

        truncated, count = _truncate_inline_data_urls_in_html(html)

        assert count == 1
        assert f"base64,{large_payload}" not in truncated
        assert "data:image/svg+xml" in truncated
        # 安全のためクォートで囲み直す
        assert '"data:image/svg+xml' in truncated

    async def test_truncate_then_merge_dedupes_same_image_across_saves(self):
        """rubber-duck blocking #2: 既存 doc の truncated event と incoming full-image
        event は truncate 後に同じ placeholder JSON になるので dedupe で 1 個にまとまる。
        """
        large_payload = "A" * 300_000
        full_image_event = {
            "event": "image",
            "data": {"url": f"data:image/png;base64,{large_payload}", "alt": "hero", "agent": "brochure-gen-agent"},
        }
        # 1st save: 元の full-image event を渡す → Cosmos doc には truncated 版が永続化される
        await save_conversation(
            conversation_id="test-dedupe",
            user_input="ハワイプラン",
            events=[full_image_event],
            status="awaiting_approval",
        )
        first_doc = _memory_store[_build_memory_key("anonymous", "test-dedupe")]
        assert len(first_doc["messages"]) == 1
        assert first_doc["messages"][0]["data"]["truncated"] is True

        # 2nd save: 同じ full-image event を再度送る (e.g. 同じセッション中の 2 回目保存)
        # truncate-before-merge により既存 truncated と incoming truncated が同一 JSON
        # になり、_merge_event_histories の identity-dedupe で 1 個にまとまる。
        await save_conversation(
            conversation_id="test-dedupe",
            user_input="ハワイプラン",
            events=[full_image_event],
            status="completed",
        )
        second_doc = _memory_store[_build_memory_key("anonymous", "test-dedupe")]

        # 重複しないこと: image event は 1 つだけ残る
        image_events = [m for m in second_doc["messages"] if m.get("event") == "image"]
        assert len(image_events) == 1
        assert image_events[0]["data"]["truncated"] is True

    def test_truncates_large_jpeg_data_url(self):
        """rubber-duck `image-jpeg-fix-plan` SHOULD-FIX: JPEG data URL も同じく truncate される。"""
        from src.conversations import _truncate_large_images_for_persistence

        large_payload = "Q" * 300_000  # > 256KB threshold
        events = [
            {"event": "image", "data": {"url": f"data:image/jpeg;base64,{large_payload}", "alt": "hero"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["url"].startswith("data:image/svg+xml")
        assert result[0]["data"]["truncated"] is True

    def test_truncates_inline_jpeg_data_url_in_html(self):
        """JPEG inline data URL も HTML scan で truncate される。"""
        from src.conversations import _truncate_inline_data_urls_in_html

        large_payload = "Q" * 300_000
        html = f'<img src="data:image/jpeg;base64,{large_payload}" alt="hero">'

        truncated, count = _truncate_inline_data_urls_in_html(html)

        assert count == 1
        assert "data:image/svg+xml" in truncated
        assert f"base64,{large_payload}" not in truncated

    def test_keeps_jpeg_below_threshold_untouched(self):
        """256KB 未満の JPEG (典型的な banner サイズ) はそのまま保存される。
        rubber-duck `image-jpeg-fix-plan` の主目的: JPEG 圧縮で大半の画像を
        whole 保存できるようにする。
        """
        from src.conversations import _truncate_large_images_for_persistence

        # 200KB JPEG (~150KB binary 相当): 256KB threshold 未満
        small_payload = "Q" * 200_000
        events = [
            {"event": "image", "data": {"url": f"data:image/jpeg;base64,{small_payload}", "alt": "banner"}},
        ]
        result = _truncate_large_images_for_persistence(events)

        assert result[0]["data"]["url"].startswith("data:image/jpeg;base64,")
        assert "truncated" not in result[0]["data"]

    def test_threshold_exact_boundary(self):
        """rubber-duck `image-jpeg-fix-impl-review` non-blocking #3 boundary case:
        data URL が exactly 256KB のとき (border) は truncate されない (`>` 比較)。
        境界 + 1 byte で truncate されることも確認する。
        """
        from src.conversations import (
            _MAX_PERSISTED_IMAGE_DATA_URL_BYTES,
            _truncate_large_images_for_persistence,
        )

        prefix = "data:image/jpeg;base64,"
        # exactly threshold: payload を threshold - len(prefix) で揃えると total が
        # ちょうど threshold になる
        exact_payload = "Q" * (_MAX_PERSISTED_IMAGE_DATA_URL_BYTES - len(prefix))
        url_exact = f"{prefix}{exact_payload}"
        assert len(url_exact) == _MAX_PERSISTED_IMAGE_DATA_URL_BYTES

        events_exact = [{"event": "image", "data": {"url": url_exact, "alt": "edge"}}]
        result_exact = _truncate_large_images_for_persistence(events_exact)
        assert result_exact[0]["data"]["url"] == url_exact, "境界値ぴったりは truncate されない"
        assert "truncated" not in result_exact[0]["data"]

        # +1 byte over threshold: truncate される
        over_payload = exact_payload + "Q"
        url_over = f"{prefix}{over_payload}"
        assert len(url_over) > _MAX_PERSISTED_IMAGE_DATA_URL_BYTES

        events_over = [{"event": "image", "data": {"url": url_over, "alt": "edge"}}]
        result_over = _truncate_large_images_for_persistence(events_over)
        assert result_over[0]["data"]["url"].startswith("data:image/svg+xml")
        assert result_over[0]["data"]["truncated"] is True


# --- 新規テスト ---


class TestCosmosClientInit:
    """Cosmos DB クライアント初期化テスト"""

    def test_no_endpoint_returns_none(self, monkeypatch):
        """COSMOS_DB_ENDPOINT 未設定時は None"""
        monkeypatch.delenv("COSMOS_DB_ENDPOINT", raising=False)
        assert _get_cosmos_client() is None

    def test_import_error_returns_none(self, monkeypatch):
        """azure-cosmos 未インストール時は None"""
        monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://test.documents.azure.com:443/")

        with patch("builtins.__import__", side_effect=ImportError("No module named 'azure.cosmos'")):
            result = _get_cosmos_client()
            assert result is None

    def test_get_container_returns_none_when_no_client(self, monkeypatch):
        """クライアントが None の場合コンテナも None"""
        monkeypatch.delenv("COSMOS_DB_ENDPOINT", raising=False)
        assert _get_container() is None


class TestSaveConversationDetails:
    """会話保存の詳細テスト"""

    async def test_save_with_artifacts_and_metrics(self):
        """artifacts がバージョン配列として保存されること"""
        await save_conversation(
            conversation_id="test-artifacts",
            user_input="テスト",
            events=[],
            artifacts={"html": "<p>test</p>"},
            metrics={"latency": 1.5},
        )
        doc = _memory_store[_build_memory_key("anonymous", "test-artifacts")]
        assert isinstance(doc["artifacts"], list)
        assert len(doc["artifacts"]) == 1
        assert doc["artifacts"][0]["html"] == "<p>test</p>"
        assert doc["artifacts"][0]["version"] == 1
        assert doc["metadata"] == {"latency": 1.5}

    async def test_save_default_artifacts_and_metrics(self):
        """artifacts/metrics 未指定時は空配列"""
        await save_conversation(
            conversation_id="test-defaults",
            user_input="テスト",
            events=[],
        )
        doc = _memory_store[_build_memory_key("anonymous", "test-defaults")]
        assert doc["artifacts"] == []
        assert doc["metadata"] == {}

    async def test_save_sets_user_id(self):
        """user_id は匿名 owner 既定値に設定されること"""
        await save_conversation(
            conversation_id="test-uid",
            user_input="テスト",
            events=[],
        )
        assert _memory_store[_build_memory_key("anonymous", "test-uid")]["user_id"] == "anonymous"

    async def test_owner_isolation_allows_same_conversation_id_per_user(self):
        """同じ conversation_id でも owner が異なれば別会話として保持できる"""
        await save_conversation("shared-conv", "owner-a", [], owner_id="user-a")
        await save_conversation("shared-conv", "owner-b", [], owner_id="user-b")

        owner_a = await get_conversation("shared-conv", owner_id="user-a")
        owner_b = await get_conversation("shared-conv", owner_id="user-b")

        assert owner_a is not None
        assert owner_b is not None
        assert owner_a["input"] == "owner-a"
        assert owner_b["input"] == "owner-b"

    async def test_save_conversation_merges_existing_metadata(self):
        """metadata は更新時にマージされる"""
        await save_conversation(
            conversation_id="test-metadata-merge",
            user_input="初回",
            events=[],
            metrics={"manager_approval_callback_token": "secret-token"},
        )

        await save_conversation(
            conversation_id="test-metadata-merge",
            user_input="更新",
            events=[],
            metrics={"latency": 1.23},
        )

        assert _memory_store[_build_memory_key("anonymous", "test-metadata-merge")]["metadata"] == {
            "manager_approval_callback_token": "secret-token",
            "latency": 1.23,
        }

    async def test_save_conversation_preserves_background_video_from_stale_full_save(self):
        """stale full-save が先に append 済みの background video を消さない。"""
        base_events = [
            {
                "event": "text",
                "data": {"agent": "brochure-gen-agent", "content_type": "html", "content": "<html>v1</html>"},
            },
            {"event": "done", "data": {"conversation_id": "conv-version-race"}},
        ]
        await save_conversation(
            conversation_id="conv-version-race",
            user_input="初回",
            events=base_events,
            owner_id="user-a",
        )

        await append_conversation_events(
            conversation_id="conv-version-race",
            user_input=None,
            new_events=[
                {
                    "event": "text",
                    "data": {
                        "agent": "video-gen-agent",
                        "content_type": "video",
                        "content": "https://example.com/v1.mp4",
                        "background_update": True,
                        "version": 1,
                    },
                }
            ],
            owner_id="user-a",
        )

        stale_refine_save_events = [
            *base_events,
            {
                "event": "text",
                "data": {"agent": "brochure-gen-agent", "content_type": "html", "content": "<html>v2</html>"},
            },
            {"event": "done", "data": {"conversation_id": "conv-version-race"}},
        ]
        await save_conversation(
            conversation_id="conv-version-race",
            user_input="初回",
            events=stale_refine_save_events,
            owner_id="user-a",
        )

        doc = await get_conversation("conv-version-race", owner_id="user-a")
        assert doc is not None
        messages = doc["messages"]
        assert any(
            event.get("data", {}).get("content") == "https://example.com/v1.mp4"
            and event.get("data", {}).get("version") == 1
            for event in messages
        )
        assert any(event.get("data", {}).get("content") == "<html>v2</html>" for event in messages)


class TestGetConversationEdgeCases:
    """会話取得のエッジケーステスト"""

    async def test_get_nonexistent_returns_none(self):
        """存在しない ID は None"""
        result = await get_conversation("does-not-exist")
        assert result is None

    async def test_list_conversations_empty(self):
        """空のストアからのリスト取得"""
        result = await list_conversations()
        assert result == []

    async def test_list_conversations_sorted_by_created_at(self):
        """会話が created_at の降順でソートされること"""
        await save_conversation("conv-a", "A", [])
        await save_conversation("conv-b", "B", [])
        result = await list_conversations()
        assert len(result) == 2
        # 最新が先頭
        assert result[0]["created_at"] >= result[1]["created_at"]

    async def test_get_conversation_rejects_other_owner(self):
        """別 owner の会話は取得できない"""
        await save_conversation("owner-bound", "secret", [], owner_id="user-a")

        result = await get_conversation("owner-bound", owner_id="user-b")

        assert result is None

    async def test_list_conversations_filters_by_owner(self):
        """一覧は caller owner に属する会話だけ返す"""
        await save_conversation("owner-a-1", "A1", [], owner_id="user-a")
        await save_conversation("owner-a-2", "A2", [], owner_id="user-a")
        await save_conversation("owner-b-1", "B1", [], owner_id="user-b")

        result = await list_conversations(owner_id="user-a")

        assert {item["id"] for item in result} == {"owner-a-1", "owner-a-2"}


class TestReplayData:
    """リプレイデータのテスト"""

    async def test_save_and_get_replay_data(self):
        """リプレイデータの保存と取得"""
        events = [
            {"event": "text", "data": {"content": "hello"}, "timestamp": 0.1},
            {"event": "done", "data": {}, "timestamp": 0.5},
        ]
        await save_replay_data("replay-test-1", events)

        result = await get_replay_data("replay-test-1")
        assert result is not None
        assert len(result) == 2
        assert result[0]["event"] == "text"

    async def test_get_replay_data_nonexistent_without_json(self, monkeypatch, tmp_path):
        """インメモリにもJSONファイルにもない場合"""
        result = await get_replay_data("no-such-replay-id-xyz")
        assert result is None

    async def test_replay_data_stored_with_prefix(self):
        """replay データが replay- プレフィックスで保存されること"""
        await save_replay_data("test-123", [{"event": "text"}])
        assert _build_memory_key("anonymous", "replay-test-123") in _memory_store
        doc = _memory_store[_build_memory_key("anonymous", "replay-test-123")]
        assert doc["type"] == "replay"
        assert doc["conversation_id"] == "test-123"

    async def test_get_replay_data_rejects_other_owner(self):
        """別 owner の replay は取得できない"""
        await save_replay_data("shared-replay", [{"event": "text"}], owner_id="user-a")

        result = await get_replay_data("shared-replay", owner_id="user-b")

        assert result is None


class TestCosmosDBPaths:
    """Cosmos DB パスのテスト（モック使用）"""

    async def test_get_conversation_cosmos_uses_background_thread(self, monkeypatch):
        """Cosmos DB 読み取りはイベントループを塞がないよう to_thread 経由で実行する"""
        mock_container = MagicMock()
        mock_container.read_item.return_value = {"id": "cosmos-get", "input": "test"}
        captured: dict[str, object] = {}

        async def fake_to_thread(func, *args, **kwargs):
            captured["func"] = func
            captured["args"] = args
            captured["kwargs"] = kwargs
            return func(*args, **kwargs)

        monkeypatch.setattr("src.conversations.asyncio.to_thread", fake_to_thread)

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_conversation("cosmos-get")

        assert result == {"id": "cosmos-get", "input": "test"}
        assert captured["func"] == mock_container.read_item
        assert captured["kwargs"] == {"item": "cosmos-get", "partition_key": "anonymous"}

    async def test_save_conversation_cosmos_upsert(self, monkeypatch):
        """Cosmos DB コンテナがある場合 upsert_item が呼ばれること"""
        mock_container = MagicMock()
        mock_container.upsert_item = MagicMock()

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-test-1",
                user_input="テスト",
                events=[],
            )
            mock_container.upsert_item.assert_called_once()

    async def test_save_conversation_cosmos_failure_falls_back(self, monkeypatch):
        """Cosmos DB upsert が失敗した場合インメモリにフォールバック"""
        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = OSError("Cosmos error")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-fallback",
                user_input="テスト",
                events=[],
            )
            assert _build_memory_key("anonymous", "cosmos-fallback") in _memory_store
            # OSError is transient → retried 4x (backoffs [0, 0.5, 1, 2])
            assert mock_container.upsert_item.call_count == 4

    async def test_save_conversation_cosmos_unexpected_error(self, monkeypatch):
        """Cosmos DB で予期しないエラーが発生した場合もフォールバック"""
        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-unexpected",
                user_input="テスト",
                events=[],
            )
            assert _build_memory_key("anonymous", "cosmos-unexpected") in _memory_store
            # RuntimeError is non-transient → no retry
            assert mock_container.upsert_item.call_count == 1

    async def test_save_conversation_cosmos_transient_then_succeeds(self, monkeypatch):
        """Cosmos DB upsert が transient (OSError) → 2 回目で成功 → in-memory に落ちない"""
        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = [OSError("transient"), None]

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-recover",
                user_input="テスト",
                events=[],
            )
            # 2nd attempt succeeded → no in-memory fallback
            assert _build_memory_key("anonymous", "cosmos-recover") not in _memory_store
            assert mock_container.upsert_item.call_count == 2

    async def test_save_conversation_cosmos_http_429_classified_transient(self, monkeypatch):
        """Cosmos HTTP 429 throttling は transient と分類されて retry される"""

        class FakeCosmosHttpResponseError(Exception):
            def __init__(self, status_code: int, message: str = ""):
                super().__init__(message)
                self.status_code = status_code

        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = FakeCosmosHttpResponseError(429, "Too many requests")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-429",
                user_input="テスト",
                events=[],
            )
            # 429 is transient → retried full 4x then in-memory fallback
            assert _build_memory_key("anonymous", "cosmos-429") in _memory_store
            assert mock_container.upsert_item.call_count == 4

    async def test_save_conversation_cosmos_http_403_classified_non_transient(self, monkeypatch):
        """Cosmos HTTP 403 (auth/permission) は非 transient → 1 回目で諦めて in-memory fallback"""

        class FakeCosmosHttpResponseError(Exception):
            def __init__(self, status_code: int, message: str = ""):
                super().__init__(message)
                self.status_code = status_code

        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = FakeCosmosHttpResponseError(403, "Forbidden")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-403",
                user_input="テスト",
                events=[],
            )
            assert _build_memory_key("anonymous", "cosmos-403") in _memory_store
            # 403 is non-transient → no retry
            assert mock_container.upsert_item.call_count == 1

    async def test_save_conversation_cosmos_service_request_error_classified_transient(self, monkeypatch):
        """azure-core ServiceRequestError (DNS / TCP failure) は transient と分類される"""

        class ServiceRequestError(Exception):
            pass

        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = ServiceRequestError("DNS resolution failed")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_conversation(
                conversation_id="cosmos-service-req",
                user_input="テスト",
                events=[],
            )
            # ServiceRequestError matched by type name → transient → retried 4x
            assert mock_container.upsert_item.call_count == 4
            assert _build_memory_key("anonymous", "cosmos-service-req") in _memory_store

    async def test_get_conversation_cosmos_success(self, monkeypatch):
        """Cosmos DB から会話を読み取れる場合"""
        mock_container = MagicMock()
        mock_container.read_item.return_value = {"id": "cosmos-get", "input": "test"}

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_conversation("cosmos-get")
            assert result is not None
            assert result["id"] == "cosmos-get"

    async def test_get_conversation_cosmos_not_found(self, monkeypatch):
        """Cosmos DB で見つからない場合は None"""
        mock_container = MagicMock()
        mock_container.read_item.side_effect = ValueError("Not found")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_conversation("cosmos-missing")
            assert result is None

    async def test_get_conversation_cosmos_unexpected_error(self, monkeypatch):
        """Cosmos DB で予期しないエラーでも None"""
        mock_container = MagicMock()
        mock_container.read_item.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_conversation("cosmos-error")
            assert result is None

    async def test_list_conversations_cosmos_success(self, monkeypatch):
        """Cosmos DB から会話一覧を取得できる場合"""
        mock_container = MagicMock()
        mock_container.query_items.return_value = iter(
            [
                {"id": "c1", "input": "q1"},
                {"id": "c2", "input": "q2"},
            ]
        )

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await list_conversations(limit=10)
            assert len(result) == 2

    async def test_list_conversations_cosmos_failure(self, monkeypatch):
        """Cosmos DB クエリ失敗時は空リスト"""
        mock_container = MagicMock()
        mock_container.query_items.side_effect = OSError("Query failed")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await list_conversations()
            assert result == []

    async def test_list_conversations_cosmos_unexpected_error(self, monkeypatch):
        """Cosmos DB で予期しないエラーも空リスト"""
        mock_container = MagicMock()
        mock_container.query_items.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await list_conversations()
            assert result == []

    async def test_save_replay_data_cosmos(self, monkeypatch):
        """Cosmos DB にリプレイデータを保存"""
        mock_container = MagicMock()
        mock_container.upsert_item = MagicMock()

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_replay_data("replay-cosmos", [{"event": "text"}])
            mock_container.upsert_item.assert_called_once()

    async def test_save_replay_data_cosmos_failure(self, monkeypatch):
        """Cosmos DB 保存失敗時はインメモリにフォールバック"""
        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = OSError("Save failed")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_replay_data("replay-fallback", [{"event": "text"}])
            assert _build_memory_key("anonymous", "replay-replay-fallback") in _memory_store

    async def test_get_replay_data_cosmos_success(self, monkeypatch):
        """Cosmos DB からリプレイデータを取得"""
        mock_container = MagicMock()
        mock_container.read_item.return_value = {"events": [{"event": "text", "data": {"content": "test"}}]}

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_replay_data("replay-cosmos-get")
            assert result is not None
            assert len(result) == 1

    async def test_get_replay_data_cosmos_not_found_falls_to_memory(self, monkeypatch):
        """Cosmos DB で見つからない場合メモリ → JSON にフォールバック"""
        mock_container = MagicMock()
        mock_container.read_item.side_effect = ValueError("Not found")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_replay_data("replay-not-in-cosmos")
            # メモリにもないので None or demo-replay.json
            assert result is None or isinstance(result, list)

    async def test_get_replay_data_cosmos_unexpected_error(self, monkeypatch):
        """Cosmos DB で予期しないエラーでもフォールバック"""
        mock_container = MagicMock()
        mock_container.read_item.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_container", return_value=mock_container):
            result = await get_replay_data("replay-error")
            assert result is None or isinstance(result, list)

    async def test_save_replay_data_cosmos_unexpected_error(self, monkeypatch):
        """Cosmos DB リプレイ保存で予期しないエラーでもフォールバック"""
        mock_container = MagicMock()
        mock_container.upsert_item.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_container", return_value=mock_container):
            await save_replay_data("replay-unexpected", [{"event": "text"}])
            assert _build_memory_key("anonymous", "replay-replay-unexpected") in _memory_store


class TestCosmosClientCreation:
    """Cosmos DB クライアント作成パスのテスト"""

    def test_cosmos_client_value_error(self, monkeypatch):
        """Cosmos DB 接続で ValueError が発生した場合"""
        monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://test.documents.azure.com:443/")

        # azure.cosmos.CosmosClient は関数内で import されるので
        # azure.cosmos モジュール自体をモックする
        import sys
        import types

        mock_cosmos_module = types.ModuleType("azure.cosmos")
        mock_cosmos_module.CosmosClient = MagicMock(side_effect=ValueError("Invalid URL"))

        with patch.dict(sys.modules, {"azure.cosmos": mock_cosmos_module}):
            result = _get_cosmos_client()
            assert result is None
            assert _conv_mod._cosmos_initialized is False
            assert _conv_mod._cosmos_retry_after_monotonic > 0.0

    def test_cosmos_client_retries_after_transient_failure(self, monkeypatch):
        """一時的な Cosmos 接続失敗後もクールダウン後に再試行できる"""
        monkeypatch.setenv("COSMOS_DB_ENDPOINT", "https://test.documents.azure.com:443/")

        import sys
        import types

        mock_client = MagicMock(name="cosmos-client")
        mock_cosmos_module = types.ModuleType("azure.cosmos")
        mock_cosmos_module.CosmosClient = MagicMock(side_effect=[RuntimeError("firewall"), mock_client])
        mock_identity_module = types.ModuleType("azure.identity")
        mock_identity_module.DefaultAzureCredential = MagicMock(return_value=MagicMock(name="credential"))

        with patch.dict(sys.modules, {"azure.cosmos": mock_cosmos_module, "azure.identity": mock_identity_module}):
            assert _get_cosmos_client() is None
            assert _conv_mod._cosmos_initialized is False

            _conv_mod._cosmos_retry_after_monotonic = 0.0
            assert _get_cosmos_client() is mock_client
            assert _conv_mod._cosmos_initialized is True

    def test_get_container_success(self, monkeypatch):
        """コンテナ正常取得"""
        mock_container = MagicMock()
        mock_db = MagicMock()
        mock_db.get_container_client.return_value = mock_container
        mock_client = MagicMock()
        mock_client.get_database_client.return_value = mock_db

        with patch("src.conversations._get_cosmos_client", return_value=mock_client):
            result = _get_container()
            assert result is mock_container

    def test_get_container_value_error(self, monkeypatch):
        """コンテナ取得で ValueError"""
        mock_client = MagicMock()
        mock_client.get_database_client.side_effect = ValueError("DB not found")

        with patch("src.conversations._get_cosmos_client", return_value=mock_client):
            result = _get_container()
            assert result is None

    def test_get_container_unexpected_error(self, monkeypatch):
        """コンテナ取得で予期しないエラー"""
        mock_client = MagicMock()
        mock_client.get_database_client.side_effect = RuntimeError("Unexpected")

        with patch("src.conversations._get_cosmos_client", return_value=mock_client):
            result = _get_container()
            assert result is None
