import duckdb
from schema_comments import apply_comments

con = duckdb.connect("expenses.duckdb")
con.execute("""
    CREATE OR REPLACE TABLE expenses AS
    SELECT *
    FROM read_csv(
        'data/*.csv',
        union_by_name = true,
        filename = true,
        header = true,
        types={'Date': 'DATE'}
    )
""")
print(con.execute("SELECT count(*) FROM expenses").fetchone())
print(con.execute("SELECT filename, count(*) FROM expenses GROUP BY 1 ORDER BY 1").fetchall())
apply_comments(con)
con.close()
