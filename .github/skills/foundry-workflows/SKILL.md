---
name: foundry-workflows
description: >-
  Foundry Agent Service Workflows の設計・実装パターン。
  Sequential Workflow、Human-in-the-Loop 承認フロー、Question ノード、
  Conversations API との接続、YAML 構成の書き方を提供する。
  Triggers: "Workflows", "ワークフロー", "Sequential", "Human-in-the-Loop",
  "承認フロー", "Question ノード", "Conversations API", "オーケストレーション"
---

# Foundry Agent Service Workflows パターン

## オーケストレーション方針（本プロジェクト）

本プロジェクトは **Foundry Conversations API（Workflows）を使わず、FastAPI 直接オーケストレーション**を採用している。
理由: Foundry Workflows の Question ノードが細粒度な承認 token セキュリティ（per-conversation bearer）に対応しないため。

実装エントリポイント: `src/api/chat.py` → `workflow_event_generator()` / `approve()`

## Workflow 構成（本プロジェクト、7 エージェント + 承認）

```yaml
# 参考: Foundry Workflows YAML (実際の実装は FastAPI 直接オーケストレーション)
workflow:
  type: sequential
  participants:
    - agent: data-search-agent         # Agent1: Fabric Lakehouse + Code Interpreter
    - agent: marketing-plan-agent      # Agent2: 施策生成 + Web Search
    - type: question                   # 承認ステップ（approval_token で保護）
      prompt: |
        企画書の内容を確認してください。
        「承認」→ 規制チェックに進みます
        「修正」→ 修正指示を入力してください
      options:
        - label: 承認
          next: regulation-check-agent
        - label: 修正
          next: marketing-plan-agent   # ループバック
    - agent: regulation-check-agent    # Agent3a: 規制チェック
    - agent: plan-revision-agent       # Agent3b: 企画書修正（Agent3a チェック結果を反映）
    - agent: brochure-gen-agent        # Agent4: 販促物生成（GPT Image 2 既定）
    - agent: video-gen-agent           # Agent5: 動画生成（Photo Avatar）
    # Agent6 (quality-review-agent) はバックグラウンド実行（オプショナル）
```

## FastAPI 直接オーケストレーションパターン

FastAPI バックエンドで各エージェントを順次実行し、SSE でフロントエンドにストリーミングする。

```python
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
import secrets

client = FoundryChatClient(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_NAME"],
    credential=DefaultAzureCredential(),
)

async def workflow_event_generator(user_input: str, conversation_id: str):
    """各エージェントを直接オーケストレーションし、SSE イベントを生成する"""
    # Agent1: データ検索
    yield format_sse("agent_progress", {"agent": "data-search-agent", "status": "start"})
    data_result = await data_search_agent.run(user_input)

    # Agent2: 施策生成
    yield format_sse("agent_progress", {"agent": "marketing-plan-agent", "status": "start"})
    plan_result = await marketing_plan_agent.run(data_result)

    # 承認ステップ: approval_token を発行して SSE で配布
    approval_token = secrets.token_urlsafe(32)
    _pending_approvals[f"{owner_id}:{conversation_id}"] = approval_token
    yield format_sse("approval_request", {
        "prompt": "企画書を確認してください。承認 or 修正指示を入力してください。",
        "conversation_id": conversation_id,
        "approval_token": approval_token,   # frontend が /approve POST に echo する
    })
    return  # approve() が呼ばれるまで中断

async def approve(conversation_id: str, decision: str, approval_token: str):
    """承認/修正レスポンスを受け取り後続エージェントを実行する"""
    # approval_token を hmac.compare_digest で検証（定数時間比較）
    ...
    # Agent3a: 規制チェック
    check_result = await regulation_check_agent.run(plan_result)
    # Agent3b: 企画書修正
    revised_plan = await plan_revision_agent.run(plan_result, check_result)
    # Agent4: 販促物生成
    brochure = await brochure_gen_agent.run(revised_plan)
    # Agent5: 動画生成
    video = await video_gen_agent.run(revised_plan)
```

## 承認エンドポイント

```python
@app.post("/api/chat/{conversation_id}/approve")
async def approve_endpoint(conversation_id: str, request: Request):
    """承認/修正レスポンスを受け取る。approval_token で保護。"""
    body = await request.json()
    # approval_token を検証 (hmac.compare_digest)
    token = body.get("approval_token", "")
    stored = _pending_approvals.get(f"{owner_id}:{conversation_id}", "")
    if not hmac.compare_digest(token, stored):
        raise HTTPException(status_code=403, detail="APPROVAL_CONTEXT_NOT_FOUND")

    return StreamingResponse(
        continue_workflow(conversation_id, body["decision"]),
        media_type="text/event-stream",
    )
```

## 制約・注意事項（2026-05 時点）

- Foundry Workflows の Question ノードは **Preview**。細粒度な承認 token セキュリティは未対応
- **本プロジェクトは FastAPI 直接オーケストレーションを採用**（HITL は FastAPI 側で実装）
- `SequentialBuilder` は HITL 中断をサポートしない。承認フローには `approve()` エンドポイントを使う
- approval_token は per-conversation 32-byte urlsafe bearer。`_refine_events()` で修正版ごとに rotate する
- Live URL: `https://ca-wmbvhdhcsuyb2-pn.wonderfultree-f9803f6f.eastus2.azurecontainerapps.io/`

## 参照

- Workflows 概要: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/workflow
- Workflows ブログ: https://devblogs.microsoft.com/foundry/introducing-multi-agent-workflows-in-foundry-agent-service/
