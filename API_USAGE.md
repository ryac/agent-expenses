# Expenses API Usage Guide

## Starting the Server

```bash
uv run python api.py
```

The server will start on `http://localhost:8000`.

You can also use uvicorn directly with auto-reload:

```bash
uv run uvicorn api:app --reload
```

## API Endpoints

### Health Check
```bash
GET /health
```

Returns the server status and current timestamp.

### Analyze Expenses
```bash
POST /api/analyze
Content-Type: application/json

{
  "task": "Your analysis task here"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Review and analyze my 2026 expenses and tell me how much I'\''m spending on average per month. Make a prediction on how much I will spend for the last quarter of the year (Oct - Dec). Give me an idea of how much I will be spending this entire year."
  }'
```

**Response:**
```json
{
  "status": "success",
  "result": "Analysis results as markdown/text...",
  "file_path": "/path/to/sandbox/analysis_20261004_120000.txt",
  "timestamp": "20261004_120000"
}
```

### Get Result File
```bash
GET /api/results/{filename}
```

Download a previously generated analysis file.

**Example:**
```bash
curl http://localhost:8000/api/results/analysis_20261004_120000.txt > result.txt
```

## Using the Python Client

You can use the provided `client_example.py` to interact with the API programmatically:

```python
import asyncio
from client_example import analyze_expenses

async def main():
    result = await analyze_expenses(
        "Review my spending habits over the last 3 months"
    )
    print(result)

asyncio.run(main())
```

Or run the example directly:

```bash
python client_example.py
```

## Example Analysis Tasks

- "Review my spending habits over the last 3 months and provide insights on how I can save money."
- "What are my top spending categories this year?"
- "How much did I spend on groceries in 2025?"
- "Compare my spending between 2025 and 2026."
- "What percentage of my income goes to rent?"

## Interactive API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide interactive documentation where you can test the API directly.

## Notes

- Analysis results are stored in the `sandbox/` directory with timestamped filenames
- The agent has a maximum of 5 turns to complete an analysis
- SQL queries are limited to read-only access for safety
- All monetary amounts are in SGD (Singapore Dollars)
