import time
import requests
import pandas as pd
from datetime import datetime, timedelta

BASE = "https://api.dhan.co/v2"

class DhanAPIError(RuntimeError):
    pass

class DhanClient:
    def __init__(self, token, client_id=""):
        self.token = token
        self.client_id = client_id
        self.ready = bool(token)

    def _headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": self.token,
        }
        # Historical API documentation currently shows access-token as the
        # required authentication header. Keep client-id available for APIs
        # that require it, without forcing it onto historical requests.
        if self.client_id:
            headers["client-id"] = self.client_id
        return headers

    def _post(self, endpoint, payload):
        time.sleep(0.25)
        r = requests.post(
            f"{BASE}{endpoint}",
            headers=self._headers(),
            json=payload,
            timeout=30
        )

        if r.status_code != 200:
            body = r.text[:500]
            raise DhanAPIError(f"HTTP {r.status_code}: {body}")

        try:
            data = r.json()
        except Exception:
            raise DhanAPIError(f"Non-JSON response: {r.text[:500]}")

        if isinstance(data, dict):
            # Dhan sometimes returns error objects with a 200 response.
            if data.get("status") == "failure" or data.get("errorCode") or data.get("errorType"):
                raise DhanAPIError(str(data))
            if "error" in data and not data.get("data"):
                raise DhanAPIError(str(data["error"]))

        return data

    def history(self, security_id, timeframe="1D", days=90):
        if timeframe == "1D":
            return self._daily(security_id, days)

        # Dhan supports 60-minute intraday candles. 4H is constructed locally
        # from completed 60-minute candles.
        hourly = self._intraday_60m(security_id, days)
        if timeframe == "1H":
            return hourly
        if timeframe == "4H":
            return self._to_4h(hourly)

        raise ValueError(f"Unsupported timeframe: {timeframe}")

    def _daily(self, security_id, days):
        end = datetime.now()
        start = end - timedelta(days=max(days, 90))

        payload = {
            "securityId": str(security_id),
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "fromDate": start.strftime("%Y-%m-%d"),
            "toDate": end.strftime("%Y-%m-%d"),
            "oi": False,
        }
        data = self._post("/charts/historical", payload)
        return self._frame(data)

    def _intraday_60m(self, security_id, days):
        # Dhan's current documentation permits 90-day windows per intraday call.
        days = min(days, 90)
        end = datetime.now()
        start = end - timedelta(days=days)

        payload = {
            "securityId": str(security_id),
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "interval": "60",
            "oi": False,
            "fromDate": start.strftime("%Y-%m-%d 09:15:00"),
            "toDate": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data = self._post("/charts/intraday", payload)
        return self._frame(data)

    @staticmethod
    def _frame(data):
        if not isinstance(data, dict) or "close" not in data:
            raise DhanAPIError(f"Unexpected candle response: {str(data)[:500]}")

        n = len(data.get("close", []))
        if n == 0:
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
            # Dhan returns Unix timestamps. Convert as UTC first and then
            # display in India time; timezone is removed for plotting/resampling.
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            df.index = idx
        else:
            df.index = pd.date_range(end=datetime.now(), periods=n, freq="D")

        return df.apply(pd.to_numeric, errors="coerce").dropna().sort_index()

    @staticmethod
    def _to_4h(df):
        if df is None or df.empty:
            return df

        # Anchor 4H windows at the NSE cash-session start (09:15).
        # Only completed windows are retained, avoiding a partial current bar.
        x = df.between_time("09:15", "15:30").copy()
        out = x.resample(
            "4h", origin="start_day", offset="9h15min",
            label="left", closed="left"
        ).agg({
            "open":"first",
            "high":"max",
            "low":"min",
            "close":"last",
            "volume":"sum"
        }).dropna()

        # Keep only bars containing at least 3 hourly observations.
        counts = x["close"].resample(
            "4h", origin="start_day", offset="9h15min",
            label="left", closed="left"
        ).count()
        out = out[counts >= 3]

        return out
