# FNO Swing Terminal

A simple Streamlit swing-trading scanner for **NSE F&O stocks only**, using Dhan market data.

## Strategy

1. RSI < 30
2. Fresh bullish MACD crossover on the latest daily candle
3. Volume >= configurable multiple of 20-day average
4. Closing price > Supertrend
5. Long setup
6. Trail stop below the Supertrend line

Default Supertrend: ATR 10, multiplier 3  
Default MACD: 12 / 26 / 9  
Default RSI: 14  
Default volume filter: 1.5x 20-day average

## Repository

```text
fno_swing_terminal/
├── app.py
├── dhan_api.py
├── indicators.py
├── universe.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── data/
```

## Local setup

Create `.streamlit/secrets.toml` from the example and enter your Dhan credentials.

Never commit the real `secrets.toml`.

Then run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

Push this repository to GitHub.

Create a Streamlit app using `app.py` as the entry point.

In the Streamlit app's Secrets settings, add:

```toml
DHAN_ACCESS_TOKEN = "your_token"
DHAN_CLIENT_ID = "your_client_id"
```

## Important

The scanner uses Dhan's daily historical-data endpoint. Your Dhan account/token must have the required Data API access. If Dhan returns a subscription/access error, the dashboard will not be able to calculate the signals.

This project is deliberately signal-only. It does not place or modify orders.
