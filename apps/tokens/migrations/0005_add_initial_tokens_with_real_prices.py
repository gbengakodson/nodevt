from django.db import migrations
from decimal import Decimal


def add_initial_tokens(apps, schema_editor):
    CryptoToken = apps.get_model('tokens', 'CryptoToken')

    # Real prices from CoinGecko (March 2026)
    tokens = [
        ('BTC', 'Bitcoin', Decimal('71699')),
        ('ETH', 'Ethereum', Decimal('2187.85')),
        ('BNB', 'Binance Coin', Decimal('647.11')),
        ('SOL', 'Solana', Decimal('91.28')),
        ('XRP', 'Ripple', Decimal('1.41')),
        ('ADA', 'Cardano', Decimal('0.27399')),
        ('DOGE', 'Dogecoin', Decimal('0.097144')),
        ('AVAX', 'Avalanche', Decimal('9.76')),
        ('DOT', 'Polkadot', Decimal('1.39')),
        ('PEPE', 'Pepe', Decimal('0.00000355')),
        ('LINK', 'Chainlink', Decimal('9.43')),
        ('UNI', 'Uniswap', Decimal('3.72')),
        ('ATOM', 'Cosmos', Decimal('1.80')),
        ('LTC', 'Litecoin', Decimal('56.42')),
        ('NEAR', 'NEAR Protocol', Decimal('1.31')),
        ('ALGO', 'Algorand', Decimal('0.087531')),
        ('VET', 'VeChain', Decimal('0.00720875')),
        ('FTM', 'Fantom', Decimal('0.04645456')),
        ('EGLD', 'MultiversX', Decimal('4.04')),
        ('THETA', 'Theta Network', Decimal('0.164249')),
    ]

    for symbol, name, price in tokens:
        CryptoToken.objects.get_or_create(
            symbol=symbol,
            defaults={
                'name': name,
                'current_price': price,
                'is_active': True
            }
        )
    print(f"Added {len(tokens)} tokens to database")


def remove_tokens(apps, schema_editor):
    CryptoToken = apps.get_model('tokens', 'CryptoToken')
    CryptoToken.objects.all().delete()
    print("Removed all tokens")


class Migration(migrations.Migration):
    dependencies = [
        ('tokens', '0004_add_initial_tokens.py'),  # Check your last migration number
    ]

    operations = [
        migrations.RunPython(add_initial_tokens, remove_tokens),
    ]