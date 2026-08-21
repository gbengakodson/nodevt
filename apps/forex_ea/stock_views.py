from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .stock_service import STOCK_UNIVERSE, get_stock_quote
from .models import FiatBalance
from decimal import Decimal
import requests


class StockBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = []
        for symbol, name in STOCK_UNIVERSE.items():
            balance_obj, _ = FiatBalance.objects.get_or_create(
                user=request.user,
                currency=symbol,
                defaults={'balance': Decimal('0')}
            )
            quote = get_stock_quote(symbol)
            data.append({
                'symbol': symbol,
                'name': name,
                'balance': float(balance_obj.balance),
                'price': quote.get('price', 0),
                'change_24h': quote.get('change_24h', 0),
            })
        return Response({'stocks': data})