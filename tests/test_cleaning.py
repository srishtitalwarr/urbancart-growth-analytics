from pathlib import Path

import pandas as pd
import pytest

from urbancart import cleaning, config


def rows(dq, prefix):
    return int(dq[dq.index.str.startswith(prefix)]["rows_affected"].iloc[0])


def test_issue_counts_on_real_data(dq):
    assert rows(dq, "Exact duplicate order rows") == 206
    assert rows(dq, "Internal QA/test accounts") == 35
    assert rows(dq, "Orders placed by QA/test accounts") == 285
    assert rows(dq, "Missing acquisition_channel") == 72
    assert rows(dq, "Cancelled or returned orders") == 679
    assert (dq[dq["status"] == "FOUND"].shape[0]) == 5


def test_clean_tables(con):
    assert con.execute("SELECT count(*) FROM stg_orders").fetchone()[0] == 5684
    assert con.execute("SELECT count(*) FROM orders_incl_test").fetchone()[0] == 5478
    assert con.execute("SELECT count(*) - count(DISTINCT order_id) FROM orders_clean").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM users_clean").fetchone()[0] == 5135 - 35
    assert con.execute(
        f"SELECT count(*) FROM users_clean WHERE email LIKE '%{config.TEST_EMAIL_DOMAIN}'").fetchone()[0] == 0
    assert con.execute(
        "SELECT count(*) FROM users_clean WHERE acquisition_channel = 'Unknown'").fetchone()[0] == 72


def _write(dir_: Path, users, orders, spend):
    pd.DataFrame(users, columns=["user_id", "signup_date", "city", "acquisition_channel", "email"]) \
        .to_csv(dir_ / "users.csv", index=False)
    pd.DataFrame(orders, columns=["order_id", "user_id", "order_date", "order_value", "status"]) \
        .to_csv(dir_ / "orders.csv", index=False)
    pd.DataFrame(spend, columns=["month", "channel", "spend_inr"]).to_csv(dir_ / "marketing_spend.csv", index=False)


def _full_spend(amount=1000):
    return [(f"2026-0{m}", ch, amount) for ch in config.PAID_CHANNELS for m in range(1, 7)]


def test_dirty_synthetic_data_is_handled(tmp_path):
    users = [
        (1, "2026-01-05", "Pune", " Meta Ads ", "a@gmail.com"),       # padded channel
        (2, "2026-01-06", "Pune", "", "b@gmail.com"),                  # blank channel
        (3, "2026-01-07", "Pune", "Affiliate", "QA.Test1@UrbanCart.in"),  # test account, mixed case
    ]
    orders = [
        (10, 1, "2026-01-10", 500, "delivered"),
        (10, 1, "2026-01-10", 500, "delivered"),     # exact duplicate
        (11, 1, "2026-02-10", 700, " Delivered "),   # messy status
        (12, 2, "2026-01-11", 300, "returned"),
        (13, 3, "2026-01-12", 9000, "delivered"),    # test account order
        (14, 99, "2026-01-12", 100, "delivered"),    # orphan
        (15, 1, "2026-01-13", -5, "delivered"),      # negative value
    ]
    _write(tmp_path, users, orders, _full_spend())
    con, dq = cleaning.build_warehouse(data_dir=tmp_path)
    dq = dq.set_index("issue")
    assert rows(dq, "Exact duplicate") == 1
    assert rows(dq, "Internal QA") == 1
    assert rows(dq, "Orders whose user_id is not in users") == 1
    assert rows(dq, "Zero, negative") == 1

    kpis = con.execute("SELECT * FROM mart_channel_kpis").df().set_index("channel")
    assert kpis.at["Meta Ads", "new_customers"] == 1
    assert kpis.at["Meta Ads", "revenue"] == 1200          # 500 + 700; dup, negative and orphan excluded
    assert kpis.at["Meta Ads", "repeat_customers"] == 1
    assert "Unknown" not in kpis.index                      # user 2 only returned an order
    assert kpis.at["Affiliate", "new_customers"] == 0       # test account removed
    con.close()


def test_missing_spend_cell_blocks_the_build(tmp_path):
    users = [(1, "2026-01-05", "Pune", "Meta Ads", "a@gmail.com")]
    orders = [(10, 1, "2026-01-10", 500, "delivered")]
    _write(tmp_path, users, orders, _full_spend()[:-1])
    with pytest.raises(ValueError, match="Blocking"):
        cleaning.build_warehouse(data_dir=tmp_path)
