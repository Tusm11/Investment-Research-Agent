import os
import joblib
import yfinance as yf
import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), "isolation_forest_model.pkl") #it is trained on the financial features of the NIFTY50 companies to detect anomalies in the financial statements of a given company. The model is used to identify red flags in the financial statements of a given company by comparing its financial features with those of its peers in the same sector.

EXPECTED_FEATURES = [
    "Debt To Equity_z",
    "Debt Ratio_z",
    "Net Debt To Ebitda_z",
    "Total Debt To Capitalization_z",
    "Current Ratio_z",
    "Quick Ratio_z",
    "Cash Ratio_z",
    "Net Profit Margin_z",
    "Operating Profit Margin_z",
    "ROE_z",
    "ROIC_z",
    "Income Quality_z",
    "Cash Flow To Debt Ratio_z",
    "Interest Coverage_z",
    "Asset Turnover_z",
]

if_model = None

#safe ratio function calculates the ratio of two numbers, handling cases where the denominator is zero or None. It returns None instead of 0 for missing data so missing metrics don't appear as 0%.
def _safe_ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None  # ← Return None, not 0, for missing data
    try:
        return numerator / denominator
    except TypeError:
        return None

#first present function retrieves the first non-None value from a mapping (like a dictionary) for a given set of keys. It returns None if none of the keys are present or if all values are None.
def _first_present(mapping, *keys):
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _safe_div(numerator, denominator):
    return _safe_ratio(numerator, denominator)

def _get_model():
    global if_model
    if if_model is not None:
        return if_model

    if os.path.exists(MODEL_PATH):
        if_model = joblib.load(MODEL_PATH)
        return if_model
    
    raise FileNotFoundError(f"Isolation Forest model not found at {MODEL_PATH}.")

#use the trained Isolation Forest model to assess the financial health of a given stock ticker. It builds a feature vector based on key financial ratios and metrics, then predicts whether the company is an anomaly compared to its peers. The function returns a structured assessment including the prediction, decision function value, anomaly score, and whether the company is flagged as an anomaly.
def assess_isolation_forest(ticker):
    """Run the trained Isolation Forest and return a structured assessment."""
    model = _get_model()
    feats = build_features(ticker)

    feature_order = list(getattr(model, "feature_names_in_", EXPECTED_FEATURES))
    vec = pd.DataFrame([[feats.get(name, 0) for name in feature_order]], columns=feature_order)
    vec = vec.replace([np.inf, -np.inf], 0).fillna(0)

    prediction = int(model.predict(vec)[0])
    decision = float(model.decision_function(vec)[0])
    anomaly_score = round(max(0.0, -decision), 4)

    return {
        "model_path": MODEL_PATH,
        "model_loaded": True,
        "prediction": prediction,
        "decision_function": round(decision, 4),
        "anomaly_score": round(anomaly_score, 4),
        "is_anomaly": prediction == -1,
        "used_features": feature_order,
    }

def build_features(ticker_symbol):
    t = yf.Ticker(ticker_symbol)

    bs = t.balance_sheet
    is_ = t.income_stmt
    cf = t.cashflow

    bs_latest = bs.iloc[:, 0] if not bs.empty else {}
    is_latest = is_.iloc[:, 0] if not is_.empty else {}
    cf_latest = cf.iloc[:, 0] if not cf.empty else {}

    revenue = _first_present(is_latest, "Total Revenue")
    net_income = _first_present(is_latest, "Net Income")
    operating_income = _first_present(is_latest, "Operating Income")
    interest_expense = _first_present(is_latest, "Interest Expense", "Interest Expense And Other")
    assets = _first_present(bs_latest, "Total Assets")
    equity = _first_present(bs_latest, "Stockholders Equity")
    debt = _first_present(bs_latest, "Total Debt")
    current_assets = _first_present(bs_latest, "Current Assets")
    current_liabilities = _first_present(bs_latest, "Current Liabilities")
    inventory = _first_present(bs_latest, "Inventory")
    cash = _first_present(bs_latest, "Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments")
    ocf = _first_present(cf_latest, "Total Cash From Operating Activities", "Operating Cash Flow")
    capex = _first_present(cf_latest, "Capital Expenditures")
    depreciation = _first_present(cf_latest, "Depreciation And Amortization")

    ebitda = (operating_income or 0) + (depreciation or 0)
    invested_capital = (debt or 0) + (equity or 0)
    net_debt = (debt or 0) - (cash or 0)

    features = {
        "Debt To Equity_z": _safe_div(debt, equity),
        "Debt Ratio_z": _safe_div(debt, assets),
        "Net Debt To Ebitda_z": _safe_div(net_debt, ebitda),
        "Total Debt To Capitalization_z": _safe_div(debt, invested_capital),
        "Current Ratio_z": _safe_div(current_assets, current_liabilities),
        "Quick Ratio_z": _safe_div((current_assets or 0) - (inventory or 0), current_liabilities),
        "Cash Ratio_z": _safe_div(cash, current_liabilities),
        "Net Profit Margin_z": _safe_div(net_income, revenue),
        "Operating Profit Margin_z": _safe_div(operating_income, revenue),
        "ROE_z": _safe_div(net_income, equity),
        "ROIC_z": _safe_div(operating_income, invested_capital),
        "Income Quality_z": _safe_div(ocf, net_income),
        "Cash Flow To Debt Ratio_z": _safe_div(ocf, debt),
        "Interest Coverage_z": _safe_div(operating_income, abs(interest_expense) if interest_expense is not None else None),
        "Asset Turnover_z": _safe_div(revenue, assets),
    }

    for key in features:
        if features[key] is None:
            features[key] = 0.0

    return features

def detect_red_flags(ticker):
    flags = []
    try:
        t = yf.Ticker(ticker)
        info = t.info
        bs = t.balance_sheet.iloc[:, 0] if not t.balance_sheet.empty else {}
        
        revenue = info.get("totalRevenue") or 0
        net_income = info.get("netIncomeToCommon") or 0
        operating_income = info.get("operatingIncome") or 0
        debt = bs.get("Total Debt") or info.get("totalDebt")
        equity = bs.get("Stockholders Equity") or info.get("totalStockholderEquity")
        
        # Check if critical data is missing
        if not revenue or not equity:
            flags.append({
                "metric": "Incomplete Financial Data",
                "value": "N/A",
                "severity": "high",
                "explanation": "Missing key financial metrics (revenue or equity) - cannot calculate ratios."
            })
            return flags  # Cannot calculate other ratios without base data
        
        debt_to_equity = debt / equity if debt and equity else 0
        
        if debt_to_equity > 5:
            flags.append({
                "metric": "High Debt",
                "value": f"Debt/Equity: {debt_to_equity:.2f}",
                "severity": "high",
                "explanation": "Company has high debt relative to equity, which increases financial risk."
            })
        elif debt is None:
            flags.append({
                "metric": "Debt Data Unavailable",
                "value": "N/A",
                "severity": "medium",
                "explanation": "Debt information not available - unable to assess leverage."
            })
        
        profit_margin = net_income / revenue if revenue else 0
        if profit_margin < 0.10 and revenue:
            flags.append({
                "metric": "Low Profit Margin",
                "value": f"{profit_margin*100:.1f}%",
                "severity": "medium",
                "explanation": "Profit margin is below 10%, indicating weaker profitability."
            })
        
        roe = info.get("returnOnEquity")
        if roe and roe < 0.15:
            flags.append({
                "metric": "Low ROE",
                "value": f"{roe*100:.1f}%",
                "severity": "low",
                "explanation": "Return on equity is below 15%, below industry best practices."
            })
        elif roe is None:
            flags.append({
                "metric": "ROE Unavailable",
                "value": "N/A",
                "severity": "low",
                "explanation": "Return on equity data not available from data sources."
            })
        
        revenue_growth = info.get("revenueGrowth")
        if revenue_growth and revenue_growth < 0.08:
            flags.append({
                "metric": "Slow Revenue Growth",
                "value": f"{revenue_growth*100:.1f}%",
                "severity": "low",
                "explanation": "Revenue growth is below 8%, indicating limited expansion momentum."
            })
        
        assessment = assess_isolation_forest(ticker)
        anomaly_score = assessment.get("anomaly_score", 0)

        if assessment.get("is_anomaly") or anomaly_score >= 0.7:
            flags.append({
                "metric": "Financial Statements",
                "value": f"Risk Score: {anomaly_score:.2f}",
                "severity": "high" if anomaly_score >= 0.85 or assessment.get("is_anomaly") else "medium",
                "explanation": (
                    f"Statistical analysis flagged this company as {'anomalous' if assessment.get('is_anomaly') else 'elevated risk'} "
                    f"(score: {anomaly_score:.2f})."
                ),
            })
            
    except Exception as e:
        logger.error(f"Red flag detection error: {e}")
        flags.append({
            "metric": "Analysis Failed",
            "value": "N/A",
            "severity": "high",
            "explanation": f"Red flag analysis could not complete: {str(e)}"
        })
        
    return flags
