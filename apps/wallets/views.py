from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import DepositRequest, WithdrawalRequest
from django.db.models import Sum, Count, Avg
from django.contrib.auth.models import User
from apps.wallets.models import Wallet



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

class AdminStatisticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.db.models import Sum, Count, Avg
        from apps.wallets.models import Wallet
        from django.contrib.auth.models import User

        # Calculate statistics
        total_buys = Transaction.objects.filter(type='BUY').count()  # Adjust based on your model
        total_solds = Transaction.objects.filter(type='SELL').count()

        # Token holdings stats
        all_wallets = Wallet.objects.filter(wallet_type='GRAND')
        total_tokens_held = all_wallets.aggregate(Sum('balance'))['balance__sum'] or 0

        return Response({
            'total_buys': total_buys,
            'total_solds': total_solds,
            'total_tokens_held': float(total_tokens_held),
            'total_yield': 0,  # Calculate based on your yield model
            'active_sell_tokens': 0,  # Based on your trading model
            'inactive_sell_tokens': 0,
            'avg_hold_time': '14d',
            'turnover_rate': '23%'
        })


class AdminHoldersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.wallets.models import Wallet
        from django.contrib.auth.models import User

        users = User.objects.filter(is_active=True)
        holder_data = []

        for user in users:
            try:
                wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
                holder_data.append({
                    'email': user.email,
                    'tokens_held': float(wallet.balance),
                    'value': float(wallet.balance) * 1.0  # Multiply by token price
                })
            except Wallet.DoesNotExist:
                holder_data.append({
                    'email': user.email,
                    'tokens_held': 0,
                    'value': 0
                })

        # Sort by tokens held
        holder_data.sort(key=lambda x: x['tokens_held'], reverse=True)

        top_holders = holder_data[:10]
        bottom_holders = [h for h in holder_data if h['tokens_held'] > 0][-10:]

        # Calculate distribution
        total_tokens = sum(h['tokens_held'] for h in holder_data)
        top_10_percent_tokens = sum(h['tokens_held'] for h in holder_data[:int(len(holder_data) * 0.1)])

        return Response({
            'top_holders': top_holders,
            'bottom_holders': bottom_holders,
            'top_percentage': (top_10_percent_tokens / total_tokens * 100) if total_tokens > 0 else 0,
            'middle_percentage': 65,
            'bottom_percentage': 10
        })


class AdminBuySellActivityView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Return mock data - replace with actual transaction data
        return Response({
            'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'buys': [12, 19, 15, 17, 14, 22, 18],
            'sells': [8, 12, 10, 9, 11, 15, 13]
        })