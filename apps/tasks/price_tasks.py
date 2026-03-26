from celery import shared_task
from django.core.cache import cache
from decimal import Decimal
import requests

@shared_task
def update_all_token_prices():
    """Update prices for all tokens from CoinGecko"""
    from apps.tokens.models import CryptoToken
    from apps.tokens.services import PriceService
    
    print("Fetching real-time prices from CoinGecko...")
    prices = PriceService.fetch_all_prices()
    
    if prices:
        updated = 0
        for symbol, price in prices.items():
            try:
                token = CryptoToken.objects.get(symbol=symbol)
                token.current_price = price
                token.save()
                updated += 1
            except CryptoToken.DoesNotExist:
                continue
        
        print(f"Updated {updated} token prices")
        return updated
    else:
        print("Failed to fetch prices")
        return 0

@shared_task
def update_single_token_price(symbol):
    """Update price for a single token"""
    from apps.tokens.models import CryptoToken
    from apps.tokens.services import PriceService
    
    prices = PriceService.fetch_all_prices()
    if prices and symbol in prices:
        token = CryptoToken.objects.get(symbol=symbol)
        token.current_price = prices[symbol]
        token.save()
        return f"Updated {symbol} to ${prices[symbol]}"
    return f"Failed to update {symbol}"