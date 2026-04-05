from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import DepositRequest, WithdrawalRequest


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