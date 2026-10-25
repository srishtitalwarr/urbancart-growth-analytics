"""Part 2 charts (static PNGs for the memo). Run after scripts/run_analysis.py.

Usage:  python scripts/make_charts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb  # noqa: E402
import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from urbancart import config, metrics  # noqa: E402

# One fixed colour per channel across every chart (validated categorical slots 1-4).
COLORS = {"Google Ads": "#2a78d6", "Meta Ads": "#eb6834", "Affiliate": "#1baf7a", "Influencer": "#eda100"}
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
NEUTRAL = "#b9b8b2"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 10.5,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.titlelocation": "left", "axes.titlepad": 26,
})


def _subtitle(ax, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=10, va="bottom")


def _source(fig, text: str = "Source: UrbanCart users, orders and spend, Jan–Jun 2026; QA accounts and duplicates removed.") -> None:
    fig.text(0.01, 0.01, text, color=MUTED, fontsize=8.5)


def chart_ltv_cac(con, out: Path) -> None:
    df = metrics.return_on_spend(con).sort_values("ltv_cac")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.barh(df["channel"], df["ltv_cac"], height=0.5,
                   color=[COLORS[c] for c in df["channel"]], edgecolor=SURFACE, linewidth=2)
    for bar, (_, r) in zip(bars, df.iterrows()):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{r['ltv_cac']:.2f}   (LTV ₹{r['ltv']:,} ÷ CAC ₹{r['cac']:,})",
                va="center", color=INK, fontsize=10)
    ax.axvline(1, color=AXIS, linewidth=1, linestyle="--")
    ax.text(1.01, 3.42, "break-even 1.0", color=MUTED, fontsize=8.5, ha="left", va="center")
    ax.set_xlim(0, 1.75)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Google returns the most per rupee; Affiliate the least")
    _subtitle(ax, "LTV:CAC by paid channel (LTV = 6-month revenue per customer × 30% margin)")
    _source(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=160)
    plt.close(fig)


def chart_monthly_cac(con, out: Path) -> None:
    df = metrics.monthly_cac_long(con)
    months = sorted(df["month"].unique())
    labels = [pd.Timestamp(m + "-01").strftime("%b") for m in months]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for ch in config.PAID_CHANNELS:
        s = df[df["channel"] == ch].set_index("month").reindex(months)["cac"]
        emphasis = ch == "Meta Ads"
        ax.plot(labels, s.values, color=COLORS[ch], linewidth=2.6 if emphasis else 2,
                marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5,
                alpha=1 if emphasis else 0.85, label=ch)
        ax.text(len(labels) - 1 + 0.12, s.values[-1], f"{ch}  ₹{s.values[-1]:,.0f}",
                va="center", color=INK, fontsize=9.5, fontweight="bold" if emphasis else "normal")
    meta = df[df["channel"] == "Meta Ads"].set_index("month")["cac"]
    spend = df[df["channel"] == "Meta Ads"].set_index("month")["spend"]
    ax.text(2.6, 330,
            f"Meta CAC +{100 * (meta.iloc[-1] / meta.iloc[0] - 1):.0f}% Jan→Jun, while its monthly\n"
            f"spend went ₹{spend.iloc[0] / 1000:.0f}k → ₹{spend.iloc[-1] / 1000:.0f}k and new customers stayed ~105–120",
            color=INK_2, fontsize=9, va="center")
    ax.set_ylim(0, 1250)
    ax.set_xlim(-0.2, len(labels) - 1 + 1.6)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"₹{v:,.0f}"))
    ax.legend(loc="lower left", frameon=False, ncol=4, fontsize=9)
    ax.set_title("Meta is the only channel getting more expensive")
    _subtitle(ax, "CAC by signup month, 2026 (monthly spend ÷ new customers who signed up that month)")
    _source(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=160)
    plt.close(fig)


def chart_qa_impact(con, out: Path) -> None:
    df = metrics.test_account_impact(con)
    g = metrics.customer_value(con).set_index("channel").loc["Google Ads"]
    google = metrics.return_on_spend(con).set_index("channel").at["Google Ads", "ltv_cac"]
    rows = [  # bottom to top
        ("Affiliate, cleaned", df.iloc[1], COLORS["Affiliate"]),
        ("Affiliate, raw data\n(35 QA accounts included)", df.iloc[0], NEUTRAL),
        ("Google Ads, cleaned\n(for reference)", {"ltv_cac": google, "revenue_per_customer": g["revenue_per_customer"],
                                                  "repeat_rate_pct": g["repeat_rate_pct"]}, COLORS["Google Ads"]),
    ]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bars = ax.barh([r[0] for r in rows], [r[1]["ltv_cac"] for r in rows], height=0.5,
                   color=[r[2] for r in rows], edgecolor=SURFACE, linewidth=2)
    for bar, (_, r, _) in zip(bars, rows):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{r['ltv_cac']:.2f}   (₹{int(r['revenue_per_customer']):,} per customer, {r['repeat_rate_pct']}% repeat)",
                va="center", color=INK, fontsize=10)
    ax.set_xlim(0, 2.0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Test accounts made Affiliate look as good as Google")
    _subtitle(ax, "Affiliate LTV:CAC before and after removing internal qa.test@urbancart.in accounts")
    _source(fig, "Source: UrbanCart users and orders, Jan–Jun 2026; duplicates removed in both versions.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out, dpi=160)
    plt.close(fig)


def main() -> None:
    if not config.DB_PATH.exists():
        raise SystemExit("Run scripts/run_analysis.py first.")
    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    chart_ltv_cac(con, config.CHARTS_DIR / "chart1_ltv_cac_by_channel.png")
    chart_monthly_cac(con, config.CHARTS_DIR / "chart2_monthly_cac_trend.png")
    chart_qa_impact(con, config.CHARTS_DIR / "chart3_affiliate_qa_impact.png")
    con.close()
    print(f"Wrote 3 charts to {config.CHARTS_DIR}")


if __name__ == "__main__":
    main()
