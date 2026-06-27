import yfinance as yf

TICKER = "RELIANCE.NS"

t = yf.Ticker(TICKER)

bs = t.balance_sheet
income = t.income_stmt
cf = t.cashflow
info = t.info

bs_latest = bs.iloc[:, 0] if not bs.empty else {}
is_latest = income.iloc[:, 0] if not income.empty else {}
cf_latest = cf.iloc[:, 0] if not cf.empty else {}

print("=== BALANCE SHEET ROWS ===")
print(list(bs.index) if not bs.empty else "EMPTY")

print("\n=== INCOME STMT ROWS ===")
print(list(income.index) if not income.empty else "EMPTY")

print("\n=== CASHFLOW ROWS ===")
print(list(cf.index) if not cf.empty else "EMPTY")

print("\n=== RAW VALUES NEEDED ===")
keys = [
    ("EBIT", is_latest.get("EBIT") or is_latest.get("Operating Income")),
    ("Total Assets", bs_latest.get("Total Assets")),
    ("Current Liabilities", bs_latest.get("Current Liabilities")),
    ("Total Debt", bs_latest.get("Total Debt") or info.get("totalDebt")),
    ("Total Revenue", is_latest.get("Total Revenue") or info.get("totalRevenue")),
    ("Operating Income", is_latest.get("Operating Income")),
    ("Net Income", is_latest.get("Net Income") or info.get("netIncomeToCommon")),
    ("Total Liabilities", bs_latest.get("Total Liabilities Net Minority Interest") or bs_latest.get("Total Liabilities")),
    ("Operating Cash Flow", cf_latest.get("Total Cash From Operating Activities") or cf_latest.get("Operating Cash Flow")),
    ("Current Assets", bs_latest.get("Current Assets")),
    ("Accounts Receivable", bs_latest.get("Accounts Receivable")),
    ("Inventory", bs_latest.get("Inventory")),
    ("Cost of Revenue", is_latest.get("Cost Of Revenue")),
]

for name, val in keys:
    status = "OK" if val is not None else "MISSING"
    print(f"  [{status}] {name}: {val}")
