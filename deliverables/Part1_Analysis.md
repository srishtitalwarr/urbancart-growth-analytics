# Part 1: Analysis

All numbers come from `scripts/run_analysis.py`, which builds the DuckDB warehouse from the raw CSVs.
SQL: [`sql/`](../sql); Python: [`src/urbancart/`](../src/urbancart).
Money is rounded to the nearest rupee and percentages to 1 dp. Data covers 2026-01-01 to 2026-06-30.

## Q1. Data quality

5 issues found, and 8 further checks passed. Every check below runs automatically on each build.

| issue | table | rows_affected | handling | status |
|---|---|---|---|---|
| Exact duplicate order rows (same order_id and identical values) | orders | 206 | Removed the extra copies and kept one row per order_id. | FOUND |
| Internal QA/test accounts (email ends with @urbancart.in) | users | 35 | Excluded these users. They are not real customers. | FOUND |
| Orders placed by QA/test accounts | orders | 285 | Excluded from revenue and customers, together with the test users. | FOUND |
| Missing acquisition_channel | users | 72 | Labelled 'Unknown'. They count in totals but in no channel, and no spend is attributed. | FOUND |
| Cancelled or returned orders | orders | 679 | Kept in the table, but excluded from revenue and customer counts (definition). | FOUND |
| Same order_id with conflicting values | orders | 0 | Would keep the earliest row. None found. | PASS |
| Duplicate user_id | users | 0 | Would keep the earliest signup. None found. | PASS |
| Unparseable id, date or amount | all | 0 | Would be dropped. None found. | PASS |
| Orders whose user_id is not in users (orphans) | orders | 0 | Would be dropped. None found. | PASS |
| Order dated before the user's signup date | orders | 0 | Would be investigated. None found. | PASS |
| Dates outside the Jan to Jun 2026 window | users/orders | 0 | Would be excluded. None found. | PASS |
| Zero, negative or unknown-status orders | orders | 0 | Would be dropped. None found. | PASS |
| Spend file: missing channel x month cells | marketing_spend | 0 | Would block CAC for that month. None found (4 channels x 6 months). | PASS |

Notes:
- **The QA accounts are the most important issue.** All 35 of them are tagged *Affiliate*. Between them they placed 285 orders (after de-duplication), every one delivered. They also account for 164 of the 164 delivered orders of ₹2,500 or more in the whole dataset. Left in, they would make Affiliate look nearly as good as Google:

| version | new_customers | cac | revenue_per_customer | repeat_rate_pct | ltv_cac |
|---|---|---|---|---|---|
| Including QA accounts | 540 | 641 | 2,339 | 14.1 | 1.10 |
| Cleaned | 505 | 685 | 957 | 8.1 | 0.42 |

- Duplicate order counts: 5,684 raw rows → 5,478 unique orders.
- *Cancelled or returned* is not an error. It is listed because it changes revenue, and it is handled exactly as the definitions require (delivered orders only).

## Q2. Acquisition cost (paid channels, Jan–Jun 2026)

| channel | spend | new_customers | cac |
|---|---|---|---|
| Google Ads | 400,000 | 655 | 611 |
| Meta Ads | 547,000 | 675 | 810 |
| Affiliate | 346,000 | 505 | 685 |
| Influencer | 297,000 | 307 | 967 |
| Total paid | 1,590,000 | 2,142 | 742 |

## Q3. Customer value (all channels)

Customers = new customers (users with at least one delivered order). Revenue = delivered orders, Jan–Jun.
*Unknown* = users with a blank acquisition channel, shown for completeness.

| channel | customers | revenue | revenue_per_customer | repeat_customers | repeat_rate_pct |
|---|---|---|---|---|---|
| Google Ads | 655 | 1,513,880 | 2,311 | 378 | 57.7 |
| Meta Ads | 675 | 1,124,892 | 1,667 | 302 | 44.7 |
| Affiliate | 505 | 483,387 | 957 | 41 | 8.1 |
| Influencer | 307 | 877,469 | 2,858 | 224 | 73.0 |
| Organic | 461 | 877,167 | 1,903 | 257 | 55.7 |
| Unknown | 40 | 85,089 | 2,127 | 21 | 52.5 |

## Q4. Return on spend (LTV = revenue per customer × 30%)

| channel | revenue_per_customer | ltv | cac | ltv_cac | rank |
|---|---|---|---|---|---|
| Google Ads | 2,311 | 693 | 611 | 1.14 | 1 |
| Influencer | 2,858 | 857 | 967 | 0.89 | 2 |
| Meta Ads | 1,667 | 500 | 810 | 0.62 | 3 |
| Affiliate | 957 | 287 | 685 | 0.42 | 4 |

- **Best: Google Ads** (LTV:CAC 1.14): a low CAC (₹611) and high value.
- **Worst: Affiliate** (LTV:CAC 0.42): its customers spend only ₹957 and rarely come back.
- No channel reaches 1.0 on six months of revenue, so none has paid back yet. The ranking is the decision input, not the absolute level.

## Q5. Trend: CAC by signup month

New customers are grouped by **signup** month, and CAC = that month's spend ÷ those customers.

| channel | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 |
|---|---|---|---|---|---|---|
| Google Ads | 592 | 621 | 596 | 602 | 644 | 611 |
| Meta Ads | 491 | 618 | 789 | 886 | 958 | 1,115 |
| Affiliate | 709 | 709 | 728 | 633 | 667 | 682 |
| Influencer | 981 | 980 | 913 | 960 | 964 | 1,000 |

| channel | cac_2026-01 | cac_2026-06 | change_inr | change_pct | spend_2026-01 | spend_2026-06 | new_customers_2026-01 | new_customers_2026-06 |
|---|---|---|---|---|---|---|---|---|
| Meta Ads | 491 | 1,115 | 624 | 127.2 | 54,000 | 116,000 | 110 | 104 |
| Google Ads | 592 | 611 | 19 | 3.2 | 74,000 | 55,000 | 125 | 90 |
| Influencer | 981 | 1,000 | 19 | 2.0 | 51,000 | 52,000 | 52 | 52 |
| Affiliate | 709 | 682 | -27 | -3.9 | 61,000 | 45,000 | 86 | 66 |

**Meta Ads is getting more expensive**: its CAC went from ₹491 in January to ₹1,115 in June, **+₹624 (+127.2%)**. Spend more than doubled (₹54,000 → ₹116,000), but new customers did not grow (110 → 104). The other channels moved within ±4%.

Marginal view (Q1 vs Q2): what did the *extra* spend buy?

| channel | q1_spend | q2_spend | q1_customers | q2_customers | extra_spend | extra_customers | marginal_cac |
|---|---|---|---|---|---|---|---|
| Google Ads | 195,000 | 205,000 | 324 | 331 | 10,000 | 7 | 1,429 |
| Meta Ads | 208,000 | 339,000 | 329 | 346 | 131,000 | 17 | 7,706 |
| Affiliate | 176,000 | 170,000 | 246 | 259 | -6,000 | 13 | - |
| Influencer | 143,000 | 154,000 | 149 | 158 | 11,000 | 9 | 1,222 |

Caveat: June sign-ups have had less time to place a first order, so June CAC is slightly overstated for **every** channel. That cannot explain Meta's steady rise from February onward.

## Q6. Sanity check: Google Ads CAC = ₹611

How I verified it:
1. **Independent re-computation.** `src/urbancart/sanity.py` recomputes it in pandas directly from the raw CSVs, sharing no code with the SQL path: drop exact duplicate orders, drop `@urbancart.in` users, keep delivered orders, count distinct Google users = 655, and ₹400,000 ÷ 655 = ₹611. It matches the SQL value exactly.
2. **Control totals.** Spend across channels equals the raw file (₹1,590,000, about ₹15.9 lakh, in line with the brief's "about ₹16 lakh"). Customers across all channels, Unknown included, equal the distinct delivered buyers. Monthly customers add up to the period total. Channel revenue equals total delivered revenue.
3. **Hand check.** In the raw `users.csv` there are 1,100 Google Ads users, none of them QA accounts. 655 of them have at least one delivered order (59.5% conversion, in line with the other channels' 42–56%). 400,000 ÷ 655 = 610.69.

| check | warehouse_sql | independent | result |
|---|---|---|---|
| Google Ads spend (SQL vs pandas) | 400,000 | 400,000 | OK |
| Google Ads new customers (SQL vs pandas) | 655 | 655 | OK |
| Google Ads CAC (SQL vs pandas) | 610.69 | 610.69 | OK |
| Google Ads LTV:CAC (SQL vs pandas) | 1.14 | 1.14 | OK |
| Meta Ads LTV:CAC (SQL vs pandas) | 0.62 | 0.62 | OK |
| Affiliate LTV:CAC (SQL vs pandas) | 0.42 | 0.42 | OK |
| Influencer LTV:CAC (SQL vs pandas) | 0.89 | 0.89 | OK |
| Total paid spend vs raw file | 1,590,000 | 1,590,000 | OK |
| Sum of channel customers = distinct delivered buyers | 2,643 | 2,643 | OK |
| Monthly new customers sum to period total (paid) | 2,142 | 2,142 | OK |
| Sum of channel revenue = delivered revenue | 4,961,884 | 4,961,884 | OK |

## Appendix: 20% cut scenario used in the Part 2 memo (quarterly, against the Q2 run-rate)

| channel | q2_spend | cut_inr | cut_pct | next_q_spend | customers_forgone_est |
|---|---|---|---|---|---|
| Google Ads | 205,000 | 0 | 0.0 | 205,000 | 0 |
| Meta Ads | 339,000 | 131,000 | 38.6 | 208,000 | 134 |
| Affiliate | 170,000 | 43,000 | 25.3 | 127,000 | 66 |
| Influencer | 154,000 | 0 | 0.0 | 154,000 | 0 |
| Total paid | 868,000 | 174,000 | 20.0 | 694,000 | 199 |

`customers_forgone_est` uses the **average** Q2 CAC, a pessimistic upper bound. For Meta, the extra Q2 spend bought customers at a marginal CAC of about ₹7,706, so the real loss from returning Meta to its Q1 level is likely much smaller.
