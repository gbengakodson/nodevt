import requests
from decimal import Decimal

FREE_RATES_URL = "https://open.er-api.com/v6/latest/USD"
TWELVE_DATA_KEY = "0e71d2b553d44d7da9915a1d1c97bf45"

CURRENCY_ALIASES = {
    'USD': 'USD',
    'EUR': 'EUR',
    'GBP': 'GBP',
    'NGN': 'NGN',
}

def get_fiat_rate(base_currency, quote_currency):
    """Return 1 base = X quote using stored history rates."""
    from .models import ForexRateHistory

    if base_currency == quote_currency:
        return Decimal('1.0')

    # Get latest rates for USD base from history
    latest_rates = {}
    try:
        for h in ForexRateHistory.objects.filter(base_currency='USD').order_by('recorded_at'):
            latest_rates[h.quote_currency] = Decimal(str(h.rate))
    except Exception:
        pass

    # If no history, use fallback (same as spot)
    fallback = {'EUR': Decimal('1.16'), 'GBP': Decimal('1.35'), 'NGN': Decimal('1348'), 'GOLD': Decimal('4560'), 'USOIL': Decimal('83.40')}

    if base_currency == 'USD':
        rate = latest_rates.get(quote_currency, fallback.get(quote_currency, Decimal('0')))
        return rate
    elif quote_currency == 'USD':
        rate = latest_rates.get(base_currency, fallback.get(base_currency, Decimal('0')))
        if rate == 0:
            return Decimal('0')
        return Decimal('1') / rate
    else:
        base_to_usd = Decimal('1') / latest_rates.get(base_currency, fallback.get(base_currency, Decimal('0')))
        usd_to_quote = latest_rates.get(quote_currency, fallback.get(quote_currency, Decimal('0')))
        return base_to_usd * usd_to_quote

def get_commodity_price(symbol):
    """Return USD price for GOLD or USOIL from history."""
    from .models import ForexRateHistory

    latest = ForexRateHistory.objects.filter(
        base_currency='USD', quote_currency=symbol
    ).order_by('-recorded_at').first()

    if latest:
        return latest.rate

    # Fallback
    fallback = {'GOLD': Decimal('4560'), 'USOIL': Decimal('83.40')}
    return fallback.get(symbol, Decimal('0'))


def get_spot_rates():
    from .models import ForexRateHistory

    data = {}
    latest = {}
    previous = {}

    try:
        for h in ForexRateHistory.objects.filter(base_currency='USD').order_by('recorded_at'):
            key = h.quote_currency
            if key in latest:
                previous[key] = latest[key]
            latest[key] = h
    except Exception:
        pass

    for symbol in ['EUR', 'GBP', 'NGN', 'GOLD', 'USOIL']:
        row = latest.get(symbol)
        if not row:
            data[symbol] = {'price': 0, 'change_24h': 0.0}
            continue

        price = float(row.rate)
        prev_row = previous.get(symbol)
        prev = float(prev_row.rate) if prev_row else 0
        change = ((price - prev) / prev * 100) if prev else 0.0

        entry = {'price': price, 'change_24h': change}

        if symbol == 'NGN':
            entry['buy_rate'] = float(row.buy_rate) if row.buy_rate else price
            entry['sell_rate'] = float(row.sell_rate) if row.sell_rate else price
            entry['source_rate'] = float(row.source_rate) if row.source_rate else price
            entry['recorded_at'] = row.recorded_at.isoformat()

        data[symbol] = entry

    data['USD'] = {'price': 1.0, 'change_24h': 0.0}
    return data


def get_ngn_dealing_rate(direction):
    """
    direction: 'buy'  → user sells NGN, gets USD (you pay buy_rate)
               'sell' → user buys NGN with USD (you charge sell_rate)
    Returns Decimal NGN per USD.
    """
    from .models import ForexRateHistory

    latest = ForexRateHistory.objects.filter(
        base_currency='USD', quote_currency='NGN'
    ).order_by('-recorded_at').first()

    if not latest:
        return None

    if direction == 'buy' and latest.buy_rate:
        return latest.buy_rate
    if direction == 'sell' and latest.sell_rate:
        return latest.sell_rate
    return latest.rate



