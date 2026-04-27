"""継続監視用の非同期・最小化済みテレメトリ helper。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from src.config import AppSettings, get_settings
from src.foundry_tracing import hash_identifier, safe_span_name_part, sanitize_span_attributes
from src.model_deployments import parse_bool_setting

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = "2026-04-continuous-monitoring-v1"
_DEFAULT_RETENTION_DAYS = 30
_REDACTION_FLAGS: dict[str, bool] = {
    "raw_prompt_logged": False,
    "raw_user_content_logged": False,
    "raw_response_logged": False,
    "raw_work_iq_logged": False,
    "transcripts_logged": False,
    "bearer_tokens_logged": False,
    "brochure_html_logged": False,
}

FoundryLogger = Callable[[dict[str, object]], Awaitable[str | None]]
MetricEmitter = Callable[[dict[str, object], AppSettings | None], None]

_records_counter: Any | None = None
_score_histogram: Any | None = None
_latency_histogram: Any | None = None
_metric_value_histogram: Any | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _retention_days(value: str | None) -> int:
    try:
        days = int((value or "").strip())
    except ValueError:
        return _DEFAULT_RETENTION_DAYS
    return min(max(days, 1), 365)


def parse_sample_rate(value: str | None) -> float:
    """サンプリング率を 0.0〜1.0 に丸める。"""
    try:
        rate = float((value or "").strip())
    except ValueError:
        return 0.0
    return min(max(rate, 0.0), 1.0)


def deterministic_sample(sample_key: str, sample_rate: float) -> bool:
    """conversation_id 等から決定的にサンプリングする。"""
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    digest = hashlib.sha256(sample_key.encode("utf-8")).hexdigest()
    bucket = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    return bucket < sample_rate


def is_continuous_monitoring_enabled(settings: AppSettings | None = None) -> bool:
    """継続監視が privacy gate を満たしているかを返す。"""
    resolved = settings or get_settings()
    return (
        parse_bool_setting(resolved["enable_continuous_monitoring"])
        and parse_bool_setting(resolved["enable_evaluation_logging"])
        and bool(resolved["project_endpoint"].strip())
    )


def _safe_dimension(value: object, *, limit: int = 80) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return safe_span_name_part(text)[:limit] or "unknown"


def _numeric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    return None


def _numeric_metrics(metrics: object, *, limit: int = 40) -> dict[str, float]:
    if not isinstance(metrics, Mapping):
        return {}
    numeric: dict[str, float] = {}
    for key, value in metrics.items():
        if len(numeric) >= limit:
            break
        score = _numeric_value(value)
        if score is not None:
            numeric[_safe_dimension(key)] = score
    return numeric


def _average_scores(metrics: Mapping[str, object]) -> float:
    scores = [
        score
        for metric in metrics.values()
        if isinstance(metric, Mapping) and (score := _numeric_value(metric.get("score"))) is not None and score >= 0
    ]
    if not scores:
        return -1.0
    return round(sum(scores) / len(scores), 4)


def _nested_score(payload: object, *path: str) -> float:
    current: object = payload
    for key in path:
        if not isinstance(current, Mapping):
            return -1.0
        current = current.get(key)
    score = _numeric_value(current)
    return round(score, 4) if score is not None else -1.0


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _base_record(record_type: str, conversation_id: str | None, settings: AppSettings | None) -> dict[str, object]:
    resolved = settings or get_settings()
    return {
        "schema_version": _SCHEMA_VERSION,
        "record_type": record_type,
        "recorded_at": _utc_now_iso(),
        "retention_days": _retention_days(resolved["evaluation_log_retention_days"]),
        "conversation_hash": hash_identifier(conversation_id),
        "redaction": dict(_REDACTION_FLAGS),
    }


def build_pipeline_monitoring_record(
    *,
    conversation_id: str,
    events: list[dict],
    status: str,
    settings: AppSettings | None = None,
) -> dict[str, object]:
    """SSE 完了イベント列から raw content なしの監視 payload を作る。"""
    record = _base_record("pipeline_completion", conversation_id, settings)
    event_types: list[str] = []
    agent_statuses: list[str] = []
    tool_statuses: list[str] = []
    tool_sources: list[str] = []
    text_chars = 0
    html_chars = 0
    text_events = 0
    html_events = 0
    image_events = 0
    done_metrics: dict[str, float] = {}

    for event in events:
        event_type = _safe_dimension(event.get("event"))
        event_types.append(event_type)
        data = event.get("data")
        data_mapping = data if isinstance(data, Mapping) else {}
        if event_type == "agent_progress":
            agent_statuses.append(
                f"{_safe_dimension(data_mapping.get('agent'))}:{_safe_dimension(data_mapping.get('status'))}"
            )
        elif event_type == "tool_event":
            tool_statuses.append(
                f"{_safe_dimension(data_mapping.get('tool'))}:{_safe_dimension(data_mapping.get('status'))}"
            )
            if data_mapping.get("source") or data_mapping.get("provider"):
                tool_sources.append(
                    f"{_safe_dimension(data_mapping.get('source'))}:{_safe_dimension(data_mapping.get('provider'))}"
                )
        elif event_type == "text":
            text_events += 1
            content = data_mapping.get("content")
            content_length = len(content) if isinstance(content, str) else 0
            text_chars += content_length
            if _safe_dimension(data_mapping.get("content_type")) == "html":
                html_events += 1
                html_chars += content_length
        elif event_type == "image":
            image_events += 1
        elif event_type == "done":
            done_metrics = _numeric_metrics(data_mapping.get("metrics"))

    record.update(
        {
            "status": _safe_dimension(status, limit=32),
            "event_counts": _count_values(event_types),
            "agent_status_counts": _count_values(agent_statuses),
            "tool_status_counts": _count_values(tool_statuses),
            "tool_source_counts": _count_values(tool_sources),
            "content_shape": {
                "text_events": text_events,
                "text_chars": text_chars,
                "html_text_events": html_events,
                "html_chars": html_chars,
                "image_events": image_events,
            },
            "metrics": done_metrics,
            "legacy_overall": -1.0,
            "plan_overall": -1.0,
            "asset_overall": -1.0,
            "evidence_overall": -1.0,
        }
    )
    return record


def build_evaluation_monitoring_record(
    *,
    conversation_id: str | None,
    artifact_version: int | None,
    query: str,
    response: str,
    html: str,
    results: Mapping[str, object],
    settings: AppSettings | None = None,
) -> dict[str, object]:
    """評価完了結果から raw prompt/HTML なしの監視 payload を作る。"""
    record = _base_record("evaluation_completion", conversation_id, settings)
    findings = results.get("findings")
    finding_statuses = [
        _safe_dimension(finding.get("status"), limit=32)
        for finding in findings
        if isinstance(findings, list) and isinstance(finding, Mapping)
    ] if isinstance(findings, list) else []

    record.update(
        {
            "artifact_version": artifact_version or 0,
            "content_shape": {
                "query_chars": len(query),
                "response_chars": len(response),
                "html_chars": len(html),
            },
            "metrics": {
                "plan_overall": _nested_score(results, "plan_quality", "overall"),
                "asset_overall": _nested_score(results, "asset_quality", "overall"),
                "evidence_overall": _nested_score(results, "evidence_quality", "overall"),
                "legacy_overall": _nested_score(results, "legacy_overall"),
            },
            "finding_status_counts": _count_values(finding_statuses),
            "evidence_count": len(results.get("evidence")) if isinstance(results.get("evidence"), list) else 0,
            "chart_count": len(results.get("charts")) if isinstance(results.get("charts"), list) else 0,
            "plan_overall": _nested_score(results, "plan_quality", "overall"),
            "asset_overall": _nested_score(results, "asset_quality", "overall"),
            "evidence_overall": _nested_score(results, "evidence_quality", "overall"),
            "legacy_overall": _nested_score(results, "legacy_overall"),
        }
    )
    return record


def _apply_local_pipeline_evaluation(record: dict[str, object], plan_markdown: str, brochure_html: str) -> None:
    """raw content は保存せず、ローカル評価スコアだけを監視 record に反映する。"""
    if not plan_markdown.strip() and not brochure_html.strip():
        return

    from src.api import evaluate as evaluate_module

    plan_metrics: dict[str, object] = {}
    if plan_markdown.strip():
        plan_metrics = {
            "plan_structure_readiness": evaluate_module._evaluate_plan_structure(plan_markdown),
            "kpi_evidence_readiness": evaluate_module._evaluate_kpi_evidence_readiness(plan_markdown),
            "offer_specificity": evaluate_module._evaluate_offer_specificity(plan_markdown),
            "travel_law_compliance": evaluate_module._evaluate_travel_law_compliance(plan_markdown, ""),
        }
    asset_metrics: dict[str, object] = {}
    if brochure_html.strip():
        asset_metrics = {
            "cta_visibility": evaluate_module._evaluate_cta_visibility(brochure_html),
            "value_visibility": evaluate_module._evaluate_value_visibility(brochure_html),
            "trust_signal_presence": evaluate_module._evaluate_trust_signal_presence(brochure_html),
            "disclosure_completeness": evaluate_module._evaluate_disclosure_completeness(brochure_html),
            "accessibility_readiness": evaluate_module._evaluate_accessibility_readiness(brochure_html),
        }

    plan_overall = _average_scores(plan_metrics)
    asset_overall = _average_scores(asset_metrics)
    metrics = record.setdefault("metrics", {})
    if isinstance(metrics, dict):
        if plan_overall >= 0:
            metrics["continuous_plan_overall"] = plan_overall
        if asset_overall >= 0:
            metrics["continuous_asset_overall"] = asset_overall
    if plan_overall >= 0:
        record["plan_overall"] = plan_overall
    if asset_overall >= 0:
        record["asset_overall"] = asset_overall
    valid = [score for score in (plan_overall, asset_overall) if score >= 0]
    if valid:
        record["legacy_overall"] = round(sum(valid) / len(valid), 4)


def _metric_attributes(record: Mapping[str, object]) -> dict[str, object]:
    return sanitize_span_attributes(
        {
            "app.monitoring.schema_version": record.get("schema_version"),
            "app.monitoring.record_type": record.get("record_type"),
            "app.conversation.hash": record.get("conversation_hash"),
            "app.monitoring.status": record.get("status"),
            "app.monitoring.artifact_version": record.get("artifact_version"),
        }
    )


def emit_app_insights_monitoring(record: dict[str, object], settings: AppSettings | None = None) -> None:
    """OpenTelemetry 経由で App Insights custom metric/event 相当を送る。未設定時は no-op。"""
    if not is_continuous_monitoring_enabled(settings):
        return
    attributes = _metric_attributes(record)
    try:
        from opentelemetry import metrics, trace
    except ImportError:
        return

    global _records_counter, _score_histogram, _latency_histogram, _metric_value_histogram
    try:
        meter = metrics.get_meter("travel-marketing-agents.continuous_monitoring")
        _records_counter = _records_counter or meter.create_counter("app.continuous_monitoring.records")
        _score_histogram = _score_histogram or meter.create_histogram("app.continuous_monitoring.overall_score")
        _latency_histogram = _latency_histogram or meter.create_histogram("app.continuous_monitoring.latency_seconds")
        _metric_value_histogram = _metric_value_histogram or meter.create_histogram(
            "app.continuous_monitoring.metric_value"
        )

        _records_counter.add(1, attributes=attributes)
        metrics_payload = record.get("metrics")
        if isinstance(metrics_payload, Mapping):
            for metric_name, metric_value in _numeric_metrics(metrics_payload).items():
                metric_attributes = dict(attributes)
                metric_attributes["app.monitoring.metric_name"] = metric_name
                if metric_name in {"plan_overall", "asset_overall", "evidence_overall", "legacy_overall"}:
                    _score_histogram.record(metric_value, attributes=metric_attributes)
                elif metric_name == "latency_seconds":
                    _latency_histogram.record(metric_value, attributes=metric_attributes)
                else:
                    _metric_value_histogram.record(metric_value, attributes=metric_attributes)

        tracer = trace.get_tracer("travel-marketing-agents.continuous_monitoring")
        span = tracer.start_span(
            f"continuous_monitoring.{safe_span_name_part(str(record.get('record_type') or 'record'))}",
            attributes=attributes,
        )
        try:
            if isinstance(metrics_payload, Mapping):
                for metric_name, metric_value in _numeric_metrics(metrics_payload, limit=20).items():
                    span.set_attribute(f"app.monitoring.metric.{metric_name}", metric_value)
        finally:
            span.end()
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.debug("App Insights 継続監視メトリクス送信をスキップ: %s", exc)


async def _default_foundry_logger(record: dict[str, object]) -> str | None:
    from src.api.evaluate import _log_to_foundry

    return await _log_to_foundry(record)


async def run_continuous_monitoring(
    record: dict[str, object],
    *,
    foundry_logger: FoundryLogger | None = None,
    metric_emitter: MetricEmitter = emit_app_insights_monitoring,
    settings: AppSettings | None = None,
) -> str | None:
    """監視 payload を App Insights / Foundry に送る。"""
    resolved = settings or get_settings()
    if not is_continuous_monitoring_enabled(resolved):
        return None
    metric_emitter(record, resolved)
    logger_func = foundry_logger or _default_foundry_logger
    return await logger_func(record)


async def run_continuous_monitoring_safe(
    record: dict[str, object],
    *,
    foundry_logger: FoundryLogger | None = None,
    metric_emitter: MetricEmitter = emit_app_insights_monitoring,
    settings: AppSettings | None = None,
) -> None:
    """継続監視ジョブを非致命的に実行する。"""
    try:
        await run_continuous_monitoring(
            record,
            foundry_logger=foundry_logger,
            metric_emitter=metric_emitter,
            settings=settings,
        )
    except (ImportError, ValueError, OSError, RuntimeError, TypeError) as exc:
        logger.warning("継続監視ジョブに失敗（非致命的）: %s", exc)
    except Exception as exc:
        logger.exception("継続監視ジョブで予期しないエラー: %s", exc)


async def run_pipeline_evaluation_monitoring_safe(
    record: dict[str, object],
    *,
    plan_markdown: str,
    brochure_html: str,
    foundry_logger: FoundryLogger | None = None,
    metric_emitter: MetricEmitter = emit_app_insights_monitoring,
    settings: AppSettings | None = None,
) -> None:
    """pipeline 完了後にローカル評価を追加し、監視ジョブを非致命的に実行する。"""
    try:
        _apply_local_pipeline_evaluation(record, plan_markdown, brochure_html)
    except (ImportError, ValueError, OSError, RuntimeError, TypeError) as exc:
        logger.warning("継続監視のローカル評価に失敗（メトリクスのみ送信）: %s", exc)
    except Exception as exc:
        logger.exception("継続監視のローカル評価で予期しないエラー: %s", exc)
    await run_continuous_monitoring_safe(
        record,
        foundry_logger=foundry_logger,
        metric_emitter=metric_emitter,
        settings=settings,
    )


def schedule_continuous_monitoring(
    background_tasks: Any | None,
    *,
    record: dict[str, object],
    sample_key: str,
    settings: AppSettings | None = None,
    foundry_logger: FoundryLogger | None = None,
    metric_emitter: MetricEmitter = emit_app_insights_monitoring,
) -> bool:
    """条件を満たす場合だけ監視ジョブを BackgroundTasks / asyncio に登録する。"""
    resolved = settings or get_settings()
    if not is_continuous_monitoring_enabled(resolved):
        return False

    sample_rate = parse_sample_rate(resolved["continuous_monitoring_sample_rate"])
    if not deterministic_sample(sample_key, sample_rate):
        return False

    record["sampling"] = {
        "sample_rate": sample_rate,
        "sample_key_hash": hash_identifier(sample_key),
        "deterministic": True,
    }

    if background_tasks is not None:
        background_tasks.add_task(
            run_continuous_monitoring_safe,
            record,
            foundry_logger=foundry_logger,
            metric_emitter=metric_emitter,
            settings=resolved,
        )
        return True

    try:
        asyncio.get_running_loop().create_task(
            run_continuous_monitoring_safe(
                record,
                foundry_logger=foundry_logger,
                metric_emitter=metric_emitter,
                settings=resolved,
            )
        )
        return True
    except RuntimeError as exc:
        logger.debug("実行中 event loop がないため継続監視ジョブをスキップ: %s", exc)
        return False


def schedule_pipeline_evaluation_monitoring(
    background_tasks: Any | None,
    *,
    record: dict[str, object],
    sample_key: str,
    plan_markdown: str,
    brochure_html: str,
    settings: AppSettings | None = None,
    foundry_logger: FoundryLogger | None = None,
    metric_emitter: MetricEmitter = emit_app_insights_monitoring,
) -> bool:
    """pipeline 完了時の sampled async local evaluation + 監視を登録する。"""
    resolved = settings or get_settings()
    if not is_continuous_monitoring_enabled(resolved):
        return False

    sample_rate = parse_sample_rate(resolved["continuous_monitoring_sample_rate"])
    if not deterministic_sample(sample_key, sample_rate):
        return False

    record["sampling"] = {
        "sample_rate": sample_rate,
        "sample_key_hash": hash_identifier(sample_key),
        "deterministic": True,
    }

    if background_tasks is not None:
        background_tasks.add_task(
            run_pipeline_evaluation_monitoring_safe,
            record,
            plan_markdown=plan_markdown,
            brochure_html=brochure_html,
            foundry_logger=foundry_logger,
            metric_emitter=metric_emitter,
            settings=resolved,
        )
        return True

    try:
        asyncio.get_running_loop().create_task(
            run_pipeline_evaluation_monitoring_safe(
                record,
                plan_markdown=plan_markdown,
                brochure_html=brochure_html,
                foundry_logger=foundry_logger,
                metric_emitter=metric_emitter,
                settings=resolved,
            )
        )
        return True
    except RuntimeError as exc:
        logger.debug("実行中 event loop がないため継続監視ジョブをスキップ: %s", exc)
        return False
