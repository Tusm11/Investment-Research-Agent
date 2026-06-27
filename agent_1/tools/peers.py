from agent_1.tools.nifty50 import NIFTY50


SECTOR_PEERS = {
    "Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Financial Services": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "NTPC.NS", "POWERGRID.NS"],
    "Consumer Cyclical": ["TITAN.NS", "TRENT.NS", "MARUTI.NS", "M&M.NS", "EICHERMOT.NS"],
    "Healthcare": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
}


def fetch_peer_list(ticker):
    ticker_root = ticker.split(".")[0]
    sector = next((sector_name for symbol, sector_name in NIFTY50 if symbol == ticker), None)
    peers = SECTOR_PEERS.get(sector, [])
    peers = [peer for peer in peers if peer.split(".")[0] != ticker_root][:5]

    return {
        "peers": peers,
        "sector": sector,
        "industry": sector,
    }


def fetch_sector_metrics(sector, peer_tickers=None):
    tickers = peer_tickers or SECTOR_PEERS.get(sector, [])
    return {
        "sector": sector,
        "peers": tickers[:5],
        "sample_size": len(tickers[:5]),
    }
