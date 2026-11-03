from app.analytics.cash_flow_analyzer import CashFlowAnalyzer


def test_cash_flow_reconciliation():
    analyzer = CashFlowAnalyzer()
    result = analyzer.analyze(5000000, 1350000, 935000, 5415000)
    assert result["ending_cash_calculated"] == 5415000
    assert result["reconciled"] is True


def test_cash_flow_no_reported():
    analyzer = CashFlowAnalyzer()
    result = analyzer.analyze(5000000, 1350000, 935000)
    assert result["reconciled"] is True
