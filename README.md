# UrbanCart: Growth & Analytics case study

Which paid channel should UrbanCart cut to save 20% of spend, and how can the CMO answer her own follow-up questions every week?

## The answer in brief
- **Cut ₹1.74L per quarter (20% of the Q2 run-rate): Meta −₹1.31L, Affiliate −₹43k.** Meta's CAC rose from ₹491 to ₹1,115 (+127%) between January and June, and its extra Q2 spend bought customers at about ₹7,700 each. Affiliate has the worst LTV:CAC (0.42).
- **Protect Google Ads**: best LTV:CAC (1.14) and a flat CAC.
- **The key data issue:** 35 internal `qa.test*@urbancart.in` accounts, all tagged Affiliate, inflated Affiliate's LTV:CAC from 0.42 to 1.10.

## Where everything is
| Brief item | File |
|---|---|
| Part 1: answers (tables) | [deliverables/Part1_Analysis.md](deliverables/Part1_Analysis.md) · [.xlsx](deliverables/Part1_Analysis.xlsx) |
| Part 1: code | [sql/](sql) (staging → clean → marts) · [src/urbancart/](src/urbancart) · [scripts/run_analysis.py](scripts/run_analysis.py) |
| Part 2: memo and charts | [deliverables/Part2_Memo.md](deliverables/Part2_Memo.md) · [deliverables/charts/](deliverables/charts) |
| Part 3: design note and diagram | [deliverables/Part3_Design.md](deliverables/Part3_Design.md) · [Part3_Architecture.png](deliverables/Part3_Architecture.png) · [.mmd](deliverables/Part3_Architecture.mmd) |
| Part 3: working prototype | [app/streamlit_app.py](app/streamlit_app.py) · [src/urbancart/qa.py](src/urbancart/qa.py) |
| AI-use note | [deliverables/AI_Use_Note.md](deliverables/AI_Use_Note.md) |
| Reflection | [deliverables/Reflection.md](deliverables/Reflection.md) |
| Requirement → evidence map | [FINAL_CHECKLIST.md](FINAL_CHECKLIST.md) |

## Setup and run (Python 3.12)
```powershell
python -m venv .venv
.venv\Scripts\activate                # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python scripts/run_analysis.py        # builds outputs/warehouse.duckdb + Part1_Analysis.md/.xlsx
python scripts/make_charts.py         # Part 2 charts
python scripts/make_diagram.py        # Part 3 diagram
python -m pytest                      # 42 tests
streamlit run app/streamlit_app.py    # dashboard + Q&A at http://localhost:8501
```
The app reads `outputs/warehouse.duckdb`. If that file is missing, it builds the warehouse in memory from `data/`.

## Method
1. **Raw → staging.** All columns are loaded as text, then typed with `TRY_CAST` and trimmed ([sql/01_staging.sql](sql/01_staging.sql)).
2. **Data-quality checks.** There are 13 declarative checks in [cleaning.py](src/urbancart/cleaning.py), each a SQL count plus a handling rule. Five issues were found: 206 duplicate order rows, 35 QA accounts (285 orders), 72 blank channels, and 679 cancelled or returned orders (excluded by definition). Eight checks passed: orphans, dates, values, spend completeness and so on. Blocking checks stop the build.
3. **Clean → marts** ([02_clean.sql](sql/02_clean.sql), [03_marts.sql](sql/03_marts.sql)). The marts are `mart_channel_kpis` (full period) and `mart_channel_monthly` (by signup month). The same mart SQL also runs with the QA accounts included, to measure their impact.
4. **Presentation** ([metrics.py](src/urbancart/metrics.py)). Money is rounded to ₹1, percentages to 1 dp, LTV:CAC to 2 dp.
5. **Verification** ([sanity.py](src/urbancart/sanity.py)). An independent pandas recomputation from the raw CSVs, plus control totals. All 11 checks match.

## Assumptions
- `@urbancart.in` emails are internal QA accounts. They and their orders are excluded.
- Rows identical in every column are export duplicates; one copy is kept.
- A blank channel is labelled `Unknown`: counted in totals, attributed to no channel.
- "Customers" in revenue per customer and repeat rate means new customers (≥1 delivered order). Revenue counts delivered orders only.
- Monthly CAC = that month's spend ÷ new customers who **signed up** that month (per the brief).
- The 20% cut is sized on the Apr–Jun 2026 run-rate (₹8.68L per quarter), the quarter before "next quarter".
- Attribution is the single `acquisition_channel` on the user record.

## Limitations
- LTV covers only up to 6 months of revenue, so every channel sits below 1.0. Use it to compare channels, not to judge payback.
- Later sign-up months have had less time to order (right-censoring). This slightly inflates June CAC for every channel.
- The marginal CAC estimate for Meta (Q1 vs Q2) rests on two data points, with no control for seasonality.
- The Q&A prototype uses a rule-based parser in place of an LLM (the LLM design is in Part 3). It answers only the whitelisted metrics and refuses anything else.
