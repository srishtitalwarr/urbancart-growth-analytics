-- Clean layer. Each rule here matches a check in cleaning.DQ_CHECKS.
-- {test_email_domain} and {unknown_channel} are filled in by cleaning.py.

-- Users with test accounts still in. Used only to measure the impact of removing them.
CREATE OR REPLACE TABLE users_incl_test AS
SELECT
    user_id,
    signup_date,
    city,
    coalesce(acquisition_channel, '{unknown_channel}') AS acquisition_channel,
    email,
    email LIKE '%{test_email_domain}'                  AS is_test_account
FROM stg_users
WHERE user_id IS NOT NULL AND signup_date IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY user_id ORDER BY signup_date) = 1;

-- Orders: drop exact duplicate rows, then any order_id still repeated
-- (keep the first row), and orders that are untyped or orphaned.
CREATE OR REPLACE TABLE orders_incl_test AS
SELECT o.*
FROM (SELECT DISTINCT * FROM stg_orders) o
JOIN users_incl_test u USING (user_id)
WHERE o.order_id IS NOT NULL
  AND o.order_date IS NOT NULL
  AND o.order_value > 0
  AND o.status IN ('delivered', 'cancelled', 'returned')
QUALIFY row_number() OVER (PARTITION BY o.order_id ORDER BY o.order_date) = 1;

CREATE OR REPLACE TABLE users_clean AS
SELECT * EXCLUDE (is_test_account) FROM users_incl_test WHERE NOT is_test_account;

CREATE OR REPLACE TABLE orders_clean AS
SELECT o.* FROM orders_incl_test o JOIN users_clean USING (user_id);

CREATE OR REPLACE TABLE spend_clean AS
SELECT month, channel, spend_inr
FROM stg_spend
WHERE channel IS NOT NULL AND spend_inr IS NOT NULL AND spend_inr >= 0;
