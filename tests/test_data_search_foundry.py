"""data-search Foundry Prompt Agent (PR 3) のテスト。

カバー範囲:
- 2-pass logic (Pass 1 success / Pass 1 zero-fabric → Pass 2 / Pass 1 401 → Pass 2 / Pass 1 5xx → fail loud)
- delegated token 不在 → ValueError
- AZURE_AI_PROJECT_ENDPOINT 不在 → ValueError
- recoverable error 判定
- Fabric tool detection
- agent definition (`MicrosoftFabricPreviewTool` 有無、Code Interpreter 有無)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from src import foundry_prompt_agents as module


class _FakeResponses:
    def __init__(self, response_queue: list[Any]) -> None:
        self._queue = list(response_queue)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._queue:
            return SimpleNamespace(id="resp_default", output=[])
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        return None


class _FakeOpenAIClient:
    def __init__(self, response_queue: list[Any]) -> None:
        self.responses = _FakeResponses(response_queue)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeAgents:
    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def get(self, *, agent_name: str):
        return SimpleNamespace(name=agent_name)


class _FakeProjectClient:
    def __init__(self, openai_client: _FakeOpenAIClient, agent_name: str) -> None:
        self._openai_client = openai_client
        self.agents = _FakeAgents(agent_name)
        self.openai_client_kwargs: list[dict[str, object]] = []
        self.closed = False

    def get_openai_client(self, **kwargs) -> _FakeOpenAIClient:
        self.openai_client_kwargs.append(kwargs)
        return self._openai_client

    def close(self) -> None:
        self.closed = True


def _settings() -> dict[str, str]:
    return {
        "project_endpoint": "https://example.test",
        "model_name": "gpt-5-4-mini",
        "data_search_prompt_agent_name": "travel-data-search",
        "marketing_plan_prompt_agent_name": "travel-marketing-plan",
        "foundry_fabric_connection_id": "",
        "enable_code_interpreter": "false",
        "enable_gpt_55": "false",
        "gpt_55_deployment_name": "",
        "enable_model_router": "false",
        "model_router_endpoint": "",
        "model_router_deployment_name": "",
        "model_deployment_allowlist": "",
    }


def _build_response_with_fabric() -> SimpleNamespace:
    """Pass 1 で Fabric tool が呼ばれ grounded answer が返った response を模擬する。

    rubber-duck `pass1-polite-refusal-impl-review` blocking #1 反映: 既存テストでも
    grounded text を含めるよう更新 (空応答は新しい defense-in-depth により Pass 2 に
    降格されるため)。
    """
    message_item = SimpleNamespace(
        type="message",
        content=[
            SimpleNamespace(
                type="output_text",
                text=(
                    "Fabric Data Agent から夏のハワイ売上 ¥38,926,615 / 予約 39件 / "
                    "旅行者 131名 / 平均評価 4.0 を取得しました。"
                ),
            )
        ],
    )
    return SimpleNamespace(
        id="resp_pass1_ok",
        output_text=(
            "Fabric Data Agent から夏のハワイ売上 ¥38,926,615 / 予約 39件 / "
            "旅行者 131名 / 平均評価 4.0 を取得しました。"
        ),
        output=[
            SimpleNamespace(type="fabric_dataagent_preview"),
            message_item,
        ],
    )


def _build_response_without_fabric() -> SimpleNamespace:
    """Pass 1 で Fabric tool が呼ばれなかった response を模擬する。"""
    return SimpleNamespace(
        id="resp_pass1_no_fabric",
        output=[SimpleNamespace(type="message")],
    )


def _patch_common(monkeypatch) -> None:
    monkeypatch.setattr(module, "get_settings", _settings)
    monkeypatch.setattr(module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(module, "resolve_model_deployment", lambda name, **_: name)


def _assert_pass2_payload_shape(call: dict[str, object]) -> None:
    """Foundry 400 regression guard (`Not allowed when agent is specified.`).

    rubber-duck `pass2-agent-ref-fix` Non-Blocking #2 反映: recoverable
    failure 全 4 経路 (zero-fabric / 401 / 400 invalid_request / serialize
    TypeError) で Pass 2 payload shape が壊れていないことを共通 helper で固定する。
    """
    assert call.get("tool_choice") == "required", "Pass 2 must force tool_choice=required"
    assert call.get("tools"), "Pass 2 must pass function tools at top level"
    extra_body = call.get("extra_body") or {}
    assert isinstance(extra_body, dict)
    assert (
        "agent_reference" not in extra_body
    ), "Pass 2 must NOT set extra_body.agent_reference (Foundry rejects agent + tools combination)"
    assert call.get(
        "instructions"
    ), "Pass 2 must pass instructions directly when agent_reference is absent"


def test_run_data_search_prompt_agent_pass1_success(monkeypatch) -> None:
    """Pass 1 で Fabric tool が呼ばれたら採用 (Pass 2 を発行しない)。"""
    _patch_common(monkeypatch)
    pass1_response = _build_response_with_fabric()
    openai_client = _FakeOpenAIClient([pass1_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass1_response
    assert len(openai_client.responses.calls) == 1, "Pass 2 should not be invoked"
    pass1_call = openai_client.responses.calls[0]
    # rubber-duck `tool-choice-required-fix` 反映 (live App Insights 2026-05-03):
    # Pass 1 は tool_choice="required" (top-level) + extra_body.agent_reference のみ。
    # 旧 ToolChoiceAllowed (extra_body.tool_choice={type:"allowed_tools", ...}) は
    # Foundry が `tool_choice.tools[0].type` で `file_search` 以外を拒否するため使わない。
    assert pass1_call["tool_choice"] == "required"
    assert pass1_call["extra_body"]["agent_reference"]["name"].startswith("travel-data-search-")
    assert (
        "tool_choice" not in pass1_call.get("extra_body", {})
    ), "Pass 1 must NOT set extra_body.tool_choice (Foundry rejects allowed_tools shape for fabric_dataagent_preview)"
    assert (
        "tools" not in pass1_call
    ), "Pass 1 must NOT pass top-level tools when agent_reference is set (Foundry rejects 'agent + tools')"


def test_run_data_search_prompt_agent_pass1_zero_fabric_falls_back_to_pass2(monkeypatch) -> None:
    """Pass 1 で Fabric tool が呼ばれなかった場合 Pass 2 に降格する。"""
    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2", output=[SimpleNamespace(type="message")])
    openai_client = _FakeOpenAIClient([_build_response_without_fabric(), pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 2, "Pass 2 must be invoked after zero-fabric Pass 1"
    pass2_call = openai_client.responses.calls[1]
    _assert_pass2_payload_shape(pass2_call)


def test_run_data_search_prompt_agent_pass1_401_falls_back_to_pass2(monkeypatch) -> None:
    """Pass 1 で 401 が出たら Pass 2 に降格する (recoverable failure)。"""
    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_after_401", output=[])
    openai_client = _FakeOpenAIClient(
        [RuntimeError("Pass 1 failed: 401 Unauthorized OBO failure"), pass2_response]
    )
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 2
    _assert_pass2_payload_shape(openai_client.responses.calls[1])


def test_run_data_search_prompt_agent_pass1_5xx_fails_loud(monkeypatch) -> None:
    """5xx / 一般 exception は Pass 2 にせず例外を伝播する。"""
    _patch_common(monkeypatch)
    openai_client = _FakeOpenAIClient([RuntimeError("Internal Server Error 500 unexpected")])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    with pytest.raises(RuntimeError, match="500"):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )

    assert len(openai_client.responses.calls) == 1, "Pass 2 must NOT be invoked on non-recoverable failure"


def test_run_data_search_prompt_agent_no_connection_id_skips_pass1(monkeypatch) -> None:
    """connection_id 未設定なら Pass 1 をスキップして Pass 2 直行する。"""
    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_only", output=[])
    openai_client = _FakeOpenAIClient([pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 1
    assert openai_client.responses.calls[0]["tool_choice"] == "required"


def test_run_data_search_prompt_agent_requires_delegated_token(monkeypatch) -> None:
    """delegated token 不在は ValueError で fail-fast する。"""
    _patch_common(monkeypatch)

    with pytest.raises(ValueError, match="delegated"):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="",
                fabric_connection_id="conn-id-123",
            )
        )


def test_run_data_search_prompt_agent_requires_project_endpoint(monkeypatch) -> None:
    """AZURE_AI_PROJECT_ENDPOINT 不在は ValueError で fail-fast する。"""
    settings_no_endpoint = _settings()
    settings_no_endpoint["project_endpoint"] = ""
    monkeypatch.setattr(module, "get_settings", lambda: settings_no_endpoint)
    monkeypatch.setattr(module, "DefaultAzureCredential", lambda: object())

    with pytest.raises(ValueError, match="AZURE_AI_PROJECT_ENDPOINT"):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )


def test_is_recoverable_pass1_failure_classification() -> None:
    """recoverable error 判定の基本ケース。"""
    assert module._is_recoverable_pass1_failure(RuntimeError("401 Unauthorized"))
    assert module._is_recoverable_pass1_failure(RuntimeError("HTTP 403 Forbidden"))
    assert module._is_recoverable_pass1_failure(RuntimeError("OBO token failure"))
    assert module._is_recoverable_pass1_failure(RuntimeError("connection not found"))
    # rubber-duck `pr3-impl-review` Blocking #1: 400 / invalid_request_error は recoverable
    assert module._is_recoverable_pass1_failure(
        RuntimeError(
            "Error code: 400 - {'error': {'message': \"Invalid type for 'extra_body.tool_choice'.\", 'type': 'invalid_request_error'}}"
        )
    )
    assert module._is_recoverable_pass1_failure(
        RuntimeError("400 Bad Request: tool_choice shape mismatch")
    )
    # rubber-duck `tool-choice-required-fix` defense-in-depth: 将来 Foundry が
    # tool_choice="required" + agent_reference の組み合わせを別 invalid_value 系で
    # reject する場合や、live App Insights で観測した
    # `Invalid value: 'fab...iew'. Value must be 'file_search'.` (param=`tool_choice.tools[0].type`)
    # 系の error が再発した場合に Pass 2 fallback で吸収する。
    assert module._is_recoverable_pass1_failure(
        RuntimeError(
            "Error code: 400 - {'error': {'message': \"Invalid value: 'fab...iew'. Value must be 'file_search'.\", "
            "'type': 'invalid_request_error', 'param': 'tool_choice.tools[0].type', 'code': 'invalid_value'}}"
        )
    )
    # rubber-duck `tca-serialize-fix` Blocking #2: client-side JSON serialize failure
    # (Pydantic obj が extra_body に紛れ込んだ場合) も Pass 2 に降格する (defense in depth)。
    assert module._is_recoverable_pass1_failure(
        TypeError("Object of type ToolChoiceAllowed is not JSON serializable")
    )
    assert not module._is_recoverable_pass1_failure(RuntimeError("Internal Server Error 500"))
    assert not module._is_recoverable_pass1_failure(RuntimeError("502 Bad Gateway"))


def test_run_data_search_prompt_agent_pass1_400_falls_back_to_pass2(monkeypatch) -> None:
    """Pass 1 で 400 invalid_request_error が出たら Pass 2 に降格する。

    rubber-duck `tool-choice-required-fix` 反映: live App Insights で観測した
    `Invalid value: 'fab...iew'. Value must be 'file_search'.` (invalid_value,
    param `tool_choice.tools[0].type`) と、過去の `Invalid type for 'extra_body.tool_choice'`
    の両方を defense-in-depth で recoverable と扱い、Pass 2 で吸収する。
    """
    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_after_400", output=[])
    bad_request = RuntimeError(
        "Error code: 400 - {'error': {'message': \"Invalid value: 'fab...iew'. Value must be 'file_search'.\", "
        "'type': 'invalid_request_error', 'param': 'tool_choice.tools[0].type', 'code': 'invalid_value'}}"
    )
    openai_client = _FakeOpenAIClient([bad_request, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 2, "Pass 2 must be invoked after 400 invalid_request_error"
    _assert_pass2_payload_shape(openai_client.responses.calls[1])


def test_pass1_payload_uses_tool_choice_required_top_level(monkeypatch) -> None:
    """Pass 1 が tool_choice="required" を top-level で渡し、extra_body には agent_reference のみ含むことを保証する。

    rubber-duck `tool-choice-required-fix` 反映: 旧 ToolChoiceAllowed
    (extra_body.tool_choice={type:"allowed_tools", ...}) は Foundry が
    `tool_choice.tools[0].type` で `file_search` 以外を拒否する (live App Insights
    2026-05-03 13:13/13:20 UTC で 3 件連続観測)。新形は
    - tool_choice: "required" (top-level, plain string)
    - extra_body: {"agent_reference": {...}} のみ
    で、agent definition に MicrosoftFabricPreviewTool だけ登録されている前提に
    依存する (live agent travel-data-search-gpt-5-4-mini:1 は Fabric only)。
    """
    import json as _json

    _patch_common(monkeypatch)
    pass1_response = _build_response_with_fabric()
    openai_client = _FakeOpenAIClient([pass1_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    pass1_call = openai_client.responses.calls[0]
    assert pass1_call["tool_choice"] == "required", (
        "Pass 1 must use tool_choice=required (string) — Foundry rejects allowed_tools shape "
        "for fabric_dataagent_preview"
    )
    extra_body = pass1_call["extra_body"]
    assert "agent_reference" in extra_body
    assert extra_body["agent_reference"]["type"] == "agent_reference"
    assert "tool_choice" not in extra_body, (
        "Pass 1 must NOT set extra_body.tool_choice — must be top-level"
    )
    assert "tools" not in pass1_call, (
        "Pass 1 must NOT pass top-level tools (Foundry rejects 'Not allowed when agent is specified.')"
    )
    # Critical: full kwargs must round-trip through json.dumps without TypeError
    _json.dumps({"extra_body": extra_body, "tool_choice": pass1_call["tool_choice"]})


def test_pass1_serialize_typeerror_falls_back_to_pass2(monkeypatch) -> None:
    """Pass 1 で client-side JSON serialize 失敗 (TypeError) が出たら Pass 2 に降格する。

    rubber-duck `tool-choice-required-fix` defense-in-depth: 新形では
    extra_body は `{"agent_reference": {...}}` の plain dict のみで TypeError 発生
    確率は激減するが、SDK 内部の future drift / 第三者拡張で Pydantic obj が
    紛れ込んだ場合の保険として fallback が効くことを固定する。
    """
    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_after_serialize", output=[])
    serialize_err = TypeError("Object of type ToolChoiceAllowed is not JSON serializable")
    openai_client = _FakeOpenAIClient([serialize_err, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 2, (
        "Pass 2 must be invoked after client-side serialize TypeError"
    )
    _assert_pass2_payload_shape(openai_client.responses.calls[1])


def test_detect_fabric_tool_invoked_handles_dict_and_object_outputs() -> None:
    """fabric tool 検出は dict / object 両方の output に対応する。"""
    obj_response = SimpleNamespace(output=[SimpleNamespace(type="fabric_dataagent_preview")])
    assert module._detect_fabric_tool_invoked(obj_response)

    dict_response = SimpleNamespace(output=[{"type": "fabric_dataagent_preview"}])
    assert module._detect_fabric_tool_invoked(dict_response)

    no_fabric = SimpleNamespace(output=[SimpleNamespace(type="message")])
    assert not module._detect_fabric_tool_invoked(no_fabric)

    empty_response = SimpleNamespace(output=[])
    assert not module._detect_fabric_tool_invoked(empty_response)


def test_build_data_search_agent_definition_with_fabric_connection() -> None:
    """connection_id ありなら Fabric tool が definition に含まれる。"""
    definition = module.build_data_search_agent_definition(
        "gpt-5-4-mini",
        fabric_connection_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/foundry/projects/proj/connections/fabric-conn",
    )
    assert definition is not None
    assert getattr(definition, "tools", None), "tools should be populated when fabric connection is set"


def test_build_data_search_agent_definition_without_fabric_connection() -> None:
    """connection_id 空なら Fabric tool は無く、CI も無効なら tools は空。"""
    definition = module.build_data_search_agent_definition(
        "gpt-5-4-mini",
        fabric_connection_id="",
        code_interpreter_enabled=False,
    )
    assert definition is not None
    tools = getattr(definition, "tools", []) or []
    assert tools == [], "tools must be empty without fabric or code interpreter"


def _make_fake_function_call_loop(final_response: Any):
    """`_run_function_call_loop` の fake (async) を作る。"""

    async def _fake(_openai_client, _initial, *, model_name: str):
        del model_name
        return final_response

    return _fake


# ---------- Bug #1 regression: stuck `fabric_data_agent_invocation` chip ----------
#
# Live smoke test 2026-05-03 では UI 上で `fabric_data_agent_invocation` chip が
# spinner のまま残り続ける現象が発生していた。原因は `success`/`no_op`/`fallback`
# という非 canonical な status が emit され、frontend `tool-events.ts:124-129` の
# `toolStatusRank()` で rank 0 (terminal でない) と判定されていたため。
#
# 修正方針: backend telemetry はもともと `auxiliary backend telemetry` 目的だった
# ので、SSE event ではなく `logger.info` で AppTraces に記録する設計に統一。
# UI は canonical な `query_data_agent` の running → completed/failed lifecycle
# だけで完結する。

def test_run_data_search_prompt_agent_does_not_emit_fabric_data_agent_invocation_event(
    monkeypatch,
) -> None:
    """`fabric_data_agent_invocation` event は SSE に emit してはいけない。

    Bug #1 regression: 旧実装では Pass 1 success / no_op / Pass 2 success / no_op
    で `success` / `no_op` / `fallback` という非 canonical status を emit して
    いた → frontend chip が spinner のまま残る。修正後は `logger.info` のみ。
    """
    _patch_common(monkeypatch)
    captured: list[Any] = []

    def _capture(payload: Any) -> None:
        captured.append(payload)

    # `emit_tool_event` is imported lazily inside `run_data_search_prompt_agent`,
    # so patch the source module rather than the consumer module.
    import src.tool_telemetry as tool_telemetry

    monkeypatch.setattr(tool_telemetry, "emit_tool_event", _capture)
    pass1_response = _build_response_with_fabric()
    openai_client = _FakeOpenAIClient([pass1_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    emitted_tools = [
        (payload.get("tool") if isinstance(payload, dict) else None) for payload in captured
    ]
    assert "fabric_data_agent_invocation" not in emitted_tools, (
        "fabric_data_agent_invocation must NOT be emitted as SSE tool_event "
        f"(got: {emitted_tools}). Use logger.info instead so the UI doesn't "
        "show a stuck spinner chip."
    )
    # canonical lifecycle chip は出ていること
    assert "query_data_agent" in emitted_tools


# rubber-duck `bug1-fix-critique` non-blocking #2 反映: 旧実装は Pass 1 success /
# Pass 1 zero-fabric / Pass 1 recoverable / Pass 2 の **4 path** で
# `fabric_data_agent_invocation` SSE event を emit していた。各 path で event が
# emit されない事を個別に保証する (将来 1 path だけ regress した場合の検出)。
@pytest.mark.parametrize(
    "scenario",
    ["pass1_success", "pass1_zero_fabric", "pass1_recoverable", "pass2_success"],
)
def test_run_data_search_prompt_agent_no_fabric_data_agent_invocation_event_in_any_path(
    monkeypatch, scenario: str
) -> None:
    """4 path 全てで `fabric_data_agent_invocation` SSE event は emit されない。"""
    _patch_common(monkeypatch)

    captured: list[Any] = []

    def _capture(payload: Any) -> None:
        captured.append(payload)

    import src.tool_telemetry as tool_telemetry

    monkeypatch.setattr(tool_telemetry, "emit_tool_event", _capture)

    pass2_response = SimpleNamespace(
        id=f"resp_pass2_for_{scenario}",
        output=[SimpleNamespace(type="fabric_dataagent_preview"), SimpleNamespace(type="message")],
    )
    if scenario == "pass1_success":
        responses = [_build_response_with_fabric()]
    elif scenario == "pass1_zero_fabric":
        responses = [_build_response_without_fabric(), pass2_response]
    elif scenario == "pass1_recoverable":
        responses = [RuntimeError("401 Unauthorized OBO failure"), pass2_response]
    else:  # pass2_success — Pass 1 で zero-fabric → Pass 2 で fabric 呼ばれる
        responses = [_build_response_without_fabric(), pass2_response]

    openai_client = _FakeOpenAIClient(responses)
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ売上",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    emitted_tools = [
        (payload.get("tool") if isinstance(payload, dict) else None) for payload in captured
    ]
    assert "fabric_data_agent_invocation" not in emitted_tools, (
        f"[{scenario}] fabric_data_agent_invocation must NOT be emitted as SSE event. "
        f"Got: {emitted_tools}"
    )


def test_run_data_search_prompt_agent_pass1_success_logs_canonical_telemetry(
    monkeypatch, caplog
) -> None:
    """Pass 1 成功時に AppTraces 用の structured log が出ること。"""
    import logging

    _patch_common(monkeypatch)
    pass1_response = _build_response_with_fabric()
    openai_client = _FakeOpenAIClient([pass1_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    with caplog.at_level(logging.INFO, logger=module.logger.name):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )

    fabric_logs = [r.getMessage() for r in caplog.records if "fabric_data_agent_invocation" in r.getMessage()]
    assert any("pass=pass1" in msg and "fabric_tool_invoked=True" in msg and "status=completed" in msg for msg in fabric_logs), (
        f"Expected canonical Pass 1 success log line; got: {fabric_logs}"
    )


def test_run_data_search_prompt_agent_pass1_zero_fabric_logs_no_op(monkeypatch, caplog) -> None:
    """Pass 1 で Fabric tool が呼ばれなかったときは AppTraces に no_op を記録する。"""
    import logging

    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_zero_fabric_log", output=[])
    openai_client = _FakeOpenAIClient([_build_response_without_fabric(), pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    with caplog.at_level(logging.INFO, logger=module.logger.name):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )

    fabric_logs = [r.getMessage() for r in caplog.records if "fabric_data_agent_invocation" in r.getMessage()]
    assert any("pass=pass1" in msg and "fabric_tool_invoked=False" in msg and "status=no_op" in msg for msg in fabric_logs), (
        f"Expected canonical Pass 1 no_op log line; got: {fabric_logs}"
    )


def test_run_data_search_prompt_agent_pass1_recoverable_logs_fallback(monkeypatch, caplog) -> None:
    """Pass 1 recoverable failure 時は AppTraces に fallback を記録する。"""
    import logging

    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(id="resp_pass2_recoverable_log", output=[])
    openai_client = _FakeOpenAIClient(
        [RuntimeError("401 Unauthorized OBO failure"), pass2_response]
    )
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    with caplog.at_level(logging.INFO, logger=module.logger.name):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )

    fabric_logs = [r.getMessage() for r in caplog.records if "fabric_data_agent_invocation" in r.getMessage()]
    assert any("pass=pass1" in msg and "status=fallback" in msg for msg in fabric_logs), (
        f"Expected canonical Pass 1 fallback log line; got: {fabric_logs}"
    )


def test_run_data_search_prompt_agent_pass2_logs_canonical_telemetry(monkeypatch, caplog) -> None:
    """Pass 2 完了時にも AppTraces に completed/no_op を記録する。"""
    import logging

    _patch_common(monkeypatch)
    pass2_response = SimpleNamespace(
        id="resp_pass2_with_fabric",
        output=[SimpleNamespace(type="fabric_dataagent_preview"), SimpleNamespace(type="message")],
    )
    openai_client = _FakeOpenAIClient([_build_response_without_fabric(), pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    with caplog.at_level(logging.INFO, logger=module.logger.name):
        asyncio.run(
            module.run_data_search_prompt_agent(
                "夏のハワイ売上",
                None,
                delegated_user_access_token="delegated-token",
                fabric_connection_id="conn-id-123",
            )
        )

    fabric_logs = [r.getMessage() for r in caplog.records if "fabric_data_agent_invocation" in r.getMessage()]
    assert any("pass=pass2" in msg and "status=completed" in msg for msg in fabric_logs), (
        f"Expected canonical Pass 2 completed log line; got: {fabric_logs}"
    )


# ---------- Pass 1 polite-refusal detection (2026-05-04) ----------
#
# `Travel_Ontology_DA_v2` の NL2Ontology は GQL を生成できないとき
# 「該当データは見つかりませんでした」等の polite refusal を返す
# (live web smoke 2026-05-03 で 4 demo prompts のうち春・沖縄・ファミリー
# で再現)。実際には沖縄 spring family は 379 bookings · ¥232M のデータが
# lakehouse に存在するため、polite refusal を検出して Pass 2 (function tool
# fallback) に降格させ、SQL endpoint から実集計値を返す。


def test_extract_responses_api_text_uses_output_text_first() -> None:
    """SDK convenience の output_text を優先して取り出せる。"""
    response = SimpleNamespace(output_text="¥232,485,000 / 379件 / 平均 4.3", output=[])
    assert module._extract_responses_api_text(response) == "¥232,485,000 / 379件 / 平均 4.3"


def test_extract_responses_api_text_falls_back_to_message_content() -> None:
    """output_text 不在時は message item の content[*].text を結合する。"""
    response = SimpleNamespace(
        output=[
            SimpleNamespace(type="fabric_dataagent_preview"),
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(text="該当データは見つかりませんでした。")],
            ),
        ],
    )
    text = module._extract_responses_api_text(response)
    assert "見つかりませんでした" in text


def test_extract_responses_api_text_handles_dict_message_content() -> None:
    """dict shape の message item でも text を抽出できる。"""
    response = {
        "output": [
            {"type": "message", "content": [{"text": "0件"}]},
        ],
    }
    response_obj = SimpleNamespace(output=response["output"])
    assert module._extract_responses_api_text(response_obj) == "0件"


def test_extract_responses_api_text_returns_empty_for_empty_response() -> None:
    """text が無ければ空文字を返す (None response も安全に処理)。"""
    assert module._extract_responses_api_text(None) == ""
    assert module._extract_responses_api_text(SimpleNamespace(output=[])) == ""
    assert (
        module._extract_responses_api_text(
            SimpleNamespace(output=[SimpleNamespace(type="fabric_dataagent_preview")])
        )
        == ""
    )


def _build_pass1_response_with_text(text: str) -> SimpleNamespace:
    """Fabric tool が呼ばれて assistant 本文 `text` を返す Pass 1 response を組み立てる。"""
    return SimpleNamespace(
        id="resp_pass1_with_text",
        output_text=text,
        output=[
            SimpleNamespace(type="fabric_dataagent_preview"),
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(text=text)],
            ),
        ],
    )


def test_pass1_polite_refusal_falls_back_to_pass2(monkeypatch) -> None:
    """Pass 1 で Fabric tool は呼ばれたが polite refusal の場合は Pass 2 に降格する。

    Live regression: 「春の沖縄ファミリー向けプランを企画して」で
    Foundry Fabric DA NL2Ontology が
    「春・沖縄・ファミリー条件での売上、予約数、平均単価、顧客評価の該当データは
    見つかりませんでした」と返すケース。沖縄 spring family は実際には 379 bookings ·
    ¥232M の grounded data が lakehouse に存在するため、Pass 2 SQL endpoint で
    実集計値を取得すべき。
    """
    _patch_common(monkeypatch)
    pass1_response = _build_pass1_response_with_text(
        "春・沖縄・ファミリー条件での売上、予約数、平均単価、顧客評価の該当データは"
        "見つかりませんでした。条件に合致する予約や評価が登録されていないためです。"
    )
    pass2_response = SimpleNamespace(id="resp_pass2_after_polite_refusal", output=[])
    openai_client = _FakeOpenAIClient([pass1_response, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "春の沖縄ファミリー向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response, "Pass 2 result must be returned when Pass 1 was a polite refusal"
    assert len(openai_client.responses.calls) == 2, (
        "Pass 2 must be invoked after Pass 1 polite refusal "
        f"(calls={len(openai_client.responses.calls)})"
    )
    _assert_pass2_payload_shape(openai_client.responses.calls[1])


def test_pass1_grounded_response_returns_directly(monkeypatch) -> None:
    """Pass 1 で Fabric tool が呼ばれ grounded metrics を返した場合 Pass 2 は呼ばない。"""
    _patch_common(monkeypatch)
    pass1_response = _build_pass1_response_with_text(
        "夏のハワイ・学生条件で売上 ¥38,926,615 / 予約 39件 / 旅行者 131名 / 平均評価 4.0 を取得しました。"
    )
    openai_client = _FakeOpenAIClient([pass1_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "夏のハワイ学生旅行向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass1_response
    assert len(openai_client.responses.calls) == 1, (
        "Pass 2 must NOT be invoked when Pass 1 returned a grounded answer"
    )


def test_pass1_empty_text_falls_back_to_pass2(monkeypatch) -> None:
    """rubber-duck blocking #1: Fabric tool 成功 + 抽出本文が空の場合は false-success を
    避けるため Pass 2 に降格する (SDK shape drift / streaming truncation 防御)。"""
    _patch_common(monkeypatch)

    fabric_call = SimpleNamespace(type="fabric_dataagent_preview", id="fab_empty")
    pass1_response = SimpleNamespace(
        id="resp_pass1_empty",
        output_text="",
        output=[fabric_call],
    )
    pass2_response = SimpleNamespace(id="resp_pass2_after_empty", output=[])
    openai_client = _FakeOpenAIClient([pass1_response, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "春の沖縄ファミリー向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response, (
        "Pass 1 で本文が空のとき false-success を避けて Pass 2 に降格すべき"
    )
    assert len(openai_client.responses.calls) == 2, (
        "Pass 1 + Pass 2 の 2 回呼ばれているはず"
    )


def test_pass1_whitespace_only_text_falls_back_to_pass2(monkeypatch) -> None:
    """空白のみの応答も empty 同様に Pass 2 に降格する。"""
    _patch_common(monkeypatch)

    pass1_response = _build_pass1_response_with_text("   \n  \t  \n")
    pass2_response = SimpleNamespace(id="resp_pass2_after_ws", output=[])
    openai_client = _FakeOpenAIClient([pass1_response, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    result = asyncio.run(
        module.run_data_search_prompt_agent(
            "春の沖縄ファミリー向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    assert result is pass2_response
    assert len(openai_client.responses.calls) == 2


def test_pass1_empty_text_emits_empty_assistant_text_reason(monkeypatch) -> None:
    """空応答 fallback event は `reason=empty_assistant_text` を含む。"""
    _patch_common(monkeypatch)

    fabric_call = SimpleNamespace(type="fabric_dataagent_preview", id="fab_empty2")
    pass1_response = SimpleNamespace(id="resp_pass1_empty2", output_text="", output=[fabric_call])
    pass2_response = SimpleNamespace(id="resp_pass2_after_empty2", output=[])
    openai_client = _FakeOpenAIClient([pass1_response, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    captured: list[dict[str, Any]] = []

    def _capture(event_data: dict[str, Any]) -> None:
        captured.append(event_data)

    import src.tool_telemetry as _telemetry
    monkeypatch.setattr(_telemetry, "emit_tool_event", _capture)

    asyncio.run(
        module.run_data_search_prompt_agent(
            "春の沖縄ファミリー向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    pass1_failed_events = [
        ev for ev in captured
        if ev.get("tool") == "query_data_agent"
        and ev.get("status") == "failed"
        and ev.get("phase") == "pass1"
    ]
    assert pass1_failed_events, f"Expected Pass 1 failed event; got: {captured}"
    error_messages = " | ".join(ev.get("error_message", "") for ev in pass1_failed_events)
    assert "no extractable assistant text" in error_messages, (
        f"Expected empty_assistant_text marker in error_message; got: {error_messages}"
    )


def test_pass1_polite_refusal_emits_low_confidence_fallback_event(monkeypatch) -> None:
    """polite refusal 時に SSE timeline 用の failed event が
    `pass2_function_tools_low_confidence` fallback で emit される。"""
    _patch_common(monkeypatch)
    pass1_response = _build_pass1_response_with_text("該当データは見つかりませんでした。")
    pass2_response = SimpleNamespace(id="resp_pass2_low_conf_event", output=[])
    openai_client = _FakeOpenAIClient([pass1_response, pass2_response])
    project_client = _FakeProjectClient(openai_client, "travel-data-search-gpt-5-4-mini")
    monkeypatch.setattr(module, "AIProjectClient", lambda endpoint, credential: project_client)
    monkeypatch.setattr(module, "_run_function_call_loop", _make_fake_function_call_loop(pass2_response))

    captured: list[dict[str, Any]] = []

    def _capture(event_data: dict[str, Any]) -> None:
        captured.append(event_data)

    import src.tool_telemetry as _telemetry
    monkeypatch.setattr(_telemetry, "emit_tool_event", _capture)

    asyncio.run(
        module.run_data_search_prompt_agent(
            "春の沖縄ファミリー向けプランを企画して",
            None,
            delegated_user_access_token="delegated-token",
            fabric_connection_id="conn-id-123",
        )
    )

    pass1_failed_events = [
        ev for ev in captured
        if ev.get("tool") == "query_data_agent"
        and ev.get("status") == "failed"
        and ev.get("phase") == "pass1"
    ]
    assert pass1_failed_events, f"Expected Pass 1 failed event; got: {captured}"
    fallback_reasons = {ev.get("fallback") for ev in pass1_failed_events}
    assert "pass2_function_tools_low_confidence" in fallback_reasons, (
        f"Expected low_confidence fallback marker; got: {fallback_reasons}"
    )
