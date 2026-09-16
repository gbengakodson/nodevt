from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.forex_ea.models import (
    StockPrice, StockPriceHistory, StockOrder,
    FiatBalance, ForexRateHistory
)
from apps.forex_ea.stock_service import NG_STOCKS


FOREX_PAIRS = {
    # input_key -> (base, quote, transform)
    # transform: how to convert the input value into "1 USD = X quote"
    'EURUSD':  ('USD', 'EUR',  'invert'),   # 1.1533 → 1 USD = 0.8671 EUR
    'GBPUSD':  ('USD', 'GBP',  'invert'),
    'USDNGN':  ('USD', 'NGN',  'direct'),   # 1325.50 → 1 USD = 1325.50 NGN
    'GOLD':    ('USD', 'GOLD', 'direct'),
    'USOIL':   ('USD', 'USOIL','direct'),
}

STOCK_SYMBOLS = {
    'AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'GOOGL', 'META',
    'KO', 'VOO', 'NFLX', 'WMT', 'SPCX',
    'ZENITHBANK', 'GTCO', 'MTNN', 'DANGCEM',
    'ACCESSCORP', 'UBA', 'SEPLAT',
}


class Command(BaseCommand):
    help = 'One-shot update for stocks + forex (EUR/GBP/NGN/GOLD/USOIL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data', required=True,
            help='Comma-separated KEY=VALUE pairs. Forex keys: EURUSD, GBPUSD, USDNGN, GOLD, USOIL'
        )

    def handle(self, *args, **opts):
        raw = opts['data']
        pairs = [p.strip() for p in raw.replace('\n', ',').split(',') if '=' in p]

        stock_updates = {}
        forex_updates = {}

        for pair in pairs:
            key, val = pair.split('=', 1)
            key = key.strip().upper()
            try:
                value = Decimal(val.strip())
            except Exception:
                self.stdout.write(self.style.ERROR(f'Bad value: {pair}'))
                continue

            if key in FOREX_PAIRS:
                forex_updates[key] = value
            elif key in STOCK_SYMBOLS:
                stock_updates[key] = value
            else:
                self.stdout.write(self.style.WARNING(f'Unknown symbol: {key}'))

        # ── STOCKS ──
        self.stdout.write(self.style.MIGRATE_HEADING('\nSTOCKS'))
        for sym, new_price in stock_updates.items():
            old = StockPrice.objects.filter(symbol=sym).first()
            old_price = old.price if old else Decimal('0')

            if old_price and old_price > 0:
                change = ((new_price - old_price) / old_price) * 100
            else:
                change = Decimal('0')

            StockPrice.objects.update_or_create(
                symbol=sym,
                defaults={'price': new_price, 'change_24h': change}
            )
            StockPriceHistory.objects.create(symbol=sym, price=new_price)

            prefix = '₦' if sym in NG_STOCKS else '$'
            arrow = '▲' if change > 0 else ('▼' if change < 0 else '▬')
            self.stdout.write(f'  {sym:<12} {prefix}{new_price:>12,.2f}   {arrow} {change:+.2f}%')

        # ── FOREX + COMMODITIES ──
        self.stdout.write(self.style.MIGRATE_HEADING('\nFOREX & COMMODITIES'))
        for input_key, raw_value in forex_updates.items():
            base, quote, transform = FOREX_PAIRS[input_key]

            if transform == 'invert':
                stored_rate = (Decimal('1') / raw_value) if raw_value else Decimal('0')
            else:
                stored_rate = raw_value

            # Compute 24h change vs previous stored rate
            prev = ForexRateHistory.objects.filter(
                base_currency=base, quote_currency=quote
            ).order_by('-recorded_at').first()

            if prev and prev.rate and prev.rate > 0:
                change = ((stored_rate - prev.rate) / prev.rate) * 100
            else:
                change = Decimal('0')

            ForexRateHistory.objects.create(
                base_currency=base, quote_currency=quote,
                rate=stored_rate
            )

            arrow = '▲' if change > 0 else ('▼' if change < 0 else '▬')
            display = f'1 USD = {stored_rate:,.4f} {quote}' if transform == 'invert' else f'1 USD = {stored_rate:,.2f} {quote}'
            self.stdout.write(f'  {input_key:<8} {display:<28}   {arrow} {change:+.2f}%')

        # ── Execute pending BUY orders ──
        pending = StockOrder.objects.filter(side='BUY', status='PENDING')
        if pending.exists():
            self.stdout.write(self.style.MIGRATE_HEADING('\nPENDING ORDERS'))
            ngn_rate = None
            for order in pending:
                sp = StockPrice.objects.filter(symbol=order.symbol).first()
                if not sp or sp.price == 0:
                    continue

                if order.symbol in NG_STOCKS:
                    if ngn_rate is None:
                        r = ForexRateHistory.objects.filter(
                            base_currency='USD', quote_currency='NGN'
                        ).order_by('-recorded_at').first()
                        if not r:
                            self.stdout.write(self.style.WARNING('  No USD/NGN rate — skipping NG orders'))
                            continue
                        ngn_rate = r.rate
                    shares = (order.amount_usdc * ngn_rate) / sp.price
                else:
                    shares = order.amount_usdc / sp.price

                fb, _ = FiatBalance.objects.get_or_create(
                    user=order.user, currency=order.symbol,
                    defaults={'balance': Decimal('0')}
                )
                fb.balance += shares
                fb.save()

                order.status = 'EXECUTED'
                order.executed_at = timezone.now()
                order.save()

                self.stdout.write(self.style.SUCCESS(
                    f'  EXECUTED {order.side} {order.symbol} for {order.user.email} — {shares:.6f} shares'
                ))

        self.stdout.write(self.style.SUCCESS('\n✓ All assets updated.'))