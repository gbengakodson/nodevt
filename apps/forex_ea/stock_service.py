import requests
import time
from datetime import date

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"

STOCK_UNIVERSE = {
    'NVDA': 'NVIDIA Corporation',
    'SPCX': 'SpaceX (Private Equity Index)',
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'WMT': 'Walmart Inc.',
    'META': 'Meta Platforms Inc.',
    'AMZN': 'Amazon.com Inc.',
    'GOOG': 'Alphabet Inc. Class C',
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

_price_cache = {}
_cache_date = None

def get_stock_quote(symbol):
    global _cache_date
    today = date.today()
    if _cache_date != today:
        _price_cache.clear()
        _cache_date = today

    if symbol in _price_cache:
        return _price_cache[symbol]

    alpha_symbol = ALPHA_SYMBOLS.get(symbol)
    if not alpha_symbol:
        return {'price': 0, 'change_24h': 0}

    url = (
        f"https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE&symbol={alpha_symbol}&apikey={ALPHA_VANTAGE_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
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

    _price_cache[symbol] = result
    time.sleep(12)   # respect free tier rate limit (5/min)
    return result