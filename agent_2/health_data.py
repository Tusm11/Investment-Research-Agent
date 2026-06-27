import yfinance as yf
import numpy as np

TARGET_METRICS = [
    "ROCE", "Debt", "Sales", "Operating Profit", "OPM %", 
    "Net Profit", "Total Assets", "Total Liabilities", 
    "Cash from Operating Activity", "Debtor Days", 
    "Inventory Days", "Working Capital Days"
]

def build_health_features(ticker_symbol):
    t = yf.Ticker(ticker_symbol)
    
    info = t.info
    bs = t.balance_sheet
    income = t.income_stmt
    cf = t.cashflow

    bs_latest = bs.iloc[:, 0] if not bs.empty else {}
    is_latest = income.iloc[:, 0] if not income.empty else {}
    cf_latest = cf.iloc[:, 0] if not cf.empty else {}

    raw = {
        "EBIT":                      is_latest.get("EBIT") or is_latest.get("Operating Income"),
        "Total Assets":              bs_latest.get("Total Assets"),
        "Current Assets":            bs_latest.get("Current Assets"),
        "Current Liabilities":       bs_latest.get("Current Liabilities"),
        "Debt":                      bs_latest.get("Total Debt") or info.get("totalDebt"),
        "Sales":                     is_latest.get("Total Revenue") or info.get("totalRevenue"),
        "Operating Profit":          is_latest.get("Operating Income"),
        "Net Profit":                is_latest.get("Net Income") or info.get("netIncomeToCommon"),
        "Total Liabilities":         bs_latest.get("Total Liabilities Net Minority Interest") or bs_latest.get("Total Liabilities"),
        "Cash from Operating Activity": cf_latest.get("Operating Cash Flow") or cf_latest.get("Total Cash From Operating Activities"),
        "Accounts Receivable":       bs_latest.get("Accounts Receivable") or bs_latest.get("Receivables"),
        "Inventory":                 bs_latest.get("Inventory"),
        "Cost of Revenue":           is_latest.get("Cost Of Revenue") or is_latest.get("Cost of Revenue") or is_latest.get("Reconciled Cost Of Revenue"),
    }

    feature_vector = {}

    def set_val(key, val):
        try:
            if val is not None and not np.isnan(float(val)):
                feature_vector[key] = round(float(val), 4)
            else:
                feature_vector[key] = None
        except Exception:
            feature_vector[key] = None

    set_val("ROCE", raw["EBIT"] / (raw["Total Assets"] - raw["Current Liabilities"]) * 100
            if raw["EBIT"] and raw["Total Assets"] and raw["Current Liabilities"] else None)

    set_val("Debt", raw["Debt"])
    set_val("Sales", raw["Sales"])
    set_val("Operating Profit", raw["Operating Profit"])
    set_val("OPM %", (raw["Operating Profit"] / raw["Sales"]) * 100
            if raw["Operating Profit"] and raw["Sales"] else None)
    set_val("Net Profit", raw["Net Profit"])
    set_val("Total Assets", raw["Total Assets"])
    set_val("Total Liabilities", raw["Total Liabilities"])
    set_val("Cash from Operating Activity", raw["Cash from Operating Activity"])

    set_val("Debtor Days", (raw["Accounts Receivable"] / raw["Sales"]) * 365
            if raw["Accounts Receivable"] and raw["Sales"] else None)
    set_val("Inventory Days", (raw["Inventory"] / raw["Cost of Revenue"]) * 365
            if raw["Inventory"] and raw["Cost of Revenue"] else None)
    set_val("Working Capital Days", ((raw["Current Assets"] - raw["Current Liabilities"]) / raw["Sales"]) * 365
            if raw["Current Assets"] and raw["Current Liabilities"] and raw["Sales"] else None)

    missing = [k for k, v in feature_vector.items() if v is None]
    return {"feature_vector": feature_vector, "missing_features": missing}
