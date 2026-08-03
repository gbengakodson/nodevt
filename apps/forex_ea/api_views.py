from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .models import UserForexProfile, ForexTrade, ForexMLM, ForexCommission, MasterTrade, SlaveAccount, SlaveTrade
from .auth import EAApiKeyAuthentication
from apps.wallets.models import Wallet
from decimal import Decimal
from apps.wallets.security.encryption import EncryptionService
from datetime import datetime

User = get_user_model()

class AuthenticateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        mt5_account = request.data.get('mt5_account')
        api_key = request.data.get('api_key')
        if not mt5_account or not api_key:
            return Response({'error': 'Missing mt5_account or api_key'}, status=400)
        try:
            profile = UserForexProfile.objects.select_related('user').get(mt5_account=mt5_account)
        except UserForexProfile.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=401)
        if not profile.check_api_key(api_key):
            return Response({'error': 'Invalid credentials'}, status=401)

        user = profile.user
        try:
            wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
            balance = wallet.balance
        except Wallet.DoesNotExist:
            balance = Decimal(0)

        if balance < Decimal('0.50'):
            return Response({'error': 'Insufficient balance'}, status=403)

        return Response({
            'user_id': str(user.id),
            'email': user.email,
            'balance': float(balance),
            'currency': 'USDT',
            'broker': profile.broker
        })


class BalanceView(APIView):
    authentication_classes = [EAApiKeyAuthentication]

    def get(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user, wallet_type='GRAND')
            balance = wallet.balance
        except Wallet.DoesNotExist:
            balance = Decimal(0)
        return Response({'balance': float(balance), 'currency': 'USDT'})


class ReportTradeView(APIView):
    authentication_classes = [EAApiKeyAuthentication]
    FEE = Decimal('0.50')

    def post(self, request):
        user = request.user
        required = ['mt5_account', 'ticket', 'symbol', 'open_time', 'close_time', 'profit', 'volume', 'trade_type', 'magic_number']
        data = {k: request.data.get(k) for k in required}
        if None in data.values():
            return Response({'error': 'Missing required fields'}, status=400)

        try:
            wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found'}, status=500)

        if wallet.balance < self.FEE:
            return Response({'error': 'Insufficient balance for fee'}, status=402)

        wallet.balance -= self.FEE
        wallet.save()

        trade = ForexTrade.objects.create(
            user=user, mt5_account=data['mt5_account'], ticket=data['ticket'],
            symbol=data['symbol'], open_time=data['open_time'], close_time=data['close_time'],
            profit=data['profit'], volume=data['volume'], trade_type=data['trade_type'],
            magic_number=data['magic_number'], fee_deducted=self.FEE
        )

        commission_rates = [Decimal('0.20'), Decimal('0.10'), Decimal('0.05'), Decimal('0.03'), Decimal('0.02')]
        upline = ForexMLM.get_upline(user, levels=5)
        paid = {}
        for i, sponsor in enumerate(upline):
            if i >= len(commission_rates):
                break
            amount = self.FEE * commission_rates[i]
            try:
                sp_wallet = Wallet.objects.get(user=sponsor, wallet_type='GRAND')
                sp_wallet.balance += amount
                sp_wallet.save()
            except Wallet.DoesNotExist:
                pass
            ForexCommission.objects.create(
                from_user=user, to_user=sponsor, trade=trade, level=i+1, amount=amount
            )
            paid[f'level_{i+1}'] = float(amount)

        return Response({
            'status': 'fee_deducted',
            'fee_charged': float(self.FEE),
            'new_balance': float(wallet.balance),
            'commissions_paid': paid
        })


class ForexProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.forex_profile
            masked = profile.api_key_hash[:10] + '...' if profile.api_key_hash else 'Not set'
        except UserForexProfile.DoesNotExist:
            return Response({'active': False})

        wallet = Wallet.objects.filter(user=request.user, wallet_type='GRAND').first()
        return Response({
            'active': True,
            'mt5_account': profile.mt5_account,
            'broker': profile.broker,
            'api_key_masked': masked,
            'balance': float(wallet.balance) if wallet else 0,
            'currency': 'USDT'
        })


class ActivateForexView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        mt5 = request.data.get('mt5_account')
        broker = request.data.get('broker')
        regenerate = request.data.get('regenerate', False)

        try:
            profile = request.user.forex_profile
        except UserForexProfile.DoesNotExist:
            if not mt5 or not broker:
                return Response({'error': 'Missing fields'}, status=400)
            if UserForexProfile.objects.filter(mt5_account=mt5).exists():
                return Response({'error': 'MT5 account already in use'}, status=400)
            raw_key = UserForexProfile.generate_api_key()
            profile = UserForexProfile.objects.create(
                user=request.user, mt5_account=mt5, broker=broker
            )
            profile.set_api_key(raw_key)
            profile.save()
            return Response({'success': True, 'api_key': raw_key})

        # Profile exists
        if regenerate:
            raw_key = UserForexProfile.generate_api_key()
            profile.set_api_key(raw_key)
            profile.save()
            return Response({'success': True, 'api_key': raw_key})
        else:
            return Response({'error': 'EA already activated. Use regenerate=true to get a new key.'}, status=400)


from .models import MasterTrade, SlaveAccount, SlaveTrade  # add this import at top if not already

class TradeOpenedView(APIView):
    authentication_classes = [EAApiKeyAuthentication]

    def post(self, request):
        user = request.user
        required = ['mt5_account', 'symbol', 'direction', 'volume', 'open_price', 'open_time', 'ticket', 'magic_number']
        data = {k: request.data.get(k) for k in required}
        if None in data.values():
            return Response({'error': 'Missing required fields'}, status=400)

        # Parse open_time – handle both "2026.08.03 09:56:58" and "2026-08-03 09:56:58"
        open_time_str = data['open_time']
        for fmt in ('%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
            try:
                open_time = datetime.strptime(open_time_str, fmt)
                break
            except ValueError:
                continue
        else:
            return Response({'error': 'Invalid open_time format. Use YYYY.MM.DD HH:MM:SS'}, status=400)

        # Make timezone aware (use UTC if your settings use UTC)
        from django.utils.timezone import make_aware
        open_time = make_aware(open_time)

        trade = MasterTrade.objects.create(
            user=user,
            master_mt5_account=data['mt5_account'],
            symbol=data['symbol'],
            direction=data['direction'],
            volume=data['volume'],
            open_price=data['open_price'],
            open_time=open_time,
            ticket=data['ticket'],
            magic_number=data['magic_number'],
            status='pending'
        )
        return Response({'status': 'recorded', 'master_trade_id': str(trade.id)}, status=201)


class TradeClosedView(APIView):
    authentication_classes = [EAApiKeyAuthentication]

    def post(self, request):
        ticket = request.data.get('ticket')
        close_time_str = request.data.get('close_time')
        if not ticket or not close_time_str:
            return Response({'error': 'Missing ticket or close_time'}, status=400)

        # Parse close_time
        for fmt in ('%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
            try:
                close_time = datetime.strptime(close_time_str, fmt)
                break
            except ValueError:
                continue
        else:
            return Response({'error': 'Invalid close_time format'}, status=400)
        from django.utils.timezone import make_aware
        close_time = make_aware(close_time)

        try:
            trade = MasterTrade.objects.get(ticket=ticket, user=request.user)
        except MasterTrade.DoesNotExist:
            return Response({'error': 'Master trade not found'}, status=404)

        trade.status = 'closed'
        trade.closed_at = close_time
        trade.save()
        return Response({'status': 'closed', 'master_trade_id': str(trade.id)})


class SlaveAccountView(APIView):
    """User adds/views their slave accounts."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        slaves = SlaveAccount.objects.filter(user=request.user)
        data = []
        for s in slaves:
            data.append({
                'id': str(s.id),
                'mt5_account': s.mt5_account,
                'broker_server': s.broker_server,
                'is_active': s.is_active,
                'created_at': s.created_at
            })
        return Response({'slaves': data})

    def post(self, request):
        mt5_account = request.data.get('mt5_account')
        password = request.data.get('password')       # raw password from user
        broker_server = request.data.get('broker_server')
        if not mt5_account or not password or not broker_server:
            return Response({'error': 'Missing mt5_account, password, or broker_server'}, status=400)

        # Encrypt password before storage
        encrypted_pw = EncryptionService.encrypt(password)
        slave = SlaveAccount.objects.create(
            user=request.user,
            mt5_account=mt5_account,
            mt5_password_encrypted=encrypted_pw,
            broker_server=broker_server
        )
        return Response({
            'success': True,
            'id': str(slave.id),
            'mt5_account': slave.mt5_account
        }, status=201)


class SlaveTradeStatusView(APIView):
    """Returns recent slave trades for the logged-in user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all slave accounts belonging to this user
        slave_accounts = SlaveAccount.objects.filter(user=request.user)
        trades = SlaveTrade.objects.filter(slave_account__in=slave_accounts).order_by('-created_at')[:20]
        data = []
        for t in trades:
            data.append({
                'id': str(t.id),
                'master_ticket': t.master_trade.ticket,
                'symbol': t.master_trade.symbol,
                'direction': t.master_trade.direction,
                'volume': t.master_trade.volume,
                'slave_ticket': t.slave_ticket,
                'closed': t.closed,
                'created_at': t.created_at
            })
        return Response({'trades': data})


class SignalView(APIView):
    authentication_classes = [EAApiKeyAuthentication]

    def post(self, request):
        # We don't need to do anything with the signal for now
        return Response({'status': 'signal_received'})
