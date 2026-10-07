"""
Example client for the Expenses API.
Shows how to make POST requests to the expense analysis endpoint.
"""

import httpx


async def analyze_expenses(task: str, base_url: str = "http://localhost:8000"):
    """Make an analysis request to the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/api/analyze",
            json={"task": task},
            timeout=300,  # 5 minute timeout for long-running analyses
        )
        response.raise_for_status()
        return response.json()


async def get_result_file(filename: str, base_url: str = "http://localhost:8000"):
    """Download a result file from the API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/api/results/{filename}")
        response.raise_for_status()
        return response.text


async def main():
    """Example usage."""
    # Example analysis task
    task = "Review and analyze my 2026 expenses and tell me how much I'm spending on average per month. Make a prediction on how much I will spend for the last quarter of the year (Oct - Dec). Give me an idea of how much I will be spending this entire year."

    print("Submitting analysis task...")
    result = await analyze_expenses(task)

    print(f"Status: {result['status']}")
    print(f"Timestamp: {result['timestamp']}")
    print("\nAnalysis Result:")
    print(result["result"])

    if result.get("filename"):
        print(f"\nResult saved to sandbox/{result['filename']} (download: {result['download_url']})")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
