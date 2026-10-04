# schema_comments.py
import duckdb

DB_PATH = "expenses.duckdb"

TABLE_COMMENT = (
    "Personal expense transactions, one row per transaction, loaded from monthly "
    "CSV files covering roughly 2016-2026. Used to better understand spending "
    "habits and identify opportunities to save money."
)

COLUMN_COMMENTS = {
    "Date": "The date the transaction occurred.",
    "Type": (
        "Spending category of the transaction (e.g. Rent, Food, Groceries, "
        "Entertainment). Use exact values in filters."
    ),
    "Description": (
        "Free-text description of the transaction, e.g. merchant or item name. "
        "Use ILIKE '%term%' to search."
    ),
    "Cost": (
        "Transaction amount in Singapore Dollars (SGD). Positive = money spent, "
        "negative = money received (e.g. refunds)."
    ),
    "filename": (
        "Path of the source CSV file this row was loaded from. Ingestion metadata "
        "only, not a transaction attribute."
    ),
}


def _lit(text: str) -> str:
    """COMMENT ON doesn't accept bound parameters, so escape quotes manually."""
    return "'" + text.replace("'", "''") + "'"


def apply_comments(con: duckdb.DuckDBPyConnection, table: str = "expenses") -> None:
    con.execute(f'COMMENT ON TABLE {table} IS {_lit(TABLE_COMMENT)}')
    for column, comment in COLUMN_COMMENTS.items():
        con.execute(f'COMMENT ON COLUMN {table}."{column}" IS {_lit(comment)}')


if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)  # needs write access, so close other connections first
    apply_comments(con)
    for row in con.execute(
        "SELECT column_name, comment FROM duckdb_columns() WHERE table_name = 'expenses'"
    ).fetchall():
        print(row)
    con.close()