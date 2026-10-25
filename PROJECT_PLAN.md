# Project Plan: UrbanCart Growth Analytics case study

## Requirements checklist (from the brief)
- [x] **Part 1, Analyse.** Use SQL/Python, show tables, keep the code, round money to ₹1 and percentages to 1 dp.
  - [x] Q1 Data quality: every issue, the rows affected, and how it was handled
  - [x] Q2 Spend, new customers and CAC per paid channel
  - [x] Q3 Revenue per customer and repeat purchase rate per channel (including Organic)
  - [x] Q4 LTV:CAC per paid channel, best and worst
  - [x] Q5 CAC by signup month per paid channel, which channel is getting more expensive, and by how much (Jan→Jun)
  - [x] Q6 Sanity check of one number
- [x] **Part 2, Recommend.** Memo ≤250 words (what to cut and by how much, what to protect, risk and what to watch) plus 2–3 charts.
- [x] **Part 3, Automate and make it self-serve.** Design note ≤400 words plus an architecture diagram.
  - [x] A. Landing zone and warehouse, scheduling, automated DQ handling, secrets, failure alerting
  - [x] B. What the tool shows and which tables it reads, the question → answer flow, guarding against LLM hallucination, testing
- [x] AI-use note (3–5 lines)
- [ ] Reflection (200–250 words, in the candidate's own words; **written by the candidate**; template in place)
- [x] One folder, files named by part

## Architecture
Raw CSVs → DuckDB (`src/urbancart/cleaning.py`: typed, deduped, test accounts removed) → metric SQL (`metrics.py`) → Markdown/Excel report, charts, and `outputs/warehouse.duckdb` → Streamlit dashboard and a rule-based Q&A (`qa.py`). The Q&A only selects whitelisted metrics; every number it shows comes from SQL.

## Milestones
1. Cleaning and the DQ log
2. Metrics and the Part 1 report
3. Charts and the memo
4. Streamlit app and Q&A
5. Design note and diagram
6. Tests, docs, checklist, local git commit

## Assumptions
1. **QA accounts** (`@urbancart.in`, 35 users) are internal test users, not customers. They and all their orders are excluded.
2. **Duplicate orders** are rows that are identical in every column. They are treated as export duplicates, and one copy is kept.
3. **Blank acquisition channel** (72 users) is labelled `Unknown`. These users count in totals but in no channel. No spend can be attributed to them.
4. **"Customers"** in Q3 means new customers (users with ≥1 delivered order), matching the definitions.
5. **Revenue** means delivered orders only, Jan–Jun 2026.
6. **CAC by month** = that month's spend ÷ new customers who *signed up* that month (as the brief specifies).
7. **The 20% cut** is sized on the latest quarter's run-rate (Apr–Jun 2026), because "next quarter" follows it.
8. Attribution is the single acquisition channel recorded on the user (last-touch as exported).

## Acceptance criteria
- Every deliverable regenerates from the raw CSVs with two commands.
- `pytest` passes. Metrics are cross-checked against an independent pandas calculation.
- Word limits are met (checked by script).
- The Streamlit app boots and answers the sample questions. Unsupported questions are refused rather than guessed.
