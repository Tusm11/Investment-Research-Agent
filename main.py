import argparse
import json
import logging

from pipeline import run_pipeline

#the main function sets up the command-line interface for the investment research pipeline, parses the input arguments, runs the pipeline with the provided question, ticker, and lookback days, and formats the output as a JSON object for display.
def main():
    parser = argparse.ArgumentParser(description="Run the investment research pipeline")
    parser.add_argument("question", help="Research question, for example: Is RELIANCE healthy?")
    parser.add_argument("--ticker", default=None, help="Ticker symbol such as RELIANCE.NS")
    parser.add_argument("--days", type=int, default=180, help="Lookback window for price and news")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = run_pipeline(args.question, ticker=args.ticker, days=args.days)

    agent1_data = result.get("agent1_output") or {}
    output = {
        "question": args.question,
        "ticker": result.get("primary_ticker"),
        "intent": result.get("intent"),
        "company": agent1_data.get("company_info", {}).get("company_name"),
        "current_price": agent1_data.get("price_history", {}).get("current_price"),
        "agent2_output": result.get("agent2_output"),
        "agent3_output": result.get("agent3_output"),
        "response": result.get("agent4_output", {}).get("response"),
        "error": result.get("error"),
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
