import requests
from django.conf import settings

STOCK_UNIVERSE = {
    # Binance Stock Tokens
    'NVDA': 'NVIDIA Corporation',
    'SPCX': 'SpaceX (Private Equity Index)',
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'WMT': 'Walmart Inc.',
    'META': 'Meta Platforms Inc.',
    'AMZN': 'Amazon.com Inc.',
    'GOOG': 'Alphabet Inc. Class C',
    # Nigerian stocks (NGX)
    'ZENITHBANK': 'Zenith Bank Plc',
    'GTCO': 'Guaranty Trust Holding Co',
    'MTNN': 'MTN Nigeria Communications Plc',
    'DANGCEM': 'Dangote Cement Plc',
    'ACCESSCORP': 'Access Holdings Plc',
    'UBA': 'United Bank for Africa Plc',
    'SEPLAT': 'Seplat Energy Plc',
}

BINANCE_STOCK_PAIRS = {
    'NVDA': 'NVDAUSDT',
    'SPCX': 'SPCXUSDT',
    'AAPL': 'AAPLUSDT',
    'MSFT': 'MSFTUSDT',
    'WMT': 'WMTUSDT',
    'META': 'METAUSDT',
    'AMZN': 'AMZNUSDT',
    'GOOG': 'GOOGUSDT',
}

def get_stock_quote(symbol):
    """Fetch live price and 24h change from Binance for stock tokens."""
    pair = BINANCE_STOCK_PAIRS.get(symbol)
    if not pair:
        return {'price': 0, 'change_24h': 0}

    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        resp = requests.get(url, params={'symbol': pair}, timeout=10)
        data = resp.json()
        if 'lastPrice' in data:
            return {
                'price': float(data['lastPrice']),
                'change_24h': float(data.get('priceChangePercent', 0))
            }
    except Exception:
        pass

    return {'price': 0, 'change_24h': 0}