# src/tools/utils.py

def _safe_search_line_items(ticker: str, fields: list[str], financials: dict) -> dict:
    """
    Safely search financial line items for a given ticker and list of fields.
    Handles missing data, empty lists, and ensures each field is processed individually.
    """
    results = {}
    if not financials or not fields:
        return results

    for field in fields:
        # Ensure field is a string
        if not isinstance(field, str):
            continue
        # Safely get the field value from financials
        results[field] = financials.get(field, None)
    return results