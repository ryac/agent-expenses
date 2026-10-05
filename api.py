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
from agents.mcp import MCPServerStdio

load_dotenv()

app = FastAPI(title="Expenses API", version="0.1.0")

DB_PATH = "expenses.duckdb"
MAX_ROWS = 200
MAX_TURNS = 5
SANDBOX_PATH = os.path.abspath(os.path.join(os.getcwd(), "sandbox"))
os.makedirs(SANDBOX_PATH, exist_ok=True)


def _connect() -> duckdb.DuckDBPyConnection:
    """Connect to DuckDB with read-only access."""
    return duckdb.connect(
        DB_PATH,
        read_only=True,
        config={"enable_external_access": False},
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
    q = query.strip().rstrip(";").strip()
    if not q.lower().startswith(("select", "with")) or ";" in q:
        return json.dumps({"error": "Only a single SELECT or WITH statement is allowed."})

    con = _connect()
    try:
        cur = con.execute(q)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        return json.dumps(
            {
                "columns": columns,
                "rows": [list(r) for r in rows[:MAX_ROWS]],
                "truncated": truncated,
            },
            default=str,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        con.close()


class AnalysisRequest(BaseModel):
    task: str


class AnalysisResponse(BaseModel):
    status: str
    result: str
    file_path: str | None = None
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

The current datetime is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        # Set up MCP server for filesystem access
        # files_params = {
        #     "command": "npx",
        #     "args": ["-y", "@modelcontextprotocol/server-filesystem", SANDBOX_PATH],
        # }

        # async with MCPServerStdio(
        #     params=files_params, client_session_timeout_seconds=60
        # ) as mcp_server_files:
        #     agent = Agent(
        #         name="Expenses Agent",
        #         model="gpt-6.1-sol",
        #         instructions=instructions,
        #         tools=[run_sql],
        #         mcp_servers=[mcp_server_files],
        #     )

        #     result = await Runner.run(agent, request.task, max_turns=MAX_TURNS)

        agent = Agent(
            name="Expenses Agent",
            model="gpt-6.1-sol",
            instructions=instructions,
            tools=[run_sql],
        )

        with trace("Finance Analysis"):
            result = await Runner.run(agent, request.task, max_turns=MAX_TURNS)

        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(SANDBOX_PATH, f"analysis_{timestamp}.md")

        # Save result to file
        with open(output_file, "w") as f:
            f.write(result.final_output)

        return AnalysisResponse(
            status="success",
            result=result.final_output,
            file_path=output_file,
            timestamp=timestamp,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing expenses: {str(e)}",
        )


@app.get("/api/results/{filename}")
async def get_result_file(filename: str):
    """Download a previously generated analysis file."""
    file_path = os.path.join(SANDBOX_PATH, filename)

    # Security: prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(SANDBOX_PATH)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
