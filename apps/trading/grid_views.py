from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.trading.models import GridBot
from apps.wallets.models import Wallet
from decimal import Decimal


class StopGridView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        bot.status = 'STOPPED'
        bot.save()
        return Response({'success': True})


class StartGridView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        bot.status = 'ACTIVE'
        bot.save()
        return Response({'success': True})


class CloseGridView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)

        if bot.pnl <= 0:
            return Response({'error': 'PNL must be positive to close'}, status=400)

        grand_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND')
        total_return = bot.amount + bot.grid_profit + Decimal(str(bot.pnl))
        grand_wallet.balance += total_return
        grand_wallet.save()

        bot.status = 'COMPLETED'
        bot.save()

        return Response({'success': True, 'amount': float(total_return)})