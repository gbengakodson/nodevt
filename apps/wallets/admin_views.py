from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from .models import DepositRequest, WithdrawalRequest
from apps.wallets.models import Wallet
from django.contrib.auth import get_user_model
from apps.referrals.models import ReferralRelationship

User = get_user_model()


class AdminDepositsView(APIView):
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
        action = request.data.get('action')

        deposit = DepositRequest.objects.get(id=deposit_id)

        if action == 'confirm':
            deposit.status = 'CONFIRMED'
            grand_wallet = Wallet.objects.get(user=deposit.user, wallet_type='GRAND')
            grand_wallet.balance += deposit.amount
            grand_wallet.save()
        elif action == 'reject':
            deposit.status = 'REJECTED'

        deposit.processed_at = timezone.now()
        deposit.save()

        return Response({'success': True})


class AdminWithdrawalsView(APIView):
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
        action = request.data.get('action')

        withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)

        if action == 'process':
            withdrawal.status = 'PROCESSED'
            grand_wallet = Wallet.objects.get(user=withdrawal.user, wallet_type='GRAND')
            grand_wallet.balance -= withdrawal.amount
            grand_wallet.save()
        elif action == 'reject':
            withdrawal.status = 'REJECTED'

        withdrawal.processed_at = timezone.now()
        withdrawal.save()

        return Response({'success': True})


class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = User.objects.all()
        data = []
        for user in users:
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
            yield_wallet = Wallet.objects.get(user=user, wallet_type='YIELD')
            referral_count = ReferralRelationship.objects.filter(referrer=user).count()

            data.append({
                'email': user.email,
                'grand_balance': str(grand_wallet.balance),
                'yield_balance': str(yield_wallet.balance),
                'referral_count': referral_count,
                'date_joined': user.date_joined.strftime('%Y-%m-%d')
            })
        return Response(data)