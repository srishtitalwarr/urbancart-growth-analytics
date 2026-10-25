"""Self-serve Q&A: turn a plain-English question into a whitelisted metric query.

Every number in an answer comes from a parameterised SQL query on the marts.
The parser only *selects* a metric, channels, a month and a mode. It never
produces numbers itself. Anything it cannot map with confidence is refused
with a list of the questions it does understand, rather than guessed at.

In production the rule-based `parse()` can be swapped for an LLM that fills
the same `Intent` through tool calling. `execute()` stays unchanged, so the
LLM still never writes numbers or SQL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from . import config


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    kind: str                 # money | pct | ratio | count
    higher_is_better: bool
    monthly: bool             # available in mart_channel_monthly
    paid_only: bool           # needs spend, so undefined for Organic/Unknown
    patterns: tuple[str, ...]


# Checked in this order, so the more specific phrases come first.
METRICS: list[Metric] = [
    Metric("ltv_cac", "LTV:CAC", "ratio", True, False, True,
           (r"ltv\s*(:|/|to|vs\.?)\s*cac", r"return on (ad )?spend", r"\breturn\b", r"\broi\b", r"payback")),
    Metric("revenue_per_customer", "Revenue per customer", "money", True, False, False,
           (r"revenue per (new )?customer", r"value per customer", r"spend per customer", r"\barpu\b",
            r"average revenue")),
    Metric("repeat_rate_pct", "Repeat purchase rate", "pct", True, False, False,
           (r"repeat", r"re-?purchase", r"retention", r"come back", r"buy again")),
    Metric("cac", "CAC", "money", False, True, True,
           (r"\bcac\b", r"acquisition cost", r"cost (per|of|to) (acquir|acquisition|new customer|customer)",
            r"cost per (new )?customer", r"more expensive", r"cheaper", r"cheapest", r"expensive")),
    Metric("ltv", "LTV (6-month, 30% margin)", "money", True, False, False,
           (r"\bltv\b", r"lifetime value")),
    Metric("spend", "Spend", "money", False, True, True,
           (r"\bspend\b", r"\bspent\b", r"budget", r"\bcost\b")),
    Metric("new_customers", "New customers", "count", True, True, False,
           (r"new customers", r"customers", r"acquired", r"acquisitions", r"conversions")),
    Metric("revenue", "Revenue (delivered)", "money", True, False, False,
           (r"revenue", r"\bsales\b", r"\bgmv\b")),
]
METRIC_BY_KEY = {m.key: m for m in METRICS}
ADDITIVE = {"spend", "new_customers", "revenue"}  # safe to sum across channels; ratios are not

CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "Google Ads": (r"google", r"adwords", r"search ads", r"\bsem\b", r"\bppc\b"),
    "Meta Ads": (r"\bmeta\b", r"facebook", r"\bfb\b", r"instagram", r"\big\b"),
    "Affiliate": (r"affiliates?",),
    "Influencer": (r"influencers?", r"creators?"),
    "Organic": (r"organic", r"unpaid", r"\bseo\b"),
}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b(?:\s*'?(\d{2,4}))?")
RANK_RE = re.compile(r"\b(best|worst|highest|lowest|most|least|top|bottom|cheapest|rank|ranking|which channel)\b")
TREND_RE = re.compile(r"\b(trend|over time|by month|monthly|each month|month by month|per month|"
                      r"getting|rising|increas\w*|grow\w*|chang\w*|jan(uary)? to)\b")
LOW_WORDS = re.compile(r"\b(lowest|least|bottom|cheapest)\b")
HIGH_WORDS = re.compile(r"\b(highest|most|top)\b")

EXAMPLES = [
    "What was Meta's CAC last month?",
    "Which channel has the best LTV:CAC?",
    "Repeat purchase rate for Organic",
    "How much did we spend on Google in March?",
    "Which channel is getting more expensive?",
    "How is Affiliate doing?",
]


@dataclass
class Intent:
    metric: str | None = None
    channels: list[str] = field(default_factory=list)
    month: str | None = None                # 'YYYY-MM'
    mode: str = "value"                     # value | rank | trend | summary
    direction: str | None = None            # high | low (rank only)
    month_error: str | None = None


@dataclass
class Answer:
    ok: bool
    text: str
    table: pd.DataFrame | None = None
    sql: str | None = None
    params: list | None = None
    intent: Intent | None = None


def available_months(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT month FROM mart_channel_monthly ORDER BY 1").fetchall()]


def parse(question: str, months: list[str]) -> Intent:
    q = question.lower().replace("’", "'").strip()
    intent = Intent()

    for m in METRICS:
        if any(re.search(p, q) for p in m.patterns):
            intent.metric = m.key
            break

    for channel, pats in CHANNEL_ALIASES.items():
        if any(re.search(p, q) for p in pats):
            intent.channels.append(channel)
    if re.search(r"\bpaid\b", q) and not intent.channels:
        intent.channels = list(config.PAID_CHANNELS)

    latest = months[-1] if months else None
    if re.search(r"\b(last|latest|this|previous|most recent|current) month\b", q):
        intent.month = latest
    else:
        for match in MONTH_RE.finditer(q):
            word, year = match.group(1), match.group(2)
            # "may" is also a verb: only treat it as a month when it reads like a date.
            if word == "may" and not (year or re.search(r"\b(in|for|of|during|since|until|to)\s+may\b", q)):
                continue
            yyyy = int(year) + (2000 if year and len(year) == 2 else 0) if year else int(latest[:4]) if latest else 2026
            candidate = f"{yyyy}-{MONTHS[word[:3]]:02d}"
            if candidate in months:
                intent.month = candidate
            else:
                intent.month_error = (f"I only have data for {months[0]} to {months[-1]}; "
                                      f"{candidate} is outside that range.")
            break

    if TREND_RE.search(q) and not intent.month:
        intent.mode = "trend"
    elif RANK_RE.search(q) and len(intent.channels) != 1:
        intent.mode = "rank"
        intent.direction = "low" if LOW_WORDS.search(q) else "high" if HIGH_WORDS.search(q) else None
        if re.search(r"\bworst\b|\bbottom\b", q):
            intent.direction = "worst"
        elif re.search(r"\bbest\b", q):
            intent.direction = "best"
        if re.search(r"most expensive", q):
            intent.metric, intent.direction = "cac", "high"
    elif intent.metric is None and len(intent.channels) == 1:
        intent.mode = "summary"
    return intent


# ---------------------------------------------------------------- execution

def _fmt(value, kind: str) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if kind == "money":
        return f"₹{value:,.0f}"
    if kind == "pct":
        return f"{value:.1f}%"
    if kind == "ratio":
        return f"{value:.2f}"
    return f"{int(value):,}"


def _month_label(month: str) -> str:
    return pd.Timestamp(month + "-01").strftime("%b %Y")


def _refuse(text: str, intent: Intent | None = None) -> Answer:
    return Answer(False, text + "\n\nTry, for example:\n" + "\n".join(f"- {e}" for e in EXAMPLES),
                  intent=intent)


def _query(con, sql: str, params: list) -> pd.DataFrame:
    return con.execute(sql, params).df()


def execute(con: duckdb.DuckDBPyConnection, intent: Intent) -> Answer:
    if intent.month_error:
        return _refuse(intent.month_error, intent)

    if intent.mode == "summary":
        return _summary(con, intent)

    if intent.metric is None:
        return _refuse("I couldn't tell which metric you mean (CAC, spend, new customers, revenue per "
                       "customer, repeat rate, LTV or LTV:CAC).", intent)
    m = METRIC_BY_KEY[intent.metric]

    if intent.month and not m.monthly:
        return _refuse(f"{m.label} is only defined for the full Jan–Jun period, not for a single month "
                       "(it needs each customer's full order history). Ask without a month.", intent)

    universe = config.PAID_CHANNELS if (m.paid_only or intent.month or intent.mode == "trend") \
        else config.ALL_CHANNELS
    unsupported = [c for c in intent.channels if c not in universe]
    if unsupported and len(unsupported) == len(intent.channels):
        why = ("has no paid spend, so CAC, spend and LTV:CAC don't apply" if m.paid_only
               else "is only reported for the full period, not by month")
        return _refuse(f"{', '.join(unsupported)} {why}.", intent)
    channels = [c for c in intent.channels if c in universe] or list(universe)

    if intent.mode == "trend":
        return _trend(con, intent, m, channels)
    if intent.mode == "rank":
        return _rank(con, intent, m, channels)
    return _value(con, intent, m, channels)


def _source(m: Metric, month: str | None) -> tuple[str, str, list]:
    if month:
        return "mart_channel_monthly", "WHERE month = ? AND channel IN ({ph})", [month]
    return "mart_channel_kpis", "WHERE channel IN ({ph})", []


def _value(con, intent: Intent, m: Metric, channels: list[str]) -> Answer:
    table, where, params = _source(m, intent.month)
    where = where.format(ph=", ".join("?" * len(channels)))
    sql = f"SELECT channel, {m.key} AS value FROM {table} {where} ORDER BY channel"
    params = params + channels
    df = _query(con, sql, params)
    period = _month_label(intent.month) if intent.month else "Jan–Jun 2026"
    if len(df) == 1:
        r = df.iloc[0]
        text = f"**{r['channel']} {m.label}, {period}: {_fmt(r['value'], m.kind)}**"
    else:
        text = f"**{m.label}, {period}:**\n" + "\n".join(
            f"- {r.channel}: {_fmt(r.value, m.kind)}" for r in df.itertuples())
        if m.key in ADDITIVE:
            text += f"\n- **Total of channels listed: {_fmt(df['value'].sum(), m.kind)}**"
    return Answer(True, text, df.rename(columns={"value": m.label}), sql, params, intent)


def _rank(con, intent: Intent, m: Metric, channels: list[str]) -> Answer:
    if intent.direction in ("best", "worst"):
        want_high = m.higher_is_better == (intent.direction == "best")
    else:
        want_high = intent.direction != "low"
    table, where, params = _source(m, intent.month)
    where = where.format(ph=", ".join("?" * len(channels)))
    order = "DESC" if want_high else "ASC"
    sql = f"SELECT channel, {m.key} AS value FROM {table} {where} ORDER BY value {order} NULLS LAST"
    params = params + channels
    df = _query(con, sql, params)
    top = df.iloc[0]
    period = _month_label(intent.month) if intent.month else "Jan–Jun 2026"
    word = intent.direction if intent.direction in ("best", "worst") else ("highest" if want_high else "lowest")
    text = (f"**{top['channel']}** has the {word} {m.label} ({period}): **{_fmt(top['value'], m.kind)}**.\n\n"
            + "Full ranking: " + ", ".join(f"{r.channel} {_fmt(r.value, m.kind)}" for r in df.itertuples()))
    return Answer(True, text, df.rename(columns={"value": m.label}), sql, params, intent)


def _trend(con, intent: Intent, m: Metric, channels: list[str]) -> Answer:
    if not m.monthly:
        return _refuse(f"{m.label} isn't available by month. Monthly metrics are spend, "
                       "new customers and CAC.", intent)
    ph = ", ".join("?" * len(channels))
    sql = (f"SELECT month, channel, {m.key} AS value FROM mart_channel_monthly "
           f"WHERE channel IN ({ph}) ORDER BY channel, month")
    df = _query(con, sql, channels)
    wide = df.pivot(index="month", columns="channel", values="value")
    change = (100 * (wide.iloc[-1] / wide.iloc[0] - 1)).sort_values(ascending=False)
    first, last = _month_label(wide.index[0]), _month_label(wide.index[-1])
    lines = [f"- {c}: {_fmt(wide[c].iloc[0], m.kind)} → {_fmt(wide[c].iloc[-1], m.kind)} ({change[c]:+.1f}%)"
             for c in change.index]
    lead = change.index[0]
    headline = f"**{m.label} by signup month, {first} → {last}.**"
    if len(change) > 1:
        word = "Biggest increase" if change[lead] > 0 else "Smallest decrease"
        headline += f" {word}: **{lead} ({change[lead]:+.1f}%)**."
    text = headline + "\n" + "\n".join(lines)
    return Answer(True, text, wide.reset_index(), sql, channels, intent)


def _summary(con, intent: Intent) -> Answer:
    ch = intent.channels[0]
    sql = ("SELECT channel, spend, new_customers, cac, revenue_per_customer, repeat_rate_pct, ltv, ltv_cac "
           "FROM mart_channel_kpis WHERE channel = ?")
    df = _query(con, sql, [ch])
    if df.empty:
        return _refuse(f"No data for {ch}.", intent)
    r = df.iloc[0]
    parts = [f"{METRIC_BY_KEY[k].label} {_fmt(r[k], METRIC_BY_KEY[k].kind)}"
             for k in ("spend", "new_customers", "cac", "revenue_per_customer", "repeat_rate_pct", "ltv_cac")
             if not pd.isna(r[k])]
    return Answer(True, f"**{ch}, Jan–Jun 2026:** " + " · ".join(parts), df, sql, [ch], intent)


def ask(con: duckdb.DuckDBPyConnection, question: str) -> Answer:
    if not question or not question.strip():
        return _refuse("Please type a question.")
    return execute(con, parse(question, available_months(con)))
