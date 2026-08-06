import requests
from django.core.management.base import BaseCommand
from apps.forex_ea.models import ForexCache
from datetime import date, timedelta

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"
SYMBOLS = [
    ("EURUSD", "EUR", "USD"), ("GBPUSD", "GBP", "USD"), ("USDJPY", "USD", "JPY"),
    ("USDNGN", "USD", "NGN"), ("AUDUSD", "AUD", "USD"), ("USDCAD", "USD", "CAD"),
    ("USDCHF", "USD", "CHF"), ("NZDUSD", "NZD", "USD"),
    ("GOLD", "XAU", "USD"), ("SILVER", "XAG", "USD"),
]

class Command(BaseCommand):
    def handle(self, *args, **options):
        for symbol, from_cur, to_cur in SYMBOLS:
            url = (
                f"https://www.alphavantage.co/query"
                f"?function=FX_DAILY"
                f"&from_symbol={from_cur}"
                f"&to_symbol={to_cur}"
                f"&apikey={ALPHA_VANTAGE_KEY}"
            )
            resp = requests.get(url)
            data = resp.json()
            series = data.get("Time Series FX (Daily)")
            if not series:
                self.stdout.write(f"No data for {symbol}")
                continue

            for date_str, values in series.items():
                date_obj = date.fromisoformat(date_str)
                ForexCache.objects.update_or_create(
                    symbol=symbol,
                    date=date_obj,
                    defaults={
                        "open": values["1. open"],
                        "high": values["2. high"],
                        "low": values["3. low"],
                        "close": values["4. close"],
                    }
                )
            self.stdout.write(f"Updated {symbol}")