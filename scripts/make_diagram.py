"""Render the Part 3 architecture diagram to deliverables/Part3_Architecture.png.

Usage:  python scripts/make_diagram.py
(The same diagram is kept as Mermaid source in deliverables/Part3_Architecture.mmd.)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "deliverables" / "Part3_Architecture.png"

INK, INK_2, MUTED, LINE = "#0b0b0b", "#52514e", "#898781", "#9a9890"
FILL = {"source": "#eef4fc", "ingest": "#fdf0ea", "store": "#e9f7f1", "serve": "#f1effc", "ops": "#f4f3ef"}
EDGE = {"source": "#2a78d6", "ingest": "#eb6834", "store": "#1baf7a", "serve": "#6250d6", "ops": "#898781"}

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]


def box(ax, x, y, w, h, title, body="", kind="store"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=FILL[kind], edgecolor=EDGE[kind], linewidth=1.4))
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="top", fontsize=10, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h - 0.52, body, ha="center", va="top", fontsize=8.3, color=INK_2, linespacing=1.35)
    return (x, y, w, h)


def arrow(ax, a, b, label="", style="-|>", dashed=False, rad=0.0, label_at=None, ha="center"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=12, color=LINE, linewidth=1.3,
                                 linestyle=(0, (4, 3)) if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        x, y = label_at or ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12)
        ax.text(x, y, label, ha=ha, va="bottom", fontsize=7.8, color=MUTED)


def right(b, dy=0.0):
    return (b[0] + b[2], b[1] + b[3] / 2 + dy)


def left(b, dy=0.0):
    return (b[0], b[1] + b[3] / 2 + dy)


def main() -> None:
    fig, ax = plt.subplots(figsize=(15, 8.2))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    fig.patch.set_facecolor("#fcfcfb")

    ax.text(0.1, 7.95, "UrbanCart daily marketing pipeline and CMO self-serve tool (GCP)",
            fontsize=14, fontweight="bold", color=INK, va="top")

    # Sources
    srcs = [("GA4", "web sessions"), ("Salesforce", "customers, orders"),
            ("MoEngage", "campaign engagement"), ("Ad platforms", "Google, Meta,\naffiliate, influencer spend")]
    src_boxes = [box(ax, 0.2, 6.0 - i * 1.35, 2.2, 1.1, t, b, "source") for i, (t, b) in enumerate(srcs)]

    ingest = box(ax, 3.0, 3.9, 2.3, 2.5, "Ingest",
                 "GA4: native\nBigQuery export\n\nOthers: Cloud Run\njobs call APIs\n(keys from\nSecret Manager)", "ingest")
    gcs = box(ax, 5.9, 4.3, 2.1, 1.7, "Cloud Storage", "raw landing zone\nsource/dt=YYYY-MM-DD\nimmutable, replayable", "store")

    bq_x = 8.6
    ax.add_patch(FancyBboxPatch((bq_x - 0.1, 1.95), 2.9, 5.15, boxstyle="round,pad=0.02,rounding_size=0.15",
                                facecolor="none", edgecolor=EDGE["store"], linewidth=1, linestyle=(0, (3, 3))))
    ax.text(bq_x + 1.35, 6.98, "BigQuery (dbt)", ha="center", va="top", fontsize=10.5, fontweight="bold", color=INK)
    raw = box(ax, bq_x, 5.5, 2.7, 1.05, "raw", "as loaded, all text", "store")
    stg = box(ax, bq_x, 3.95, 2.7, 1.3, "staging + DQ tests",
              "typed, trimmed, de-duplicated,\nQA accounts filtered;\nmarts swap in only if tests pass", "store")
    mart = box(ax, bq_x, 2.15, 2.7, 1.55, "marts",
               "mart_channel_kpis\nmart_channel_monthly\ndq_log", "store")

    app = box(ax, 12.1, 4.1, 2.7, 2.2, "Streamlit on Cloud Run",
              "Google login (IAP)\n\nDashboard: KPIs, LTV:CAC,\nmonthly CAC, DQ status\n+ question box\n\nread-only, parameterised SQL", "serve")
    llm = box(ax, 12.1, 1.85, 2.7, 1.75, "Claude (tool use)",
              "picks get_metric(metric,\nchannel, month) from enums\nnever writes SQL or numbers", "serve")
    cmo = box(ax, 12.85, 6.75, 1.2, 0.85, "CMO", "", "serve")

    for b in src_boxes:
        arrow(ax, right(b), left(ingest))
    arrow(ax, (ingest[0] + ingest[2], gcs[1] + gcs[3] / 2), left(gcs), "daily", label_at=(5.6, 5.2))
    arrow(ax, (gcs[0] + gcs[2], gcs[1] + gcs[3] - 0.3), left(raw), "load")
    arrow(ax, (bq_x + 1.35, raw[1]), (bq_x + 1.35, stg[1] + stg[3]))
    arrow(ax, (bq_x + 1.35, stg[1]), (bq_x + 1.35, mart[1] + mart[3]))
    arrow(ax, right(mart, 0.3), left(app, -0.6), rad=-0.15)
    arrow(ax, (app[0] + 1.35, app[1]), (llm[0] + 1.35, llm[1] + llm[3]), style="<|-|>")
    ax.text(app[0] + 1.45, (app[1] + llm[1] + llm[3]) / 2, "question → tool call", fontsize=7.8, color=MUTED, va="center")
    arrow(ax, (cmo[0] + 0.6, cmo[1]), (app[0] + 1.35, app[1] + app[3]), style="<|-|>")

    # Ops row
    sched = box(ax, 0.2, 0.25, 2.9, 1.2, "Cloud Scheduler → Workflows", "06:00 IST: ingest → dbt build → publish", "ops")
    sec = box(ax, 3.4, 0.25, 2.4, 1.2, "Secret Manager", "API keys; least-privilege\nservice account", "ops")
    quar = box(ax, 6.1, 0.25, 2.2, 1.2, "quarantine tables", "rows failing a\nwarn-level test", "ops")
    mon = box(ax, 8.6, 0.25, 3.0, 1.2, "Cloud Monitoring alerts",
              "job failed, test error, or marts\nolder than 26 h → Slack + email", "ops")

    arrow(ax, (sched[0] + 2.6, sched[1] + sched[3]), (ingest[0] + 0.5, ingest[1]), "triggers", dashed=True,
          label_at=(3.0, 2.4), ha="right")
    arrow(ax, (sec[0] + 1.6, sec[1] + sec[3]), (ingest[0] + 1.6, ingest[1]), "keys", dashed=True,
          label_at=(4.92, 2.4), ha="left")
    arrow(ax, (stg[0], stg[1] + 0.3), (quar[0] + 1.6, quar[1] + quar[3]), "warn", dashed=True, rad=0.2)
    arrow(ax, (mart[0] + 1.35, mart[1]), (mon[0] + 1.6, mon[1] + mon[3]), "error / stale", dashed=True,
          label_at=(10.15, 1.62), ha="left")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
