import os
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView  # <-- ADD THIS LINE
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal

from apps.tokens.models import CryptoToken, Purchase
from apps.tokens.serializers import CryptoTokenSerializer, UserTokenBalanceSerializer, PurchaseSerializer, SellSerializer
from apps.wallets.models import Wallet, Transaction





class TradingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List all available crypto tokens"""
        from apps.tokens.models import CryptoToken
        tokens = CryptoToken.objects.filter(is_active=True)

        # Debug print
        print(f"LIST METHOD CALLED - Found {tokens.count()} active tokens")

        serializer = CryptoTokenSerializer(tokens, many=True)
        print(f"Serialized data length: {len(serializer.data)}")

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_tokens(self, request):
        """Get current user's token balances"""
        balances = request.user.token_balances.filter(quantity__gt=0)
        serializer = UserTokenBalanceSerializer(balances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def buy(self, request):
        """Buy crypto tokens"""
        serializer = PurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        amount_usdc = serializer.validated_data['amount_usdc']

        # Get token
        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        # Get or create grand wallet
        grand_wallet, created = Wallet.objects.get_or_create(
            user=request.user,
            wallet_type='GRAND',
            defaults={'balance': 0}
        )

        if grand_wallet.balance < amount_usdc:
            return Response({
                'error': 'Insufficient balance',
                'your_balance': str(grand_wallet.balance),
                'required': str(amount_usdc)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculate token quantity
        token_quantity = amount_usdc / token.current_price

        # Calculate node fee (10%)
        node_fee = amount_usdc * Decimal('0.1')

        # Deduct from grand wallet
        grand_wallet.balance -= amount_usdc
        grand_wallet.save()

        # Update user's token balance
        user_balance, created = request.user.token_balances.get_or_create(
            token=token,
            defaults={'quantity': 0, 'average_buy_price': 0}
        )

        # Add tokens with average price calculation
        total_quantity = user_balance.quantity + token_quantity
        total_cost = (user_balance.quantity * user_balance.average_buy_price) + (token_quantity * token.current_price)
        user_balance.average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
        user_balance.quantity = total_quantity
        user_balance.save()

        # Create purchase record
        purchase = Purchase.objects.create(
            user=request.user,
            token=token,
            quantity=token_quantity,
            price_per_token=token.current_price,
            total_amount=amount_usdc,
            node_fee=node_fee
        )

        # Create transaction record
        Transaction.objects.create(
            user=request.user,
            transaction_type='PURCHASE',
            amount=amount_usdc,
            fee=node_fee,
            status='COMPLETED',
            metadata={
                'token_id': str(token.id),
                'token_symbol': token.symbol,
                'quantity': str(token_quantity),
                'price': str(token.current_price)
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'message': f'Successfully purchased {token_quantity:.8f} {token.symbol}',
            'purchase': {
                'token': token.symbol,
                'quantity': str(token_quantity),
                'price_per_token': str(token.current_price),
                'total_amount': str(amount_usdc),
                'node_fee': str(node_fee)
            },
            'grand_balance': str(grand_wallet.balance)
        })

    @action(detail=False, methods=['post'])
    def sell(self, request):
        """Sell crypto tokens - only if current price >= average buy price"""
        serializer = SellSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        quantity = serializer.validated_data['quantity']

        # Get token
        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        # Get user's token balance
        try:
            user_balance = request.user.token_balances.get(token=token)
        except:
            return Response({
                'error': 'You don\'t own any of this token'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if user has enough tokens
        if user_balance.quantity < quantity:
            return Response({
                'error': 'Insufficient token balance',
                'your_balance': str(user_balance.quantity),
                'requested': str(quantity)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check selling condition: current price >= average buy price
        if token.current_price < user_balance.average_buy_price:
            return Response({
                'error': 'Cannot sell at this time',
                'reason': 'Current price is below your purchase price',
                'current_price': str(token.current_price),
                'average_buy_price': str(user_balance.average_buy_price)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calculate sale amount
        sale_amount = quantity * token.current_price

        # Get or create grand wallet
        grand_wallet, created = Wallet.objects.get_or_create(
            user=request.user,
            wallet_type='GRAND',
            defaults={'balance': 0}
        )

        # Add to grand wallet
        grand_wallet.balance += sale_amount
        grand_wallet.save()

        # Remove tokens from user's balance
        user_balance.quantity -= quantity
        if user_balance.quantity == 0:
            user_balance.average_buy_price = 0
        user_balance.save()

        # Create transaction record
        Transaction.objects.create(
            user=request.user,
            transaction_type='SALE',
            amount=sale_amount,
            fee=0,
            status='COMPLETED',
            metadata={
                'token_id': str(token.id),
                'token_symbol': token.symbol,
                'quantity': str(quantity),
                'price': str(token.current_price),
                'average_buy_price': str(user_balance.average_buy_price)
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'message': f'Successfully sold {quantity} {token.symbol}',
            'sale': {
                'token': token.symbol,
                'quantity': str(quantity),
                'price_per_token': str(token.current_price),
                'total_amount': str(sale_amount)
            },
            'grand_balance': str(grand_wallet.balance),
            'remaining_quantity': str(user_balance.quantity)
        })

    @action(detail=False, methods=['get'])
    def my_balance(self, request):
        """Get user's USDC balance and deposit address"""
        from apps.wallets.models import Wallet
        from apps.wallets.services.deposit_service import DepositService
        from apps.wallets.services.web3_service import Web3Service

        # Create wallet if user doesn't have one
        if not request.user.wallet_address:
            try:
                address = DepositService.get_deposit_address(request.user)
                print(f"Created wallet for {request.user.email}: {address}")
            except Exception as e:
                print(f"Error creating wallet: {e}")

        # Get or create grand wallet
        grand_wallet, created = Wallet.objects.get_or_create(
            user=request.user,
            wallet_type='GRAND',
            defaults={'balance': 0}
        )

        # Get or create yield wallet
        yield_wallet, created = Wallet.objects.get_or_create(
            user=request.user,
            wallet_type='YIELD',
            defaults={'balance': 0}
        )

        # Get real blockchain balance if user has deposit address
        blockchain_balance = 0
        deposit_address = None

        if request.user.wallet_address:
            try:
                ws = Web3Service()
                blockchain_balance = ws.get_usdc_balance(request.user.wallet_address)
                deposit_address = request.user.wallet_address
            except Exception as e:
                print(f"Error getting blockchain balance: {e}")
                deposit_address = request.user.wallet_address

        return Response({
            'grand_balance': str(grand_wallet.balance),
            'yield_balance': str(yield_wallet.balance),
            'blockchain_balance': str(blockchain_balance),
            'deposit_address': deposit_address,
            'network': 'BSC (BEP20)',
            'token': 'USDC'
        })

    @action(detail=False, methods=['post'])
    def withdraw_yield(self, request):
        """Withdraw yield to grand balance"""
        from apps.wallets.models import Wallet

        amount = Decimal(str(request.data.get('amount', 0)))

        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            yield_wallet = Wallet.objects.get(user=request.user, wallet_type='YIELD')
            grand_wallet = Wallet.objects.get(user=request.user, wallet_type='GRAND')

            if yield_wallet.balance < amount:
                return Response({'error': 'Insufficient yield balance'}, status=status.HTTP_400_BAD_REQUEST)

            yield_wallet.balance -= amount
            yield_wallet.save()

            grand_wallet.balance += amount
            grand_wallet.save()

            Transaction.objects.create(
                user=request.user,
                transaction_type='WITHDRAWAL',
                amount=amount,
                fee=0,
                status='COMPLETED',
                metadata={'from_wallet': 'YIELD', 'to_wallet': 'GRAND', 'type': 'yield_withdrawal'},
                completed_at=timezone.now()
            )

            return Response({
                'success': True,
                'amount': str(amount),
                'new_yield_balance': str(yield_wallet.balance),
                'new_grand_balance': str(grand_wallet.balance)
            })

        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def recent_distributions(self, request):
        """Get recent yield distributions for user"""
        from apps.yield_earnings.models import YieldDistribution
        import random
        from datetime import datetime, timedelta

        try:
            # Get recent credited distributions
            distributions = YieldDistribution.objects.filter(
                user=request.user,
                is_credited=True
            ).order_by('-credited_at')[:10]

            data = []
            for d in distributions:
                data.append({
                    'token': d.token_balance.token.symbol if d.token_balance else 'USDC',
                    'amount': str(d.amount),
                    'time': d.credited_at.strftime('%Y-%m-%d %H:%M:%S') if d.credited_at else d.created_at.strftime(
                        '%Y-%m-%d %H:%M:%S')
                })

            # If no real distributions, return sample data for testing
            if not data:
                # Get user's tokens to show realistic samples
                user_tokens = [b.token.symbol for b in request.user.token_balances.filter(quantity__gt=0)]
                token_list = user_tokens if user_tokens else ['BTC', 'ETH', 'BNB', 'SOL']

                for i in range(5):
                    date = datetime.now() - timedelta(hours=i * 2)
                    amount = round(random.uniform(0.05, 2.5), 4)
                    data.append({
                        'token': random.choice(token_list),
                        'amount': str(amount),
                        'time': date.strftime('%Y-%m-%d %H:%M:%S')
                    })

            return Response(data)

        except Exception as e:
            print(f"Error in recent_distributions: {e}")
            # Return empty array on error
            return Response([])

    @action(detail=False, methods=['get'])
    def debug_tokens(self, request):
        """Debug endpoint to check tokens"""
        from apps.tokens.models import UserTokenBalance

        try:
            balances = UserTokenBalance.objects.filter(user=request.user)
            data = []
            for b in balances:
                data.append({
                    'symbol': b.token.symbol,
                    'quantity': str(b.quantity),
                    'avg_price': str(b.average_buy_price),
                    'token_id': str(b.token.id)
                })
            return Response({
                'success': True,
                'count': balances.count(),
                'balances': data,
                'user': request.user.email
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)

    @action(detail=False, methods=['get'])
    def referral_stats(self, request):
        """Get referral statistics for user"""
        from apps.referrals.models import ReferralRelationship, ReferralEarning

        # Count referrals
        total_referrals = ReferralRelationship.objects.filter(referrer=request.user).count()
        active_referrals = ReferralRelationship.objects.filter(
            referrer=request.user,
            referred__is_active=True
        ).count()

        # Calculate total commissions
        earnings = ReferralEarning.objects.filter(user=request.user)
        total_commissions = sum(e.amount for e in earnings)
        pending_commissions = 0  # All commissions are credited immediately

        return Response({
            'total_referrals': total_referrals,
            'active_referrals': active_referrals,
            'total_commissions': total_commissions,
            'pending_commissions': pending_commissions
        })

    @action(detail=False, methods=['get'])
    def referral_tree(self, request):
        """Get referral tree for user (up to 7 generations)"""
        from apps.referrals.models import ReferralRelationship

        levels = []
        current_users = [request.user]

        for level_num in range(1, 8):
            next_users = []
            level_data = []

            for user in current_users:
                referrals = ReferralRelationship.objects.filter(referrer=user).select_related('referred')
                for ref in referrals:
                    next_users.append(ref.referred)
                    level_data.append({
                        'name': ref.referred.username or ref.referred.email.split('@')[0],
                        'email': ref.referred.email,
                        'earnings': 0  # Could calculate from ReferralEarning
                    })

            if level_data:
                levels.append({'level': level_num, 'referrals': level_data})
            current_users = next_users

            if not current_users:
                break

        return Response({'levels': levels})

    @action(detail=False, methods=['get'])
    def referral_earnings(self, request):
        """Get referral earnings history"""
        from apps.referrals.models import ReferralEarning

        earnings = ReferralEarning.objects.filter(user=request.user).order_by('-created_at')[:20]

        data = []
        for e in earnings:
            data.append({
                'date': e.created_at.strftime('%Y-%m-%d %H:%M'),
                'from_user': e.from_user.username or e.from_user.email.split('@')[0],
                'level': e.level,
                'purchase_amount': str(e.purchase.total_amount),
                'commission': str(e.amount)
            })

        return Response(data)

    @action(detail=False, methods=['get'])
    def deposit_address(self, request):
        """Get or create deposit address for user"""
        from apps.wallets.services.deposit_service import DepositService

        try:
            address = DepositService.get_deposit_address(request.user)
            return Response({'address': address})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def set_take_profit(self, request):
        """Set a take profit order for a token"""
        from apps.tokens.models import TakeProfitOrder
        from decimal import Decimal

        token_id = request.data.get('token_id')
        quantity = Decimal(str(request.data.get('quantity', 0)))
        target_percentage = Decimal(str(request.data.get('target_percentage', 0)))

        if not token_id or quantity <= 0 or target_percentage <= 0:
            return Response({'error': 'Invalid parameters'}, status=status.HTTP_400_BAD_REQUEST)

        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        # Get user's token balance
        try:
            user_balance = request.user.token_balances.get(token=token)
        except:
            return Response({'error': 'You don\'t own this token'}, status=status.HTTP_400_BAD_REQUEST)

        if user_balance.quantity < quantity:
            return Response({'error': 'Insufficient token balance'}, status=status.HTTP_400_BAD_REQUEST)

        purchase_price = user_balance.average_buy_price
        target_price = purchase_price * (1 + target_percentage / 100)

        order = TakeProfitOrder.objects.create(
            user=request.user,
            token=token,
            quantity=quantity,
            purchase_price=purchase_price,
            target_price=target_price,
            target_percentage=target_percentage
        )

        return Response({
            'success': True,
            'order_id': str(order.id),
            'token': token.symbol,
            'quantity': str(quantity),
            'purchase_price': str(purchase_price),
            'target_price': str(target_price),
            'target_percentage': str(target_percentage),
            'message': f'Take profit order set: Sell {quantity} {token.symbol} at +{target_percentage}% (${target_price})'
        })

    @action(detail=False, methods=['get'])
    def take_profit_orders(self, request):
        """Get user's active take profit orders"""
        from apps.tokens.models import TakeProfitOrder

        orders = TakeProfitOrder.objects.filter(user=request.user, status='ACTIVE')

        data = []
        for order in orders:
            data.append({
                'id': str(order.id),
                'token_symbol': order.token.symbol,
                'quantity': str(order.quantity),
                'purchase_price': str(order.purchase_price),
                'target_price': str(order.target_price),
                'target_percentage': str(order.target_percentage),
                'current_price': str(order.token.current_price),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M')
            })

        return Response(data)

    @action(detail=False, methods=['post'])
    def cancel_take_profit(self, request):
        """Cancel a take profit order"""
        from apps.tokens.models import TakeProfitOrder

        order_id = request.data.get('order_id')

        try:
            order = TakeProfitOrder.objects.get(id=order_id, user=request.user, status='ACTIVE')
            order.status = 'CANCELLED'
            order.save()
            return Response({'success': True, 'message': 'Take profit order cancelled'})
        except TakeProfitOrder.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['get'])
    def test_tokens(self, request):
        """Test endpoint to check tokens"""
        from apps.tokens.models import CryptoToken
        tokens = CryptoToken.objects.filter(is_active=True)
        data = [{'symbol': t.symbol, 'name': t.name, 'price': str(t.current_price)} for t in tokens]
        return Response({'count': len(data), 'tokens': data})



@csrf_exempt
@require_http_methods(["GET", "POST"])
def check_deposits_webhook(request):
        """Webhook endpoint to trigger deposit checking"""

        print("=" * 50)
        print("DEPOSIT CHECK WEBHOOK CALLED")
        print("=" * 50)
        # Simple security - check a secret key
        secret_key = request.GET.get('secret') or request.POST.get('secret')
        expected_secret = os.environ.get('DEPOSIT_CHECK_SECRET', 'your-secret-key-here')

        if secret_key != expected_secret:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        try:
            call_command('check_credits')
            return JsonResponse({'status': 'success', 'message': 'Deposit check completed'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)