"""Tests for the SQL guardrails: the AST validator and the DuckDB engine settings.

Run with: uv run pytest
"""

import duckdb
import pytest

import api
from guardrails import UnsafeSQLError, validate_sql

ALLOWED = [
    'SELECT sum("Cost") FROM expenses',
    'WITH x AS (SELECT * FROM expenses) SELECT count(*) FROM x',
    "SELECT 1 UNION SELECT 2",
    'SELECT "Type", sum("Cost") FROM expenses GROUP BY 1 ORDER BY 2 DESC LIMIT 5',
]

REJECTED = {
    "stacked statements": "SELECT 1; DROP TABLE expenses",
    "delete": "DELETE FROM expenses",
    "drop": "DROP TABLE expenses",
    "update": 'UPDATE expenses SET "Cost" = 0',
    "attach": "ATTACH 'other.db'",
    "copy": "COPY expenses TO 'out.csv'",
    "pragma": "PRAGMA database_list",
    "set": "SET enable_external_access = true",
    "dml hidden in a CTE": "WITH d AS (DELETE FROM expenses RETURNING *) SELECT * FROM d",
    "table function": "SELECT * FROM read_csv('/etc/passwd')",
    "table function in a join": "SELECT * FROM expenses, read_csv('/etc/passwd')",
    "table function in a subquery": "SELECT * FROM expenses WHERE \"Cost\" > (SELECT count(*) FROM read_csv('/etc/passwd'))",
    "duckdb catalog function": "SELECT * FROM duckdb_tables()",
    "information_schema": "SELECT * FROM information_schema.tables",
    "unknown table": "SELECT * FROM secrets",
    "select into": "SELECT * INTO copy_of_expenses FROM expenses",
    "unparseable": "SELEC FROM WHERE",
}


@pytest.mark.parametrize("sql", ALLOWED)
def test_validator_allows_read_only_queries(sql):
    validate_sql(sql)


@pytest.mark.parametrize("sql", REJECTED.values(), ids=REJECTED.keys())
def test_validator_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


def test_validator_does_not_catch_scalar_file_functions():
    """Documents a known gap: the allowlist only inspects tables, so a file function in a
    scalar position passes validation. The engine-level settings below are what stop it."""
    validate_sql("SELECT read_text('/etc/passwd')")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """Connections built by the real api._connect(), pointed at a throwaway database."""
    db = tmp_path / "test.duckdb"
    setup = duckdb.connect(str(db))
    setup.execute('CREATE TABLE expenses ("Date" DATE, "Type" VARCHAR, "Cost" DOUBLE)')
    setup.execute("INSERT INTO expenses VALUES ('2026-01-01', 'Rent', 100.0)")
    setup.close()
    monkeypatch.setattr(api, "DB_PATH", str(db))
    return api._connect


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM expenses",
        "DROP TABLE expenses",
        "INSERT INTO expenses VALUES ('2026-02-01', 'Rent', 1.0)",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM glob('/etc/*')",
        "SELECT read_text('/etc/passwd')",
        "SET enable_external_access = true",
    ],
)
def test_engine_blocks_unsafe_statements_even_without_the_validator(engine, sql):
    con = engine()
    try:
        with pytest.raises(duckdb.Error):
            con.execute(sql)
    finally:
        con.close()


def test_engine_still_answers_normal_queries(engine):
    con = engine()
    try:
        assert con.execute('SELECT sum("Cost") FROM expenses').fetchone() == (100.0,)
    finally:
        con.close()
