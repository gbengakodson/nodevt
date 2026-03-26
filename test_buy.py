import requests
import json

url = "http://127.0.0.1:8000/api/trading/buy/"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0NDQ5NTg2LCJpYXQiOjE3NzQ0NDIzODcsImp0aSI6ImNhZGU3NmQwM2FmMTRjOGRiODE4MGEzZThmODkwNGIyIiwidXNlcl9pZCI6IjA1YTZjNzk3LTJlMTctNDAyYS1iOTdjLWE0YzEyNDU0YmFkMCJ9.6xMfqTreJGz675UR3M6WrsJ6VeuYUAda-3lXVu4J6wQ"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

data = {
    "token_id": "d2d5477c-238d-4b7f-bc0a-cefc0bb67949",
    "amount_usdc": 100
}

response = requests.post(url, headers=headers, json=data)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")