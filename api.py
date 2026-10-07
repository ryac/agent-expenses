import os
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import duckdb
from dotenv import load_dotenv

from agents import Agent, Runner, function_tool, trace
import logging
import threading
from guardrails import validate_sql, UnsafeSQLError
from provider_registry import build_model


load_dotenv(override=True)
logging.basicConfig(level=logging.INFO, filename="expenses.log", format="%(asctime)s %(name)s %(levelname)s %(message)s")

logger = logging.getLogger("expenses.sql")
api_logger = logging.getLogger("expenses.api")

app = FastAPI(title="Expenses API", version="0.1.0")

DB_PATH = "expenses.duckdb"
MAX_ROWS = 200
MAX_TURNS = 15
SANDBOX_PATH = os.path.abspath(os.path.join(os.getcwd(), "sandbox"))
os.makedirs(SANDBOX_PATH, exist_ok=True)


def _connect() -> duckdb.DuckDBPyConnection:
    """Connect to DuckDB with read-only access."""
    return duckdb.connect(
        DB_PATH,
        read_only=True,
        config={"enable_external_access": False, "lock_configuration": True},
    )


def _schema_description() -> str:
    """Get schema description from the database."""
    con = _connect()
    try:
        table_comment = con.execute(
            "SELECT comment FROM duckdb_tables() WHERE table_name = 'expenses'"
        ).fetchone()[0]
        columns = con.execute(
            """
            SELECT column_name, data_type, comment
            FROM duckdb_columns()
            WHERE table_name = 'expenses'
            ORDER BY column_index
            """
        ).fetchall()
        types = [
            r[0]
            for r in con.execute(
                'SELECT DISTINCT "Type" FROM expenses WHERE "Type" IS NOT NULL ORDER BY 1'
            ).fetchall()
        ]
        min_d, max_d = con.execute(
            'SELECT min("Date"), max("Date") FROM expenses'
        ).fetchone()
    finally:
        con.close()

    lines = [f"Table: expenses - {table_comment}", "\nColumns:"]
    lines += [f'- "{name}" ({dtype}): {comment}' for name, dtype, comment in columns]
    lines.append(f'\nValid values for "Type": {", ".join(types)}')
    lines.append(f"\nDate range in data: {min_d} to {max_d}")
    return "\n".join(lines)


@function_tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SQL query against the `expenses` table and return
    the results as JSON. Only a single SELECT (or WITH ... SELECT) statement is
    allowed. Results are capped at 200 rows, so aggregate in SQL (SUM, COUNT,
    GROUP BY) instead of fetching raw rows whenever possible. If the query
    fails, the error message is returned so you can fix the SQL and retry.
    """
    q = query.strip()
    try:
        validate_sql(q)
    except UnsafeSQLError as e:
        logger.warning("REJECTED: %s | %s", e, q)
        return json.dumps({"error": str(e)})

    logger.info("EXECUTING: %s", q)
    con = _connect()
    timer = threading.Timer(10, con.interrupt)  # 10s query timeout
    timer.start()
    try:
        print(f">> running SQL query: {q[:100] if len(q) > 100 else q}")
        cur = con.execute(q)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        res = json.dumps(
            {
                "columns": columns,
                "rows": [list(r) for r in rows[:MAX_ROWS]],
                "truncated": truncated,
            },
            default=str,
        )
        return res
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        timer.cancel()
        con.close()


class AnalysisRequest(BaseModel):
    task: str


class AnalysisResponse(BaseModel):
    status: str
    result: str
    filename: str | None = None
    download_url: str | None = None
    timestamp: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_expenses(request: AnalysisRequest):
    """
    Analyze expenses based on the provided task.

    Example task: "Review and analyze my 2026 expenses and tell me how much I'm spending
    on average per month."
    """
    if not request.task or not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    try:
        instructions = f"""You answer questions about the user's personal expenses by
writing DuckDB SQL and calling the run_sql tool.

{_schema_description()}

Guidelines:
- Costs are in SGD. Positive = money spent, negative = money received (refunds).
- Use exact "Type" values from the list above when filtering.
- Prefer aggregating in SQL over returning raw rows.
- If a query errors or returns something surprising, fix the SQL and retry.
- If results are truncated, say so rather than presenting them as complete.
- State the time period and any assumptions behind your answer.
- Write your answer as a professional looking analysis including the SQL queries you used and any assumptions, in Markdown format.

In the final output, include the original task as well to keep context.

The current datetime is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        agent = Agent(
            name="Expenses Agent",
            model=build_model(),
            instructions=instructions,
            tools=[run_sql],
        )

        with trace("Finance Analysis"):
            result = await Runner.run(agent, request.task, max_turns=MAX_TURNS)

        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # millisecond precision
        output_file = os.path.join(SANDBOX_PATH, f"analysis_{timestamp}.md")

        # Save result to file
        contents = f"{result.final_output}\n\n---\nProvider: {os.getenv('EXPENSES_PROVIDER')}\n\nModel: {os.getenv('EXPENSES_MODEL')}\n\nTimestamp: {timestamp}"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(contents)

        filename = os.path.basename(output_file)
        return AnalysisResponse(
            status="success",
            result=contents,
            filename=filename,
            download_url=f"/api/results/{filename}",
            timestamp=timestamp,
        )

    except Exception:
        api_logger.exception("Analysis failed for task: %r", request.task)
        raise HTTPException(
            status_code=500,
            detail="Error analyzing expenses. Check server logs.",
        )


@app.get("/api/results/{filename}")
async def get_result_file(filename: str):
    """Download a previously generated analysis file."""

    base = Path(SANDBOX_PATH).resolve()
    file_path = (base / filename).resolve()
    if not file_path.is_relative_to(base):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
