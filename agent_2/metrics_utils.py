import numpy as np
#features used to train the health score model
FEATURES = [
    "ROE",
    "Operating_Margin",
    "Debt_to_Equity",
    "Current_Ratio",
    "Revenue_Growth",
    "FCF_Margin",
]
#bounds are used to filter outliers in the training data for the health score model. Each feature has a lower and upper bound, and any data points outside of these bounds are considered outliers and are removed from the training data. This helps to improve the accuracy of the model by ensuring that it is trained on representative data.
BOUNDS = {
    "ROE": (-2, 2),
    "Operating_Margin": (-1, 1),
    "Debt_to_Equity": (0, 500),
    "Current_Ratio": (0, 10),
    "Revenue_Growth": (-1, 2),
    "FCF_Margin": (-1, 1),
}

#normalizng the live vectors
def normalize_live_metrics(metrics):
    revenue = metrics.get("totalRevenue") or 0
    fcf = metrics.get("freeCashflow") or 0
    fcf_margin = (fcf / revenue) if revenue else 0

    roe = metrics.get("returnOnEquity") or 0
    if abs(roe) > 5:
        roe = roe / 100

    row = {
        "ROE": float(np.clip(roe, *BOUNDS["ROE"])), #clip() is used to limit the values of the features to be within the specified bounds. If a value is less than the lower bound, it is set to the lower bound, and if it is greater than the upper bound, it is set to the upper bound. This helps to prevent extreme values from skewing the model's predictions.
        "Operating_Margin": float(np.clip(metrics.get("operatingMargins") or 0, *BOUNDS["Operating_Margin"])),
        "Debt_to_Equity": float(np.clip(metrics.get("debtToEquity") or 0, *BOUNDS["Debt_to_Equity"])),
        "Current_Ratio": float(np.clip(metrics.get("currentRatio") or 0, *BOUNDS["Current_Ratio"])),
        "Revenue_Growth": float(np.clip(metrics.get("revenueGrowth") or 0, *BOUNDS["Revenue_Growth"])),
        "FCF_Margin": float(np.clip(fcf_margin, *BOUNDS["FCF_Margin"])),
    }
    return row


def filter_training_frame(df):
    df = df.replace([np.inf, -np.inf], np.nan)
    for col, (lo, hi) in BOUNDS.items():
        df = df[(df[col].isna()) | ((df[col] >= lo) & (df[col] <= hi))]
    return df.dropna(subset=FEATURES)
