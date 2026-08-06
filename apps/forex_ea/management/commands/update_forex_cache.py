import requests
from django.core.management.base import BaseCommand
from apps.forex_ea.models import ForexCache
from datetime import date
import time

TWELVE_API_KEY = "0e71d2b553d44d7da9915a1d1c97bf45"
SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDNGN": "USD/NGN",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "NZDUSD": "NZD/USD",
    "GOLD": "XAU/USD",
    "WTI": "WTI/USD",           # ← Crude Oil
    "NATURALGAS": "XNG/USD",   # ← Natural Gas
}

class Command(BaseCommand):
    def handle(self, *args, **options):
        for symbol, twelve_symbol in SYMBOLS.items():
            url = (
                f"https://api.twelvedata.com/time_series"
                f"?symbol={twelve_symbol}&interval=1day&outputsize=30&apikey={TWELVE_API_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            if data.get("status") == "error":
                self.stdout.write(f"Error for {symbol}: {data.get('message')}")
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
            self.stdout.write(f"Updated {symbol}")
            time.sleep(10)