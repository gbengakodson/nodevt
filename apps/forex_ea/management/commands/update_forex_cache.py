import requests
import time
from django.core.management.base import BaseCommand
from apps.forex_ea.models import ForexCache
from datetime import date

TWELVE_API_KEY = "0e71d2b553d44d7da9915a1d1c97bf45"
ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"

# Symbols from Twelve Data (free tier covers these)
TWELVE_SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDNGN": "USD/NGN",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "NZDUSD": "NZD/USD",
    "GOLD": "XAU/USD",
}

# Commodities only available via Alpha Vantage (free tier)
ALPHA_SYMBOLS = {
    "WTI": ("WTI", None),          # Alpha Vantage function WTI
    "NATURALGAS": ("NATURAL_GAS", None),
}

class Command(BaseCommand):
    def handle(self, *args, **options):
        # ── Twelve Data ──
        for symbol, twelve_symbol in TWELVE_SYMBOLS.items():
            url = (
                f"https://api.twelvedata.com/time_series"
                f"?symbol={twelve_symbol}&interval=1day&outputsize=30&apikey={TWELVE_API_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            if data.get("status") == "error":
                self.stdout.write(f"Twelve Data error for {symbol}: {data.get('message')}")
                time.sleep(10)
                continue

            for item in data.get("values", []):
                date_obj = date.fromisoformat(item["datetime"])
                ForexCache.objects.update_or_create(
                    symbol=symbol,
                    date=date_obj,
                    defaults={
                        "open":  item["open"],
                        "high":  item["high"],
                        "low":   item["low"],
                        "close": item["close"],
                    }
                )
            self.stdout.write(f"Updated {symbol} (Twelve Data)")
            time.sleep(10)   # respect 8 req/min limit

        # ── Alpha Vantage (commodities) ──
        for symbol, (function, _) in ALPHA_SYMBOLS.items():
            url = (
                f"https://www.alphavantage.co/query"
                f"?function={function}&apikey={ALPHA_VANTAGE_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            if not data.get("data"):
                self.stdout.write(f"Alpha Vantage error for {symbol}")
                time.sleep(5)
                continue

            for item in data["data"][:30]:
                date_obj = date.fromisoformat(item["date"])
                val = float(item["value"])
                ForexCache.objects.update_or_create(
                    symbol=symbol,
                    date=date_obj,
                    defaults={
                        "open":  val,
                        "high":  val,
                        "low":   val,
                        "close": val,
                    }
                )
            self.stdout.write(f"Updated {symbol} (Alpha Vantage)")
            time.sleep(5)