"""Answers to Part 1 Q2 to Q5, read from the marts and rounded for presentation.

Rounding rules from the brief: money to the nearest rupee, percentages to 1 dp.
Ratios (LTV:CAC) are shown to 2 dp.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from . import config

PAID = "('" + "','".join(config.PAID_CHANNELS) + "')"
ORDER = "CASE channel " + " ".join(
    f"WHEN '{c}' THEN {i}" for i, c in enumerate(config.ALL_CHANNELS + [config.UNKNOWN_CHANNEL])
) + " END"


def _money(s: pd.Series) -> pd.Series:
    return s.astype(float).round(0).astype("Int64")


def acquisition_cost(con: duckdb.DuckDBPyConnection, suffix: str = "") -> pd.DataFrame:
    """Q2: spend, new customers and CAC per paid channel, plus a total row."""
    df = con.execute(f"""
        SELECT channel, spend::DOUBLE AS spend, new_customers, cac::DOUBLE AS cac
        FROM mart_channel_kpis{suffix} WHERE channel IN {PAID} ORDER BY {ORDER}
    """).df()
    total = pd.DataFrame([{
        "channel": "Total paid",
        "spend": df["spend"].sum(),
        "new_customers": df["new_customers"].sum(),
        "cac": df["spend"].sum() / df["new_customers"].sum(),
    }])
    df = pd.concat([df, total], ignore_index=True)
    df["spend"], df["cac"] = _money(df["spend"]), _money(df["cac"])
    return df


def customer_value(con: duckdb.DuckDBPyConnection, suffix: str = "") -> pd.DataFrame:
    """Q3: revenue per customer and repeat purchase rate for every channel, including Organic."""
    df = con.execute(f"""
        SELECT channel, new_customers AS customers, revenue::DOUBLE AS revenue,
               revenue_per_customer::DOUBLE AS revenue_per_customer,
               repeat_customers, repeat_rate_pct::DOUBLE AS repeat_rate_pct
        FROM mart_channel_kpis{suffix} ORDER BY {ORDER}
    """).df()
    df["revenue"] = _money(df["revenue"])
    df["revenue_per_customer"] = _money(df["revenue_per_customer"])
    df["repeat_rate_pct"] = df["repeat_rate_pct"].round(1)
    return df


def return_on_spend(con: duckdb.DuckDBPyConnection, suffix: str = "") -> pd.DataFrame:
    """Q4: LTV:CAC per paid channel, best first. LTV = revenue per customer x 30% margin."""
    df = con.execute(f"""
        SELECT channel, revenue_per_customer::DOUBLE AS revenue_per_customer,
               ltv::DOUBLE AS ltv, cac::DOUBLE AS cac, ltv_cac::DOUBLE AS ltv_cac
        FROM mart_channel_kpis{suffix} WHERE channel IN {PAID} ORDER BY ltv_cac DESC
    """).df()
    for col in ("revenue_per_customer", "ltv", "cac"):
        df[col] = _money(df[col])
    df["ltv_cac"] = df["ltv_cac"].round(2)
    df["rank"] = range(1, len(df) + 1)
    return df


def monthly_cac_long(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"""
        SELECT month, channel, spend::DOUBLE AS spend, new_customers, cac::DOUBLE AS cac
        FROM mart_channel_monthly ORDER BY {ORDER}, month
    """).df()


def monthly_cac(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Q5: CAC by signup month (rows are channels, columns are months)."""
    df = monthly_cac_long(con)
    wide = df.pivot(index="channel", columns="month", values="cac").reindex(config.PAID_CHANNELS)
    return wide.round(0).astype("Int64").reset_index()


def cac_trend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Q5: January vs June CAC per paid channel, most expensive-growing first."""
    df = monthly_cac_long(con)
    first, last = df["month"].min(), df["month"].max()
    jan = df[df["month"] == first].set_index("channel")
    jun = df[df["month"] == last].set_index("channel")
    out = pd.DataFrame({
        f"cac_{first}": jan["cac"],
        f"cac_{last}": jun["cac"],
        "change_inr": jun["cac"] - jan["cac"],
        "change_pct": 100 * (jun["cac"] / jan["cac"] - 1),
        f"spend_{first}": jan["spend"],
        f"spend_{last}": jun["spend"],
        f"new_customers_{first}": jan["new_customers"],
        f"new_customers_{last}": jun["new_customers"],
    }).reindex(config.PAID_CHANNELS)
    for col in out.columns:
        out[col] = out[col].round(1) if col == "change_pct" else _money(out[col])
    return out.sort_values("change_pct", ascending=False).reset_index()


def test_account_impact(con: duckdb.DuckDBPyConnection, channel: str = "Affiliate") -> pd.DataFrame:
    """How the QA accounts distort a channel's metrics (they are all tagged Affiliate)."""
    rows = []
    for label, suffix in (("Including QA accounts", "_incl_test"), ("Cleaned", "")):
        r = con.execute(f"""
            SELECT new_customers, cac::DOUBLE, revenue_per_customer::DOUBLE,
                   repeat_rate_pct::DOUBLE, ltv_cac::DOUBLE
            FROM mart_channel_kpis{suffix} WHERE channel = ?
        """, [channel]).fetchone()
        rows.append({"version": label, "new_customers": r[0], "cac": round(r[1]),
                     "revenue_per_customer": round(r[2]), "repeat_rate_pct": round(r[3], 1),
                     "ltv_cac": round(r[4], 2)})
    return pd.DataFrame(rows)


def quarterly_spend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Spend per paid channel in Q1 and Q2 2026. Q2 is the run-rate the 20% cut is sized on."""
    df = con.execute(f"""
        SELECT channel,
               sum(spend) FILTER (WHERE month <= '2026-03')::DOUBLE AS q1_spend,
               sum(spend) FILTER (WHERE month >  '2026-03')::DOUBLE AS q2_spend,
               sum(spend) FILTER (WHERE month >  '2026-03')::DOUBLE
                 / sum(new_customers) FILTER (WHERE month > '2026-03') AS q2_cac
        FROM mart_channel_monthly GROUP BY channel ORDER BY {ORDER}
    """).df()
    for col in ("q1_spend", "q2_spend", "q2_cac"):
        df[col] = _money(df[col])
    return df


def marginal_cac(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Q1 to Q2 change in spend divided by the change in new customers: what the extra rupees bought."""
    df = con.execute(f"""
        SELECT channel,
               sum(spend) FILTER (WHERE month <= '2026-03')::DOUBLE AS q1_spend,
               sum(spend) FILTER (WHERE month >  '2026-03')::DOUBLE AS q2_spend,
               sum(new_customers) FILTER (WHERE month <= '2026-03') AS q1_customers,
               sum(new_customers) FILTER (WHERE month >  '2026-03') AS q2_customers
        FROM mart_channel_monthly GROUP BY channel ORDER BY {ORDER}
    """).df()
    df["extra_spend"] = df["q2_spend"] - df["q1_spend"]
    df["extra_customers"] = df["q2_customers"] - df["q1_customers"]
    # Only meaningful when spend went up materially and customers did too.
    valid = (df["extra_spend"] > 0) & (df["extra_customers"] > 0)
    df["marginal_cac"] = (df["extra_spend"] / df["extra_customers"]).where(valid)
    for col in ("q1_spend", "q2_spend", "extra_spend", "marginal_cac"):
        df[col] = _money(df[col])
    return df


def cut_scenario(con: duckdb.DuckDBPyConnection, cuts_inr: dict[str, float]) -> pd.DataFrame:
    """Apply rupee cuts to the Q2 quarterly run-rate and estimate new customers forgone.

    Customers forgone = rupees cut / Q2 average CAC. This is a pessimistic upper
    bound: the last rupee usually buys fewer customers than the average one, so
    the real loss from cutting the least efficient spend is probably smaller.
    """
    q = quarterly_spend(con).set_index("channel")
    out = pd.DataFrame({"q2_spend": q["q2_spend"].astype(float)})
    out["cut_inr"] = pd.Series(cuts_inr, dtype=float).reindex(q.index).fillna(0)
    out["cut_pct"] = 100 * out["cut_inr"] / out["q2_spend"]
    out["next_q_spend"] = out["q2_spend"] - out["cut_inr"]
    out["customers_forgone_est"] = out["cut_inr"] / q["q2_cac"].astype(float)
    total = out.sum(numeric_only=True)
    total["cut_pct"] = 100 * total["cut_inr"] / total["q2_spend"]
    out.loc["Total paid"] = total
    for col in ("q2_spend", "cut_inr", "next_q_spend", "customers_forgone_est"):
        out[col] = _money(out[col])
    out["cut_pct"] = out["cut_pct"].round(1)
    return out.reset_index()


def data_as_of(con: duckdb.DuckDBPyConnection) -> str:
    return str(con.execute("SELECT data_as_of FROM meta").fetchone()[0])
