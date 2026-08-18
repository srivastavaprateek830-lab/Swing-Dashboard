import time
import requests
import pandas as pd
from datetime import datetime, timedelta

BASE = "https://api.dhan.co/v2"

class DhanClient:
    def __init__(self, token, client_id=""):
        self.token = token
        self.client_id = client_id
        self.ready = bool(token)

    def _headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": self.token,
        }

    def daily_history(self, security_id, days=180):
        end = datetime.now()
        start = end - timedelta(days=days + 30)

        payload = {
            "securityId": str(security_id),
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "fromDate": start.strftime("%Y-%m-%d"),
            "toDate": end.strftime("%Y-%m-%d"),
        }

        time.sleep(0.22)  # stay comfortably below Dhan data API rate limits
        r = requests.post(
            f"{BASE}/charts/historical",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )

        if r.status_code != 200:
            raise RuntimeError(f"Dhan {r.status_code}: {r.text[:250]}")

        data = r.json()
        if not isinstance(data, dict) or "close" not in data:
            return None

        df = pd.DataFrame({
            "open": data.get("open", []),
            "high": data.get("high", []),
            "low": data.get("low", []),
            "close": data.get("close", []),
            "volume": data.get("volume", []),
        })

        ts = data.get("timestamp", [])
        if ts:
            df.index = pd.to_datetime(ts, unit="s")
        else:
            df.index = pd.date_range(end=end.date(), periods=len(df), freq="B")

        df = df.apply(pd.to_numeric, errors="coerce").dropna()
        return df.sort_index()
