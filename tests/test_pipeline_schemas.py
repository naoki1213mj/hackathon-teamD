"""pipeline_schemas の正規化テスト。"""

from src.pipeline_schemas import (
    normalize_evidence_items,
    normalize_pipeline_metrics,
    normalize_source_ingestion_state,
    normalize_work_iq_source_metadata,
)
from src.tool_telemetry import build_tool_event_data
from src.work_iq_session import sanitize_work_iq_session_for_storage


def test_normalize_evidence_items_filters_unsafe_urls_and_metadata() -> None:
    """EvidenceItem は URL と metadata を安全な形へ正規化する。"""
    normalized = normalize_evidence_items(
        [
            {
                "id": "ev-1",
                "title": "需要データ",
                "source": "fabric",
                "url": "javascript:alert(1)",
                "quote": "Authorization: Bearer secret-token",
                "relevance": 0.9,
                "metadata": {"region": "okinawa", "token": "secret", "raw": {"nested": "ignored"}},
            },
            {"id": "ev-2", "source": "web", "url": "https://example.com/report?sig=secret"},
            {"title": "source missing"},
        ]
    )

    assert normalized == [
        {
            "id": "ev-1",
            "title": "需要データ",
            "source": "fabric",
            "quote": "[redacted]",
            "relevance": 0.9,
            "metadata": {"region": "okinawa"},
        },
        {"id": "ev-2", "title": "", "source": "web"},
    ]


def test_normalize_evidence_items_redacts_bare_token_and_auth_metadata() -> None:
    """EvidenceItem は裸の token 値と auth metadata key も漏らさない。"""
    normalized = normalize_evidence_items(
        [
            {
                "source": "web",
                "quote": "source returned token=xyz and should be redacted",
                "metadata": {"auth": "secret", "safe": "ok"},
            }
        ]
    )

    assert normalized == [
        {
            "id": "",
            "title": "",
            "source": "web",
            "quote": "source returned [redacted] and should be redacted",
            "metadata": {"safe": "ok"},
        }
    ]


def test_normalize_pipeline_metrics_accepts_legacy_and_extended_fields() -> None:
    """既存 metrics 互換を保ちつつ拡張 fields を保持する。"""
    normalized = normalize_pipeline_metrics(
        {
            "latency_seconds": 1.2,
            "tool_calls": 3,
            "total_tokens": 42,
            "prompt_tokens": 10,
            "completion_tokens": 32,
            "estimated_cost_usd": 0.004,
            "agent_latencies": {"data-search-agent": 0.7, "bad": -1},
            "agent_tokens": {"data-search-agent": 42, "bad": -1},
            "agent_prompt_tokens": {"data-search-agent": 10},
            "agent_completion_tokens": {"data-search-agent": 32},
            "agent_estimated_costs_usd": {"data-search-agent": 0.004},
            "evidence": [{"source": "fabric", "title": "売上履歴"}],
            "charts": [{"chart_type": "bar", "data": [{"month": "4月", "sales": 1000}]}],
            "trace_events": [{"name": "agent.run", "duration_ms": 120}],
            "debug_events": [{"level": "warning", "message": "fallback used"}],
            "source_ingestion": [{"source": "sharepoint", "status": "partial", "items_ingested": 8}],
        }
    )

    assert normalized is not None
    assert normalized["latency_seconds"] == 1.2
    assert normalized["tool_calls"] == 3
    assert normalized["total_tokens"] == 42
    assert normalized["prompt_tokens"] == 10
    assert normalized["agent_latencies"] == {"data-search-agent": 0.7}
    assert normalized["agent_tokens"] == {"data-search-agent": 42}
    assert normalized["agent_prompt_tokens"] == {"data-search-agent": 10}
    assert normalized["agent_completion_tokens"] == {"data-search-agent": 32}
    assert normalized["agent_estimated_costs_usd"] == {"data-search-agent": 0.004}
    assert normalized["evidence"][0]["source"] == "fabric"
    assert normalized["charts"][0]["chart_type"] == "bar"
    assert normalized["trace_events"][0]["name"] == "agent.run"
    assert normalized["debug_events"][0]["level"] == "warning"
    assert normalized["source_ingestion"][0]["status"] == "partial"


def test_build_tool_event_data_normalizes_optional_schema_fields() -> None:
    """tool_event は既存 fields に optional schema fields を追加できる。"""
    payload = build_tool_event_data(
        "web_search",
        "completed",
        agent_name="marketing-plan-agent",
        evidence=[{"source": "web", "url": "https://example.com/report", "relevance": 0.8}],
        charts=[{"chart_type": "line", "title": "需要推移"}],
        trace_events=[{"name": "search.call", "duration_ms": 20}],
        debug_events=[{"message": "cache hit", "level": "info"}],
        source_metadata=[{"source": "meeting_notes", "count": 2, "connector": "teams"}],
        source_ingestion=[{"source": "fabric", "status": "completed", "items_ingested": 10}],
    )

    assert payload["tool"] == "web_search"
    assert payload["provider"] == "foundry"
    assert payload["evidence"][0]["url"] == "https://example.com/report"
    assert payload["charts"][0]["chart_type"] == "line"
    assert payload["trace_events"][0]["name"] == "search.call"
    assert payload["debug_events"][0]["level"] == "info"
    assert payload["source_metadata"][0]["connector"] == "teams"
    assert payload["source_ingestion"][0]["items_ingested"] == 10


def test_work_iq_source_metadata_preserves_additive_fields() -> None:
    """Work IQ metadata は既存 source/label/count に加えて additive fields を保存する。"""
    normalized = normalize_work_iq_source_metadata(
        [
            {
                "source": "emails",
                "label": "メール",
                "count": 4,
                "status": "completed",
                "summary": "<b>メール要約</b>",
                "preview": "価格より体験価値を重視",
                "confidence": 0.75,
            }
        ]
    )
    assert normalized == [
        {
            "source": "emails",
            "label": "メール",
            "count": 4,
            "status": "completed",
            "summary": "メール要約",
            "preview": "価格より体験価値を重視",
            "confidence": 0.75,
        }
    ]

    session = sanitize_work_iq_session_for_storage(
        {
            "enabled": True,
            "source_scope": ["emails"],
            "auth_mode": "delegated",
            "brief_source_metadata": [
                {
                    "source": "emails",
                    "count": 4,
                    "connector": "outlook",
                    "summary": "<script>unsafe()</script>安全な要約",
                    "evidence_ids": ["ev-1"],
                }
            ],
        }
    )

    assert session is not None
    assert session["brief_source_metadata"] == [
        {
            "source": "emails",
            "count": 4,
            "connector": "outlook",
            "summary": "安全な要約",
            "evidence_ids": ["ev-1"],
        }
    ]


def test_source_ingestion_state_normalizes_unknown_status() -> None:
    """source ingestion state は未知 status を unknown に丸める。"""
    normalized = normalize_source_ingestion_state(
        [{"source": "sharepoint", "status": "queued", "items_discovered": 12, "items_failed": -1}]
    )

    assert normalized == [{"source": "sharepoint", "status": "unknown", "items_discovered": 12}]
