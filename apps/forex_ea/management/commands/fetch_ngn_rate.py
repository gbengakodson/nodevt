import requests
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.forex_ea.models import ForexRateHistory


CBN_CDN = "https://cdn.jsdelivr.net/gh/AllRates-Today/central-bank-exchange-rates@main/data/cbn/latest.json"


class Command(BaseCommand):
    help = 'Fetch CBN USD/NGN middle rate, apply buy/sell spread, store in ForexRateHistory'

    def add_arguments(self, parser):
        parser.add_argument('--buy-markup', type=float, default=50.0)
        parser.add_argument('--sell-markup', type=float, default=55.0)
        parser.add_argument('--cbn-rate', type=float, default=None,
                            help='Override CBN middle rate (skip API)')

    def handle(self, *args, **opts):
        cbn_rate = opts['cbn_rate']

        if cbn_rate is None:
            try:
                r = requests.get(CBN_CDN, timeout=15)
                data = r.json()
                rates = data.get('rates', [])
                cbn_rate = None
                for row in rates:
                    if (row.get('base') == 'USD' and row.get('quote') == 'NGN'
                            and row.get('type') == 'middle'):
                        cbn_rate = float(row.get('value'))
                        break
                if cbn_rate is None:
                    self.stdout.write(self.style.ERROR(
                        f'USD/NGN middle not found. Keys: {list(data.keys())}'
                    ))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'CBN fetch failed: {e}'))
                return

        buy_markup = Decimal(str(opts['buy_markup']))
        sell_markup = Decimal(str(opts['sell_markup']))
        cbn = Decimal(str(cbn_rate))

        buy_rate = cbn + buy_markup
        sell_rate = cbn + sell_markup

        prev = ForexRateHistory.objects.filter(
            base_currency='USD', quote_currency='NGN'
        ).order_by('-recorded_at').first()

        if prev and prev.sell_rate:
            change = abs((sell_rate - prev.sell_rate) / prev.sell_rate) * 100
            if change > 10:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  Large move ({change:.2f}%) vs previous {prev.sell_rate}. '
                    f'Confirm with --cbn-rate=<value> if intentional.'
                ))

        ForexRateHistory.objects.create(
            base_currency='USD',
            quote_currency='NGN',
            rate=cbn,
            source_rate=cbn,
            source='CBN',
            buy_rate=buy_rate,
            sell_rate=sell_rate,
        )

        self.stdout.write(self.style.SUCCESS(
            f'✓ CBN ₦{cbn:,.4f} → BUY ₦{buy_rate:,.2f} / SELL ₦{sell_rate:,.2f} '
            f'at {timezone.now().strftime("%d %b %Y %H:%M")}'
        ))