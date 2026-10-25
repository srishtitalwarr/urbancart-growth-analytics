"""CMO self-serve dashboard + Q&A.

Run:  streamlit run app/streamlit_app.py
Reads only the marts in outputs/warehouse.duckdb (built by scripts/run_analysis.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import altair as alt  # noqa: E402
import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from urbancart import cleaning, config, metrics, qa  # noqa: E402

COLORS = {"Google Ads": "#2a78d6", "Meta Ads": "#eb6834", "Affiliate": "#1baf7a",
          "Influencer": "#eda100", "Organic": "#6250d6", "Unknown": "#898781"}
COLOR_SCALE = alt.Scale(domain=list(COLORS), range=list(COLORS.values()))

st.set_page_config(page_title="UrbanCart Channel Performance", layout="wide")


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if config.DB_PATH.exists():
        return duckdb.connect(str(config.DB_PATH), read_only=True)
    con, _ = cleaning.build_warehouse()  # fall back to an in-memory build from the raw CSVs
    return con


con = get_connection()
as_of = metrics.data_as_of(con)

st.title("UrbanCart: Channel performance")
st.caption(f"Data through **{as_of}** · Delivered orders only · QA accounts and duplicate orders removed · "
           f"LTV = 6-month revenue per customer × {config.CONTRIBUTION_MARGIN:.0%} margin")

tab_ask, tab_overview, tab_trend, tab_dq = st.tabs(["💬 Ask a question", "📊 Overview", "📈 Monthly CAC", "🧪 Data quality"])

with tab_ask:
    st.write("Ask about **CAC, spend, new customers, revenue per customer, repeat rate, LTV or LTV:CAC**, "
             "by channel, and by month for spend, customers and CAC.")
    cols = st.columns(3)
    for i, example in enumerate(qa.EXAMPLES):
        if cols[i % 3].button(example, key=f"ex{i}", use_container_width=True):
            st.session_state["question"] = example
    question = st.text_input("Your question", key="question", placeholder="What was Meta's CAC last month?")
    if question:
        answer = qa.ask(con, question)
        if answer.ok:
            st.success(answer.text)
            if answer.table is not None and len(answer.table) > 1:
                st.dataframe(answer.table, hide_index=True)
            with st.expander("How this was calculated"):
                st.code(answer.sql, language="sql")
                st.write("Parameters:", answer.params)
                st.caption(f"Interpreted as: {answer.intent}. Source tables: mart_channel_kpis / "
                           f"mart_channel_monthly, data through {as_of}.")
        else:
            st.warning(answer.text)

with tab_overview:
    kpis = metrics.acquisition_cost(con).set_index("channel")
    ros = metrics.return_on_spend(con)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Paid spend (Jan–Jun)", f"₹{kpis.at['Total paid', 'spend']:,}")
    c2.metric("New paid customers", f"{kpis.at['Total paid', 'new_customers']:,}")
    c3.metric("Blended paid CAC", f"₹{kpis.at['Total paid', 'cac']:,}")
    c4.metric("Best LTV:CAC", f"{ros.iloc[0]['channel']} {ros.iloc[0]['ltv_cac']:.2f}")

    st.subheader("LTV:CAC by paid channel")
    st.altair_chart(
        alt.Chart(ros).mark_bar(cornerRadiusEnd=4, height=22).encode(
            x=alt.X("ltv_cac:Q", title="LTV:CAC"),
            y=alt.Y("channel:N", sort="-x", title=None),
            color=alt.Color("channel:N", scale=COLOR_SCALE, legend=None),
            tooltip=["channel", "ltv_cac", "ltv", "cac", "revenue_per_customer"],
        ).properties(height=200),
        use_container_width=True,
    )
    st.subheader("All channels")
    full = metrics.customer_value(con).merge(
        metrics.acquisition_cost(con)[["channel", "spend", "cac"]], on="channel", how="left"
    ).merge(ros[["channel", "ltv", "ltv_cac"]], on="channel", how="left")
    st.dataframe(full, hide_index=True)

with tab_trend:
    long = metrics.monthly_cac_long(con)
    st.altair_chart(
        alt.Chart(long).mark_line(point=True, strokeWidth=2).encode(
            x=alt.X("month:O", title="Signup month"),
            y=alt.Y("cac:Q", title="CAC (₹)"),
            color=alt.Color("channel:N", scale=COLOR_SCALE),
            tooltip=["month", "channel", alt.Tooltip("cac:Q", format=",.0f"), "spend", "new_customers"],
        ).properties(height=380),
        use_container_width=True,
    )
    st.dataframe(metrics.cac_trend(con), hide_index=True)
    st.caption("Note: the latest month's sign-ups have had less time to place their first order, "
               "so its CAC is slightly overstated for every channel.")

with tab_dq:
    dq = con.execute("SELECT * FROM dq_log").df()
    st.write(f"{(dq['status'] == 'FOUND').sum()} issues found and handled, "
             f"{(dq['status'] == 'PASS').sum()} checks passed on the last build.")
    st.dataframe(dq, hide_index=True)
    st.subheader("Why it matters: Affiliate with and without the QA accounts")
    st.dataframe(metrics.test_account_impact(con), hide_index=True)
