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
        from apps.tokens.models import UserTokenBalance, Purchase, CryptoToken
        from apps.wallets.models import Wallet
        from django.db.models import F, Sum, Q, Avg
        from datetime import timedelta
        from django.utils import timezone
        from decimal import Decimal
        import logging

        logger = logging.getLogger(__name__)

        # Total token VALUE
        total_token_value = UserTokenBalance.objects.aggregate(
            total=Sum(F('quantity') * F('token__current_price'))
        )['total'] or Decimal('0')

        total_buys = Purchase.objects.count()

        # Platform USDC balance from BLOCKCHAIN (not database)
        platform_wallet_address = "0x3183f4c0a08D91717127534cFeF0ABDF320D2ca4"  # Your platform wallet
        platform_usdc_balance = Decimal('0')

        try:
            from web3 import Web3
            # Connect to BSC
            bsc_rpc = "https://bsc-dataseed.binance.org/"
            w3 = Web3(Web3.HTTPProvider(bsc_rpc))

            if w3.is_connected():
                # USDC Contract on BSC
                usdc_contract_address = "0x3183f4c0a08D91717127534cFeF0ABDF320D2ca4"
                usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'

                contract = w3.eth.contract(address=usdc_contract_address, abi=usdc_abi)
                balance_wei = contract.functions.balanceOf(platform_wallet_address).call()
                platform_usdc_balance = Decimal(str(balance_wei / 10 ** 18))  # USDC has 18 decimals
                logger.info(f"Blockchain balance: {platform_usdc_balance} USDC")
            else:
                raise Exception("Web3 connection failed")

        except Exception as e:
            logger.error(f"Error fetching blockchain balance: {str(e)}")
            # Fallback to database balance if blockchain fails
            platform_usdc_balance = Wallet.objects.filter(
                wallet_type='GRAND'
            ).aggregate(total=Sum('balance'))['total'] or Decimal('0')
            logger.warning(f"Using database fallback balance: {platform_usdc_balance}")

        # Active/Inactive sell counts
        all_balances = UserTokenBalance.objects.filter(quantity__gt=0)
        active_sell = all_balances.filter(
            token__current_price__gt=F('average_buy_price')
        ).count()
        inactive_sell = all_balances.filter(
            token__current_price__lte=F('average_buy_price')
        ).count()

        # Unique holders
        unique_holders = UserTokenBalance.objects.filter(quantity__gt=0).values('user').distinct().count()

        # Average token value per holder
        avg_token_value = total_token_value / unique_holders if unique_holders > 0 else 0

        # Most held token
        most_held = UserTokenBalance.objects.values('token__symbol', 'token__name').annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity').first()
        most_held_token = f"{most_held['token__symbol']}" if most_held else '-'

        # Total volume from purchases
        total_volume = Purchase.objects.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')

        # REAL: Average Hold Time (using created_at from UserTokenBalance)
        avg_hold_seconds = UserTokenBalance.objects.filter(
            quantity__gt=0
        ).aggregate(
            avg_age=Avg(timezone.now() - F('created_at'))
        )['avg_age']

        if avg_hold_seconds:
            avg_days = avg_hold_seconds.total_seconds() / 86400
            avg_hold_time = f"{int(avg_days)}d"
        else:
            avg_hold_time = "0d"

        # REAL: Turnover Rate = (Total Sells / Total Buys) * 100
        from apps.wallets.models import WithdrawalRequest
        total_sells = WithdrawalRequest.objects.filter(status='PROCESSED').count()
        turnover_rate = f"{int((total_sells / total_buys) * 100)}%" if total_buys > 0 else "0%"

        return Response({
            'total_buys': total_buys,
            'platform_usdc_balance': float(platform_usdc_balance),
            'total_tokens_held': float(total_token_value),
            'total_yield': 0,
            'active_sell_tokens': active_sell,
            'inactive_sell_tokens': inactive_sell,
            'unique_holders': unique_holders,
            'avg_token_value': float(avg_token_value),
            'most_held_token': most_held_token,
            'total_volume': float(total_volume),
            'avg_hold_time': avg_hold_time,
            'turnover_rate': turnover_rate
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


from django.core.mail import send_mail
from django.conf import settings


class AdminSendEmailView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        from django.core.mail import send_mail
        from django.conf import settings
        from django.contrib.auth.models import User
        import logging

        logger = logging.getLogger(__name__)

        subject = request.data.get('subject')
        message = request.data.get('message')
        user_ids = request.data.get('user_ids', [])

        if user_ids:
            users = User.objects.filter(id__in=user_ids, is_active=True)
        else:
            users = User.objects.filter(is_active=True)

        success_count = 0
        failed_list = []

        for user in users:
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL or 'noreply@yourdomain.com',
                    [user.email],
                    fail_silently=False,
                )
                success_count += 1
                logger.info(f"Email sent to {user.email}")
            except Exception as e:
                failed_list.append(user.email)
                logger.error(f"Failed to send to {user.email}: {str(e)}")

        return Response({
            'success': True,
            'sent_count': success_count,
            'total': users.count(),
            'failed': failed_list
        })


from apps.chat.models import ChatMessage


class AdminChatMessagesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Get all messages grouped by user
        from django.contrib.auth.models import User
        from django.db.models import Count, Max

        users_with_messages = User.objects.filter(
            chat_messages__isnull=False
        ).annotate(
            message_count=Count('chat_messages'),
            last_message=Max('chat_messages__created_at')
        ).order_by('-last_message')

        result = []
        for user in users_with_messages:
            # Get last message
            last_msg = ChatMessage.objects.filter(user=user).last()
            unread_count = ChatMessage.objects.filter(user=user, is_read=False, is_admin_reply=False).count()

            result.append({
                'user_id': str(user.id),
                'user_email': user.email,
                'message_count': user.message_count,
                'unread_count': unread_count,
                'last_message': last_msg.message[:50] if last_msg else '',
                'last_message_time': last_msg.created_at.strftime('%Y-%m-%d %H:%M') if last_msg else ''
            })

        return Response(result)

    def get_conversation(self, request, user_id):
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        messages = ChatMessage.objects.filter(user=user).order_by('created_at')

        # Mark messages as read
        ChatMessage.objects.filter(user=user, is_admin_reply=False, is_read=False).update(is_read=True)

        data = [{
            'id': str(m.id),
            'message': m.message,
            'is_admin_reply': m.is_admin_reply,
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_read': m.is_read
        } for m in messages]

        return Response({'user_email': user.email, 'messages': data})

    def post(self, request, user_id):
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        reply_message = request.data.get('message')

        if reply_message:
            ChatMessage.objects.create(
                user=user,
                message=reply_message,
                is_admin_reply=True,
                is_read=True
            )
            return Response({'success': True, 'message': 'Reply sent'})

        return Response({'error': 'Message required'}, status=400)