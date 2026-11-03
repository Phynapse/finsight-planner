from app.analytics.variance_analyzer import VarianceAnalyzer


def test_variance_analyzer_revenue_favourable():
    analyzer = VarianceAnalyzer()
    result = analyzer.analyze_variance(950000, 900000, "revenue")
    assert result["absolute_variance"] == 50000
    assert result["favourable_unfavourable"] == "favourable"


def test_variance_analyzer_expense_unfavourable():
    analyzer = VarianceAnalyzer()
    result = analyzer.analyze_variance(125000, 120000, "compensation_expense")
    assert result["absolute_variance"] == 5000
    assert result["favourable_unfavourable"] == "unfavourable"


def test_variance_analyzer_expense_favourable():
    analyzer = VarianceAnalyzer()
    result = analyzer.analyze_variance(120000, 125000, "compensation_expense")
    assert result["absolute_variance"] == -5000
    assert result["favourable_unfavourable"] == "favourable"


def test_variance_analyzer_zero_budget():
    analyzer = VarianceAnalyzer()
    result = analyzer.analyze_variance(50000, 0, "marketing_expense")
    assert result["percentage_variance"] is None
    assert len(result["caveats"]) > 0
