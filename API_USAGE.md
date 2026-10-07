# Expenses API Usage Guide

## Starting the Server

```bash
uv run python api.py
```

The server binds to `http://127.0.0.1:8000` (localhost only). To use uvicorn directly with auto-reload:

```bash
uv run uvicorn api:app --reload
```

The model provider is configured in `.env` (`EXPENSES_PROVIDER`, `EXPENSES_MODEL` and the matching API key). See the [README](README.md#quick-start).

## Endpoints

### `GET /health`

Liveness check.

```json
{"status": "healthy", "timestamp": "2026-10-07T12:00:00.123456"}
```

### `POST /api/analyze`

Runs the agent on a question and returns a Markdown analysis.

**Request**

```json
{"task": "What are my top 5 spending categories in 2026?"}
```

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"task": "What are my top 5 spending categories in 2026?"}'
```

**Response (200)**

```json
{
  "status": "success",
  "result": "# Top 5 spending categories ... (Markdown, including the SQL used)\n\n---\nProvider: openai\n\nModel: gpt-4.1\n\nTimestamp: 20261007_120000_123",
  "filename": "analysis_20261007_120000_123.md",
  "download_url": "/api/results/analysis_20261007_120000_123.md",
  "timestamp": "20261007_120000_123"
}
```

- `result` is the full Markdown answer. It includes the original task, the SQL queries used, the assumptions made, and a footer with the provider, model and timestamp.
- The same content is saved to `sandbox/<filename>`. The timestamp has millisecond precision (`YYYYMMDD_HHMMSS_mmm`) so concurrent requests don't collide.
- Requests are synchronous and can take several seconds (typically around 10s, longer for multi-step questions). Use a generous client timeout.

**Errors**

| Status | Cause |
|---|---|
| `400` | Empty or whitespace-only `task` |
| `422` | Malformed request body (missing `task`) |
| `500` | The agent run failed (provider error, rate limit, turn limit exceeded). The response is deliberately generic; details are in `expenses.log` |

### `GET /api/results/{filename}`

Downloads a previously generated analysis (served as `text/markdown`).

```bash
curl http://127.0.0.1:8000/api/results/analysis_20261007_120000_123.md -o result.md
```

| Status | Cause |
|---|---|
| `403` | Path resolves outside the `sandbox/` directory |
| `404` | File not found |

## Python client

`client_example.py` provides async helpers, `analyze_expenses(task)` and `get_result_file(filename)`:

```python
import asyncio
from client_example import analyze_expenses

result = asyncio.run(analyze_expenses("How much did I spend on groceries in 2025?"))
print(result["result"])
print(result["download_url"])
```

Or run the bundled example:

```bash
uv run python client_example.py
```

## Example questions

- "How much did I spend on groceries in 2025?"
- "What are my top spending categories this year?"
- "Compare my spending between 2025 and 2026."
- "What percentage of my 2026 spending went to Entertainment and Travel?"
- "Review my 2026 spending, project Q4, and estimate the full-year total."
- "Where could I cut costs in my Food and Coffee spending?"

The data contains expenses only (no income), in SGD, from 2016 to the latest ingested month. Questions outside that scope are answered with what the data supports, with assumptions stated.

## Interactive documentation

With the server running:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Notes

- The agent has a maximum of 15 turns per request.
- SQL runs through the guardrails in `guardrails.py` against a read-only DuckDB connection, with a 10-second query timeout and a 200-row result cap. See [Guardrails](README.md#guardrails).
- All monetary amounts are in SGD. Positive values are spending; negative values are money received (e.g. refunds).
- To measure the agent's quality against this API, see the [evaluation harness](README.md#evaluation-harness).
