"""Load the raw CSVs into DuckDB, run the data-quality checks, and build clean tables and marts.

The DQ checks are declarative: each one is a SQL count of affected rows plus the
handling rule applied in sql/02_clean.sql. The same list runs in the daily
pipeline, where a non-zero count on a check marked `blocking` fails the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from . import config


@dataclass(frozen=True)
class DQCheck:
    issue: str
    table: str
    count_sql: str
    handling: str
    blocking: bool = False  # True means the pipeline should stop rather than auto-fix


DQ_CHECKS: list[DQCheck] = [
    DQCheck(
        "Exact duplicate order rows (same order_id and identical values)",
        "orders",
        "SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM stg_orders)) FROM stg_orders",
        "Removed the extra copies and kept one row per order_id.",
    ),
    DQCheck(
        "Internal QA/test accounts (email ends with {domain})",
        "users",
        "SELECT count(*) FROM stg_users WHERE email LIKE '%{domain}'",
        "Excluded these users. They are not real customers.",
    ),
    DQCheck(
        "Orders placed by QA/test accounts",
        "orders",
        "SELECT count(*) FROM (SELECT DISTINCT * FROM stg_orders) "
        "WHERE user_id IN (SELECT user_id FROM stg_users WHERE email LIKE '%{domain}')",
        "Excluded from revenue and customers, together with the test users.",
    ),
    DQCheck(
        "Missing acquisition_channel",
        "users",
        "SELECT count(*) FROM stg_users WHERE acquisition_channel IS NULL",
        "Labelled 'Unknown'. They count in totals but in no channel, and no spend is attributed.",
    ),
    DQCheck(
        "Cancelled or returned orders",
        "orders",
        "SELECT count(*) FROM (SELECT DISTINCT * FROM stg_orders) WHERE status <> 'delivered'",
        "Kept in the table, but excluded from revenue and customer counts (definition).",
    ),
    DQCheck(
        "Same order_id with conflicting values",
        "orders",
        "SELECT count(*) FROM (SELECT order_id FROM (SELECT DISTINCT * FROM stg_orders) "
        "GROUP BY order_id HAVING count(*) > 1)",
        "Would keep the earliest row. None found.",
    ),
    DQCheck(
        "Duplicate user_id",
        "users",
        "SELECT count(*) - count(DISTINCT user_id) FROM stg_users",
        "Would keep the earliest signup. None found.",
    ),
    DQCheck(
        "Unparseable id, date or amount",
        "all",
        "SELECT (SELECT count(*) FROM stg_users WHERE user_id IS NULL OR signup_date IS NULL) "
        "+ (SELECT count(*) FROM stg_orders WHERE order_id IS NULL OR user_id IS NULL "
        "   OR order_date IS NULL OR order_value IS NULL) "
        "+ (SELECT count(*) FROM stg_spend WHERE spend_inr IS NULL OR channel IS NULL)",
        "Would be dropped. None found.",
        blocking=True,
    ),
    DQCheck(
        "Orders whose user_id is not in users (orphans)",
        "orders",
        "SELECT count(*) FROM stg_orders WHERE user_id NOT IN (SELECT user_id FROM stg_users)",
        "Would be dropped. None found.",
    ),
    DQCheck(
        "Order dated before the user's signup date",
        "orders",
        "SELECT count(*) FROM stg_orders o JOIN stg_users u USING (user_id) "
        "WHERE o.order_date < u.signup_date",
        "Would be investigated. None found.",
    ),
    DQCheck(
        "Dates outside the Jan to Jun 2026 window",
        "users/orders",
        "SELECT (SELECT count(*) FROM stg_users WHERE signup_date NOT BETWEEN DATE '{start}' AND DATE '{end}') "
        "+ (SELECT count(*) FROM stg_orders WHERE order_date NOT BETWEEN DATE '{start}' AND DATE '{end}')",
        "Would be excluded. None found.",
    ),
    DQCheck(
        "Zero, negative or unknown-status orders",
        "orders",
        "SELECT count(*) FROM stg_orders WHERE order_value <= 0 "
        "OR status NOT IN ('delivered', 'cancelled', 'returned')",
        "Would be dropped. None found.",
    ),
    DQCheck(
        "Spend file: missing channel x month cells",
        "marketing_spend",
        "SELECT 24 - count(DISTINCT (month, channel)) FROM stg_spend",
        "Would block CAC for that month. None found (4 channels x 6 months).",
        blocking=True,
    ),
]


def _render(sql: str, **params) -> str:
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", str(value))
    return sql


def _run_sql_file(con: duckdb.DuckDBPyConnection, name: str, **params) -> None:
    con.execute(_render((config.SQL_DIR / name).read_text(encoding="utf-8"), **params))


def run_dq_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return one row per check: issue, table, rows affected, handling, status."""
    params = dict(domain=config.TEST_EMAIL_DOMAIN, start=config.PERIOD_START, end=config.PERIOD_END)
    rows = []
    for check in DQ_CHECKS:
        n = con.execute(_render(check.count_sql, **params)).fetchone()[0]
        rows.append({
            "issue": _render(check.issue, **params),
            "table": check.table,
            "rows_affected": int(n),
            "handling": check.handling,
            "status": "FOUND" if n else "PASS",
            "blocking": check.blocking,
        })
    return pd.DataFrame(rows)


def build_warehouse(
    db_path: str | Path = ":memory:", data_dir: str | Path = config.DATA_DIR
) -> tuple[duckdb.DuckDBPyConnection, pd.DataFrame]:
    """Build raw → staging → clean → marts. Returns the connection and the DQ log."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    _run_sql_file(con, "01_staging.sql", data_dir=Path(data_dir).as_posix())

    dq_log = run_dq_checks(con)
    blocking = dq_log[dq_log["blocking"] & (dq_log["rows_affected"] > 0)]
    if not blocking.empty:
        raise ValueError(f"Blocking data-quality failures:\n{blocking.to_string()}")

    _run_sql_file(con, "02_clean.sql",
                  test_email_domain=config.TEST_EMAIL_DOMAIN, unknown_channel=config.UNKNOWN_CHANNEL)
    _run_sql_file(con, "03_marts.sql", users="users_clean", orders="orders_clean",
                  suffix="", margin=config.CONTRIBUTION_MARGIN)
    # Same marts with the QA accounts left in, to show their impact.
    _run_sql_file(con, "03_marts.sql", users="users_incl_test", orders="orders_incl_test",
                  suffix="_incl_test", margin=config.CONTRIBUTION_MARGIN)

    con.register("dq_log_df", dq_log)
    con.execute("CREATE OR REPLACE TABLE dq_log AS SELECT * FROM dq_log_df")
    con.unregister("dq_log_df")
    con.execute("CREATE OR REPLACE TABLE meta AS SELECT max(order_date) AS data_as_of, now() AS built_at FROM orders_clean")
    return con, dq_log
