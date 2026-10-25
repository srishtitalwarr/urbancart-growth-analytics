"""Part 1 Q6: re-derive key numbers independently (pandas on the raw CSVs, no SQL)
and reconcile them with the warehouse marts."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config


def pandas_channel_kpis(data_dir: Path = config.DATA_DIR) -> pd.DataFrame:
    """Recompute spend, new customers, CAC, revenue per customer, repeat rate and LTV:CAC from scratch."""
    users = pd.read_csv(data_dir / "users.csv")
    orders = pd.read_csv(data_dir / "orders.csv").drop_duplicates()
    spend = pd.read_csv(data_dir / "marketing_spend.csv")

    users = users[~users["email"].str.lower().str.endswith(config.TEST_EMAIL_DOMAIN)]
    users["acquisition_channel"] = users["acquisition_channel"].fillna(config.UNKNOWN_CHANNEL)
    delivered = orders[orders["status"] == "delivered"].merge(users, on="user_id")

    per_customer = delivered.groupby(["acquisition_channel", "user_id"]).agg(
        n=("order_id", "size"), revenue=("order_value", "sum")).reset_index()
    kpis = per_customer.groupby("acquisition_channel").agg(
        new_customers=("user_id", "nunique"),
        revenue=("revenue", "sum"),
        repeat_customers=("n", lambda s: int((s >= 2).sum())),
    )
    kpis["spend"] = spend.groupby("channel")["spend_inr"].sum()
    kpis["cac"] = kpis["spend"] / kpis["new_customers"]
    kpis["revenue_per_customer"] = kpis["revenue"] / kpis["new_customers"]
    kpis["repeat_rate_pct"] = 100 * kpis["repeat_customers"] / kpis["new_customers"]
    kpis["ltv_cac"] = config.CONTRIBUTION_MARGIN * kpis["revenue_per_customer"] / kpis["cac"]
    return kpis.rename_axis("channel").reset_index()


def reconcile(con: duckdb.DuckDBPyConnection, data_dir: Path = config.DATA_DIR) -> pd.DataFrame:
    """Side-by-side check of SQL vs pandas, plus control totals. Every row should say OK."""
    sql = con.execute("SELECT * FROM mart_channel_kpis").df().set_index("channel")
    pdk = pandas_channel_kpis(data_dir).set_index("channel")
    rows = []

    def add(check: str, sql_value: float, independent: float, tol: float = 1e-6) -> None:
        ok = abs(float(sql_value) - float(independent)) <= tol
        rows.append({"check": check, "warehouse_sql": float(sql_value),
                     "independent": float(independent), "result": "OK" if ok else "MISMATCH"})

    g = "Google Ads"
    add("Google Ads spend (SQL vs pandas)", sql.at[g, "spend"], pdk.at[g, "spend"])
    add("Google Ads new customers (SQL vs pandas)", sql.at[g, "new_customers"], pdk.at[g, "new_customers"])
    add("Google Ads CAC (SQL vs pandas)", sql.at[g, "cac"], pdk.at[g, "cac"])
    for ch in config.PAID_CHANNELS:
        add(f"{ch} LTV:CAC (SQL vs pandas)", sql.at[ch, "ltv_cac"], pdk.at[ch, "ltv_cac"])

    raw_spend = pd.read_csv(data_dir / "marketing_spend.csv")["spend_inr"].sum()
    add("Total paid spend vs raw file", sql["spend"].sum(), raw_spend)

    buyers = con.execute(
        "SELECT count(DISTINCT user_id) FROM orders_clean WHERE status = 'delivered'").fetchone()[0]
    add("Sum of channel customers = distinct delivered buyers", sql["new_customers"].sum(), buyers)

    monthly = con.execute("SELECT sum(new_customers) FROM mart_channel_monthly").fetchone()[0]
    paid_total = sql.loc[config.PAID_CHANNELS, "new_customers"].sum()
    add("Monthly new customers sum to period total (paid)", monthly, paid_total)

    rev = con.execute("SELECT sum(order_value) FROM orders_clean WHERE status = 'delivered'").fetchone()[0]
    add("Sum of channel revenue = delivered revenue", sql["revenue"].sum(), rev, tol=0.01)
    return pd.DataFrame(rows)
