import requests
from decimal import Decimal
import pandas as pd
from datetime import datetime, timedelta



class PriceService:
    COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
    
    SYMBOL_TO_ID = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'AVAX': 'avalanche-2',
        'DOT': 'polkadot',
        'PEPE': 'pepe',
        'LINK': 'chainlink',
        'UNI': 'uniswap',
        'ATOM': 'cosmos',
        'LTC': 'litecoin',
        'NEAR': 'near',
        'ALGO': 'algorand',
        'VET': 'vechain',
        'FTM': 'fantom',
        'EGLD': 'elrond-erd-2',
        'THETA': 'theta-token',
    }
    
    @classmethod
    def fetch_all_prices(cls):
        """Fetch real-time prices for all tokens from CoinGecko"""
        token_ids = list(cls.SYMBOL_TO_ID.values())
        ids_string = ','.join(token_ids)
        
        try:
            response = requests.get(
                cls.COINGECKO_API,
                params={
                    'ids': ids_string,
                    'vs_currencies': 'usd'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                prices = {}
                
                for symbol, coin_id in cls.SYMBOL_TO_ID.items():
                    if coin_id in data:
                        if 'usd' in data[coin_id]:
                            price = Decimal(str(data[coin_id]['usd']))
                            prices[symbol] = price
                        else:
                            print(f"Warning: No USD price for {coin_id}")
                    else:
                        print(f"Warning: {coin_id} not found in response")
                
                return prices if prices else None
            else:
                print(f"Error fetching prices: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    @classmethod
    def update_token_prices(cls):
        """Update all token prices in database"""
        prices = cls.fetch_all_prices()
        
        if prices:
            from .models import CryptoToken
            
            updated = 0
            for symbol, price in prices.items():
                try:
                    token = CryptoToken.objects.get(symbol=symbol)
                    token.current_price = price
                    token.save()
                    updated += 1
                    print(f"Updated {symbol}: ${price}")
                except CryptoToken.DoesNotExist:
                    print(f"Token {symbol} not found in database")
            
            return updated
        return 0

    @classmethod
    def get_historical_dataframe(cls, coin_symbol, days=7):
        """Get historical price data as pandas DataFrame"""
        coin_id = cls.SYMBOL_TO_ID.get(coin_symbol)
        if not coin_id:
            return pd.DataFrame()

        try:
            response = requests.get(
                f"{cls.COINGECKO_API}/coins/{coin_id}/market_chart",
                params={'vs_currency': 'usd', 'days': days},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                prices = data['prices']

                # Create DataFrame
                df = pd.DataFrame(prices, columns=['timestamp', 'price'])
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['date_str'] = df['date'].dt.strftime('%Y-%m-%d %H:%M')

                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return pd.DataFrame()