"""
Data validation layer for Agent 1 responses.

Transforms silent failures into explicit error states so the pipeline can propagate them
rather than treating empty data as real results.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DataFetchStatus:
    """Marker for data fetch results with status information."""
    
    SUCCESS = "success"
    NO_DATA = "no_data"
    RETRIEVAL_ERROR = "retrieval_error"
    ANALYSIS_ERROR = "analysis_error"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"


def wrap_result(
    status: str,
    data: Optional[Dict[str, Any]] = None,
    error_reason: Optional[str] = None,
    source: Optional[str] = None,
    fetch_time_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Wrap a result with metadata about fetch status.
    
    Returns:
        {
            "status": "success|no_data|retrieval_error|...",
            "data": {...},  # Empty dict if failed
            "error_reason": "Human-readable reason if failed",
            "source": "yfinance|news_api|...",
            "fetch_time_ms": 1234,
            "timestamp": "2026-09-03T...",
        }
    """
    return {
        "status": status,
        "data": data or {},
        "error_reason": error_reason,
        "source": source,
        "fetch_time_ms": fetch_time_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    Quick validation that ticker has expected format.
    
    Returns:
        (is_valid, error_reason)
    """
    if not ticker:
        return False, "Ticker is empty"
    
    if not isinstance(ticker, str):
        return False, f"Ticker must be string, got {type(ticker)}"
    
    if "." not in ticker:
        return False, f"Ticker must include exchange suffix (e.g., TCS.NS), got {ticker}"
    
    parts = ticker.split(".")
    if len(parts) != 2 or len(parts[0]) == 0:
        return False, f"Invalid ticker format: {ticker}"
    
    return True, ""


def validate_price_data(data: Dict[str, Any], ticker: str) -> tuple[bool, str]:
    """
    Validate that price history has reasonable structure.
    
    Returns:
        (is_valid, error_reason)
    """
    if not isinstance(data, dict):
        return False, f"Price data must be dict, got {type(data)}"
    
    if not data:
        # Empty dict is OK - means no data available
        return True, ""
    
    # Check that price history has expected fields
    ohlcv = data.get("ohlcv", [])
    if ohlcv and not isinstance(ohlcv, list):
        return False, f"ohlcv must be list, got {type(ohlcv)}"
    
    current_price = data.get("current_price")
    if current_price is not None:
        try:
            float(current_price)
        except (ValueError, TypeError):
            return False, f"current_price must be numeric, got {current_price}"
    
    return True, ""


def validate_news_data(data: Dict[str, Any], ticker: str) -> tuple[bool, str]:
    """
    Validate that news data has expected structure.
    
    Returns:
        (is_valid, error_reason)
    """
    if not isinstance(data, dict):
        return False, f"News data must be dict, got {type(data)}"
    
    if not data:
        # Empty dict is OK
        return True, ""
    
    articles = data.get("articles", [])
    if not isinstance(articles, list):
        return False, f"articles must be list, got {type(articles)}"
    
    # Each article should have minimal fields
    for i, article in enumerate(articles):
        if not isinstance(article, dict):
            return False, f"Article {i} is not dict: {type(article)}"
        if not article.get("title"):
            return False, f"Article {i} missing title"
    
    return True, ""


def validate_company_info(data: Dict[str, Any], ticker: str) -> tuple[bool, str]:
    """
    Validate that company_info has expected structure.
    
    Returns:
        (is_valid, error_reason)
    """
    if not isinstance(data, dict):
        return False, f"Company info must be dict, got {type(data)}"
    
    if not data:
        # Empty dict means no data available (is OK)
        return True, ""
    
    # At least company_name should be present
    if not data.get("company_name"):
        logger.warning(f"Company info missing company_name for {ticker}")
    
    return True, ""


def validate_analyst_data(data: Dict[str, Any], ticker: str) -> tuple[bool, str]:
    """
    Validate that analyst data has expected structure.
    
    Returns:
        (is_valid, error_reason)
    """
    if not isinstance(data, dict):
        return False, f"Analyst data must be dict, got {type(data)}"
    
    if not data:
        # Empty dict is OK
        return True, ""
    
    # Check numeric fields if present
    target_price = data.get("target_mean_price")
    if target_price is not None:
        try:
            float(target_price)
        except (ValueError, TypeError):
            return False, f"target_mean_price must be numeric, got {target_price}"
    
    return True, ""


def validate_all_data(payload: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Validate entire fetch_all_data payload and add metadata.
    
    Returns updated payload with validation results.
    """
    # First validate ticker
    ticker_valid, ticker_error = validate_ticker(ticker)
    if not ticker_valid:
        return {
            "status": DataFetchStatus.VALIDATION_ERROR,
            "error_reason": f"Invalid ticker: {ticker_error}",
            "ticker": ticker,
        }
    
    # Validate each section
    validators = {
        "price_history": validate_price_data,
        "news": validate_news_data,
        "company_info": validate_company_info,
        "analyst_data": validate_analyst_data,
    }
    
    payload["_validation"] = {
        "ticker": ticker,
        "checks": {},
    }
    
    for section, validator in validators.items():
        section_data = payload.get(section, {})
        is_valid, error = validator(section_data, ticker)
        payload["_validation"]["checks"][section] = {
            "valid": is_valid,
            "error": error,
        }
        if not is_valid:
            logger.error(f"Validation failed for {section}: {error}")
    
    return payload


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test valid result
    result = wrap_result(
        status=DataFetchStatus.SUCCESS,
        data={"articles": [{"title": "Test", "url": "http://test.com"}]},
        source="news_api",
        fetch_time_ms=150.5,
    )
    print(f"Valid result: {result}")
    
    # Test error result
    error_result = wrap_result(
        status=DataFetchStatus.RETRIEVAL_ERROR,
        error_reason="Connection timeout after 5 seconds",
        source="yfinance",
    )
    print(f"Error result: {error_result}")
    
    # Test validation
    ticker_valid, error = validate_ticker("TCS.NS")
    print(f"Ticker valid: {ticker_valid}, error: {error}")
    
    ticker_invalid, error = validate_ticker("INVALID")
    print(f"Ticker invalid: {ticker_invalid}, error: {error}")
