from app.routers.analytics import build_monthly_trend_summary


def test_build_monthly_trend_summary_orders_latest_first():
    raw_rows = [
        ("2026-07", 5, 3, 1),
        ("2026-08", 8, 6, 2),
        ("2026-09", 10, 4, 3),
    ]

    summary = build_monthly_trend_summary(raw_rows)

    assert summary[0]["month"] == "2026-09"
    assert summary[0]["lost_reports"] == 10
    assert summary[0]["found_reports"] == 4
    assert summary[0]["approved_claims"] == 3

    assert summary[-1]["month"] == "2026-07"
