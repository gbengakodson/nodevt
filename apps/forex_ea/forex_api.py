import requests
from rest_framework.views import APIView
from rest_framework.response import Response

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"

SYMBOL_MAP = {
    "EURUSD": ("FX_DAILY", "EUR", "USD"),
    "GBPUSD": ("FX_DAILY", "GBP", "USD"),
    "USDJPY": ("FX_DAILY", "USD", "JPY"),
    "USDNGN": ("FX_DAILY", "USD", "NGN"),
    "AUDUSD": ("FX_DAILY", "AUD", "USD"),
    "USDCAD": ("FX_DAILY", "USD", "CAD"),
    "USDCHF": ("FX_DAILY", "USD", "CHF"),
    "NZDUSD": ("FX_DAILY", "NZD", "USD"),
    # Commodities
    "WTI":      ("WTI", None, None),
    "USOIL":    ("WTI", None, None),
    "NATURALGAS": ("NATURAL_GAS", None, None),
    "GOLD":     ("FX_DAILY", "XAU", "USD"),
    "SILVER":   ("FX_DAILY", "XAG", "USD"),
}

class ForexDailyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        pair = request.GET.get("pair", "").upper()
        info = SYMBOL_MAP.get(pair)
        if not info:
            return Response({"error": f"Symbol {pair} not supported"}, status=400)

        function, from_cur, to_cur = info

        if function == "FX_DAILY" and from_cur and to_cur:
            url = (
                f"https://www.alphavantage.co/query"
                f"?function={function}"
                f"&from_symbol={from_cur}"
                f"&to_symbol={to_cur}"
                f"&apikey={ALPHA_VANTAGE_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            series = data.get("Time Series FX (Daily)")
            if not series:
                return Response({"error": "No data found"}, status=404)

            result = []
            for date_str, values in sorted(series.items(), reverse=True)[:30]:
                result.append({
                    "date": date_str,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                })
            result.reverse()
            return Response({"pair": pair, "data": result})

        # Commodities – we only have single values, so we'll fake OHLC (all equal to close)
        elif function in ("WTI", "NATURAL_GAS"):
            url = (
                f"https://www.alphavantage.co/query"
                f"?function={function}"
                f"&apikey={ALPHA_VANTAGE_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            if not data.get("data"):
                return Response({"error": "No data found"}, status=404)
            result = []
            for item in data["data"][:30]:
                val = float(item["value"])
                result.append({
                    "date": item["date"],
                    "open": val,
                    "high": val,
                    "low": val,
                    "close": val,
                })
            result.reverse()
            return Response({"pair": pair, "data": result})

        return Response({"error": "Unsupported"}, status=500)