"""会話履歴の永続化。Cosmos DB またはインメモリ辞書にフォールバックする。"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# インメモリストア（Cosmos DB 未設定時のフォールバック）
_memory_store: dict[str, dict] = {}
_conversation_locks: dict[str, asyncio.Lock] = {}
_DEFAULT_OWNER_ID = "anonymous"
_REPLACE_METADATA_FLAG = "__replace_metadata__"

# Cosmos DB クライアントのシングルトン（接続プーリングを再利用するため）
_cosmos_client = None
_cosmos_initialized = False
_cosmos_retry_after_monotonic = 0.0
_COSMOS_CLIENT_RETRY_SECONDS = 60.0


def _normalize_owner_id(owner_id: str | None) -> str:
    """未指定 owner を安全な既定値へ正規化する。"""
    normalized = str(owner_id).strip() if owner_id is not None else ""
    return normalized or _DEFAULT_OWNER_ID


def _build_memory_key(owner_id: str, document_id: str) -> str:
    """インメモリ保存用の複合キーを返す。"""
    return f"{owner_id}:{document_id}"


def _event_identity(event: object) -> str:
    """イベント重複排除用の安定した identity を返す。"""
    try:
        return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(event)


def _merge_event_histories(existing_events: object, incoming_events: object) -> list[dict]:
    """stale full-save で既存イベントを失わないよう、順序保持でマージする。"""
    existing_list = existing_events if isinstance(existing_events, list) else []
    incoming_list = incoming_events if isinstance(incoming_events, list) else []

    if not existing_list:
        return list(incoming_list)
    if not incoming_list:
        return list(existing_list)

    merged = list(existing_list)
    seen = {_event_identity(event) for event in merged}
    for event in incoming_list:
        key = _event_identity(event)
        if key in seen:
            continue
        merged.append(event)
        seen.add(key)
    return merged


def _get_owner_id_from_document(doc: dict | None) -> str:
    """保存済み会話ドキュメントから owner_id を取得する。"""
    if not isinstance(doc, dict):
        return _DEFAULT_OWNER_ID
    return _normalize_owner_id(str(doc.get("user_id", "")))


def replace_conversation_metadata(metadata: dict | None) -> dict | None:
    """既存 metadata を置換する保存指示付き payload を返す。"""
    if metadata is None:
        return None
    return {_REPLACE_METADATA_FLAG: True, **metadata}


def _get_conversation_lock(conversation_id: str, owner_id: str) -> asyncio.Lock:
    """会話ごとの保存処理を直列化するロックを返す。"""
    lock_key = _build_memory_key(owner_id, conversation_id)
    lock = _conversation_locks.get(lock_key)
    if lock is None:
        lock = asyncio.Lock()
        _conversation_locks[lock_key] = lock
    return lock


def _is_demo_replay_request(conversation_id: str) -> bool:
    """デモ用 replay のみ JSON フォールバックを許可する。"""
    return conversation_id.startswith("demo-")


def _get_cosmos_client():
    """Cosmos DB クライアントを取得する。未設定時は None を返す。

    CosmosClient は接続プーリングを内蔵しているため、モジュールレベルで
    シングルトンとして保持し、呼び出しごとの再生成を避ける。
    """
    global _cosmos_client, _cosmos_initialized, _cosmos_retry_after_monotonic
    if _cosmos_initialized:
        return _cosmos_client

    endpoint = os.environ.get("COSMOS_DB_ENDPOINT", "")
    if not endpoint:
        _cosmos_initialized = True
        return None
    now = time.monotonic()
    if _cosmos_retry_after_monotonic > now:
        return None
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        _cosmos_client = CosmosClient(url=endpoint, credential=DefaultAzureCredential())
        _cosmos_initialized = True
        _cosmos_retry_after_monotonic = 0.0
        return _cosmos_client
    except ImportError:
        _cosmos_initialized = True
        logger.warning("azure-cosmos がインストールされていません")
        return None
    except (ValueError, OSError) as exc:
        logger.warning("Cosmos DB クライアントの作成に失敗: %s", exc)
        _cosmos_client = None
        _cosmos_initialized = False
        _cosmos_retry_after_monotonic = time.monotonic() + _COSMOS_CLIENT_RETRY_SECONDS
        return None
    except Exception as exc:
        logger.exception("Cosmos DB クライアントの作成で予期しないエラー: %s", exc)
        _cosmos_client = None
        _cosmos_initialized = False
        _cosmos_retry_after_monotonic = time.monotonic() + _COSMOS_CLIENT_RETRY_SECONDS
        return None


def _get_container():
    """conversations コンテナを取得する。"""
    client = _get_cosmos_client()
    if not client:
        return None
    try:
        database = client.get_database_client("travel-marketing")
        return database.get_container_client("conversations")
    except (ValueError, OSError) as exc:
        logger.warning("Cosmos DB コンテナの取得に失敗: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Cosmos DB コンテナの取得で予期しないエラー: %s", exc)
        return None


async def save_conversation(
    conversation_id: str,
    user_input: str,
    events: list[dict],
    artifacts: dict | None = None,
    metrics: dict | None = None,
    status: str = "completed",
    owner_id: str | None = None,
) -> None:
    """会話をストアに保存する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    async with _get_conversation_lock(conversation_id, resolved_owner_id):
        existing = await get_conversation(conversation_id, owner_id=resolved_owner_id, allow_cross_owner=owner_id is None)
        document_owner_id = _get_owner_id_from_document(existing) if existing else resolved_owner_id
        doc = _build_conversation_doc(
            conversation_id=conversation_id,
            existing=existing,
            user_input=user_input,
            events=events,
            artifacts=artifacts,
            metrics=metrics,
            status=status,
            owner_id=document_owner_id,
        )
        await _persist_conversation_doc(doc)


async def append_conversation_events(
    conversation_id: str,
    user_input: str | None,
    new_events: list[dict],
    artifacts: dict | None = None,
    metrics: dict | None = None,
    status: str | None = None,
    owner_id: str | None = None,
) -> dict | None:
    """既存会話へイベントを追記しつつ保存する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    async with _get_conversation_lock(conversation_id, resolved_owner_id):
        existing = await get_conversation(conversation_id, owner_id=resolved_owner_id, allow_cross_owner=owner_id is None)
        existing_messages = existing.get("messages", []) if existing else []
        if not isinstance(existing_messages, list):
            existing_messages = []

        resolved_user_input = user_input
        if resolved_user_input is None:
            resolved_user_input = str(existing.get("input", "")) if existing else ""

        resolved_status = status or str(existing.get("status", "completed")) if existing else "completed"
        doc = _build_conversation_doc(
            conversation_id=conversation_id,
            existing=existing,
            user_input=resolved_user_input,
            events=[*existing_messages, *new_events],
            artifacts=artifacts,
            metrics=metrics,
            status=resolved_status,
            owner_id=_get_owner_id_from_document(existing) if existing else resolved_owner_id,
        )
        await _persist_conversation_doc(doc)
        return doc


# Cosmos doc 2MB hard limit 対策。GPT-Image-2 / MAI-Image-2 は base64 PNG
# (data:image/png;base64,...) を返し 1 枚 ~500KB-1.5MB ある。brochure-gen で
# hero+banner=2 枚以上保存すると merged_messages が 2MB を超えて Cosmos が
# `RequestEntityTooLarge` (413) を返し、_persist_conversation_doc は
# in-memory にフォールバック → Cosmos には古い `awaiting_approval` が
# 残り、polling restoreConversation や page reload で UI が承認画面に
# 戻るバグが再現する (Bug 4 root cause、App Insights traces 2026-05-02
# 10:35:00 / 10:35:45 で confirmed)。
#
# SSE ストリームと in-memory state は full image を保持し、Cosmos に
# 書く瞬間だけ data URL を小さな SVG プレースホルダで置換する。
# `data:image/svg+xml;...` は数百バイトに収まり、frontend は同じ
# `<img src={url}>` で何も変えずにレンダリングできる。
#
# 注: brochure HTML は `text` event に `content_type=html` で書かれ、
# その中に `<img src="data:image/png;base64,...">` が inline で含まれる
# ため、`image` event だけでなく HTML inline data URL も同じ閾値で
# 置換する必要がある (rubber-duck `pr1-impl-critique` blocking #1)。
_MAX_PERSISTED_IMAGE_DATA_URL_BYTES = 64 * 1024  # 64KB
_TRUNCATED_IMAGE_PLACEHOLDER_TEMPLATE = (
    "data:image/svg+xml;charset=utf-8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='400'%3E"
    "%3Crect width='800' height='400' fill='%23e2e8f0'/%3E"
    "%3Ctext x='400' y='180' text-anchor='middle' font-size='18' "
    "font-family='sans-serif' fill='%23475569'%3E"
    "%E5%AE%B9%E9%87%8F%E5%88%B6%E9%99%90%E3%81%AB%E3%82%88%E3%82%8A%E7%94%BB%E5%83%8F%E3%82%92%E7%9C%81%E7%95%A5"
    "%3C/text%3E"
    "%3Ctext x='400' y='220' text-anchor='middle' font-size='14' "
    "font-family='sans-serif' fill='%2364748b'%3E"
    "original_size={size}B"
    "%3C/text%3E"
    "%3C/svg%3E"
)


# `<img src="data:image/...;base64,...">` 形式の inline 画像を検出する。
# 以下を全て許容:
#   - ダブルクォート src="data:..." / シングルクォート src='data:...'
#   - 等号前後の whitespace: src = "data:..."
#   - クォートなし src=data:image/png;base64,xxx
# `<img\b` を要求して img タグ起点に限定する (CSS background-image や
# template literal の data: URL を誤って書き換えない)。
# 注意: 完璧な HTML パーサではないが、brochure-gen が出力する典型的な
# img 形態は全てカバーする。malformed HTML / `srcset` は今回対象外
# (rubber-duck pr1-final-review #1)。
_HTML_INLINE_IMG_DATA_URL_QUOTED_RE = re.compile(
    r"""(<img\b[^>]*?\bsrc\s*=\s*)(["'])(data:[^"']+)(\2)""",
    re.IGNORECASE,
)

# クォートなし src=data:... 形式. 属性値は whitespace / `>` で終端。
# data: URL 内に whitespace は含まれない (base64 / URL-encode 済み) ので
# `[^\s>]+` で安全に切れる。
_HTML_INLINE_IMG_DATA_URL_UNQUOTED_RE = re.compile(
    r"""(<img\b[^>]*?\bsrc\s*=\s*)(data:[^\s>"']+)""",
    re.IGNORECASE,
)


def _truncate_inline_data_urls_in_html(html: str) -> tuple[str, int]:
    """HTML の `<img src="data:...">` 形式の大きな inline 画像を
    プレースホルダ URL で置換する。

    Returns (truncated_html, replaced_count)。`_MAX_PERSISTED_IMAGE_DATA_URL_BYTES`
    を超える data URL のみ置換し、小さい SVG / fallback 画像はそのまま保持する。

    クォート付き / なし、等号前後の whitespace 全形式に対応する。
    (rubber-duck pr1-final-review blocking #1)
    """
    if not isinstance(html, str) or "data:" not in html:
        return html, 0

    replaced = 0

    def _sub_quoted(match: re.Match[str]) -> str:
        nonlocal replaced
        prefix, quote, url, _close_quote = match.group(1), match.group(2), match.group(3), match.group(4)
        url_bytes = len(url.encode("utf-8"))
        if url_bytes <= _MAX_PERSISTED_IMAGE_DATA_URL_BYTES:
            return match.group(0)
        replaced += 1
        placeholder = _TRUNCATED_IMAGE_PLACEHOLDER_TEMPLATE.replace("{size}", str(url_bytes))
        return f"{prefix}{quote}{placeholder}{quote}"

    def _sub_unquoted(match: re.Match[str]) -> str:
        nonlocal replaced
        prefix, url = match.group(1), match.group(2)
        url_bytes = len(url.encode("utf-8"))
        if url_bytes <= _MAX_PERSISTED_IMAGE_DATA_URL_BYTES:
            return match.group(0)
        replaced += 1
        placeholder = _TRUNCATED_IMAGE_PLACEHOLDER_TEMPLATE.replace("{size}", str(url_bytes))
        # 戻すときは安全のためクォートで囲む (元が unquoted でも valid HTML)
        return f'{prefix}"{placeholder}"'

    # quoted を先に処理 (unquoted regex がクォート部分にも match しないよう
    # quoted のあとは data: URL がプレースホルダ化されているので unquoted
    # regex は何もしない、という順序で安全)
    truncated = _HTML_INLINE_IMG_DATA_URL_QUOTED_RE.sub(_sub_quoted, html)
    truncated = _HTML_INLINE_IMG_DATA_URL_UNQUOTED_RE.sub(_sub_unquoted, truncated)
    return truncated, replaced


def _truncate_large_images_for_persistence(events: object) -> list[dict]:
    """Cosmos 2MB 制限を超えないよう、image / brochure HTML 内の大きな
    data URL を小さな SVG プレースホルダで置換する。

    対象:
      - `event == 'image'` で `data.url` が `data:` 始まり閾値超え
      - `event == 'text'` で `data.content_type == 'html'` (brochure-gen) かつ
        HTML 内 `<img src="data:...">` が閾値超え

    SVG / 小さいプレースホルダ / http(s) URL はそのまま保持する。元 event dict は
    破壊せず、置換時のみ shallow-copy で新しい dict を返す。

    Note: `_merge_event_histories` の dedupe より **先** に呼び出すこと
    (rubber-duck `pr1-impl-critique` blocking #2)。プレースホルダは
    deterministic (timestamp なし) なので、既保存の truncated event と
    今回 incoming の full-image event が "同じ画像" であれば、両方を
    truncate した後に JSON-identity で dedupe される。
    """
    if not isinstance(events, list):
        return []
    sanitized: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            sanitized.append(event)
            continue
        event_type = event.get("event")
        data = event.get("data")
        if not isinstance(data, dict):
            sanitized.append(event)
            continue

        if event_type == "image":
            url = data.get("url")
            if not isinstance(url, str) or not url.startswith("data:"):
                sanitized.append(event)
                continue
            url_bytes = len(url.encode("utf-8"))
            if url_bytes <= _MAX_PERSISTED_IMAGE_DATA_URL_BYTES:
                sanitized.append(event)
                continue
            placeholder = _TRUNCATED_IMAGE_PLACEHOLDER_TEMPLATE.replace("{size}", str(url_bytes))
            new_data = {
                **data,
                "url": placeholder,
                "truncated": True,
                "original_size_bytes": url_bytes,
            }
            sanitized.append({**event, "data": new_data})
            continue

        if event_type == "text" and data.get("content_type") == "html":
            html = data.get("content")
            if not isinstance(html, str):
                sanitized.append(event)
                continue
            truncated_html, replaced = _truncate_inline_data_urls_in_html(html)
            if replaced == 0:
                sanitized.append(event)
                continue
            new_data = {
                **data,
                "content": truncated_html,
                "truncated_inline_images": replaced,
            }
            sanitized.append({**event, "data": new_data})
            continue

        sanitized.append(event)
    return sanitized


def _build_conversation_doc(
    conversation_id: str,
    existing: dict | None,
    user_input: str,
    events: list[dict],
    artifacts: dict | None,
    metrics: dict | None,
    status: str,
    owner_id: str,
) -> dict:
    """保存用の会話ドキュメントを構築する。"""
    now = datetime.now(timezone.utc).isoformat()

    existing_artifacts = existing.get("artifacts", []) if existing else []
    if not isinstance(existing_artifacts, list):
        existing_artifacts = [existing_artifacts] if existing_artifacts else []

    new_artifact = dict(artifacts) if artifacts else {}
    if new_artifact:
        new_artifact["version"] = len(existing_artifacts) + 1
        new_artifact["created_at"] = now
        artifact_versions = [*existing_artifacts, new_artifact]
    else:
        artifact_versions = existing_artifacts

    existing_metadata = existing.get("metadata", {}) if existing else {}
    if not isinstance(existing_metadata, dict):
        existing_metadata = {}
    if isinstance(metrics, dict) and metrics.get(_REPLACE_METADATA_FLAG) is True:
        merged_metadata = {
            key: value for key, value in metrics.items() if key != _REPLACE_METADATA_FLAG
        }
    else:
        merged_metadata = {**existing_metadata, **(metrics or {})}

    return {
        "id": conversation_id,
        "user_id": _normalize_owner_id(owner_id),
        "created_at": existing.get("created_at", now) if existing else now,
        "updated_at": now,
        "status": status,
        "input": user_input,
        # Truncate inline data: URLs in BOTH existing-doc messages (already
        # persisted, possibly already truncated) and incoming events BEFORE
        # `_merge_event_histories` dedupe. Placeholder URL is deterministic
        # so two identity-different copies of the "same image" collapse to
        # one entry after JSON-identity dedup (rubber-duck blocking #2).
        "messages": _merge_event_histories(
            _truncate_large_images_for_persistence(existing.get("messages", []) if existing else []),
            _truncate_large_images_for_persistence(events),
        ),
        "artifacts": artifact_versions,
        "metadata": merged_metadata,
    }


async def _persist_conversation_doc(doc: dict) -> None:
    """会話ドキュメントを実ストアへ保存する。

    Cosmos が configured のとき、transient な write 失敗 (5xx, network) は
    短い backoff で 3 回リトライしてから in-memory にフォールバックする
    (rubber-duck 監査 2026-05-02: bug「post-approval events が in-memory
    fallback で Cosmos から失われ background_update が stale ベースで
    append し regulation/brochure events が失われる」根本対応)。

    リトライしても失敗した場合のみ in-memory に保存し、severity を
    `_emit_cosmos_fallback_signal` で通知する。

    リトライ対象は ValueError / OSError に加え、Cosmos / Azure SDK の
    transient 例外 (azure-core ServiceRequest/ServiceResponse/HttpResponseError
    の 408/429/5xx) も含める。これらは SDK 内部から AzureError として送出される
    ため、SDK 直接 import を避けつつ exception name + status_code を判定する。
    """
    conversation_id = str(doc.get("id", ""))
    owner_id = _get_owner_id_from_document(doc)
    container = _get_container()
    if container:
        # Backoff 0.5s, 1.0s, 2.0s — 合計 3.5s 以内。承認 SSE finally に組み込む
        # 用途のため deadline を意識した短い retry を選択する。
        backoffs = [0.0, 0.5, 1.0, 2.0]
        last_exc: Exception | None = None
        for attempt, wait in enumerate(backoffs):
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                await asyncio.to_thread(container.upsert_item, doc)
                if attempt > 0:
                    logger.info(
                        "会話 %s を Cosmos DB に保存 (attempt=%d/%d)",
                        conversation_id, attempt + 1, len(backoffs),
                    )
                else:
                    logger.info("会話 %s を Cosmos DB に保存", conversation_id)
                return
            except Exception as exc:  # noqa: BLE001 — classify below
                last_exc = exc
                if not _is_transient_cosmos_exception(exc):
                    logger.exception(
                        "Cosmos DB 保存で非一時的な例外 (attempt=%d/%d): %s",
                        attempt + 1, len(backoffs), exc,
                    )
                    break
                if attempt < len(backoffs) - 1:
                    logger.info(
                        "Cosmos DB 保存 transient 失敗 (attempt=%d/%d): %s",
                        attempt + 1, len(backoffs), exc,
                    )
                continue
        # All attempts exhausted
        if last_exc is not None:
            logger.warning(
                "Cosmos DB への保存に %d 回失敗、インメモリにフォールバック: %s",
                len(backoffs), last_exc,
            )
            _emit_cosmos_fallback_signal(doc, reason=f"{type(last_exc).__name__}: {last_exc}")

    _memory_store[_build_memory_key(owner_id, conversation_id)] = doc
    logger.info("会話 %s をインメモリに保存", conversation_id)


# Status codes that the Cosmos / Azure SDK marks as retriable transient writes:
# 408 Request Timeout, 429 Too Many Requests, 449 Retry With,
# 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable,
# 504 Gateway Timeout. We accept either an HTTP-style status_code attribute
# (Azure azure-core HttpResponseError / Cosmos CosmosHttpResponseError) or
# the well-known transient exception class names from azure-core.
_TRANSIENT_COSMOS_STATUS_CODES = frozenset({408, 429, 449, 500, 502, 503, 504})
_TRANSIENT_COSMOS_EXCEPTION_NAMES = frozenset({
    "ServiceRequestError",
    "ServiceResponseError",
    "ServiceRequestTimeoutError",
    "ServiceResponseTimeoutError",
    "AzureError",
})


def _is_transient_cosmos_exception(exc: Exception) -> bool:
    """Cosmos / azure-core SDK の transient (再試行で回復し得る) 例外かを判定する。

    `ValueError` / `OSError` は network/parsing の一時障害で従来から retry 対象。
    azure-core の `ServiceRequestError` / `ServiceResponseError` (DNS 解決失敗、
    TCP reset、TLS handshake エラー、socket timeout 等) と、
    `CosmosHttpResponseError` / `HttpResponseError` のうち status_code が
    408/429/449/5xx のものは Cosmos 仕様上 retry 推奨。
    """
    if isinstance(exc, (ValueError, OSError)):
        return True
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code in _TRANSIENT_COSMOS_STATUS_CODES:
        return True
    name = type(exc).__name__
    if name in _TRANSIENT_COSMOS_EXCEPTION_NAMES:
        return True
    return False


def _emit_cosmos_fallback_signal(doc: dict, *, reason: str) -> None:
    """Cosmos が configured かつ失敗したケースを構造化テレメトリで通知する。

    特に承認待ち (`awaiting_approval` / `awaiting_manager_approval`) や、
    post-approval の `completed` 保存が in-memory に落ちると、replica 再起動で
    成果物 (regulation/brochure/video text) が消失する致命的状態になる。
    rubber-duck 監査 2026-05-02 で実例を catch (conv 84d2a335-..., 03:57:43 in-memory
    fallback → background_update が stale Cosmos doc を base に上書きして
    regulation/brochure events 喪失) したため、completed も critical 扱いに格上げした。
    """
    status = str(doc.get("status", "")).strip()
    msg_count = len(doc.get("messages") or [])
    # `completed` でも post-approval events (msg_count >= ~13) を含む場合は critical
    is_post_approval_completed = status == "completed" and msg_count >= 13
    severity = (
        "critical"
        if status in {"awaiting_approval", "awaiting_manager_approval"} or is_post_approval_completed
        else "warning"
    )
    payload = {
        "conversation_id": str(doc.get("id", "")),
        "status": status,
        "severity": severity,
        "reason": reason,
        "msg_count": msg_count,
    }
    if severity == "critical":
        logger.error(
            "Cosmos 永続化失敗 (critical, status=%s msg_count=%d): conversation=%s reason=%s — replica 再起動で承認/成果物が消失する可能性",
            status,
            msg_count,
            payload["conversation_id"],
            reason,
        )
    try:  # pragma: no cover - App Insights が設定されている場合のみ機能
        from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: F401
        from opentelemetry import trace

        tracer = trace.get_tracer("travel.cosmos_fallback")
        with tracer.start_as_current_span("cosmos_fallback") as span:
            for key, value in payload.items():
                span.set_attribute(key, value)
    except Exception:  # noqa: BLE001
        return


async def get_conversation(
    conversation_id: str,
    owner_id: str | None = None,
    *,
    allow_cross_owner: bool = False,
) -> dict | None:
    """会話を取得する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    container = _get_container()
    if container:
        try:
            if allow_cross_owner and owner_id is None:
                items = await asyncio.to_thread(
                    list,
                    container.query_items(
                        query="SELECT * FROM c WHERE c.id = @id",
                        parameters=[{"name": "@id", "value": conversation_id}],
                        enable_cross_partition_query=True,
                    ),
                )
                for item in items:
                    if isinstance(item, dict):
                        return item
                return None

            result = await asyncio.to_thread(
                container.read_item,
                item=conversation_id,
                partition_key=resolved_owner_id,
            )
            return result if isinstance(result, dict) else None
        except (ValueError, OSError) as exc:
            logger.debug("Cosmos DB から会話 %s が見つからない: %s", conversation_id, exc)
            return None
        except Exception as exc:
            logger.debug("Cosmos DB から会話 %s の取得で予期しないエラー: %s", conversation_id, exc)
            return None

    if allow_cross_owner and owner_id is None:
        for doc in _memory_store.values():
            if isinstance(doc, dict) and str(doc.get("id", "")) == conversation_id and doc.get("type") != "replay":
                return doc
        return None

    doc = _memory_store.get(_build_memory_key(resolved_owner_id, conversation_id))
    if isinstance(doc, dict) and doc.get("type") != "replay":
        return doc
    return None


async def list_conversations(owner_id: str | None = None, limit: int = 20) -> list[dict]:
    """会話一覧を取得する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    container = _get_container()
    if container:
        try:
            query = (
                "SELECT c.id, c.input, c.status, c.created_at FROM c ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
            )
            items = await asyncio.to_thread(
                list,
                container.query_items(
                    query=query,
                    parameters=[{"name": "@limit", "value": limit}],
                    partition_key=resolved_owner_id,
                ),
            )
            return items
        except (ValueError, OSError) as exc:
            logger.warning("Cosmos DB からの一覧取得に失敗: %s", exc)
            return []
        except Exception as exc:
            logger.exception("Cosmos DB からの一覧取得で予期しないエラー: %s", exc)
            return []

    filtered_items = [
        doc
        for doc in _memory_store.values()
        if isinstance(doc, dict) and doc.get("type") != "replay" and _get_owner_id_from_document(doc) == resolved_owner_id
    ]
    return sorted(filtered_items, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]


async def save_replay_data(
    conversation_id: str,
    events_with_timing: list[dict],
    owner_id: str | None = None,
) -> None:
    """リプレイ用の SSE イベントデータをタイムスタンプ付きで保存する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    container = _get_container()
    replay_doc = {
        "id": f"replay-{conversation_id}",
        "user_id": resolved_owner_id,
        "type": "replay",
        "conversation_id": conversation_id,
        "events": events_with_timing,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if container:
        try:
            await asyncio.to_thread(container.upsert_item, replay_doc)
            return
        except (ValueError, OSError) as exc:
            logger.warning("Cosmos DB へのリプレイデータ保存に失敗: %s", exc)
        except Exception as exc:
            logger.exception("Cosmos DB へのリプレイデータ保存で予期しないエラー: %s", exc)

    _memory_store[_build_memory_key(resolved_owner_id, f"replay-{conversation_id}")] = replay_doc


async def get_replay_data(
    conversation_id: str,
    owner_id: str | None = None,
    *,
    allow_cross_owner: bool = False,
) -> list[dict] | None:
    """リプレイ用の SSE イベントデータを取得する。"""
    resolved_owner_id = _normalize_owner_id(owner_id)
    container = _get_container()
    if container:
        try:
            if allow_cross_owner and owner_id is None:
                items = await asyncio.to_thread(
                    list,
                    container.query_items(
                        query="SELECT * FROM c WHERE c.id = @id",
                        parameters=[{"name": "@id", "value": f"replay-{conversation_id}"}],
                        enable_cross_partition_query=True,
                    ),
                )
                doc = next((item for item in items if isinstance(item, dict)), None)
            else:
                doc = await asyncio.to_thread(
                    container.read_item,
                    item=f"replay-{conversation_id}",
                    partition_key=resolved_owner_id,
                )
            if isinstance(doc, dict):
                return doc.get("events", [])
            return None
        except (ValueError, OSError) as exc:
            logger.debug("Cosmos DB からリプレイデータ取得失敗: %s", exc)
        except Exception as exc:
            logger.debug("Cosmos DB からリプレイデータ取得で予期しないエラー: %s", exc)

    if allow_cross_owner and owner_id is None:
        doc = next(
            (
                value
                for value in _memory_store.values()
                if isinstance(value, dict) and str(value.get("id", "")) == f"replay-{conversation_id}"
            ),
            None,
        )
    else:
        doc = _memory_store.get(_build_memory_key(resolved_owner_id, f"replay-{conversation_id}"))
    if doc:
        return doc.get("events", [])

    # JSON ファイルからのフォールバックはデモ replay のみ許可
    if not _is_demo_replay_request(conversation_id):
        return None

    import json
    from pathlib import Path

    replay_file = Path(__file__).resolve().parent.parent / "data" / "demo-replay.json"
    if replay_file.exists():
        try:
            with open(replay_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("events", [])
        except (ValueError, OSError) as exc:
            logger.warning("リプレイ JSON の読み込みに失敗: %s", exc)
        except Exception as exc:
            logger.exception("リプレイ JSON の読み込みで予期しないエラー: %s", exc)

    return None
