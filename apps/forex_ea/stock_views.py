from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .stock_service import STOCK_UNIVERSE
from .models import FiatBalance
from decimal import Decimal
import requests

class StockBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = []
        for symbol, name in STOCK_UNIVERSE.items():
            # Get balance from FiatBalance (using symbol as currency)
            balance_obj, _ = FiatBalance.objects.get_or_create(
                user=request.user,
                currency=symbol,
                defaults={'balance': Decimal('0')}
            )
            price = Decimal('0')
            change = Decimal('0')
            # In a later step, we'll fetch live prices here.
            # For now, balance and zero price are returned.
            data.append({
                'symbol': symbol,
                'name': name,
                'balance': float(balance_obj.balance),
                'price': float(price),
                'change_24h': float(change),
            })
        return Response({'stocks': data})