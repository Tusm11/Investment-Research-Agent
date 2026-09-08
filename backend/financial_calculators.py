"""Financial calculations and formula library."""
import numpy as np

def get_field(row, *keys):
    """Try multiple key names, return first non-null value."""
    for k in keys:
        try:
            v = row.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                return float(v)
        except:
            pass
    return None

def to_cr(val):
    """Convert to ₹ crores."""
    if val is None:
        return None
    try:
        v = float(val)
        return round(v / 1e7, 1) if abs(v) > 1e6 else None
    except:
        return None

# P&L CALCULATIONS
def calc_operating_profit(row):
    """Operating Profit = Revenue - Operating Expenses, or EBIT directly."""
    ebit = get_field(row, "EBIT", "Operating Income")
    if ebit:
        return ebit
    # Try Revenue - Operating Expenses
    rev = get_field(row, "Total Revenue", "Operating Revenue")
    op_exp = get_field(row, "Operating Expense", "Total Expenses")
    if rev and op_exp:
        return rev - op_exp
    # Try Gross Profit - SG&A
    gross = get_field(row, "Gross Profit")
    sga = get_field(row, "Selling General And Administration")
    if gross and sga:
        return gross - sga
    return None

def calc_opm(row, revenue):
    """OPM % = Operating Profit / Revenue."""
    op_profit = calc_operating_profit(row)
    if op_profit and revenue:
        return round(op_profit / revenue * 100, 2)
    return None

def calc_pbt(row, op_profit, revenue):
    """PBT = Operating Profit + Other Income - Interest - Depreciation."""
    pbt = get_field(row, "Pretax Income")
    if pbt:
        return pbt
    if op_profit:
        other_income = get_field(row, "Other Income", "Other Operating Income") or 0
        interest = get_field(row, "Interest Expense", "Net Interest Income") or 0
        depr = get_field(row, "Depreciation And Amortization In Income Statement", 
                         "Depreciation", "Reconciled Depreciation") or 0
        return op_profit + other_income - interest - depr
    return None

def calc_tax(row, pbt, net_profit):
    """Tax = PBT - Net Profit."""
    tax = get_field(row, "Tax Provision")
    if tax:
        return tax
    if pbt and net_profit:
        return max(0, pbt - net_profit)
    return None

def calc_eps(row, net_profit, shares_out, current_price=None, pe_ratio=None, is_latest_year=False):
    """
    EPS = Net Profit / Average Shares (reported figures only).
    Never estimate EPS from Price / P/E — that fabricates a value not in the statements.
    """
    # Direct EPS from financials first
    eps = get_field(row, "Diluted EPS", "Basic EPS")
    if eps:
        return eps
    # Bottom-up: EPS = Net Profit / Average Shares (both reported in the statement)
    if net_profit and shares_out and shares_out > 0:
        return net_profit / shares_out
    return None

# BALANCE SHEET CALCULATIONS
def calc_total_liabilities(row, total_assets):
    """Total Liabilities = Total Assets - Total Equity."""
    liab = get_field(row, "Total Liabilities Net Minority Interest")
    if liab:
        return liab
    if total_assets:
        equity = get_field(row, "Stockholders Equity", "Common Stock Equity")
        if equity:
            return total_assets - equity
    return None

def calc_other_liabilities(row, total_liab, current_liab, non_current_liab):
    """Other Liabilities = Total - Current - NonCurrent."""
    other = get_field(row, "Other Current Liabilities", "Other Non Current Liabilities")
    if other:
        return other
    if total_liab and current_liab and non_current_liab:
        return total_liab - current_liab - non_current_liab
    return None

def calc_other_assets(row, total_assets, ppe, invest, other_non_curr):
    """Other Assets = Total - PPE - Investments - Current."""
    other = get_field(row, "Other Non Current Assets", "Other Assets")
    if other:
        return other
    current = get_field(row, "Current Assets")
    if total_assets and current:
        return total_assets - current
    return None

def calc_reserves(row, equity, share_capital):
    """Reserves = Total Equity - Equity Share Capital."""
    res = get_field(row, "Retained Earnings", "Additional Paid In Capital")
    if res:
        return res
    if equity and share_capital:
        return equity - share_capital
    return None

# RATIO CALCULATIONS
def calc_roe(net_profit, equity):
    """ROE % = Net Profit / Total Equity * 100."""
    if net_profit and equity and equity > 0:
        return round(net_profit / equity * 100, 2)
    return None

def calc_roce(op_profit, total_assets, current_liab):
    """ROCE % = EBIT / (Total Assets - Current Liabilities) * 100."""
    if op_profit and total_assets and current_liab:
        capital = total_assets - current_liab
        if capital > 0:
            return round(op_profit / capital * 100, 2)
    return None

def calc_de_ratio(total_debt, equity):
    """Debt to Equity = Total Debt / Total Equity (as decimal ratio like 1.8, not rupees)."""
    if total_debt and equity and equity > 0:
        return round(total_debt / equity, 2)
    return None

def calc_current_ratio(current_assets, current_liab):
    """Current Ratio = Current Assets / Current Liabilities."""
    if current_assets and current_liab and current_liab > 0:
        return round(current_assets / current_liab, 2)
    return None

def calc_pe_ratio(current_price, eps):
    """P/E = Current Price / EPS."""
    if current_price and eps and eps > 0:
        return round(current_price / eps, 2)
    return None
