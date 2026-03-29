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
