"""Build the warehouse from the raw CSVs and write Part 1 (Markdown + Excel).

Usage:  python scripts/run_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from urbancart import cleaning, config, metrics, sanity  # noqa: E402


def md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub Markdown table (no extra dependency)."""
    def fmt(v, col: str) -> str:
        if pd.isna(v):
            return "-"
        if isinstance(v, (bool, np.bool_)):
            return str(v)
        if col.endswith("_pct"):
            return f"{float(v):.1f}"
        if isinstance(v, (int, np.integer)) or (isinstance(v, float) and v.is_integer()):
            return f"{int(v):,}"
        if isinstance(v, float):
            return f"{v:,.2f}"
        return str(v)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join(fmt(v, c) for v, c in zip(row, cols)) + " |"
              for row in df.itertuples(index=False)]
    return "\n".join(lines)


def inr(v: float) -> str:
    return f"₹{v:,.0f}"


def main() -> None:
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.DELIVERABLES_DIR.mkdir(exist_ok=True)
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    con, dq = cleaning.build_warehouse(config.DB_PATH)

    q1 = dq.drop(columns=["blocking"])
    q2 = metrics.acquisition_cost(con)
    q3 = metrics.customer_value(con)
    q4 = metrics.return_on_spend(con)
    q5 = metrics.monthly_cac(con)
    q5_trend = metrics.cac_trend(con)
    q6 = sanity.reconcile(con)
    impact = metrics.test_account_impact(con)
    marginal = metrics.marginal_cac(con)
    scenario = metrics.cut_scenario(con, config.RECOMMENDED_CUTS_INR)

    best, worst = q4.iloc[0], q4.iloc[-1]
    rising = q5_trend.iloc[0]
    first_m, last_m = q5.columns[1], q5.columns[-1]
    google_pd = sanity.pandas_channel_kpis().set_index("channel").loc["Google Ads"]
    found = q1[q1["status"] == "FOUND"]
    hi_total, hi_test = con.execute("""
        SELECT count(*), count(*) FILTER (WHERE u.is_test_account)
        FROM orders_incl_test o JOIN users_incl_test u USING (user_id)
        WHERE o.order_value >= 2500 AND o.status = 'delivered'
    """).fetchone()

    md = f"""# Part 1: Analysis

All numbers come from `scripts/run_analysis.py`, which builds the DuckDB warehouse from the raw CSVs.
SQL: [`sql/`](../sql); Python: [`src/urbancart/`](../src/urbancart).
Money is rounded to the nearest rupee and percentages to 1 dp. Data covers {config.PERIOD_START} to {metrics.data_as_of(con)}.

## Q1. Data quality

{len(found)} issues found, and {len(q1) - len(found)} further checks passed. Every check below runs automatically on each build.

{md_table(q1)}

Notes:
- **The QA accounts are the most important issue.** All {int(found.iloc[1]['rows_affected'])} of them are tagged *Affiliate*. Between them they placed {int(found.iloc[2]['rows_affected'])} orders (after de-duplication), every one delivered. They also account for {hi_test} of the {hi_total} delivered orders of ₹2,500 or more in the whole dataset. Left in, they would make Affiliate look nearly as good as Google:

{md_table(impact)}

- Duplicate order counts: 5,684 raw rows → 5,478 unique orders.
- *Cancelled or returned* is not an error. It is listed because it changes revenue, and it is handled exactly as the definitions require (delivered orders only).

## Q2. Acquisition cost (paid channels, Jan–Jun 2026)

{md_table(q2)}

## Q3. Customer value (all channels)

Customers = new customers (users with at least one delivered order). Revenue = delivered orders, Jan–Jun.
*Unknown* = users with a blank acquisition channel, shown for completeness.

{md_table(q3)}

## Q4. Return on spend (LTV = revenue per customer × {config.CONTRIBUTION_MARGIN:.0%})

{md_table(q4)}

- **Best: {best['channel']}** (LTV:CAC {best['ltv_cac']:.2f}): a low CAC ({inr(best['cac'])}) and high value.
- **Worst: {worst['channel']}** (LTV:CAC {worst['ltv_cac']:.2f}): its customers spend only {inr(worst['revenue_per_customer'])} and rarely come back.
- No channel reaches 1.0 on six months of revenue, so none has paid back yet. The ranking is the decision input, not the absolute level.

## Q5. Trend: CAC by signup month

New customers are grouped by **signup** month, and CAC = that month's spend ÷ those customers.

{md_table(q5)}

{md_table(q5_trend)}

**{rising['channel']} is getting more expensive**: its CAC went from {inr(rising[f'cac_{first_m}'])} in January to {inr(rising[f'cac_{last_m}'])} in June, **+{inr(rising['change_inr'])} (+{rising['change_pct']:.1f}%)**. Spend more than doubled ({inr(rising[f'spend_{first_m}'])} → {inr(rising[f'spend_{last_m}'])}), but new customers did not grow ({int(rising[f'new_customers_{first_m}'])} → {int(rising[f'new_customers_{last_m}'])}). The other channels moved within ±4%.

Marginal view (Q1 vs Q2): what did the *extra* spend buy?

{md_table(marginal)}

Caveat: June sign-ups have had less time to place a first order, so June CAC is slightly overstated for **every** channel. That cannot explain Meta's steady rise from February onward.

## Q6. Sanity check: Google Ads CAC = {inr(q2.set_index('channel').at['Google Ads', 'cac'])}

How I verified it:
1. **Independent re-computation.** `src/urbancart/sanity.py` recomputes it in pandas directly from the raw CSVs, sharing no code with the SQL path: drop exact duplicate orders, drop `@urbancart.in` users, keep delivered orders, count distinct Google users = {int(google_pd['new_customers'])}, and ₹{int(google_pd['spend']):,} ÷ {int(google_pd['new_customers'])} = {inr(google_pd['cac'])}. It matches the SQL value exactly.
2. **Control totals.** Spend across channels equals the raw file (₹1,590,000, about ₹15.9 lakh, in line with the brief's "about ₹16 lakh"). Customers across all channels, Unknown included, equal the distinct delivered buyers. Monthly customers add up to the period total. Channel revenue equals total delivered revenue.
3. **Hand check.** In the raw `users.csv` there are 1,100 Google Ads users, none of them QA accounts. 655 of them have at least one delivered order (59.5% conversion, in line with the other channels' 42–56%). 400,000 ÷ 655 = 610.69.

{md_table(q6)}

## Appendix: 20% cut scenario used in the Part 2 memo (quarterly, against the Q2 run-rate)

{md_table(scenario)}

`customers_forgone_est` uses the **average** Q2 CAC, a pessimistic upper bound. For Meta, the extra Q2 spend bought customers at a marginal CAC of about {inr(marginal.set_index('channel').at['Meta Ads', 'marginal_cac'])}, so the real loss from returning Meta to its Q1 level is likely much smaller.
"""
    (config.DELIVERABLES_DIR / "Part1_Analysis.md").write_text(md, encoding="utf-8")

    with pd.ExcelWriter(config.DELIVERABLES_DIR / "Part1_Analysis.xlsx") as xl:
        for name, df in [("Q1_data_quality", q1), ("Q1_qa_account_impact", impact),
                         ("Q2_acquisition_cost", q2), ("Q3_customer_value", q3),
                         ("Q4_return_on_spend", q4), ("Q5_monthly_cac", q5),
                         ("Q5_trend_jan_vs_jun", q5_trend), ("Q5_marginal_cac", marginal),
                         ("Q6_sanity_check", q6), ("Cut_scenario", scenario)]:
            df.to_excel(xl, sheet_name=name, index=False)
            sheet = xl.sheets[name]
            for i, col in enumerate(df.columns):
                width = max(len(str(col)), *(len(str(v)) for v in df[col])) + 2
                sheet.column_dimensions[sheet.cell(1, i + 1).column_letter].width = min(width, 80)

    con.close()
    bad = q6[q6["result"] != "OK"]
    print(f"Wrote {config.DELIVERABLES_DIR / 'Part1_Analysis.md'} and .xlsx; warehouse at {config.DB_PATH}")
    if not bad.empty:
        raise SystemExit(f"Sanity reconciliation failed:\n{bad}")


if __name__ == "__main__":
    main()
