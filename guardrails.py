import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"expenses"}
FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop,
    exp.Create, exp.Alter, exp.Merge, exp.Command,
)

class UnsafeSQLError(ValueError):
    pass

def validate_sql(sql: str) -> None:
    """Raise UnsafeSQLError unless sql is one read-only query on allowed tables."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s]
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQLError(f"Could not parse SQL: {e}")

    if len(statements) != 1:
        raise UnsafeSQLError("Exactly one statement is allowed.")

    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise UnsafeSQLError("Only SELECT or WITH ... SELECT is allowed.")

    if any(tree.find_all(*FORBIDDEN)):
        raise UnsafeSQLError("Write or DDL operations are not allowed.")

    cte_names = {cte.alias for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.name not in ALLOWED_TABLES | cte_names:
            raise UnsafeSQLError(f"Table or function not allowed: {table.name or '(table function)'}")