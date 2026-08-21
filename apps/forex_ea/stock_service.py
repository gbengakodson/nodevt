import requests

TWELVE_DATA_KEY = "0e71d2b553d44d7da9915a1d1c97bf45"

STOCK_UNIVERSE = {
    # Nigerian stocks (NGX) – Twelve Data may not support some; we'll handle missing gracefully
    'ZENITHBANK': 'Zenith Bank Plc',
    'GTCO': 'Guaranty Trust Holding Co',
    'MTNN': 'MTN Nigeria Communications Plc',
    'DANGCEM': 'Dangote Cement Plc',
    'ACCESSCORP': 'Access Holdings Plc',
    'UBA': 'United Bank for Africa Plc',
    'SEPLAT': 'Seplat Energy Plc',
    'BUAFOODS': 'BUA Foods Plc',
    'ARADEL': 'Aradel Holdings Plc',
    'TRANSCORP': 'Transnational Corporation Plc',
    # Foreign stocks
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'TSLA': 'Tesla Inc.',
    'NVDA': 'NVIDIA Corporation',
    'AMZN': 'Amazon.com Inc.',
    'GOOGL': 'Alphabet Inc. Class A',
    'META': 'Meta Platforms Inc.',
    'KO': 'Coca-Cola Company',
    'VOO': 'S&P 500 ETF',
    'NFLX': 'Netflix Inc.',
}

# Mapping for Twelve Data symbols
TWELVE_SYMBOL_MAP = {
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'TSLA': 'TSLA',
    'NVDA': 'NVDA',
    'AMZN': 'AMZN',
    'GOOGL': 'GOOGL',
    'META': 'META',
    'KO': 'KO',
    'VOO': 'VOO',
    'NFLX': 'NFLX',
    # Nigerian stocks may not be available on free tier; we can add placeholders
}

def get_stock_quote(symbol):
    """Fetch latest price and 24h change for a stock."""
    twelve_symbol = TWELVE_SYMBOL_MAP.get(symbol)
    if not twelve_symbol:
        return {'price': 0, 'change_24h': 0}

    url = f"https://api.twelvedata.com/quote?symbol={twelve_symbol}&apikey={TWELVE_DATA_KEY}"
    resp = requests.get(url)
    data = resp.json()
    if data.get('status') == 'ok':
        return {
            'price': float(data.get('close', 0)),
            'change_24h': float(data.get('change_percent', 0))
        }
    return {'price': 0, 'change_24h': 0}