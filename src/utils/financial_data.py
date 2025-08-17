"""Utilities for safe financial data access."""

from typing import Any, Union, Optional
from src.data.models import LineItem, FinancialMetrics


def safe_get_field(
    data_item: Union[LineItem, FinancialMetrics], 
    field_name: str, 
    default: Any = None
) -> Any:
    """
    Safely get a field from a financial data item with proper fallback.
    
    Args:
        data_item: LineItem or FinancialMetrics object
        field_name: Name of the field to access
        default: Default value if field doesn't exist or is None
        
    Returns:
        Field value or default
    """
    try:
        value = getattr(data_item, field_name, default)
        # Return default for None, NaN, or empty values
        if value is None or (isinstance(value, float) and value != value):  # NaN check
            return default
        return value
    except (AttributeError, TypeError):
        return default


def safe_get_numeric_field(
    data_item: Union[LineItem, FinancialMetrics], 
    field_name: str, 
    default: float = 0.0
) -> float:
    """
    Safely get a numeric field with 0.0 as default.
    
    Args:
        data_item: LineItem or FinancialMetrics object
        field_name: Name of the field to access
        default: Default numeric value (defaults to 0.0)
        
    Returns:
        Numeric field value or default
    """
    value = safe_get_field(data_item, field_name, default)
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def calculate_working_capital_change(
    current_item: LineItem, 
    previous_item: Optional[LineItem] = None
) -> float:
    """
    Calculate working capital change between periods.
    
    Args:
        current_item: Current period financial data
        previous_item: Previous period financial data (optional)
        
    Returns:
        Working capital change (0 if previous period not available)
    """
    if previous_item is None:
        return 0.0
    
    current_wc = (
        safe_get_numeric_field(current_item, 'current_assets') - 
        safe_get_numeric_field(current_item, 'current_liabilities')
    )
    
    previous_wc = (
        safe_get_numeric_field(previous_item, 'current_assets') - 
        safe_get_numeric_field(previous_item, 'current_liabilities')
    )
    
    return current_wc - previous_wc


def calculate_shareholders_equity(data_item: Union[LineItem, FinancialMetrics]) -> float:
    """
    Calculate shareholders equity from total assets and liabilities.
    
    Args:
        data_item: Financial data item
        
    Returns:
        Shareholders equity or 0 if cannot be calculated
    """
    total_assets = safe_get_numeric_field(data_item, 'total_assets')
    total_liabilities = safe_get_numeric_field(data_item, 'total_liabilities')
    
    if total_assets > 0 and total_liabilities >= 0:
        return total_assets - total_liabilities
    return 0.0


def validate_required_fields(
    data_item: Union[LineItem, FinancialMetrics], 
    required_fields: list[str]
) -> tuple[bool, list[str]]:
    """
    Validate that required fields are present and not None.
    
    Args:
        data_item: Financial data item to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, missing_fields)
    """
    missing_fields = []
    
    for field in required_fields:
        value = safe_get_field(data_item, field)
        if value is None:
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields