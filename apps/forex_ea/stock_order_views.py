from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.utils import timezone
from .models import StockOrder, FiatBalance
from apps.wallets.models import Wallet

class StockOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        symbol = request.data.get('symbol', '').upper()
        side = request.data.get('side', 'BUY').upper()
        try:
            amount_usdc = Decimal(str(request.data.get('amount_usdc', '0')))
        except:
            return Response({'error': 'Invalid amount'}, status=400)

        if not symbol or amount_usdc <= 0:
            return Response({'error': 'Symbol and positive amount required'}, status=400)

        if side not in ['BUY', 'SELL']:
            return Response({'error': 'Invalid side'}, status=400)

        # For BUY: check user has enough USDC in GRAND wallet (or on-chain)
        if side == 'BUY':
            wallet = Wallet.objects.filter(user=request.user, wallet_type='GRAND').first()
            if not wallet or wallet.balance < amount_usdc:
                return Response({'error': 'Insufficient USDC balance'}, status=400)
            # Deduct USDC immediately and hold in pending order? Or just record pending and deduct later?
            # For simplicity, deduct now and refund if order cancelled/fails.
            wallet.balance -= amount_usdc
            wallet.save()

        order = StockOrder.objects.create(
            user=request.user,
            symbol=symbol,
            side=side,
            amount_usdc=amount_usdc,
            status='PENDING'
        )

        return Response({
            'success': True,
            'order_id': str(order.id),
            'status': order.status,
            'message': f'{side} order placed for {symbol}. Will execute at next price update.'
        })