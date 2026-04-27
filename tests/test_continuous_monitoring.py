"""継続監視サービスの privacy-safe 動作テスト。"""

import pytest

from src.config import AppSettings
from src.continuous_monitoring import (
    build_evaluation_monitoring_record,
    build_pipeline_monitoring_record,
    deterministic_sample,
    run_continuous_monitoring_safe,
    run_pipeline_evaluation_monitoring_safe,
    schedule_continuous_monitoring,
)


class FakeBackgroundTasks:
    """BackgroundTasks 互換の最小 fake。"""

    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def add_task(self, func: object, *args: object, **kwargs: object) -> None:
        self.calls.append((func, args, kwargs))


def _settings(**overrides: str) -> AppSettings:
    """必要な AppSettings をテスト用に組み立てる。"""
    values = {key: "" for key in AppSettings.__annotations__}
    values.update(
        {
            "project_endpoint": "",
            "model_name": "gpt-5-4-mini",
            "work_iq_timeout_seconds": "120",
            "improvement_mcp_api_key_header": "Ocp-Apim-Subscription-Key",
            "environment": "development",
            "allowed_origins": "http://localhost:5173",
            "enable_foundry_tracing": "false",
            "enable_continuous_monitoring": "false",
            "continuous_monitoring_sample_rate": "0.1",
            "enable_evaluation_logging": "false",
            "evaluation_log_retention_days": "30",
        }
    )
    values.update(overrides)
    return AppSettings(**values)  # type: ignore[typeddict-item]


def _enabled_settings(**overrides: str) -> AppSettings:
    values = {
        "project_endpoint": "https://example.services.ai.azure.com/api/projects/demo",
        "enable_continuous_monitoring": "true",
        "continuous_monitoring_sample_rate": "1",
        "enable_evaluation_logging": "true",
    }
    values.update(overrides)
    return _settings(**values)


def test_schedule_continuous_monitoring_disabled_by_default() -> None:
    """既定では監視ジョブを登録しない。"""
    tasks = FakeBackgroundTasks()
    record = build_pipeline_monitoring_record(
        conversation_id="conv-secret",
        events=[],
        status="completed",
        settings=_settings(),
    )

    scheduled = schedule_continuous_monitoring(
        tasks,
        record=record,
        sample_key="pipeline:conv-secret",
        settings=_settings(),
    )

    assert scheduled is False
    assert tasks.calls == []


def test_schedule_continuous_monitoring_sampling_off() -> None:
    """サンプル率 0 なら opt-in 済みでも登録しない。"""
    tasks = FakeBackgroundTasks()
    settings = _enabled_settings(continuous_monitoring_sample_rate="0")
    record = build_pipeline_monitoring_record(
        conversation_id="conv-secret",
        events=[],
        status="completed",
        settings=settings,
    )

    scheduled = schedule_continuous_monitoring(
        tasks,
        record=record,
        sample_key="pipeline:conv-secret",
        settings=settings,
    )

    assert scheduled is False
    assert tasks.calls == []


def test_schedule_continuous_monitoring_opt_in_registers_sanitized_job() -> None:
    """opt-in と sampling 通過時だけ sanitized payload をバックグラウンド登録する。"""
    tasks = FakeBackgroundTasks()
    settings = _enabled_settings()
    events = [
        {
            "event": "text",
            "data": {
                "content": "<html><body>Authorization: Bearer raw-token</body></html>",
                "content_type": "html",
            },
        },
        {
            "event": "done",
            "data": {"metrics": {"latency_seconds": 1.2, "tool_calls": 3, "total_tokens": 100}},
        },
    ]
    record = build_pipeline_monitoring_record(
        conversation_id="conv-secret",
        events=events,
        status="completed",
        settings=settings,
    )

    scheduled = schedule_continuous_monitoring(
        tasks,
        record=record,
        sample_key="pipeline:conv-secret",
        settings=settings,
    )

    assert scheduled is True
    assert len(tasks.calls) == 1
    assert record["redaction"]["brochure_html_logged"] is False
    assert "raw-token" not in str(record)
    assert record["content_shape"]["html_chars"] > 0
    assert record["sampling"]["sample_rate"] == 1.0


def test_evaluation_monitoring_record_never_contains_raw_content() -> None:
    """評価監視 payload は raw prompt / transcript / HTML を含まない。"""
    raw_query = "Work IQ meeting note Authorization: Bearer raw-secret"
    raw_response = "# 企画書\ntranscript: raw customer call"
    raw_html = "<html><body data-token='secret'>予約はこちら</body></html>"
    record = build_evaluation_monitoring_record(
        conversation_id="conv-secret",
        artifact_version=2,
        query=raw_query,
        response=raw_response,
        html=raw_html,
        results={
            "plan_quality": {"overall": 4.0},
            "asset_quality": {"overall": 3.5},
            "evidence_quality": {"overall": 3.0},
            "legacy_overall": 3.75,
            "findings": [{"status": "warn", "evidence_ids": ["ev-1"]}],
        },
        settings=_enabled_settings(),
    )

    serialized = str(record)
    assert raw_query not in serialized
    assert raw_response not in serialized
    assert raw_html not in serialized
    assert "raw-secret" not in serialized
    assert "raw customer call" not in serialized
    assert record["content_shape"] == {
        "query_chars": len(raw_query),
        "response_chars": len(raw_response),
        "html_chars": len(raw_html),
    }
    assert record["metrics"]["plan_overall"] == 4.0
    assert record["finding_status_counts"] == {"warn": 1}


@pytest.mark.asyncio
async def test_run_continuous_monitoring_safe_swallows_failures() -> None:
    """送信失敗は SSE/API 応答へ波及しない。"""
    settings = _enabled_settings()
    record = build_pipeline_monitoring_record(
        conversation_id="conv-secret",
        events=[{"event": "done", "data": {"metrics": {"latency_seconds": 1}}}],
        status="completed",
        settings=settings,
    )

    async def failing_foundry_logger(_record: dict[str, object]) -> str | None:
        raise RuntimeError("boom")

    def noop_metric_emitter(_record: dict[str, object], _settings: AppSettings | None) -> None:
        return None

    await run_continuous_monitoring_safe(
        record,
        foundry_logger=failing_foundry_logger,
        metric_emitter=noop_metric_emitter,
        settings=settings,
    )


@pytest.mark.asyncio
async def test_pipeline_evaluation_monitoring_adds_scores_without_raw_content() -> None:
    """pipeline 完了後評価は raw content を送信 payload に残さない。"""
    settings = _enabled_settings()
    calls: list[dict[str, object]] = []
    record = build_pipeline_monitoring_record(
        conversation_id="conv-secret",
        events=[{"event": "done", "data": {"metrics": {"latency_seconds": 1}}}],
        status="completed",
        settings=settings,
    )
    raw_plan = """
    # 春の沖縄プラン
    キャッチコピー: 家族で海を楽しむ旅
    ターゲット: ファミリー
    プラン概要: 2泊3日で観光と休息を両立
    KPI: 予約数 200 件
    価格帯: 98,000円（税込）
    取消料と旅行条件を明記
    """
    raw_html = "<html><body data-token='secret'>予約はこちら 98,000円（税込） 登録番号 安心サポート</body></html>"

    async def capture_foundry_logger(sent_record: dict[str, object]) -> str | None:
        calls.append(sent_record.copy())
        return "ok"

    def noop_metric_emitter(_record: dict[str, object], _settings: AppSettings | None) -> None:
        return None

    await run_pipeline_evaluation_monitoring_safe(
        record,
        plan_markdown=raw_plan,
        brochure_html=raw_html,
        foundry_logger=capture_foundry_logger,
        metric_emitter=noop_metric_emitter,
        settings=settings,
    )

    assert len(calls) == 1
    sent = calls[0]
    assert sent["plan_overall"] >= 0
    assert sent["asset_overall"] >= 0
    assert "continuous_plan_overall" in sent["metrics"]
    assert "春の沖縄プラン" not in str(sent)
    assert "data-token" not in str(sent)


def test_deterministic_sample_is_stable() -> None:
    """同じ key/rate は同じサンプリング結果になる。"""
    assert deterministic_sample("same-key", 0.5) is deterministic_sample("same-key", 0.5)
    assert deterministic_sample("same-key", 0) is False
    assert deterministic_sample("same-key", 1) is True
