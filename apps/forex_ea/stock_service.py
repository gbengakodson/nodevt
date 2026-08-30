import requests
from datetime import date
import time

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"
ITICK_TOKEN = "373ac1195a174064bf4f3c0c5c551395fe5d733854d94247b801b20207716c99"
ITICK_BASE_URL = "https://api0.itick.org"

STOCK_UNIVERSE = {
    # Foreign stocks (Binance token names, price via Alpha Vantage)
    'NVDA': 'NVIDIA Corporation',
    'SPCX': 'SpaceX (Private Equity Index)',
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'WMT': 'Walmart Inc.',
    'META': 'Meta Platforms Inc.',
    'AMZN': 'Amazon.com Inc.',
    'GOOG': 'Alphabet Inc. Class C',
    # Nigerian stocks (NGX, price via iTick)
    'ZENITHBANK': 'Zenith Bank Plc',
    'GTCO': 'Guaranty Trust Holding Co',
    'MTNN': 'MTN Nigeria Communications Plc',
    'DANGCEM': 'Dangote Cement Plc',
    'ACCESSCORP': 'Access Holdings Plc',
    'UBA': 'United Bank for Africa Plc',
    'SEPLAT': 'Seplat Energy Plc',
}

ALPHA_SYMBOLS = {
    'NVDA': 'NVDA',
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'WMT': 'WMT',
    'META': 'META',
    'AMZN': 'AMZN',
    'GOOG': 'GOOG',
}

FALLBACK_STOCK_PRICES = {
    'NVDA': 115.00,
    'SPCX': 150.00,   # private proxy, estimated
    'AAPL': 312.00,
    'MSFT': 490.00,
    'WMT': 95.00,
    'META': 580.00,
    'AMZN': 210.00,
    'GOOG': 175.00,
    'ZENITHBANK': 45.00,
    'GTCO': 55.00,
    'MTNN': 280.00,
    'DANGCEM': 650.00,
    'ACCESSCORP': 30.00,
    'UBA': 28.00,
    'SEPLAT': 2500.00,
}

NG_STOCKS = ['ZENITHBANK','GTCO','MTNN','DANGCEM','ACCESSCORP','UBA','SEPLAT']

_price_cache = {}

def get_ng_stock_quote(symbol):
    """Fetch live Nigerian stock price from iTick."""
    url = f"{ITICK_BASE_URL}/stock/quote"
    params = {"region": "ng", "code": symbol.upper()}
    headers = {"accept": "application/json", "token": ITICK_TOKEN}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0 and data.get('data'):
            q = data['data']
            return {
                'price': float(q.get('ld', 0)),
                'change_24h': float(q.get('chp', 0))
            }
    except Exception:
        pass
    return {'price': 0, 'change_24h': 0}

def get_stock_quote(symbol):
    if symbol in _price_cache:
        return _price_cache[symbol]

    if symbol in NG_STOCKS:
        result = get_ng_stock_quote(symbol)
    else:
        alpha_symbol = ALPHA_SYMBOLS.get(symbol)
        if not alpha_symbol:
            return {'price': 0, 'change_24h': 0}
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=GLOBAL_QUOTE&symbol={alpha_symbol}&apikey={ALPHA_VANTAGE_KEY}"
        )
        try:
            data = requests.get(url, timeout=10).json()
            quote = data.get('Global Quote')
            if quote:
                result = {
                    'price': float(quote.get('05. price', 0)),
                    'change_24h': float(quote.get('10. change percent', '0%').replace('%', ''))
                }
            else:
                result = {'price': 0, 'change_24h': 0}
        except Exception:
            result = {'price': 0, 'change_24h': 0}
        time.sleep(12)

    if result.get('price', 0) == 0 and symbol in FALLBACK_STOCK_PRICES:
        result = {
            'price': FALLBACK_STOCK_PRICES[symbol],
            'change_24h': 0.0,
            'source': 'estimated'
        }

    _price_cache[symbol] = result
    return result