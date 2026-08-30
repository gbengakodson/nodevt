from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .stock_service import STOCK_UNIVERSE
from .models import StockPrice, FiatBalance
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
            stock_price = StockPrice.objects.filter(symbol=symbol).first()
            price = stock_price.price if stock_price else 0
            change = stock_price.change_24h if stock_price else 0
            data.append({
                'symbol': symbol,
                'name': name,
                'balance': float(balance_obj.balance),
                'price': float(price),
                'change_24h': float(change),
            })
        return Response({'stocks': data})