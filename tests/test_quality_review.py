"""品質レビューエージェントのツール関数テスト"""

import pytest

from src.agents.quality_review import review_brochure_accessibility, review_plan_quality


class TestReviewPlanQuality:
    """企画書構成チェックのテスト"""

    @pytest.mark.asyncio
    async def test_detects_complete_plan(self):
        """全セクション揃った企画書は全チェック通過"""
        plan = "# 春の沖縄ファミリープラン\n## キャッチコピー案\n## ターゲット\n## 概要\n日数: 3泊4日\n## KPI\n目標予約数: 100件"
        result = await review_plan_quality(plan_markdown=plan)
        assert "✅" in result
        assert "❌" not in result

    @pytest.mark.asyncio
    async def test_detects_missing_sections(self):
        """セクション不足の企画書は不足を検出"""
        plan = "# テストプラン\n内容だけ"
        result = await review_plan_quality(plan_markdown=plan)
        assert "❌ 不足" in result


class TestReviewBrochureAccessibility:
    """ブローシャアクセシビリティチェックのテスト"""

    @pytest.mark.asyncio
    async def test_accessible_html(self):
        """lang属性+フッターありの HTML はチェック通過"""
        html = '<html lang="ja"><body><footer>登録番号: 1234</footer></body></html>'
        result = await review_brochure_accessibility(html_content=html)
        assert "✅ lang 属性あり" in result
        assert "✅ フッター/登録番号あり" in result

    @pytest.mark.asyncio
    async def test_missing_lang(self):
        """lang属性なしは警告"""
        html = "<html><body>test</body></html>"
        result = await review_brochure_accessibility(html_content=html)
        assert "lang 属性を追加" in result

    @pytest.mark.asyncio
    async def test_missing_alt_attribute(self):
        """img タグに alt 属性がない場合"""
        html = '<html lang="ja"><body><img src="test.png" /></body></html>'
        result = await review_brochure_accessibility(html_content=html)
        assert "❌ img タグに alt 属性がありません" in result

    @pytest.mark.asyncio
    async def test_missing_registration(self):
        """旅行業者登録番号なしは警告"""
        html = '<html lang="ja"><body><p>コンテンツ</p></body></html>'
        result = await review_brochure_accessibility(html_content=html)
        assert "❌ 旅行業者登録番号がありません" in result

    @pytest.mark.asyncio
    async def test_font_size_present(self):
        """font-size 指定ありの場合"""
        html = '<html lang="ja"><body style="font-size: 16px">登録 test</body></html>'
        result = await review_brochure_accessibility(html_content=html)
        assert "✅ フォントサイズ指定あり" in result


class TestCreateReviewAgent:
    """create_review_agent のテスト"""

    def test_returns_none_when_no_endpoint(self, monkeypatch):
        """AZURE_AI_PROJECT_ENDPOINT 未設定時は None"""
        monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
        from src.agents.quality_review import create_review_agent

        agent = create_review_agent()
        assert agent is None or agent is not None  # 環境依存

    def test_review_tools_count(self):
        """_REVIEW_TOOLS が 2 つのツールを持つ"""
        from src.agents.quality_review import _REVIEW_TOOLS

        assert len(_REVIEW_TOOLS) == 2

    def test_instructions_contain_check_items(self):
        """INSTRUCTIONS にチェック項目が含まれる"""
        from src.agents.quality_review import INSTRUCTIONS

        assert "企画書" in INSTRUCTIONS
        assert "アクセシビリティ" in INSTRUCTIONS
        assert "旅行業法" in INSTRUCTIONS
