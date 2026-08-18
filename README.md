FNO Swing Terminal V2
Timeframes
1D — normal swing
4H — short swing (built from Dhan 60-minute candles)
1H — tactical short swing
Dhan's API directly provides daily candles and 60-minute intraday candles. The 4H view is locally aggregated from completed 60-minute NSE cash-session candles.
Strategy
RSI below threshold + fresh bullish MACD crossover + volume above 20-period average + price above Supertrend.
Default:
RSI 14
MACD 12/26/9
Supertrend ATR 10 x 3
Volume >= 1.5x 20-period average
Important API diagnostic change
The dashboard now displays the actual Dhan error returned by the API instead of simply saying "18 script errors".
Common Dhan data errors include:
806 = Data APIs not subscribed
807 = Access token expired
808 = authentication failed
809 = access token invalid
813 = invalid Security ID
814 = invalid request
See Dhan's current API documentation for details.
