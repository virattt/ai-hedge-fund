"""Map Financial Datasets line-item names to US-GAAP XBRL concepts in Finnhub reports."""

from __future__ import annotations

LINE_ITEM_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap_Revenues",
        "us-gaap_SalesRevenueNet",
    ],
    "net_income": ["us-gaap_NetIncomeLoss"],
    "gross_profit": ["us-gaap_GrossProfit"],
    "operating_income": ["us-gaap_OperatingIncomeLoss"],
    "ebit": ["us-gaap_OperatingIncomeLoss"],
    "ebitda": ["us-gaap_OperatingIncomeLoss"],
    "earnings_per_share": [
        "us-gaap_EarningsPerShareDiluted",
        "us-gaap_EarningsPerShareBasic",
    ],
    "free_cash_flow": [],
    "capital_expenditure": [
        "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment",
    ],
    "depreciation_and_amortization": [
        "us-gaap_DepreciationDepletionAndAmortization",
        "us-gaap_DepreciationAndAmortization",
    ],
    "total_assets": ["us-gaap_Assets"],
    "total_liabilities": ["us-gaap_Liabilities"],
    "shareholders_equity": [
        "us-gaap_StockholdersEquity",
        "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "current_assets": ["us-gaap_AssetsCurrent"],
    "current_liabilities": ["us-gaap_LiabilitiesCurrent"],
    "cash_and_equivalents": [
        "us-gaap_CashAndCashEquivalentsAtCarryingValue",
        "us-gaap_CashCashEquivalentsAndShortTermInvestments",
    ],
    "total_debt": [
        "us-gaap_LongTermDebtAndCapitalLeaseObligations",
        "us-gaap_LongTermDebt",
        "us-gaap_DebtCurrent",
    ],
    "outstanding_shares": [
        "us-gaap_CommonStockSharesOutstanding",
        "us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
        "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "research_and_development": ["us-gaap_ResearchAndDevelopmentExpense"],
    "interest_expense": ["us-gaap_InterestExpense"],
    "dividends_and_other_cash_distributions": [
        "us-gaap_PaymentsOfDividends",
        "us-gaap_PaymentsOfDividendsCommonStock",
    ],
    "issuance_or_purchase_of_equity_shares": [
        "us-gaap_PaymentsForRepurchaseOfCommonStock",
        "us-gaap_ProceedsFromIssuanceOfCommonStock",
    ],
    "book_value_per_share": [],
    "working_capital": [],
    "operating_expense": ["us-gaap_OperatingExpenses"],
    "gross_margin": [],
    "operating_margin": [],
    "debt_to_equity": [],
    "return_on_invested_capital": [],
}


def extract_concept_value(report: dict, concepts: list[str]) -> float | None:
    """Find the first matching concept value across ic/bs/cf sections."""
    for section in ("ic", "bs", "cf"):
        for item in report.get(section, []):
            concept = item.get("concept", "")
            if concept in concepts:
                value = item.get("value")
                if value is not None:
                    return float(value)
    return None


def compute_free_cash_flow(report: dict) -> float | None:
    operating_cf = extract_concept_value(
        report,
        [
            "us-gaap_NetCashProvidedByUsedInOperatingActivities",
            "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ],
    )
    capex = extract_concept_value(
        report,
        ["us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"],
    )
    if operating_cf is None:
        return None
    if capex is None:
        return operating_cf
    return operating_cf - abs(capex)


def extract_line_item(report: dict, line_item: str) -> float | None:
    if line_item == "free_cash_flow":
        return compute_free_cash_flow(report)
    concepts = LINE_ITEM_CONCEPTS.get(line_item, [])
    if not concepts:
        return None
    return extract_concept_value(report, concepts)
