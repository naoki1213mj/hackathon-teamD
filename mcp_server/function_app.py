"""Azure Functions MCP server entrypoint for improvement briefs."""

import logging
from typing import Any

import azure.functions as func

try:
    from .improvement_brief import generate_improvement_brief_result
except ImportError:
    from improvement_brief import generate_improvement_brief_result

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="plan_markdown", description="改善対象の企画書 Markdown 全文")
@app.mcp_tool_property(arg_name="evaluation_payload", description="品質評価結果を表す JSON 文字列")
@app.mcp_tool_property(arg_name="regulation_summary", description="規制チェック結果の要約テキスト")
@app.mcp_tool_property(arg_name="rejection_history", description="差し戻し履歴を表す JSON 配列文字列")
@app.mcp_tool_property(arg_name="user_feedback", description="直近の改善依頼テキスト")
def generate_improvement_brief(
    plan_markdown: str,
    evaluation_payload: str = "",
    regulation_summary: str = "",
    rejection_history: str = "",
    user_feedback: str = "",
) -> dict[str, Any]:
    """品質評価から改善ブリーフを返す。"""
    logging.info("generate_improvement_brief called")
    return generate_improvement_brief_result(
        plan_markdown=plan_markdown,
        evaluation_payload=evaluation_payload,
        regulation_summary=regulation_summary,
        rejection_history=rejection_history,
        user_feedback=user_feedback,
    )
