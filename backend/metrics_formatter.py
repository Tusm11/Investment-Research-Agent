"""
Format financial metrics with correct units and handle N/A values.

Rules:
- Never display 0 for missing data - use N/A instead
- Use correct currency units (₹ for rupees)
- Format large numbers with comma separators
- Handle percentages consistently
- Ratios should show 2 decimal places
"""

import math
from typing import Optional, Union


def is_valid_number(value) -> bool:
    """Check if value is a valid numeric value (not None, not NaN)."""
    if value is None:
        return False
    try:
        num = float(value)
        return not (math.isnan(num) or math.isinf(num))
    except (ValueError, TypeError):
        return False


def format_currency(value: Optional[Union[int, float]], unit: str = "₹") -> str:
    """
    Format currency value.
    
    Args:
        value: Numeric value or None
        unit: Currency symbol (default: ₹ for rupees)
    
    Returns:
        Formatted string with thousand separators, or "N/A"
    """
    if not is_valid_number(value):
        return "N/A"
    
    num = float(value)
    
    # Handle large numbers with abbreviations
    if abs(num) >= 1e9:
        return f"{unit}{num/1e9:.2f}B"
    elif abs(num) >= 1e7:  # Crore
        return f"{unit}{num/1e7:.2f}Cr"
    elif abs(num) >= 1e5:  # Lakh
        return f"{unit}{num/1e5:.2f}L"
    else:
        return f"{unit}{num:,.2f}"


def format_ratio(value: Optional[Union[int, float]], decimals: int = 2) -> str:
    """
    Format ratio (P/E, P/B, Debt/Equity, etc).
    
    Args:
        value: Numeric value or None
        decimals: Decimal places (default: 2)
    
    Returns:
        Formatted ratio or "N/A"
    """
    if not is_valid_number(value):
        return "N/A"
    
    num = float(value)
    
    # Check for absurd values (raw rupees instead of ratio)
    if abs(num) > 1e6:
        return "N/A"
    
    return f"{num:.{decimals}f}"


def format_percentage(value: Optional[Union[int, float]], decimals: int = 2) -> str:
    """
    Format percentage value.
    
    Args:
        value: Decimal value (0.15 = 15%) or already a percentage (15)
        decimals: Decimal places (default: 2)
    
    Returns:
        Formatted percentage or "N/A"
    """
    if not is_valid_number(value):
        return "N/A"
    
    num = float(value)
    
    # If value is between -1 and 1, assume it's decimal (0.15)
    if -1 <= num <= 1:
        return f"{num * 100:.{decimals}f}%"
    # Otherwise assume it's already percentage
    else:
        return f"{num:.{decimals}f}%"


def format_market_cap(value: Optional[Union[int, float]]) -> str:
    """
    Format market cap (usually very large number).
    
    Args:
        value: Market cap value
    
    Returns:
        Formatted market cap or "N/A"
    """
    if not is_valid_number(value):
        return "N/A"
    
    num = float(value)
    
    # Market cap is usually in rupees, convert to Cr or L
    if abs(num) >= 1e8:  # >= 1 Crore
        cr = num / 1e7
        if cr >= 100000:  # >= 1 Lakh Cr
            return f"₹{cr/100000:.2f}L Cr"
        elif cr >= 1000:  # >= 1K Cr
            return f"₹{cr/1000:.2f}K Cr"
        else:
            return f"₹{cr:.2f}Cr"
    else:
        return format_currency(num)


def format_financial_metric(
    metric_name: str,
    value: Optional[Union[int, float]],
    default: str = "N/A"
) -> str:
    """
    Format a financial metric based on its name.
    
    Args:
        metric_name: Name of metric (case-insensitive)
        value: Numeric value
        default: Fallback if value is N/A
    
    Returns:
        Formatted metric value
    """
    metric = metric_name.lower()
    
    if not is_valid_number(value):
        return default
    
    # Percentages
    if any(p in metric for p in ["yield", "margin", "growth", "return", "change"]):
        return format_percentage(value)
    
    # Ratios
    if any(r in metric for r in ["p/e", "pe_ratio", "p/b", "pb_ratio", "debt", "current_ratio", "quick_ratio", "cash_ratio", "roe", "roa", "roce"]):
        return format_ratio(value)
    
    # Currency - Market Cap and Price
    if any(c in metric for c in ["market_cap", "price", "target", "revenue", "earnings", "cash", "cash flow"]):
        return format_currency(value)
    
    # Default to ratio formatting
    return format_ratio(value)


def validate_and_format_metrics(metrics: dict) -> dict:
    """
    Take a metrics dictionary and return formatted version with N/A for missing values.
    
    Args:
        metrics: Dictionary of {metric_name: value}
    
    Returns:
        Dictionary of {metric_name: formatted_string}
    """
    formatted = {}
    
    for key, value in metrics.items():
        formatted[key] = format_financial_metric(key, value)
    
    return formatted


def normalize_metric_value(metric_name: str, value: Optional[Union[int, float]]) -> Optional[float]:
    """
    Normalize metric value for internal calculations.
    Returns None if value is invalid (instead of 0).
    
    Args:
        metric_name: Name of metric
        value: Raw value
    
    Returns:
        Normalized float or None
    """
    if not is_valid_number(value):
        return None
    
    num = float(value)
    
    # For percentages, if value > 1, assume it's already a percentage
    if any(p in metric_name.lower() for p in ["yield", "margin", "growth", "return"]):
        if num > 1:
            # Already percentage, convert to decimal
            return num / 100
        else:
            # Already decimal
            return num
    
    return num


if __name__ == "__main__":
    # Test cases
    print("Currency formatting:")
    print(f"  100: {format_currency(100)}")
    print(f"  1000000: {format_currency(1000000)}")
    print(f"  100000000: {format_currency(100000000)}")
    print(f"  None: {format_currency(None)}")
    
    print("\nRatio formatting:")
    print(f"  20.5: {format_ratio(20.5)}")
    print(f"  1.2: {format_ratio(1.2)}")
    print(f"  None: {format_ratio(None)}")
    
    print("\nPercentage formatting:")
    print(f"  0.25: {format_percentage(0.25)}")
    print(f"  25: {format_percentage(25)}")
    print(f"  None: {format_percentage(None)}")
    
    print("\nMarket cap formatting:")
    print(f"  500000000: {format_market_cap(500000000)}")
    print(f"  50000000000: {format_market_cap(50000000000)}")
    
    print("\nMetric formatting:")
    print(f"  pe_ratio=20.5: {format_financial_metric('pe_ratio', 20.5)}")
    print(f"  dividend_yield=0.03: {format_financial_metric('dividend_yield', 0.03)}")
    print(f"  market_cap=100000000: {format_financial_metric('market_cap', 100000000)}")
    print(f"  revenue_growth=None: {format_financial_metric('revenue_growth', None)}")
