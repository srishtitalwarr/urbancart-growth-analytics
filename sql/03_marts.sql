-- Marts: the only tables that reports, the dashboard and the Q&A read.
-- {users}, {orders}, {suffix} and {margin} are filled in by cleaning.py, so the
-- same logic can run with and without the test accounts.

-- One row per new customer (a user with at least one delivered order).
CREATE OR REPLACE TABLE mart_customers{suffix} AS
SELECT
    u.user_id,
    u.acquisition_channel                    AS channel,
    strftime(u.signup_date, '%Y-%m')         AS signup_month,
    count(*)                                 AS delivered_orders,
    sum(o.order_value)                       AS revenue
FROM {users} u
JOIN {orders} o USING (user_id)
WHERE o.status = 'delivered'
GROUP BY u.user_id, u.acquisition_channel, u.signup_date;

-- Channel KPIs for the full period. Values are unrounded; presentation rounds them.
CREATE OR REPLACE TABLE mart_channel_kpis{suffix} AS
WITH spend AS (
    SELECT channel, sum(spend_inr) AS spend FROM spend_clean GROUP BY channel
),
cust AS (
    SELECT
        channel,
        count(*)                                   AS new_customers,
        sum(revenue)                               AS revenue,
        count(*) FILTER (WHERE delivered_orders >= 2) AS repeat_customers
    FROM mart_customers{suffix}
    GROUP BY channel
)
SELECT
    coalesce(c.channel, s.channel)                 AS channel,
    s.spend IS NOT NULL                            AS is_paid,
    s.spend                                        AS spend,
    coalesce(c.new_customers, 0)                   AS new_customers,
    s.spend / NULLIF(c.new_customers, 0)           AS cac,
    c.revenue                                      AS revenue,
    c.revenue / NULLIF(c.new_customers, 0)         AS revenue_per_customer,
    c.repeat_customers                             AS repeat_customers,
    100.0 * c.repeat_customers / NULLIF(c.new_customers, 0) AS repeat_rate_pct,
    {margin} * c.revenue / NULLIF(c.new_customers, 0)       AS ltv,
    ({margin} * c.revenue / NULLIF(c.new_customers, 0))
        / NULLIF(s.spend / NULLIF(c.new_customers, 0), 0)   AS ltv_cac
FROM cust c
FULL OUTER JOIN spend s ON s.channel = c.channel;

-- Paid channel x signup month: spend, new customers (grouped by signup month), CAC.
CREATE OR REPLACE TABLE mart_channel_monthly{suffix} AS
SELECT
    s.month,
    s.channel,
    s.spend_inr                                    AS spend,
    count(m.user_id)                               AS new_customers,
    s.spend_inr / NULLIF(count(m.user_id), 0)      AS cac
FROM spend_clean s
LEFT JOIN mart_customers{suffix} m
       ON m.channel = s.channel AND m.signup_month = s.month
GROUP BY s.month, s.channel, s.spend_inr;
