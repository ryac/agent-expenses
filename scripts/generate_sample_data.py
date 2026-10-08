"""Generate synthetic expense CSVs in the same format as the real data.

    uv run python scripts/generate_sample_data.py

Output goes to sample_data/ and is deterministic (fixed seed). The categories and date
range are chosen so the evaluation harness's golden cases have data to run against.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path("sample_data")
SEED = 42

# category -> (transactions per month range, amount range in SGD, description choices)
MONTHLY = {
    "Groceries": ((6, 10), (8, 90), ["NTUC FairPrice", "Cold Storage", "Sheng Siong", "Market"]),
    "Food": ((8, 14), (4, 35), ["Hawker lunch", "Cafe brunch", "Dinner out", "Food delivery"]),
    "Coffee": ((3, 8), (3, 7), ["Flat white", "Iced latte", "Kopi"]),
    "Transportation": ((6, 12), (2, 25), ["MRT", "Bus", "Taxi", "Ride share"]),
    "Entertainment": ((1, 4), (10, 60), ["Cinema", "Concert", "Streaming", "Bowling"]),
    "Misc": ((2, 6), (5, 80), ["Household", "Gift", "Pharmacy", "Haircut"]),
}
FIXED_MONTHLY = {
    "Rent": ("Monthly rent", 2200.0),
    "Health Insurance": ("Health insurance premium", 110.0),
    "Phone": ("Mobile plan", 28.0),
    "Internet": ("Fibre broadband", 32.0),
}


def month_rows(rng: random.Random, year: int, month: int) -> list[tuple]:
    first = date(year, month, 1)
    last = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)

    def random_day() -> date:
        return first + timedelta(days=rng.randint(0, (last - first).days))

    rows = []
    for category, (desc, amount) in FIXED_MONTHLY.items():
        rows.append((first + timedelta(days=1), category, desc, amount))
    for category, ((lo, hi), (amin, amax), descs) in MONTHLY.items():
        for _ in range(rng.randint(lo, hi)):
            rows.append((random_day(), category, rng.choice(descs), round(rng.uniform(amin, amax), 2)))
    if month in (3, 9):
        rows.append((random_day(), "Travel", "Flights and hotel", round(rng.uniform(300, 1100), 2)))
    if month == 6:
        rows.append((random_day(), "Insurance", "Annual insurance premium", 1450.0))
    if month == 8:
        rows.append((random_day(), "Entertainment", "Refund: cancelled event", -45.0))
    return sorted(rows)


def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(exist_ok=True)
    count = 0
    for year, month in [(y, m) for y in (2025, 2026) for m in range(1, 13) if (y, m) <= (2026, 9)]:
        path = OUT_DIR / f"{year % 100:02d}-{month:02d}.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Type", "Description", "Cost"])
            for day, category, desc, cost in month_rows(rng, year, month):
                writer.writerow([f"{day.isoformat()}T08:00:00.000Z", category, desc, f"{cost:.2f}"])
                count += 1
    print(f"Wrote {count} rows to {OUT_DIR}/")


if __name__ == "__main__":
    main()
