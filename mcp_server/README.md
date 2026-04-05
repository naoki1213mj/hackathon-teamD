# Improvement Brief MCP Server

Azure Functions MCP extension を使って `generate_improvement_brief` ツールを公開する最小構成です。

## 前提

- Python 3.14 以上
- [uv](https://docs.astral.sh/uv/)
- Azure Functions Core Tools v4
- Azure Functions Flex Consumption でのデプロイ権限

## ローカル起動

```powershell
cd mcp_server
uv venv
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
func start
```

MCP endpoint は `http://localhost:7071/runtime/webhooks/mcp` です。

## Azure への出し方

1. `mcp_server/` を Azure Functions Flex Consumption にデプロイする
2. Functions の system key `mcp_extension` を取得する
3. APIM の `Expose an existing MCP server` で backend に `https://<funcapp>.azurewebsites.net/runtime/webhooks/mcp` を登録する
4. backend へ `x-functions-key: <mcp_extension system key>` を転送する
5. FastAPI 側の `IMPROVEMENT_MCP_ENDPOINT` を `https://<apim>.azure-api.net/improvement-mcp/runtime/webhooks/mcp` に合わせる

## APIM 登録

1. Function App を Azure に配置する
2. APIM の `Expose an existing MCP server` で `https://<funcapp>.azurewebsites.net/runtime/webhooks/mcp` を登録する
3. FastAPI 側には APIM 公開 endpoint `https://<apim>.azure-api.net/<base-path>/runtime/webhooks/mcp` を `IMPROVEMENT_MCP_ENDPOINT` として設定する
4. APIM が `subscriptionRequired=false` なら `IMPROVEMENT_MCP_API_KEY` は不要。必須にする場合だけ `IMPROVEMENT_MCP_API_KEY` と `IMPROVEMENT_MCP_API_KEY_HEADER` を設定する

## 互換性メモ

- APIM の公開 path は `/mcp` ではなく `/runtime/webhooks/mcp` になる
- クライアントは `Accept: application/json, text/event-stream` を送る
- Azure Functions MCP extension では JSON-RPC request id を数値文字列にすると安定する
- `tools/call` の `content[].text` は JSON だけでなく Python リテラル文字列として返る場合がある
