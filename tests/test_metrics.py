import pytest

from urbancart import config, metrics, sanity


def test_spend_totals(con):
    q2 = metrics.acquisition_cost(con).set_index("channel")
    assert q2.at["Total paid", "spend"] == 1_590_000
    assert q2.loc[config.PAID_CHANNELS, "spend"].tolist() == [400_000, 547_000, 346_000, 297_000]


def test_matches_independent_pandas(con):
    sql = con.execute("SELECT * FROM mart_channel_kpis").df().set_index("channel")
    pdk = sanity.pandas_channel_kpis().set_index("channel")
    for ch in config.ALL_CHANNELS:
        for col in ("new_customers", "revenue_per_customer", "repeat_rate_pct"):
            assert sql.at[ch, col] == pytest.approx(pdk.at[ch, col]), (ch, col)
    for ch in config.PAID_CHANNELS:
        assert sql.at[ch, "cac"] == pytest.approx(pdk.at[ch, "cac"])
        assert sql.at[ch, "ltv_cac"] == pytest.approx(pdk.at[ch, "ltv_cac"])


def test_reconciliation_all_ok(con):
    assert (sanity.reconcile(con)["result"] == "OK").all()


def test_headline_numbers(con):
    q2 = metrics.acquisition_cost(con).set_index("channel")
    assert q2.loc[config.PAID_CHANNELS, "cac"].tolist() == [611, 810, 685, 967]
    q4 = metrics.return_on_spend(con)
    assert q4["channel"].tolist() == ["Google Ads", "Influencer", "Meta Ads", "Affiliate"]
    assert q4["ltv_cac"].tolist() == [1.14, 0.89, 0.62, 0.42]
    trend = metrics.cac_trend(con).iloc[0]
    assert trend["channel"] == "Meta Ads" and trend["change_pct"] == 127.2


def test_rounding_rules(con):
    q3 = metrics.customer_value(con)
    assert str(q3["revenue_per_customer"].dtype) == "Int64"       # whole rupees
    assert (q3["repeat_rate_pct"] == q3["repeat_rate_pct"].round(1)).all()


def test_monthly_customers_add_up(con):
    monthly = metrics.monthly_cac_long(con).groupby("channel")["new_customers"].sum()
    q2 = metrics.acquisition_cost(con).set_index("channel")
    for ch in config.PAID_CHANNELS:
        assert monthly[ch] == q2.at[ch, "new_customers"]


def test_qa_accounts_inflate_affiliate(con):
    impact = metrics.test_account_impact(con).set_index("version")
    assert impact.at["Including QA accounts", "ltv_cac"] > 2 * impact.at["Cleaned", "ltv_cac"]


def test_recommended_cut_is_twenty_percent(con):
    s = metrics.cut_scenario(con, config.RECOMMENDED_CUTS_INR).set_index("channel")
    assert s.at["Total paid", "cut_pct"] == pytest.approx(20.0, abs=0.1)
    assert s.at["Google Ads", "cut_inr"] == 0
