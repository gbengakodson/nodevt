import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.tokens.models import CryptoToken

tokens = [
    ('BTC', 'Bitcoin'),
    ('ETH', 'Ethereum'),
    ('BNB', 'Binance Coin'),
    ('SOL', 'Solana'),
    ('XRP', 'Ripple'),
    ('ADA', 'Cardano'),
    ('DOGE', 'Dogecoin'),
    ('AVAX', 'Avalanche'),
    ('DOT', 'Polkadot'),
    ('MATIC', 'Polygon'),
    ('LINK', 'Chainlink'),
    ('UNI', 'Uniswap'),
    ('ATOM', 'Cosmos'),
    ('LTC', 'Litecoin'),
    ('NEAR', 'NEAR Protocol'),
    ('ALGO', 'Algorand'),
    ('VET', 'VeChain'),
    ('FTM', 'Fantom'),
    ('EGLD', 'MultiversX'),
    ('THETA', 'Theta Network'),
]

for symbol, name in tokens:
    token, created = CryptoToken.objects.get_or_create(
        symbol=symbol,
        defaults={
            'name': name,
            'current_price': 0,  # You'll update this later
            'is_active': True
        }
    )
    if created:
        print(f"Added {symbol} - {name}")
    else:
        print(f"{symbol} already exists")

print(f"\nTotal tokens: {CryptoToken.objects.count()}")