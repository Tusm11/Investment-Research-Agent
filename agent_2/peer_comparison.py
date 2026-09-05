import numpy as np 
from concurrent.futures import ThreadPoolExecutor, as_completed
from agent_1.tools.nifty50 import NIFTY50
from agent_2.health_data import build_health_features

TARGET_METRICS = [
    "ROCE", "Debt", "Sales", "Operating Profit", "OPM %", 
    "Net Profit", "Total Assets", "Total Liabilities", 
    "Cash from Operating Activity", "Debtor Days", 
    "Inventory Days", "Working Capital Days"
]

def get_sector(ticker): #fetching the sector for a given ticker symbol from the NIFTY50 list
    for t, s in NIFTY50:
        if t == ticker:
            return s
    return "Unknown"

def get_peers(sector, exclude_ticker): #fetching the peers for a given sector from the NIFTY50 list, excluding the given ticker symbol
    return [t for t, s in NIFTY50 if s == sector and t != exclude_ticker]

def percentile(val, peer_vals):
    if val is None or np.isnan(val) or not peer_vals:
        return 50
    valid_peers = [v for v in peer_vals if v is not None and not np.isnan(v)]
    if not valid_peers:
        return 50
    
    count_below = sum(1 for v in valid_peers if v < val)
    count_equal = sum(1 for v in valid_peers if v == val)
    pct = ((count_below + 0.5 * count_equal) / len(valid_peers)) * 100
    return int(round(pct))

def compare_peers(ticker, company_features):
    if not company_features:
        return {"sector": "Unknown", "metrics": {}}

    sector = get_sector(ticker)
    if sector == "Unknown":
        return {"sector": "Unknown", "metrics": {}}

    peers = get_peers(sector, ticker)
    if not peers:
        return {"sector": sector, "metrics": {}}

    peer_data = {m: [] for m in TARGET_METRICS}

    def _fetch_peer(peer):
        try:
            return peer, build_health_features(peer)["feature_vector"]
        except Exception:
            return peer, {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_peer, peer): peer for peer in peers}
        for future in as_completed(futures, timeout=20):
            try:
                _, feats = future.result(timeout=5)
                for m in TARGET_METRICS:
                    val = feats.get(m)
                    if val is not None and not np.isnan(val):
                        peer_data[m].append(val)
            except Exception:
                pass

    output_metrics = {}

    for m in TARGET_METRICS:
        c_val = company_features.get(m)
        p_vals = peer_data[m]
        
        avg = np.mean(p_vals) if p_vals else None
        pct = percentile(c_val, p_vals)
        
        c_val_rounded = round(c_val, 2) if c_val is not None else None
        avg_rounded = round(avg, 2) if avg is not None and not np.isnan(avg) else None
        
        output_metrics[m] = {
            "company": c_val_rounded,
            "sector_average": avg_rounded,
            "percentile": pct
        }

    return {
        "sector": sector,
        "peers": peers,
        "metrics": output_metrics
    }
