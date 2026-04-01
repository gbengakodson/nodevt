import os
import requests

# Create directory if it doesn't exist
os.makedirs('static/coins', exist_ok=True)

# Coin logos URLs
logos = {
    'BTC': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
    'ETH': 'https://cryptologos.cc/logos/ethereum-eth-logo.png',
    'BNB': 'https://cryptologos.cc/logos/bnb-bnb-logo.png',
    'SOL': 'https://cryptologos.cc/logos/solana-sol-logo.png',
    'XRP': 'https://cryptologos.cc/logos/xrp-xrp-logo.png',
    'ADA': 'https://cryptologos.cc/logos/cardano-ada-logo.png',
    'DOGE': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png',
    'AVAX': 'https://cryptologos.cc/logos/avalanche-avax-logo.png',
    'DOT': 'https://assets.coingecko.com/coins/images/12171/small/polkadot.png',
    'NEAR': 'https://cryptologos.cc/logos/near-protocol-near-logo.png',
    'LTC': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png',
    'THETA': 'https://cryptologos.cc/logos/theta-theta-logo.png',
    'PEPE': 'https://cryptologos.cc/logos/pepe-pepe-logo.png',
    'LINK': 'https://cryptologos.cc/logos/chainlink-link-logo.png',
    'UNI': 'https://assets.coingecko.com/coins/images/12504/small/uni.jpg',
    'ATOM': 'https://cryptologos.cc/logos/cosmos-atom-logo.png',
    'ALGO': 'https://cryptologos.cc/logos/algorand-algo-logo.png',
    'VET': 'https://cryptologos.cc/logos/vechain-vet-logo.png',
    'FTM': 'https://cryptologos.cc/logos/fantom-ftm-logo.png',
    'EGLD': 'https://assets.coingecko.com/coins/images/12335/small/egld.png'
}

print("Downloading coin logos...")

for symbol, url in logos.items():
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            filepath = f'static/coins/{symbol}.png'
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded {symbol}.png")
        else:
            print(f"Failed to download {symbol}: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error downloading {symbol}: {e}")

print("\nDone! Logos saved in static/coins/")