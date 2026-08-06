import requests
from rest_framework.views import APIView
from rest_framework.response import Response

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"

# Map symbols to Alpha Vantage functions / from-to currencies
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
    # Cocoa – Alpha Vantage free tier has no direct endpoint; we'll skip it for now
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
            data_key = "Time Series FX (Daily)"
        elif function in ("WTI", "NATURAL_GAS"):
            url = (
                f"https://www.alphavantage.co/query"
                f"?function={function}"
                f"&apikey={ALPHA_VANTAGE_KEY}"
            )
            data_key = "data"      # Commodities return a different structure
        else:
            return Response({"error": "Unsupported function"}, status=500)

        resp = requests.get(url)
        data = resp.json()

        # Handle commodity responses (they have a "data" array)
        if data_key == "data":
            if not data.get("data"):
                return Response({"error": "No data found"}, status=404)
            # Alpha Vantage commodity response: { "data": [ { "date": "...", "value": "..." }, ... ] }
            result = []
            for item in data["data"][:30]:
                result.append({
                    "date": item["date"],
                    "close": float(item["value"]),
                })
            result.reverse()
            return Response({"pair": pair, "data": result})
        else:
            series = data.get(data_key)
            if not series:
                return Response({"error": "No data found"}, status=404)
            result = []
            for date_str, values in sorted(series.items(), reverse=True)[:30]:
                result.append({
                    "date": date_str,
                    "close": float(values["4. close"]),
                })
            result.reverse()
            return Response({"pair": pair, "data": result})