import requests

ALPHA_VANTAGE_KEY = "GJB9YUD6E6ACTXKC"

STOCK_UNIVERSE = {
    # Binance Stock Tokens (for display; price from Alpha Vantage)
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

ALPHA_SYMBOLS = {
    'NVDA': 'NVDA',
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'WMT': 'WMT',
    'META': 'META',
    'AMZN': 'AMZN',
    'GOOG': 'GOOG',
    # SPCX not available on Alpha Vantage
}

def get_stock_quote(symbol):
    """Fetch live price and 24h change from Alpha Vantage."""
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
            return {
                'price': float(quote.get('05. price', 0)),
                'change_24h': float(quote.get('10. change percent', '0%').replace('%', ''))
            }
    except Exception:
        pass

    return {'price': 0, 'change_24h': 0}