import requests
import json
from decimal import Decimal, ROUND_DOWN

url_buy = "http://127.0.0.1:8000/api/trading/buy/"
url_sell = "http://127.0.0.1:8000/api/trading/sell/"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0NDQ5NTg2LCJpYXQiOjE3NzQ0NDIzODcsImp0aSI6ImNhZGU3NmQwM2FmMTRjOGRiODE4MGEzZThmODkwNGIyIiwidXNlcl9pZCI6IjA1YTZjNzk3LTJlMTctNDAyYS1iOTdjLWE0YzEyNDU0YmFkMCJ9.6xMfqTreJGz675UR3M6WrsJ6VeuYUAda-3lXVu4J6wQ"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

btc_id = "d2d5477c-238d-4b7f-bc0a-cefc0bb67949"

print("=" * 50)
print("STEP 1: Buying BTC with $100")
print("=" * 50)

buy_data = {
    "token_id": btc_id,
    "amount_usdc": 100
}

response = requests.post(url_buy, headers=headers, json=buy_data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}\n")

if response.status_code == 200:
    result = response.json()
    quantity_str = result['purchase']['quantity']
    quantity = Decimal(quantity_str)
    
    # Round to 8 decimal places
    quantity_rounded = quantity.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
    print(f"Bought {quantity_rounded} BTC (rounded to 8 decimals)")
    
    print("\n" + "=" * 50)
    print("STEP 2: Selling same BTC at current price")
    print("=" * 50)
    
    sell_data = {
        "token_id": btc_id,
        "quantity": float(quantity_rounded)
    }
    
    response = requests.post(url_sell, headers=headers, json=sell_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")