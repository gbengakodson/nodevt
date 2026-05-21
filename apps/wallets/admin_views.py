from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from .models import DepositRequest, WithdrawalRequest
from apps.wallets.models import Wallet
from django.contrib.auth import get_user_model
from apps.referrals.models import ReferralRelationship

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.permissions import AllowAny

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
        from apps.tokens.models import UserTokenBalance, Purchase
        from apps.trading.models import GridBot
        from decimal import Decimal

        users = User.objects.all()
        data = []
        for user in users:
            grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
            yield_wallet = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
            referral_count = ReferralRelationship.objects.filter(referrer=user).count()

            spot_value = Decimal('0')
            for b in UserTokenBalance.objects.filter(user=user, quantity__gt=0):
                spot_value += b.quantity * b.token.current_price

            grid_value = Decimal('0')
            for bot in GridBot.objects.filter(user=user, status='ACTIVE'):
                grid_value += bot.amount + bot.grid_profit + bot.pnl

            has_purchases = Purchase.objects.filter(user=user).exists()
            is_sample = not has_purchases and referral_count == 0

            data.append({
                'email': user.email,
                'wallet_address': user.wallet_address or '',  # ← ADD THIS
                'grand_balance': str(grand_wallet.balance if grand_wallet else 0),
                'yield_balance': str(yield_wallet.balance if yield_wallet else 0),
                'spot_value': str(spot_value),
                'grid_value': str(grid_value),
                'referral_count': referral_count,
                'is_sample': is_sample,
                'date_joined': user.date_joined.strftime('%Y-%m-%d')
            })
        return Response(data)




class PublicStatsView(APIView):
    """Public version of admin stats - no auth required"""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.tokens.models import UserTokenBalance, Purchase
        from apps.trading.models import GridBot
        from django.db.models import Sum, Count
        from decimal import Decimal

        # Total users
        total_users = User.objects.filter(is_active=True).count()

        # Platform balance (sum of all grand wallets)
        platform_balance = Wallet.objects.filter(wallet_type='GRAND').aggregate(total=Sum('balance'))['total'] or Decimal('0')

        # Total tokens held (spot value)
        total_tokens_held = Decimal('0')
        for b in UserTokenBalance.objects.filter(quantity__gt=0):
            total_tokens_held += b.quantity * b.token.current_price

        # Total buys
        total_buys = Purchase.objects.count()

        # Unique holders
        unique_holders = UserTokenBalance.objects.filter(quantity__gt=0).values('user').distinct().count()

        # Most held token
        most_held = UserTokenBalance.objects.filter(quantity__gt=0).values('token__symbol').annotate(total=Sum('quantity')).order_by('-total').first()
        most_held_token = most_held['token__symbol'] if most_held else '-'

        # Volume
        total_volume = Purchase.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        return Response({
            'total_users': total_users,
            'platform_usdc_balance': float(platform_balance),
            'total_tokens_held': float(total_tokens_held),
            'total_buys': total_buys,
            'unique_holders': unique_holders,
            'avg_token_value': float(total_tokens_held / unique_holders) if unique_holders > 0 else 0,
            'most_held_token': most_held_token,
            'total_volume': float(total_volume),
        })


class PublicDepositsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.wallets.models import Transaction

        deposits = Transaction.objects.filter(
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).select_related('user').order_by('-created_at')[:30]

        data = []
        for d in deposits:
            data.append({
                'created_at': d.created_at.strftime('%Y-%m-%d %H:%M'),
                'user': d.user.wallet_address or d.user.email,
                'email': d.user.email,
                'amount': str(d.amount),
                'tx_hash': d.tx_hash or '',
                'status': d.status,
            })
        return Response(data)


class PublicWithdrawalsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.wallets.models import Transaction

        withdrawals = Transaction.objects.filter(
            transaction_type='WITHDRAWAL',
            status='COMPLETED'
        ).select_related('user').order_by('-created_at')[:30]

        data = []
        for w in withdrawals:
            data.append({
                'created_at': w.created_at.strftime('%Y-%m-%d %H:%M'),
                'user': w.user.wallet_address or w.user.email,
                'email': w.user.email,
                'amount': str(w.amount),
                'wallet_address': w.metadata.get('to_address', '') if w.metadata else '',
                'tx_hash': w.tx_hash or '',
                'status': w.status,
            })
        return Response(data)


class PublicHoldersView(APIView):
    """Public holders list - no auth"""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.tokens.models import UserTokenBalance
        balances = UserTokenBalance.objects.filter(quantity__gt=0).select_related('user', 'token').order_by('-quantity')[:30]
        data = []
        for b in balances:
            value = b.quantity * b.token.current_price
            invested = b.quantity * b.average_buy_price
            pnl = value - invested
            data.append({
                'user': b.user.wallet_address or anon_email(b.user.email),
                'email': b.user.email,
                'wallet_address': b.user.wallet_address or '',
                'token_symbol': b.token.symbol,
                'quantity': str(b.quantity),
                'value': float(value),
                'pnl': float(pnl),
            })
        return Response(data)


class PublicUsersView(APIView):
    """Public users list - no auth"""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.tokens.models import UserTokenBalance
        from apps.trading.models import GridBot
        from decimal import Decimal

        users = User.objects.filter(is_active=True)
        data = []
        for user in users:
            grand = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
            yw = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
            refs = ReferralRelationship.objects.filter(referrer=user).count()

            spot = Decimal('0')
            for b in UserTokenBalance.objects.filter(user=user, quantity__gt=0):
                spot += b.quantity * b.token.current_price

            grid = Decimal('0')
            for bot in GridBot.objects.filter(user=user, status='ACTIVE'):
                grid += bot.amount + bot.grid_profit + bot.pnl

            data.append({
                'user': user.wallet_address or anon_email(user.email),
                'email': user.email,
                'wallet_address': user.wallet_address or '',
                'grand_balance': str(grand.balance if grand else 0),
                'yield_balance': str(yw.balance if yw else 0),
                'spot_value': str(spot),
                'grid_value': str(grid),
                'referral_count': refs,
            })
        return Response(data)


class AdminKYCActions(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get pending KYC applications"""
        from apps.accounts.models import User
        pending = User.objects.filter(kyc_status='PENDING').order_by('-date_joined')
        data = [{
            'email': u.email,
            'id_type': u.id_type,
            'id_number': u.id_number,
            'phone_number': u.phone_number,
            'country': u.country,
            'date_joined': u.date_joined.strftime('%Y-%m-%d'),
            'kyc_status': u.kyc_status
        } for u in pending]
        return Response(data)

    def post(self, request):
        email = request.data.get('email')
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        user = User.objects.get(email=email)
        if action == 'approve':
            user.kyc_status = 'APPROVED'
            user.is_verified = True
            user.date_verified = timezone.now()
        elif action == 'reject':
            user.kyc_status = 'REJECTED'
            # Store rejection reason in metadata or a notification
            from apps.chatbot.models import UserNotification
            NotificationService.create_notification(
                user=user,
                title='🔴 KYC Rejected — Action Required',
                message=f'Your KYC was rejected. Reason: {reason}. Please update your information and resubmit.',
                notification_type='ALERT'
            )
        user.save()
        return Response({'success': True})


def anon_email(email):
    if not email: return 'Unknown'
    parts = email.split('@')
    name = parts[0]
    domain = parts[1] if len(parts) > 1 else ''
    if len(name) <= 3: return name[0] + '***@' + domain
    return name[:2] + '***' + name[-1] + '@' + domain


