from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .stock_service import STOCK_UNIVERSE, NG_STOCKS
from .models import StockPrice, FiatBalance, StockOrder
from decimal import Decimal


class StockBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = StockOrder.objects.filter(user=request.user).order_by('-created_at')[:30]
        history = [
            {
                'id': str(o.id),
                'symbol': o.symbol,
                'side': o.side,
                'amount_usdc': float(o.amount_usdc),
                'status': o.status,
                'created_at': o.created_at.strftime('%b %d, %H:%M'),
            }
            for o in orders
        ]

        data = []
        for symbol, name in STOCK_UNIVERSE.items():
            balance_obj, _ = FiatBalance.objects.get_or_create(
                user=request.user, currency=symbol,
                defaults={'balance': Decimal('0')}
            )

            sp = StockPrice.objects.filter(symbol=symbol).first()
            price = sp.price if sp else Decimal('0')
            change = sp.change_24h if sp else Decimal('0')

            currency = 'NGN' if symbol in NG_STOCKS else 'USD'

            data.append({
                'symbol': symbol,
                'name': name,
                'balance': float(balance_obj.balance),
                'price': float(price),
                'change_24h': float(change),
                'currency': currency,
            })

        return Response({'stocks': data, 'history': history})