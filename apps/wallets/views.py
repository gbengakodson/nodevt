from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import DepositRequest, WithdrawalRequest
from django.db.models import Sum, Count, Avg, F
from django.contrib.auth.models import User
from apps.wallets.models import Wallet
from decimal import Decimal
from apps.tokens.models import CryptoToken, UserTokenBalance, Purchase
import logging

logger = logging.getLogger(__name__)



class SubmitDepositRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tx_hash = request.data.get('tx_hash')
        amount = request.data.get('amount')
        wallet_address = request.data.get('wallet_address')

        deposit = DepositRequest.objects.create(
            user=request.user,
            tx_hash=tx_hash,
            amount=amount,
            wallet_address=wallet_address
        )

        # Notify admin (you can add email notification here)

        return Response({'success': True, 'message': 'Deposit request submitted. Admin will review within 24 hours.'})


class SubmitWithdrawalRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get('amount')
        wallet_address = request.data.get('wallet_address')

        # Check balance
        from apps.wallets.models import Wallet
        grand_wallet = Wallet.objects.get(user=request.user, wallet_type='GRAND')

        if grand_wallet.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            wallet_address=wallet_address
        )

        return Response(
            {'success': True, 'message': 'Withdrawal request submitted. Admin will process within 24 hours.'})


class AdminDepositRequestsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        deposits = DepositRequest.objects.all().order_by('-created_at')
        data = [{
            'id': str(d.id),
            'user': d.user.email,
            'amount': str(d.amount),
            'tx_hash': d.tx_hash,
            'status': d.status,
            'created_at': d.created_at.strftime('%Y-%m-%d %H:%M')
        } for d in deposits]
        return Response(data)

    def post(self, request):
        deposit_id = request.data.get('deposit_id')
        action = request.data.get('action')  # 'confirm' or 'reject'

        deposit = DepositRequest.objects.get(id=deposit_id)

        if action == 'confirm':
            deposit.status = 'CONFIRMED'
            # Credit user's grand wallet
            from apps.wallets.models import Wallet
            grand_wallet = Wallet.objects.get(user=deposit.user, wallet_type='GRAND')
            grand_wallet.balance += deposit.amount
            grand_wallet.save()
        elif action == 'reject':
            deposit.status = 'REJECTED'

        deposit.processed_at = timezone.now()
        deposit.save()

        return Response({'success': True})


class AdminWithdrawalRequestsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        withdrawals = WithdrawalRequest.objects.all().order_by('-created_at')
        data = [{
            'id': str(w.id),
            'user': w.user.email,
            'amount': str(w.amount),
            'wallet_address': w.wallet_address,
            'status': w.status,
            'created_at': w.created_at.strftime('%Y-%m-%d %H:%M')
        } for w in withdrawals]
        return Response(data)

    def post(self, request):
        withdrawal_id = request.data.get('withdrawal_id')
        action = request.data.get('action')  # 'process' or 'reject'

        withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)

        if action == 'process':
            withdrawal.status = 'PROCESSED'
            # Deduct from user's grand wallet
            from apps.wallets.models import Wallet
            grand_wallet = Wallet.objects.get(user=withdrawal.user, wallet_type='GRAND')
            grand_wallet.balance -= withdrawal.amount
            grand_wallet.save()
        elif action == 'reject':
            withdrawal.status = 'REJECTED'

        withdrawal.processed_at = timezone.now()
        withdrawal.save()

        return Response({'success': True})


class WithdrawalRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import WithdrawalRequest
        from apps.wallets.models import Wallet

        amount = request.data.get('amount')
        wallet_address = request.data.get('wallet_address')

        if not amount or not wallet_address:
            return Response({'error': 'All fields are required'}, status=400)

        amount = Decimal(str(amount))

        if amount < 10:
            return Response({'error': 'Minimum withdrawal is $10 USDC'}, status=400)

        grand_wallet = Wallet.objects.get(user=request.user, wallet_type='GRAND')

        if grand_wallet.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            wallet_address=wallet_address
        )

        return Response({'success': True, 'message': 'Withdrawal request submitted'})


# Add these to your apps/wallets/views.py

# Add these imports at the top of your views.p


# Replace your AdminStatisticsView with this safe version
class AdminStatisticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.tokens.models import UserTokenBalance, Purchase

        # Total token VALUE (not quantity)
        total_token_value = UserTokenBalance.objects.aggregate(
            total=Sum(F('quantity') * F('token__current_price'))
        )['total'] or Decimal('0')

        total_buys = Purchase.objects.count()

        return Response({
            'total_buys': total_buys,
            'total_solds': 0,
            'total_tokens_held': float(total_token_value),  # This is now USD value
            'total_yield': 0,
            'active_sell_tokens': 0,
            'inactive_sell_tokens': 0,
            'avg_hold_time': '0d',
            'turnover_rate': '0%'
        })


# Replace your AdminHoldersView with this safe version
class AdminHoldersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.tokens.models import UserTokenBalance

        holders = UserTokenBalance.objects.filter(quantity__gt=0).select_related('user', 'token')

        holder_data = []
        for h in holders:
            holder_data.append({
                'email': h.user.email,
                'token_symbol': h.token.symbol,  # Add token symbol
                'token_name': h.token.name,  # Add token name
                'quantity': float(h.quantity),
                'value': float(h.current_value)
            })

        # Sort by value (USD)
        holder_data.sort(key=lambda x: x['value'], reverse=True)

        return Response({
            'top_holders': holder_data[:10],  # Show 10 top holders
            'bottom_holders': holder_data[-5:] if len(holder_data) > 5 else [],
            'top_percentage': 65,
            'middle_percentage': 25,
            'bottom_percentage': 10
        })


# Replace your AdminBuySellActivityView with this safe version
class AdminBuySellActivityView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.tokens.models import Purchase
        from apps.wallets.models import Transaction
        from datetime import datetime, timedelta

        # Get last 7 days
        days = []
        buys = []
        sells = []

        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)

            # Count purchases (buys)
            daily_buys = Purchase.objects.filter(
                created_at__date=date
            ).count()

            # Count sale transactions
            daily_sells = Transaction.objects.filter(
                transaction_type='SALE',
                created_at__date=date
            ).count()

            days.append(date.strftime('%a'))
            buys.append(daily_buys)
            sells.append(daily_sells)

        return Response({
            'days': days,
            'buys': buys,
            'sells': sells
        })


# Update your existing AdminUsersView
class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from apps.wallets.models import Wallet

            users = User.objects.filter(is_active=True)
            user_data = []

            for user in users[:50]:  # Limit to 50 users for performance
                try:
                    grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
                    grand_balance = float(grand_wallet.balance)
                except Wallet.DoesNotExist:
                    grand_balance = 0

                try:
                    yield_wallet = Wallet.objects.get(user=user, wallet_type='YIELD')
                    yield_balance = float(yield_wallet.balance)
                except Wallet.DoesNotExist:
                    yield_balance = 0

                user_data.append({
                    'date_joined': user.date_joined.strftime('%Y-%m-%d'),
                    'email': user.email,
                    'grand_balance': grand_balance,
                    'yield_balance': yield_balance,
                    'tokens_held': grand_balance,
                    'sell_active': False,  # Set based on your logic
                    'referral_count': 0
                })

            return Response(user_data)
        except Exception as e:
            logger.error(f"AdminUsersView error: {str(e)}")
            return Response([])