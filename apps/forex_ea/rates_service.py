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
    latest_rates = {}
    try:
        for h in ForexRateHistory.objects.filter(base_currency='USD').order_by('recorded_at'):
            latest_rates[h.quote_currency] = float(h.rate)
    except Exception:
        pass

    for symbol in ['EUR', 'GBP', 'NGN', 'GOLD', 'USOIL']:
        data[symbol] = {
            'price': latest_rates.get(symbol, 0),
            'change_24h': 0.0
        }

    data['USD'] = {'price': 1.0, 'change_24h': 0.0}
    return data