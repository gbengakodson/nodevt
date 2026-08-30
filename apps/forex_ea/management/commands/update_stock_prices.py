from django.core.management.base import BaseCommand
from apps.forex_ea.models import StockPrice

FOREIGN_FALLBACK = {
    'NVDA': 115.00,
    'AAPL': 312.00,
    'MSFT': 490.00,
    'WMT': 95.00,
    'META': 580.00,
    'AMZN': 210.00,
    'GOOG': 175.00,
    'SPCX': 150.00,
}

NIGERIAN_STOCKS = {
    'ZENITHBANK': 45.00,
    'GTCO': 55.00,
    'MTNN': 280.00,
    'DANGCEM': 650.00,
    'ACCESSCORP': 30.00,
    'UBA': 28.00,
    'SEPLAT': 2500.00,
}

class Command(BaseCommand):
    help = 'Update stock prices from fallback dictionaries'

    def handle(self, *args, **options):
        for sym, price in FOREIGN_FALLBACK.items():
            StockPrice.objects.update_or_create(
                symbol=sym,
                defaults={'price': price, 'change_24h': 0.0}
            )
            self.stdout.write(f'Updated {sym}: ${price:.2f}')

        for sym, price in NIGERIAN_STOCKS.items():
            StockPrice.objects.update_or_create(
                symbol=sym,
                defaults={'price': price, 'change_24h': 0.0}
            )
            self.stdout.write(f'Updated {sym}: ₦{price:.2f}')