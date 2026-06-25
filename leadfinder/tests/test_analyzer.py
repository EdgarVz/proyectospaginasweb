import pytest
from unittest.mock import AsyncMock, patch
from leadfinder.analyzer import Analyzer


@pytest.fixture
def analyzer():
    return Analyzer()


@pytest.mark.asyncio
async def test_analyze_returns_metrics_dict(analyzer):
    lighthouse_result = {
        "performance_score": 85,
        "accessibility_score": 90,
        "seo_score": 80,
        "best_practices_score": 75,
    }
    html_result = {
        "mobile_friendly": 1,
        "has_meta_description": 1,
        "has_open_graph": 1,
        "has_ssl": 1,
        "technologies": [],
    }

    with (
        patch.object(analyzer, "_run_lighthouse", new=AsyncMock(return_value=lighthouse_result)),
        patch.object(analyzer, "_inspect_html", new=AsyncMock(return_value=html_result)),
    ):
        result = await analyzer.analyze("https://example.com")

    assert result["performance_score"] == 85
    assert result["accessibility_score"] == 90
    assert result["seo_score"] == 80
    assert result["best_practices_score"] == 75
    assert result["mobile_friendly"] == 1
    assert result["has_meta_description"] == 1
    assert result["has_open_graph"] == 1
    assert result["has_ssl"] == 1
    assert result["technologies"] == []
    assert "lead_score" in result


@pytest.mark.asyncio
async def test_analyze_includes_lead_score(analyzer):
    with (
        patch.object(analyzer, "_run_lighthouse", new=AsyncMock(return_value={"performance_score": 50, "seo_score": 50, "best_practices_score": 50})),
        patch.object(analyzer, "_inspect_html", new=AsyncMock(return_value={"mobile_friendly": 0, "has_meta_description": 0, "has_open_graph": 0, "has_ssl": 1, "technologies": []})),
    ):
        result = await analyzer.analyze("https://example.com")

    assert isinstance(result["lead_score"], float)


@pytest.mark.asyncio
async def test_lighthouse_error_propagates(analyzer):
    with (
        patch.object(analyzer, "_run_lighthouse", new=AsyncMock(side_effect=RuntimeError("Lighthouse not found. Install: npm install -g lighthouse"))),
        patch.object(analyzer, "_inspect_html", new=AsyncMock(return_value={"mobile_friendly": 0, "has_meta_description": 0, "has_open_graph": 0, "has_ssl": 0, "technologies": []})),
    ):
        with pytest.raises(RuntimeError, match="Lighthouse not found"):
            await analyzer.analyze("https://example.com")
