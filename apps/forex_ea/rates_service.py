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
    """Return 1 base = X quote for fiat currencies using open.er-api.com."""
    if base_currency == quote_currency:
        return Decimal('1.0')

    # Fetch latest rates with USD as base
    resp = requests.get(FREE_RATES_URL)
    data = resp.json()
    if data.get('result') != 'success':
        raise Exception("Rate fetch failed")

    rates = data['rates']
    # Convert through USD
    if base_currency == 'USD':
        return Decimal(str(rates[quote_currency]))
    elif quote_currency == 'USD':
        return Decimal('1.0') / Decimal(str(rates[base_currency]))
    else:
        # Cross rate: base -> USD -> quote
        base_to_usd = Decimal('1.0') / Decimal(str(rates[base_currency]))
        usd_to_quote = Decimal(str(rates[quote_currency]))
        return base_to_usd * usd_to_quote

def get_commodity_price(symbol):
    """Return USD price for one unit of GOLD or USOIL using Twelve Data."""
    if symbol == 'GOLD':
        twelve_symbol = 'XAU/USD'
    elif symbol == 'USOIL':
        twelve_symbol = 'WTI/USD'   # approximate; adjust if needed
    else:
        raise Exception("Unsupported commodity")

    url = (
        f"https://api.twelvedata.com/price?symbol={twelve_symbol}&apikey={TWELVE_DATA_KEY}"
    )
    resp = requests.get(url)
    data = resp.json()
    if data.get('status') == 'error':
        raise Exception(data.get('message'))
    return Decimal(data['price'])