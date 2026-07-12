import csv
import io
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.backend.repositories.holdings_repository import HoldingsRepository
from app.backend.models.holdings import HoldingImportRow


class HoldingsService:
    def __init__(self, db: Session):
        self.repo = HoldingsRepository(db)

    def parse_csv_text(self, csv_text: str, portfolio_override: Optional[str] = None) -> tuple[list[HoldingImportRow], list[str]]:
        """Parse AJ Bell-style CSV/tab-separated text into holding rows."""
        rows: list[HoldingImportRow] = []
        errors: list[str] = []

        lines = csv_text.strip().splitlines()
        if not lines:
            errors.append("No data provided")
            return rows, errors

        # Detect delimiter
        first_line = lines[0]
        if "\t" in first_line:
            delimiter = "\t"
        elif "," in first_line:
            delimiter = ","
        else:
            delimiter = ","

        reader = csv.reader(io.StringIO(csv_text.strip()), delimiter=delimiter)
        all_rows = list(reader)

        if not all_rows:
            errors.append("No data found")
            return rows, errors

        # Try to detect header row
        header = [col.strip().lower() for col in all_rows[0]]
        data_rows = all_rows[1:] if _looks_like_header(header) else all_rows

        # Map column indices
        col_map = _map_columns(header) if _looks_like_header(header) else None

        for i, row in enumerate(data_rows, start=1):
            try:
                if not any(cell.strip() for cell in row):
                    continue
                parsed = _parse_row(row, col_map, portfolio_override)
                if parsed:
                    rows.append(parsed)
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        return rows, errors

    def import_holdings(self, portfolio_name: str, rows: list[HoldingImportRow]) -> int:
        """Import parsed rows into the database."""
        count = 0
        for row in rows:
            # Use per-row portfolio if available, otherwise use the provided portfolio_name
            effective_portfolio = row.portfolio or portfolio_name
            self.repo.create(
                portfolio_name=effective_portfolio,
                ticker=row.ticker,
                investment_name=row.investment_name,
                quantity=row.quantity,
                buy_price=row.buy_price,
                cost_basis=row.cost_basis,
                currency=row.currency,
            )
            count += 1
        return count


def _looks_like_header(cols: list[str]) -> bool:
    keywords = {"ticker", "symbol", "stock", "name", "investment", "holding",
                "quantity", "qty", "units", "shares", "price", "cost", "value",
                "currency", "ccy", "fund", "sedol", "isin", "portfolio",
                "valuation currency", "market currency"}
    return any(kw in col for col in cols for kw in keywords)


def _map_columns(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for i, col in enumerate(header):
        # Ticker column — match "ticker" but NOT "ticker" as substring of other words
        if col in ("ticker", "symbol", "epic", "code"):
            mapping["ticker"] = i
        # Investment name
        elif col in ("investment", "name", "holding", "fund", "stock") or col == "investment":
            mapping["investment_name"] = i
        # Quantity
        elif any(k in col for k in ("quantity", "qty", "units", "shares")):
            mapping["quantity"] = i
        # Buy price (explicit buy price column)
        elif any(k in col for k in ("buy price", "avg price", "purchase price", "price paid", "cost price")):
            mapping["buy_price"] = i
        # Cost basis — match "cost" but NOT "cost price"
        elif re.search(r"cost", col) and "price" not in col:
            mapping["cost_basis"] = i
        # Currency — prefer "valuation currency" over generic "currency"
        elif "valuation currency" in col:
            mapping["currency"] = i
        elif col in ("currency", "ccy") and "currency" not in mapping:
            mapping["currency"] = i
        # Portfolio column (AJ Bell has this per-row)
        elif col == "portfolio":
            mapping["portfolio"] = i
    return mapping


def _parse_number(value: str) -> float:
    """Parse a number from string, handling currency symbols and commas."""
    cleaned = re.sub(r"[£$€,\s]", "", value.strip())
    if not cleaned or cleaned == "-":
        return 0.0
    return float(cleaned)


def _parse_row(row: list[str], col_map: Optional[dict[str, int]], portfolio_override: Optional[str] = None) -> Optional[HoldingImportRow]:
    """Parse a single row into a HoldingImportRow."""
    if col_map:
        ticker = row[col_map["ticker"]].strip() if "ticker" in col_map else ""
        investment_name = row[col_map["investment_name"]].strip() if "investment_name" in col_map else ticker
        quantity = _parse_number(row[col_map["quantity"]]) if "quantity" in col_map else 0
        buy_price = _parse_number(row[col_map["buy_price"]]) if "buy_price" in col_map else 0
        cost_basis = _parse_number(row[col_map["cost_basis"]]) if "cost_basis" in col_map else None
        currency = row[col_map["currency"]].strip().upper() if "currency" in col_map else "GBP"
        portfolio = row[col_map["portfolio"]].strip() if "portfolio" in col_map else None

        # AJ Bell format: no buy_price column, derive from cost / quantity
        if buy_price == 0 and cost_basis and quantity > 0:
            buy_price = cost_basis / quantity
    else:
        # Positional fallback: ticker, name, quantity, buy_price, [cost_basis], [currency]
        if len(row) < 4:
            return None
        ticker = row[0].strip()
        investment_name = row[1].strip()
        quantity = _parse_number(row[2])
        buy_price = _parse_number(row[3])
        cost_basis = _parse_number(row[4]) if len(row) > 4 else None
        currency = row[5].strip().upper() if len(row) > 5 else "GBP"
        portfolio = None

    if not ticker or quantity <= 0:
        return None

    if not investment_name:
        investment_name = ticker

    # Clean investment name: strip exchange info like "(NYSE:BRK.B)" for display
    clean_name = re.sub(r"\s*\([A-Z]+:[A-Z0-9.]+\)\s*$", "", investment_name).strip()
    if clean_name:
        investment_name = clean_name

    return HoldingImportRow(
        ticker=ticker.upper(),
        investment_name=investment_name,
        quantity=quantity,
        buy_price=round(buy_price, 4),
        cost_basis=cost_basis,
        currency=currency,
        portfolio=portfolio if not portfolio_override else None,
    )
