"""Azure Functions MCP サーバー — 旅行マーケティング AI パイプラインのカスタムツール群

Foundry Agent Service の Remote MCP ツールとして登録する。
Flex Consumption プラン + Python 3.13 で実行。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.request

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger(__name__)

# --- ブランドカラー定数（regulations/brand_guidelines.md 準拠） ---
_BRAND_PRIMARY = "#0066CC"
_BRAND_SECONDARY = "#00A86B"
_BRAND_ACCENT = "#FF6B35"
_BRAND_TEXT = "#333333"
_BRAND_BG = "#FFFFFF"
_BRAND_BG_ALT = "#F5F5F5"

# --- テンプレートプリセット ---
_TEMPLATE_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "header_bg": f"linear-gradient(135deg, {_BRAND_PRIMARY}, {_BRAND_SECONDARY})",
        "accent": _BRAND_ACCENT,
        "body_bg": _BRAND_BG,
        "card_bg": _BRAND_BG_ALT,
    },
    "luxury": {
        "header_bg": f"linear-gradient(135deg, #1a1a2e, {_BRAND_PRIMARY})",
        "accent": "#D4AF37",
        "body_bg": "#fafafa",
        "card_bg": "#ffffff",
    },
    "nature": {
        "header_bg": f"linear-gradient(135deg, {_BRAND_SECONDARY}, #2d6a4f)",
        "accent": _BRAND_ACCENT,
        "body_bg": "#f0f7f0",
        "card_bg": "#ffffff",
    },
    "adventure": {
        "header_bg": f"linear-gradient(135deg, {_BRAND_ACCENT}, #e63946)",
        "accent": _BRAND_PRIMARY,
        "body_bg": "#fff8f0",
        "card_bg": "#ffffff",
    },
}


def _build_brand_css(preset: dict[str, str]) -> str:
    """ブランドガイドラインに基づく CSS を生成する"""
    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Noto+Sans+JP:wght@400;700&display=swap');
  :root {{
    --brand-primary: {_BRAND_PRIMARY};
    --brand-secondary: {_BRAND_SECONDARY};
    --brand-accent: {preset['accent']};
    --brand-text: {_BRAND_TEXT};
    --brand-bg: {preset['body_bg']};
    --brand-bg-alt: {preset['card_bg']};
  }}
  body {{
    font-family: 'Noto Sans JP', 'Inter', sans-serif;
    color: var(--brand-text);
    background: var(--brand-bg);
    margin: 0;
    padding: 0;
    line-height: 1.8;
  }}
  h1, h2, h3, h4, h5, h6 {{
    font-family: 'Noto Sans JP', sans-serif;
    font-weight: 700;
  }}
  .brand-header {{
    background: {preset['header_bg']};
    color: #ffffff;
    padding: 2rem;
    text-align: center;
  }}
  .brand-footer {{
    background: {_BRAND_TEXT};
    color: #cccccc;
    padding: 1.5rem 2rem;
    font-size: 0.8rem;
    text-align: center;
    line-height: 1.6;
  }}
  .brand-card {{
    background: var(--brand-bg-alt);
    border-radius: 8px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
  }}
  .brand-accent {{
    color: var(--brand-accent);
  }}
  a {{
    color: var(--brand-primary);
  }}
  img {{
    max-width: 100%%;
    height: auto;
    border-radius: 8px;
  }}
</style>
"""


@app.route(route="generate_brochure_pdf", methods=["POST"])
async def generate_brochure_pdf(req: func.HttpRequest) -> func.HttpResponse:
    """HTML ブローシャを PDF に変換する（MCP ツール）"""
    try:
        body = req.get_json()
        html_content: str = body.get("html", "")
        if not html_content:
            return func.HttpResponse(
                json.dumps({"error": "html フィールドが必要です"}),
                status_code=400,
                mimetype="application/json",
            )

        logger.info("ブローシャ PDF 生成リクエスト: %d 文字", len(html_content))

        # weasyprint が利用可能なら PDF を生成する
        try:
            import weasyprint  # noqa: F811

            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": "PDF 生成完了",
                    "size_bytes": len(pdf_bytes),
                    "pdf_base64": pdf_b64,
                }),
                mimetype="application/json",
            )
        except ImportError:
            logger.warning("weasyprint が未インストール。HTML をそのまま返します")
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": "PDF 変換には weasyprint が必要です。HTML をそのまま返します",
                    "size_bytes": len(html_content),
                    "html": html_content,
                }),
                mimetype="application/json",
            )
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "無効な JSON リクエスト"}),
            status_code=400,
            mimetype="application/json",
        )


@app.route(route="apply_brand_template", methods=["POST"])
async def apply_brand_template(req: func.HttpRequest) -> func.HttpResponse:
    """社内ブランドテンプレートを適用する（MCP ツール）

    regulations/brand_guidelines.md に基づくブランド CSS を注入する。
    template_name で異なるスタイルプリセットを選択可能。
    """
    try:
        body = req.get_json()
        html_content: str = body.get("html", "")
        template_name: str = body.get("template", "default")

        preset = _TEMPLATE_PRESETS.get(template_name, _TEMPLATE_PRESETS["default"])
        brand_css = _build_brand_css(preset)

        # <head> が存在すれば CSS を挿入、なければ先頭に追加
        if "<head>" in html_content:
            branded_html = html_content.replace("<head>", f"<head>{brand_css}")
        else:
            branded_html = f"{brand_css}\n{html_content}"

        logger.info(
            "ブランドテンプレート適用: template=%s, 入力 %d 文字 → 出力 %d 文字",
            template_name, len(html_content), len(branded_html),
        )
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "html": branded_html,
                "template": template_name,
                "available_templates": list(_TEMPLATE_PRESETS.keys()),
            }),
            mimetype="application/json",
        )
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "無効な JSON リクエスト"}),
            status_code=400,
            mimetype="application/json",
        )


@app.route(route="notify_teams", methods=["POST"])
async def notify_teams(req: func.HttpRequest) -> func.HttpResponse:
    """成果物完成時に Teams チャネルに通知を送信する（MCP ツール）

    TEAMS_WEBHOOK_URL が設定されていれば Adaptive Card を送信する。
    未設定の場合はログ出力のみでフォールバックする。
    """
    try:
        body = req.get_json()
        plan_title: str = body.get("title", "新しい企画書")
        conversation_id: str = body.get("conversation_id", "")
        summary: str = body.get("summary", "")

        webhook_url = os.environ.get("TEAMS_WEBHOOK_URL", "")

        if not webhook_url:
            logger.warning(
                "TEAMS_WEBHOOK_URL 未設定。通知をスキップします: title=%s",
                plan_title,
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": f"通知をログに記録しました: {plan_title}",
                    "note": "TEAMS_WEBHOOK_URL が未設定のため、実際の Teams 送信はスキップされました",
                }),
                mimetype="application/json",
            )

        # Adaptive Card ペイロードを組み立てる
        adaptive_card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Large",
                            "weight": "Bolder",
                            "text": f"📋 {plan_title}",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": summary or "新しい企画書が生成されました。",
                            "wrap": True,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "会話 ID", "value": conversation_id or "N/A"},
                                {"title": "ステータス", "value": "✅ 生成完了"},
                            ],
                        },
                    ],
                },
            }],
        }

        payload = json.dumps(adaptive_card).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                resp_status = resp.status
            logger.info(
                "Teams 通知送信完了: title=%s, status=%d", plan_title, resp_status,
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": f"Teams に通知しました: {plan_title}",
                    "http_status": resp_status,
                }),
                mimetype="application/json",
            )
        except urllib.error.URLError as exc:
            logger.exception("Teams Webhook への送信に失敗しました")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Teams 通知の送信に失敗しました: {exc}",
                }),
                status_code=502,
                mimetype="application/json",
            )
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "無効な JSON リクエスト"}),
            status_code=400,
            mimetype="application/json",
        )


@app.route(route="save_to_sharepoint", methods=["POST"])
async def save_to_sharepoint(req: func.HttpRequest) -> func.HttpResponse:
    """生成した成果物を SharePoint に保存する（MCP ツール）

    SHAREPOINT_SITE_URL が設定されていれば Microsoft Graph API で
    SharePoint ドキュメントライブラリにアップロードする。
    未設定の場合はログ出力のみでフォールバックする。
    """
    try:
        body = req.get_json()
        filename: str = body.get("filename", "output.html")
        content: str = body.get("content", "")
        folder: str = body.get("folder", "/Shared Documents/Marketing")

        site_url = os.environ.get("SHAREPOINT_SITE_URL", "")

        if not site_url:
            logger.warning(
                "SHAREPOINT_SITE_URL 未設定。保存をスキップします: filename=%s",
                filename,
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": f"保存をログに記録しました: {folder}/{filename}",
                    "path": f"{folder}/{filename}",
                    "note": "SHAREPOINT_SITE_URL が未設定のため、実際の SharePoint アップロードはスキップされました",
                }),
                mimetype="application/json",
            )

        # DefaultAzureCredential でアクセストークンを取得
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token("https://graph.microsoft.com/.default")

        # サイト ID を取得
        hostname = site_url.replace("https://", "").split("/")[0]
        site_path = "/".join(site_url.replace("https://", "").split("/")[1:])
        site_api_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"

        site_req = urllib.request.Request(
            site_api_url,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(site_req, timeout=10) as resp:
            site_data = json.loads(resp.read().decode("utf-8"))
        site_id = site_data["id"]

        # ドライブ（ドキュメントライブラリ）の取得
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drives_req = urllib.request.Request(
            drives_url,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(drives_req, timeout=10) as resp:
            drives_data = json.loads(resp.read().decode("utf-8"))

        drive_id = drives_data["value"][0]["id"]

        # ファイルアップロード（PUT で小さいファイルを直接アップロード）
        upload_path = f"{folder}/{filename}".lstrip("/")
        upload_url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
            f"/root:/{upload_path}:/content"
        )
        file_bytes = content.encode("utf-8")
        upload_req = urllib.request.Request(
            upload_url,
            data=file_bytes,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/octet-stream",
            },
            method="PUT",
        )

        try:
            with urllib.request.urlopen(upload_req, timeout=30) as resp:
                upload_result = json.loads(resp.read().decode("utf-8"))
            web_url = upload_result.get("webUrl", f"{folder}/{filename}")
            logger.info(
                "SharePoint アップロード完了: %s (%d bytes)",
                web_url, len(file_bytes),
            )
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": f"SharePoint に保存しました: {web_url}",
                    "path": web_url,
                    "size_bytes": len(file_bytes),
                }),
                mimetype="application/json",
            )
        except urllib.error.URLError as exc:
            logger.exception("SharePoint へのアップロードに失敗しました")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"SharePoint アップロードに失敗: {exc}",
                }),
                status_code=502,
                mimetype="application/json",
            )
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "無効な JSON リクエスト"}),
            status_code=400,
            mimetype="application/json",
        )
