"""
Sector-aware metrics selection.

Different sectors require different key metrics for meaningful analysis.
This module detects sector and returns appropriate metrics to display.
"""

from typing import Optional, List, Dict


# Sector definitions with key metrics
SECTOR_METRICS = {
    "FINANCIALS": {
        "name": "Financial Services & Banking",
        "keywords": ["bank", "financial", "insurance", "nbl", "icici", "hdfc", "axis", "kotak", "yes"],
        "primary_metrics": [
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "roa", "label": "ROA", "type": "ratio"},
            {"name": "nim", "label": "Net Interest Margin", "type": "ratio"},
            {"name": "deposits_growth", "label": "Deposit Growth", "type": "percentage"},
            {"name": "credit_growth", "label": "Credit Growth", "type": "percentage"},
            {"name": "npa_ratio", "label": "NPA Ratio", "type": "ratio"},
            {"name": "capital_adequacy", "label": "Capital Adequacy", "type": "ratio"},
        ],
        "watch_metrics": [
            {"name": "casa_ratio", "label": "CASA Ratio", "type": "ratio"},
            {"name": "cost_to_income", "label": "Cost-to-Income", "type": "ratio"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
        ]
    },
    
    "IT": {
        "name": "Information Technology",
        "keywords": ["it", "infosys", "tcs", "wipro", "hcl", "tech", "software"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "eps_growth", "label": "EPS Growth", "type": "percentage"},
            {"name": "net_margin", "label": "Net Margin", "type": "percentage"},
            {"name": "utilization", "label": "Utilization Rate", "type": "percentage"},
        ],
        "watch_metrics": [
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
        ]
    },
    
    "AUTOMOTIVE": {
        "name": "Automotive",
        "keywords": ["auto", "maruti", "bajaj", "hero", "tata", "mahindra", "tvs", "car", "vehicle"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "volume_growth", "label": "Volume Growth", "type": "percentage"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "operating_margin", "label": "Operating Margin", "type": "percentage"},
            {"name": "roce", "label": "ROCE", "type": "ratio"},
            {"name": "export_ratio", "label": "Export Revenue %", "type": "percentage"},
        ],
        "watch_metrics": [
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
            {"name": "market_share", "label": "Market Share", "type": "percentage"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
        ]
    },
    
    "PHARMA": {
        "name": "Pharmaceuticals & Healthcare",
        "keywords": ["pharma", "pharman", "drug", "healthcare", "health", "medical", "cipla", "sunpharma", "lupin"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "net_margin", "label": "Net Margin", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "r_and_d_percent", "label": "R&D % of Revenue", "type": "percentage"},
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
        ],
        "watch_metrics": [
            {"name": "export_revenue", "label": "Export Revenue %", "type": "percentage"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
        ]
    },
    
    "ENERGY": {
        "name": "Oil, Gas & Energy",
        "keywords": ["energy", "oil", "gas", "power", "reliance", "ntpc", "coal"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
            {"name": "net_debt_to_ebitda", "label": "Net Debt/EBITDA", "type": "ratio"},
        ],
        "watch_metrics": [
            {"name": "capex_intensity", "label": "Capex Intensity", "type": "percentage"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
            {"name": "operating_margin", "label": "Operating Margin", "type": "percentage"},
        ]
    },
    
    "CONSUMER": {
        "name": "Consumer Discretionary & FMCG",
        "keywords": ["consumer", "fmcg", "retail", "food", "beverage", "nestle", "britannia", "ipl"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "volume_growth", "label": "Volume Growth", "type": "percentage"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "net_margin", "label": "Net Margin", "type": "percentage"},
            {"name": "brand_value", "label": "Brand Equity Trend", "type": "text"},
        ],
        "watch_metrics": [
            {"name": "market_share_trend", "label": "Market Share Trend", "type": "percentage"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
        ]
    },
    
    "UTILITIES": {
        "name": "Utilities & Infrastructure",
        "keywords": ["utility", "power", "water", "infrastructure", "toll", "airport"],
        "primary_metrics": [
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
            {"name": "interest_coverage", "label": "Interest Coverage", "type": "ratio"},
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
        ],
        "watch_metrics": [
            {"name": "net_debt_to_ebitda", "label": "Net Debt/EBITDA", "type": "ratio"},
            {"name": "capex_intensity", "label": "Capex Intensity", "type": "percentage"},
        ]
    },
    
    "METALS": {
        "name": "Metals & Mining",
        "keywords": ["metal", "mining", "steel", "aluminum", "copper", "tata steel"],
        "primary_metrics": [
            {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
            {"name": "ebitda_margin", "label": "EBITDA Margin", "type": "percentage"},
            {"name": "roe", "label": "ROE", "type": "ratio"},
            {"name": "capex_intensity", "label": "Capex Intensity", "type": "percentage"},
            {"name": "net_debt_to_ebitda", "label": "Net Debt/EBITDA", "type": "ratio"},
            {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
        ],
        "watch_metrics": [
            {"name": "commodity_price_exposure", "label": "Price Exposure", "type": "text"},
            {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
            {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
        ]
    },
}

# Default metrics if sector not identified
DEFAULT_METRICS = [
    {"name": "roe", "label": "ROE", "type": "ratio"},
    {"name": "revenue_growth", "label": "Revenue Growth", "type": "percentage"},
    {"name": "net_margin", "label": "Net Margin", "type": "percentage"},
    {"name": "debt_to_equity", "label": "Debt-to-Equity", "type": "ratio"},
    {"name": "fcf", "label": "Free Cash Flow", "type": "currency"},
    {"name": "dividend_yield", "label": "Dividend Yield", "type": "percentage"},
]


def detect_sector(company_name: str, sector_hint: Optional[str] = None) -> tuple[str, Dict]:
    """
    Detect sector from company name or sector hint.
    
    Args:
        company_name: Company name
        sector_hint: Optional explicit sector name
    
    Returns:
        (sector_key, sector_metrics_dict)
    """
    text = f"{company_name} {sector_hint or ''}".lower()
    
    for sector_key, sector_info in SECTOR_METRICS.items():
        for keyword in sector_info["keywords"]:
            if keyword in text:
                return sector_key, sector_info
    
    # Return default if not matched
    return "DEFAULT", {
        "name": "General",
        "keywords": [],
        "primary_metrics": DEFAULT_METRICS,
        "watch_metrics": [],
    }


def get_sector_metrics(company_name: str, sector_hint: Optional[str] = None) -> Dict:
    """
    Get sector-appropriate metrics for a company.
    
    Returns:
        {
            "sector": "FINANCIALS",
            "sector_name": "Financial Services & Banking",
            "primary_metrics": [...],
            "watch_metrics": [...],
            "all_metrics": [...],
        }
    """
    sector_key, sector_info = detect_sector(company_name, sector_hint)
    
    return {
        "sector": sector_key,
        "sector_name": sector_info.get("name", "General"),
        "primary_metrics": sector_info.get("primary_metrics", DEFAULT_METRICS),
        "watch_metrics": sector_info.get("watch_metrics", []),
        "all_metrics": sector_info.get("primary_metrics", []) + sector_info.get("watch_metrics", []),
    }


def filter_metrics_for_display(
    all_metrics: Dict,
    sector_key: str,
    max_primary: int = 6,
    max_secondary: int = 4
) -> Dict:
    """
    Filter metrics for display based on sector.
    
    Args:
        all_metrics: Dictionary of all available metrics
        sector_key: Detected sector
        max_primary: Max primary metrics to show
        max_secondary: Max secondary metrics to show
    
    Returns:
        Filtered metrics dict with "primary" and "secondary" keys
    """
    if sector_key not in SECTOR_METRICS:
        sector_key = "DEFAULT"
    
    sector_info = SECTOR_METRICS.get(sector_key, {})
    primary_names = [m["name"] for m in sector_info.get("primary_metrics", DEFAULT_METRICS)[:max_primary]]
    secondary_names = [m["name"] for m in sector_info.get("watch_metrics", [])[:max_secondary]]
    
    primary = {}
    secondary = {}
    other = {}
    
    for name, value in all_metrics.items():
        if name in primary_names:
            primary[name] = value
        elif name in secondary_names:
            secondary[name] = value
        else:
            other[name] = value
    
    return {
        "primary": primary,
        "secondary": secondary,
        "other": other,
    }


if __name__ == "__main__":
    # Test cases
    print("Sector Detection Tests:")
    print("-" * 50)
    
    test_companies = [
        ("HDFC Bank", None),
        ("Infosys", None),
        ("Maruti Suzuki", None),
        ("Cipla", None),
        ("Reliance Industries", None),
        ("Nestle India", None),
        ("NTPC", None),
        ("Tata Steel", None),
        ("Unknown Company", None),
    ]
    
    for company, hint in test_companies:
        sector, info = detect_sector(company, hint)
        print(f"{company:25} → {info.get('name', 'Unknown')}")
    
    print("\nSector Metrics Example (HDFC Bank):")
    print("-" * 50)
    metrics = get_sector_metrics("HDFC Bank")
    print(f"Sector: {metrics['sector_name']}")
    print(f"Primary Metrics:")
    for m in metrics['primary_metrics'][:6]:
        print(f"  - {m['label']} ({m['name']})")
    print(f"Watch Metrics:")
    for m in metrics['watch_metrics'][:4]:
        print(f"  - {m['label']} ({m['name']})")
