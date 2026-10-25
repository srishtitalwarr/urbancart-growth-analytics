-- Raw layer: load every column as text so that malformed values surface in the
-- DQ checks instead of failing the load. {data_dir} is filled in by cleaning.py.

CREATE OR REPLACE TABLE raw_users AS
SELECT * FROM read_csv('{data_dir}/users.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE raw_orders AS
SELECT * FROM read_csv('{data_dir}/orders.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE raw_spend AS
SELECT * FROM read_csv('{data_dir}/marketing_spend.csv', all_varchar = true, header = true);

-- Staging layer: typed and trimmed, but no rows removed yet.
CREATE OR REPLACE TABLE stg_users AS
SELECT
    TRY_CAST(trim(user_id) AS INTEGER)               AS user_id,
    TRY_CAST(trim(signup_date) AS DATE)              AS signup_date,
    NULLIF(trim(city), '')                           AS city,
    NULLIF(trim(acquisition_channel), '')            AS acquisition_channel,
    lower(NULLIF(trim(email), ''))                   AS email
FROM raw_users;

CREATE OR REPLACE TABLE stg_orders AS
SELECT
    TRY_CAST(trim(order_id) AS INTEGER)              AS order_id,
    TRY_CAST(trim(user_id) AS INTEGER)               AS user_id,
    TRY_CAST(trim(order_date) AS DATE)               AS order_date,
    TRY_CAST(trim(order_value) AS DECIMAL(12, 2))    AS order_value,
    lower(NULLIF(trim(status), ''))                  AS status
FROM raw_orders;

CREATE OR REPLACE TABLE stg_spend AS
SELECT
    trim(month)                                      AS month,
    NULLIF(trim(channel), '')                        AS channel,
    TRY_CAST(trim(spend_inr) AS DECIMAL(14, 2))      AS spend_inr
FROM raw_spend;
