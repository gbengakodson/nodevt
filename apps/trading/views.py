import os
from decimal import Decimal
from django.conf import settings
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, F
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView

from apps.tokens.models import CryptoToken, Purchase, UserTokenBalance
from apps.tokens.serializers import CryptoTokenSerializer, UserTokenBalanceSerializer, PurchaseSerializer, SellSerializer
from apps.wallets.models import Wallet, Transaction
from apps.trading.models import GridBot
from apps.core.models import PlatformSetting



def update_prices_webhook(request):
    """Webhook endpoint to trigger price updates"""
    from django.core.management import call_command
    call_command('update_prices')
    return JsonResponse({'status': 'success', 'message': 'Prices updated'})


class TradingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List all available crypto tokens"""
        tokens = CryptoToken.objects.filter(is_active=True)
        serializer = CryptoTokenSerializer(tokens, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_tokens(self, request):
        """Get current user's token balances"""
        balances = request.user.token_balances.filter(quantity__gt=0)
        serializer = UserTokenBalanceSerializer(balances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def buy(self, request):
        """Buy crypto tokens - Market Order (1% fee) or Grid Bot (10% fee)"""
        serializer = PurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        amount_usdc = serializer.validated_data['amount_usdc']
        order_type = request.data.get('order_type', 'market').lower()

        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        grand_wallet, _ = Wallet.objects.get_or_create(
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

        # Fee calculation
        if order_type == 'market':
            fee_percent = Decimal('0.01')
        else:
            fee_percent = Decimal('0.10')

        node_fee = amount_usdc * fee_percent
        amount_after_fee = amount_usdc - node_fee
        token_quantity = amount_after_fee / token.current_price

        grand_wallet.balance -= amount_usdc
        grand_wallet.save()

        if order_type == 'market':
            user_balance, _ = request.user.token_balances.get_or_create(
                token=token,
                defaults={'quantity': 0, 'average_buy_price': 0}
            )
            total_quantity = user_balance.quantity + token_quantity
            total_cost = (user_balance.quantity * user_balance.average_buy_price) + (token_quantity * token.current_price)
            user_balance.average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
            user_balance.quantity = total_quantity
            user_balance.save()
        else:
            upper_price = token.current_price * Decimal('1.8')
            lower_price = token.current_price * Decimal('0.2')
            GridBot.objects.create(
                user=request.user,
                token=token,
                amount=amount_after_fee,
                lower_price=lower_price,
                upper_price=upper_price,
                grids=100,
                status='ACTIVE',
                grid_profit=Decimal('0'),
                price_at_creation=token.current_price,
                created_at=timezone.now(),
            )

        # Create purchase record
        purchase = Purchase.objects.create(
            user=request.user,
            token=token,
            quantity=token_quantity,
            price_per_token=token.current_price,
            total_amount=amount_after_fee,
            node_fee=node_fee,
            order_type=order_type.upper()
        )

        # Distribute node fee to referrals (only for grid bot orders)
        referral_count = 0
        if order_type == 'grid':
            from apps.referrals.services.referral_service import ReferralService
            try:
                distributions = ReferralService.distribute_node_fee(request.user, node_fee, purchase)
                referral_count = len(distributions) if distributions else 0
            except Exception as e:
                print(f"Error distributing referral fees: {e}")

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
                'price': str(token.current_price),
                'node_fee': str(node_fee),
                'order_type': order_type,
                'referrals_credited': referral_count
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'message': f'Successfully {"purchased" if order_type == "market" else "activated grid bot for"} {token.symbol}',
            'purchase': {
                'token': token.symbol,
                'quantity': str(token_quantity),
                'price_per_token': str(token.current_price),
                'total_amount': str(amount_after_fee),
                'node_fee': str(node_fee),
                'order_type': order_type
            },
            'referral_commission': {
                'total_fee': str(node_fee),
                'referrers_count': referral_count,
                'distributed': referral_count > 0
            } if order_type == 'grid' else None,
            'grand_balance': str(grand_wallet.balance)
        })

    @action(detail=False, methods=['get'])
    def my_grids(self, request):
        """Get user's active grid bots"""
        grid_bots = GridBot.objects.filter(user=request.user, status='ACTIVE').select_related('token')
        data = []
        for bot in grid_bots:
            data.append({
                'id': str(bot.id),
                'token_symbol': bot.token.symbol if bot.token else 'UNKNOWN',
                'token_name': bot.token.name if bot.token else 'Unknown',
                'amount': float(bot.amount),
                'lower_price': float(bot.lower_price),
                'upper_price': float(bot.upper_price),
                'grids': bot.grids,
                'current_grid_level': bot.current_grid_level,
                'grid_profit': float(bot.grid_profit),
                'pnl': float(bot.pnl),
                'pnl_percent': float(bot.pnl_percent),
                'price_at_creation': float(bot.price_at_creation),
                'total_yield_earned': float(bot.total_yield_earned) if hasattr(bot, 'total_yield_earned') else 0,
                'created_at': bot.created_at.isoformat(),
                'status': bot.status,
            })
        return Response(data)

    @action(detail=False, methods=['get'])
    def my_grids_all(self, request):
        """Get ALL user's grid bots (active and stopped)"""
        grid_bots = GridBot.objects.filter(user=request.user).exclude(status='COMPLETED').select_related('token')
        data = []
        for bot in grid_bots:
            data.append({
                'id': str(bot.id),
                'token_symbol': bot.token.symbol if bot.token else 'UNKNOWN',
                'token_name': bot.token.name if bot.token else 'Unknown',
                'amount': float(bot.amount),
                'lower_price': float(bot.lower_price),
                'upper_price': float(bot.upper_price),
                'grids': bot.grids,
                'current_grid_level': bot.current_grid_level,
                'grid_profit': float(bot.grid_profit),
                'pnl': float(bot.pnl),
                'pnl_percent': float(bot.pnl_percent),
                'price_at_creation': float(bot.price_at_creation),
                'total_yield_earned': float(bot.total_yield_earned) if hasattr(bot, 'total_yield_earned') else 0,
                'created_at': bot.created_at.isoformat(),
                'status': bot.status,
            })
        return Response(data)

    @action(detail=False, methods=['post'])
    def collect_grid_profit(self, request):
        """Move grid profit from a specific bot to yield wallet"""
        bot_id = request.data.get('bot_id')
        if not bot_id:
            return Response({'error': 'Bot ID required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            bot = GridBot.objects.get(id=bot_id, user=request.user, status='ACTIVE')
        except GridBot.DoesNotExist:
            return Response({'error': 'Active grid bot not found'}, status=status.HTTP_404_NOT_FOUND)

        if bot.grid_profit <= 0:
            return Response({'error': 'No grid profit to collect'}, status=status.HTTP_400_BAD_REQUEST)

        profit_amount = bot.grid_profit

        yield_wallet, _ = Wallet.objects.get_or_create(
            user=request.user,
            wallet_type='YIELD',
            defaults={'balance': 0}
        )

        yield_wallet.balance += profit_amount
        yield_wallet.save()

        bot.total_yield_earned = (bot.total_yield_earned or 0) + profit_amount
        bot.grid_profit = Decimal('0')
        bot.save()

        Transaction.objects.create(
            user=request.user,
            transaction_type='YIELD',
            amount=profit_amount,
            fee=0,
            status='COMPLETED',
            metadata={
                'grid_bot_id': str(bot.id),
                'token': bot.token.symbol,
                'source': 'grid_profit_collection'
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'amount_collected': float(profit_amount),
            'yield_wallet_balance': float(yield_wallet.balance),
            'bot_grid_profit_remaining': float(bot.grid_profit),
            'bot_total_yield_earned': float(bot.total_yield_earned)
        })

    @action(detail=False, methods=['post'])
    def move_yield_to_grand(self, request):
        """Move funds from yield wallet to grand wallet (min 10% of portfolio)"""
        amount = Decimal(str(request.data.get('amount', 0)))
        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            yield_wallet = Wallet.objects.get(user=request.user, wallet_type='YIELD')
            grand_wallet, _ = Wallet.objects.get_or_create(
                user=request.user, wallet_type='GRAND', defaults={'balance': 0}
            )
        except Wallet.DoesNotExist:
            return Response({'error': 'Yield wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

        if yield_wallet.balance < amount:
            return Response({'error': 'Insufficient yield balance'}, status=status.HTTP_400_BAD_REQUEST)

        token_value = UserTokenBalance.objects.filter(
            user=request.user, quantity__gt=0
        ).annotate(
            total_value=F('quantity') * F('token__current_price')
        ).aggregate(total=Sum('total_value'))['total'] or Decimal('0')

        active_bots = GridBot.objects.filter(user=request.user, status='ACTIVE')
        grid_value = sum(
            (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0) + (bot.total_yield_earned or 0)
            for bot in active_bots
        )

        total_portfolio = token_value + grid_value + (grand_wallet.balance or 0) + (yield_wallet.balance or 0)
        min_required = total_portfolio * Decimal('0.10')

        if yield_wallet.balance < min_required:
            return Response({
                'error': 'Yield balance must be at least 10% of portfolio value to transfer',
                'min_required': float(min_required),
                'current_yield_balance': float(yield_wallet.balance),
                'portfolio_value': float(total_portfolio),
            }, status=status.HTTP_400_BAD_REQUEST)

        if amount < min_required:
            return Response({
                'error': f'Minimum transfer amount is {float(min_required):.2f} (10% of portfolio)',
                'min_required': float(min_required),
                'requested': float(amount)
            }, status=status.HTTP_400_BAD_REQUEST)

        yield_wallet.balance -= amount
        yield_wallet.save()
        grand_wallet.balance += amount
        grand_wallet.save()

        Transaction.objects.create(
            user=request.user,
            transaction_type='YIELD',
            amount=amount,
            fee=0,
            status='COMPLETED',
            metadata={
                'from_wallet': 'YIELD',
                'to_wallet': 'GRAND',
                'portfolio_value': str(total_portfolio),
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'amount_moved': float(amount),
            'yield_balance': float(yield_wallet.balance),
            'grand_balance': float(grand_wallet.balance),
            'portfolio_value': float(total_portfolio),
        })

    @action(detail=False, methods=['get'])
    def portfolio_summary(self, request):
        """Get portfolio summary with yield wallet info"""
        token_value = UserTokenBalance.objects.filter(
            user=request.user, quantity__gt=0
        ).annotate(
            total_value=F('quantity') * F('token__current_price')
        ).aggregate(total=Sum('total_value'))['total'] or Decimal('0')

        active_bots = GridBot.objects.filter(user=request.user, status='ACTIVE')
        grid_value = sum(
            (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0) + (bot.total_yield_earned or 0)
            for bot in active_bots
        )

        grand_wallet = Wallet.objects.filter(user=request.user, wallet_type='GRAND').first()
        yield_wallet = Wallet.objects.filter(user=request.user, wallet_type='YIELD').first()

        grand_balance = grand_wallet.balance if grand_wallet else Decimal('0')
        yield_balance = yield_wallet.balance if yield_wallet else Decimal('0')
        total_portfolio = token_value + grid_value + grand_balance + yield_balance
        min_required = total_portfolio * Decimal('0.10')
        can_transfer = yield_balance >= min_required and yield_balance > 0

        return Response({
            'token_value': float(token_value),
            'grid_value': float(grid_value),
            'grand_balance': float(grand_balance),
            'yield_balance': float(yield_balance),
            'total_portfolio': float(total_portfolio),
            'min_required_to_transfer': float(min_required),
            'current_percentage': float((yield_balance / total_portfolio) * 100) if total_portfolio > 0 else 0,
            'can_transfer': can_transfer
        })

    @action(detail=False, methods=['post'])
    def sell(self, request):
        """Sell crypto tokens - spot market order"""
        serializer = SellSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        quantity = serializer.validated_data['quantity']

        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        try:
            user_balance = request.user.token_balances.get(token=token)
        except:
            return Response({
                'error': 'You don\'t own any of this token'
            }, status=status.HTTP_400_BAD_REQUEST)

        if user_balance.quantity < quantity:
            return Response({
                'error': 'Insufficient token balance',
                'your_balance': str(user_balance.quantity),
                'requested': str(quantity)
            }, status=status.HTTP_400_BAD_REQUEST)

        # REMOVED: Price check - spot tokens can be sold anytime

        sale_amount = quantity * token.current_price

        grand_wallet, _ = Wallet.objects.get_or_create(
            user=request.user, wallet_type='GRAND', defaults={'balance': 0}
        )
        grand_wallet.balance += sale_amount
        grand_wallet.save()

        user_balance.quantity -= quantity
        if user_balance.quantity == 0:
            user_balance.average_buy_price = 0
        user_balance.save()

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

    @action(detail=False, methods=['post'])
    def stop_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        bot.status = 'STOPPED'
        bot.save()
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def start_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        bot.status = 'ACTIVE'
        bot.save()
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def close_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)

        total_return = (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0) + (bot.total_yield_earned or 0)

        grand_wallet, _ = Wallet.objects.get_or_create(
            user=request.user, wallet_type='GRAND', defaults={'balance': 0}
        )
        grand_wallet.balance += total_return
        grand_wallet.save()

        Transaction.objects.create(
            user=request.user,
            transaction_type='GRID_CLOSE',
            amount=total_return,
            fee=0,
            status='COMPLETED',
            metadata={
                'grid_bot_id': str(bot.id),
                'token': bot.token.symbol,
                'investment': str(bot.amount),
                'grid_profit': str(bot.grid_profit),
                'pnl': str(bot.pnl),
                'yield_earned': str(bot.total_yield_earned)
            },
            completed_at=timezone.now()
        )

        bot.status = 'COMPLETED'
        bot.save()

        return Response({
            'success': True,
            'total_return': float(total_return),
            'breakdown': {
                'investment': float(bot.amount),
                'grid_profit': float(bot.grid_profit),
                'pnl': float(bot.pnl),
                'yield_earned': float(bot.total_yield_earned)
            }
        })

    @action(detail=False, methods=['post'])
    def auto_close_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        if bot.pnl_percent >= 20:
            total_return = (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0)
            grand_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND', defaults={'balance': 0})
            grand_wallet.balance += total_return
            grand_wallet.save()
            bot.status = 'COMPLETED'
            bot.save()
            return Response({'success': True, 'amount': float(total_return)})
        return Response({'error': 'PNL not reached 20%'}, status=400)

    @action(detail=False, methods=['get'])
    def my_balance(self, request):
        from apps.wallets.services.deposit_service import DepositService
        from apps.wallets.services.web3_service import Web3Service

        if not request.user.wallet_address:
            try:
                DepositService.get_deposit_address(request.user)
            except Exception as e:
                print(f"Error creating wallet: {e}")

        grand_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND', defaults={'balance': 0})
        yield_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='YIELD', defaults={'balance': 0})

        blockchain_balance = 0
        deposit_address = request.user.wallet_address
        if request.user.wallet_address:
            try:
                ws = Web3Service()
                blockchain_balance = ws.get_usdc_balance(request.user.wallet_address)
            except Exception as e:
                print(f"Error getting blockchain balance: {e}")

        return Response({
            'grand_balance': str(grand_wallet.balance),
            'yield_balance': str(yield_wallet.balance),
            'blockchain_balance': str(blockchain_balance),
            'deposit_address': deposit_address,
            'network': 'BSC (BEP20)',
            'token': 'USDC'
        })

    @action(detail=False, methods=['post'])
    def withdraw_external(self, request):
        """Withdraw USDC to external wallet via Web3 with OTP verification"""
        from apps.wallets.services.binance_service import BinanceService
        from apps.accounts.services.otp_service import OTPService
        import traceback

        address = request.data.get('address', '').strip()
        amount = Decimal(str(request.data.get('amount', 0)))
        otp_code = request.data.get('otp', '').strip()

        # Validate address and amount
        if not address.startswith('0x'):
            return Response({'error': 'Invalid address'}, status=400)
        if amount < 10:
            return Response({'error': 'Min $10'}, status=400)

        # OTP Verification
        if not otp_code:
            OTPService.generate_otp(request.user, 'WITHDRAWAL')
            return Response({'require_otp': True, 'message': 'OTP sent to your email'})

        otp_result = OTPService.verify_otp(request.user, otp_code, 'WITHDRAWAL')
        if not otp_result['success']:
            return Response({'error': otp_result['error']}, status=400)

        # Check balance
        grand = Wallet.objects.get(user=request.user, wallet_type='GRAND')
        if grand.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        # Deduct first
        grand.balance -= amount
        grand.save()

        try:
            bs = BinanceService()
            result = bs.withdraw_via_web3(address, float(amount))
            if result['success']:
                Transaction.objects.create(
                    user=request.user, transaction_type='WITHDRAWAL',
                    amount=amount, fee=Decimal('0'), status='COMPLETED',
                    tx_hash=result.get('tx_hash', ''),
                    metadata={'to_address': address},
                    completed_at=timezone.now()
                )
                return Response(
                    {'success': True, 'tx_id': result.get('tx_hash', ''), 'new_balance': float(grand.balance)})
            else:
                grand.balance += amount
                grand.save()
                return Response({'error': result.get('error', 'Failed')}, status=400)
        except Exception as e:
            print('WITHDRAW ERROR:', str(e))
            traceback.print_exc()
            grand.balance += amount
            grand.save()
            return Response({'error': str(e)}, status=500)



    @action(detail=False, methods=['post'])
    def withdraw_yield(self, request):
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
                user=request.user, transaction_type='WITHDRAWAL', amount=amount, fee=0, status='COMPLETED',
                metadata={'from_wallet': 'YIELD', 'to_wallet': 'GRAND'}, completed_at=timezone.now()
            )
            return Response({
                'success': True, 'amount': str(amount),
                'new_yield_balance': str(yield_wallet.balance),
                'new_grand_balance': str(grand_wallet.balance)
            })
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def recent_distributions(self, request):
        from apps.yield_earnings.models import YieldDistribution
        import random
        from datetime import datetime, timedelta
        try:
            distributions = YieldDistribution.objects.filter(user=request.user, is_credited=True).order_by('-credited_at')[:10]
            data = []
            for d in distributions:
                data.append({
                    'token': d.token_balance.token.symbol if d.token_balance else 'USDC',
                    'amount': str(d.amount),
                    'time': d.credited_at.strftime('%Y-%m-%d %H:%M:%S') if d.credited_at else d.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            if not data:
                user_tokens = [b.token.symbol for b in request.user.token_balances.filter(quantity__gt=0)]
                token_list = user_tokens if user_tokens else ['BTC', 'ETH', 'BNB', 'SOL']
                for i in range(5):
                    date = datetime.now() - timedelta(hours=i * 2)
                    data.append({'token': random.choice(token_list), 'amount': str(round(random.uniform(0.05, 2.5), 4)), 'time': date.strftime('%Y-%m-%d %H:%M:%S')})
            return Response(data)
        except Exception as e:
            print(f"Error in recent_distributions: {e}")
            return Response([])

    @action(detail=False, methods=['get'])
    def referral_stats(self, request):
        from apps.referrals.models import ReferralRelationship, ReferralEarning
        total_referrals = ReferralRelationship.objects.filter(referrer=request.user, level=1).count()
        active_referrals = 0
        for rel in ReferralRelationship.objects.filter(referrer=request.user, level=1):
            if Purchase.objects.filter(user=rel.referred).exists():
                active_referrals += 1
        total_commissions = ReferralEarning.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or 0
        return Response({
            'total_referrals': total_referrals,
            'active_referrals': active_referrals,
            'total_commissions': float(total_commissions),
            'pending_commissions': 0.0
        })

    @action(detail=False, methods=['get'])
    def referrals_list(self, request):
        from apps.referrals.models import ReferralRelationship, ReferralEarning
        referrals = ReferralRelationship.objects.filter(referrer=request.user, level=1).select_related('referred')
        data = []
        for rel in referrals:
            referred_user = rel.referred
            purchases = Purchase.objects.filter(user=referred_user)
            total_purchases = purchases.count()
            total_spent = purchases.aggregate(total=Sum('total_amount'))['total'] or 0
            is_active = total_purchases > 0
            earnings = ReferralEarning.objects.filter(user=request.user, from_user=referred_user).aggregate(total=Sum('amount'))['total'] or 0
            data.append({
                'username': referred_user.username or referred_user.email.split('@')[0],
                'email': referred_user.email,
                'joined_at': referred_user.date_joined.isoformat() if hasattr(referred_user, 'date_joined') else '',
                'is_active': is_active,
                'total_purchases': total_purchases,
                'total_spent': float(total_spent),
                'total_commission': float(earnings),
                'level': 1
            })
        return Response(data)

    @action(detail=False, methods=['get'])
    def referral_tree(self, request):
        from apps.referrals.models import ReferralRelationship, ReferralEarning
        try:
            levels = []
            current_users = [request.user]
            for level_num in range(1, 8):
                next_users = []
                level_data = []
                for user in current_users:
                    referrals = ReferralRelationship.objects.filter(referrer=user).select_related('referred')
                    for ref in referrals:
                        next_users.append(ref.referred)
                        referred = ref.referred
                        has_purchased = Purchase.objects.filter(user=referred).exists() or UserTokenBalance.objects.filter(user=referred, quantity__gt=0).exists()
                        has_grid_bot = GridBot.objects.filter(user=referred).exclude(status='COMPLETED').exists()
                        earnings = ReferralEarning.objects.filter(user=request.user, from_user=referred).aggregate(total=Sum('amount'))['total'] or 0
                        is_active = has_purchased or has_grid_bot
                        level_data.append({
                            'name': referred.username or (referred.email.split('@')[0] if referred.email else 'User'),
                            'email': referred.email or '',
                            'status': "Active" if is_active else "Registered",
                            'status_icon': "🟢" if is_active else "⚪",
                            'has_purchased': has_purchased,
                            'has_grid_bot': has_grid_bot,
                            'earnings': float(earnings),
                            'joined_at': referred.date_joined.strftime('%Y-%m-%d') if hasattr(referred, 'date_joined') else 'N/A'
                        })
                if level_data:
                    levels.append({'level': level_num, 'referrals': level_data})
                current_users = next_users
                if not current_users:
                    break
            return Response({'levels': levels})
        except Exception as e:
            print(f"Error in referral_tree: {e}")
            return Response({'levels': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def referral_earnings(self, request):
        from apps.referrals.models import ReferralEarning
        try:
            earnings = ReferralEarning.objects.filter(user=request.user).select_related('purchase', 'from_user').order_by('-created_at')[:50]
            data = []
            for e in earnings:
                data.append({
                    'date': e.created_at.strftime('%Y-%m-%d %H:%M') if e.created_at else 'N/A',
                    'from_user': e.from_user.email if e.from_user else 'Unknown',
                    'level': e.level or 1,
                    'purchase_amount': str(e.purchase.total_amount) if e.purchase else '0',
                    'commission': str(e.amount) if e.amount else '0'
                })
            return Response(data)
        except Exception as ex:
            print(f"Error in referral_earnings: {ex}")
            return Response([])

    @action(detail=False, methods=['get'])
    def deposit_address(self, request):
        from apps.wallets.services.deposit_service import DepositService
        try:
            address = DepositService.get_deposit_address(request.user)
            return Response({'address': address})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def set_take_profit(self, request):
        from apps.tokens.models import TakeProfitOrder
        token_id = request.data.get('token_id')
        quantity = Decimal(str(request.data.get('quantity', 0)))
        target_percentage = Decimal(str(request.data.get('target_percentage', 0)))
        if not token_id or quantity <= 0 or target_percentage <= 0:
            return Response({'error': 'Invalid parameters'}, status=status.HTTP_400_BAD_REQUEST)
        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)
        try:
            user_balance = request.user.token_balances.get(token=token)
        except:
            return Response({'error': 'You don\'t own this token'}, status=status.HTTP_400_BAD_REQUEST)
        if user_balance.quantity < quantity:
            return Response({'error': 'Insufficient token balance'}, status=status.HTTP_400_BAD_REQUEST)
        target_price = user_balance.average_buy_price * (1 + target_percentage / 100)
        order = TakeProfitOrder.objects.create(
            user=request.user, token=token, quantity=quantity,
            purchase_price=user_balance.average_buy_price,
            target_price=target_price, target_percentage=target_percentage
        )
        return Response({
            'success': True, 'order_id': str(order.id), 'token': token.symbol,
            'quantity': str(quantity), 'target_price': str(target_price),
            'target_percentage': str(target_percentage)
        })

    @action(detail=False, methods=['get'])
    def take_profit_orders(self, request):
        from apps.tokens.models import TakeProfitOrder
        orders = TakeProfitOrder.objects.filter(user=request.user, status='ACTIVE')
        data = [{'id': str(o.id), 'token_symbol': o.token.symbol, 'quantity': str(o.quantity),
                 'purchase_price': str(o.purchase_price), 'target_price': str(o.target_price),
                 'target_percentage': str(o.target_percentage), 'current_price': str(o.token.current_price),
                 'created_at': o.created_at.strftime('%Y-%m-%d %H:%M')} for o in orders]
        return Response(data)

    @action(detail=False, methods=['post'])
    def cancel_take_profit(self, request):
        from apps.tokens.models import TakeProfitOrder
        try:
            order = TakeProfitOrder.objects.get(id=request.data.get('order_id'), user=request.user, status='ACTIVE')
            order.status = 'CANCELLED'
            order.save()
            return Response({'success': True})
        except TakeProfitOrder.DoesNotExist:
            return Response({'error': 'Order not found'}, status=400)

    @action(detail=False, methods=['get'])
    def recent_transactions(self, request):
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]
        data = [{'id': str(tx.id), 'type': tx.transaction_type, 'amount': str(tx.amount),
                 'fee': str(tx.fee), 'status': tx.status,
                 'date': tx.created_at.strftime('%Y-%m-%d %H:%M'), 'tx_hash': tx.tx_hash} for tx in transactions]
        return Response(data)

    @action(detail=False, methods=['post'])
    def withdraw(self, request):
        """Withdraw USDC via Web3 from central wallet"""
        from apps.wallets.services.binance_service import BinanceService

        address = request.data.get('address', '').strip()
        amount = Decimal(str(request.data.get('amount', 0)))

        if not address.startswith('0x') or len(address) != 42:
            return Response({'error': 'Invalid BSC address'}, status=400)
        if amount < 10:
            return Response({'error': 'Minimum $10 USDC'}, status=400)

        grand_wallet = Wallet.objects.select_for_update().get(user=request.user, wallet_type='GRAND')

        if grand_wallet.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        # Deduct first
        grand_wallet.balance -= amount
        grand_wallet.save()

        tx_record = Transaction.objects.create(
            user=request.user, transaction_type='WITHDRAWAL',
            amount=amount, fee=Decimal('0'), status='PENDING',
            metadata={'to_address': address, 'network': 'BSC'}
        )

        try:
            bs = BinanceService()
            result = bs.withdraw_via_web3(address, float(amount))

            if result['success']:
                tx_record.status = 'COMPLETED'
                tx_record.tx_hash = result.get('tx_hash', '')
                tx_record.completed_at = timezone.now()
                tx_record.save()
                return Response({
                    'success': True, 'amount': float(amount),
                    'tx_id': result.get('tx_hash', ''),
                    'new_balance': float(grand_wallet.balance)
                })
            else:
                grand_wallet.balance += amount
                grand_wallet.save()
                tx_record.status = 'FAILED'
                tx_record.save()
                return Response({'error': result.get('error', 'Failed')}, status=400)

        except Exception as e:
            grand_wallet.balance += amount
            grand_wallet.save()
            tx_record.status = 'FAILED'
            tx_record.save()
            return Response({'error': str(e)}, status=500)




    @action(detail=False, methods=['get'])
    def my_spot_tokens(self, request):
        """Get only market order token balances (not grid bot tokens)"""
        # Get all token balances
        balances = request.user.token_balances.filter(quantity__gt=0)

        # Get tokens that were bought via market orders
        market_purchases = Purchase.objects.filter(
            user=request.user,
            order_type='MARKET'
        ).values_list('token_id', flat=True).distinct()

        # Filter balances to only include market-bought tokens
        spot_balances = balances.filter(token_id__in=market_purchases)

        serializer = UserTokenBalanceSerializer(spot_balances, many=True)
        return Response(serializer.data)


class AdminYieldRateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        setting, _ = PlatformSetting.objects.get_or_create(key='monthly_yield_rate', defaults={'value': 10})
        return Response({'current_rate': float(setting.value)})

    def post(self, request):
        new_rate = request.data.get('rate')
        if new_rate:
            setting, _ = PlatformSetting.objects.get_or_create(key='monthly_yield_rate')
            setting.value = Decimal(str(new_rate))
            setting.save()
            return Response({'success': True, 'new_rate': new_rate})
        return Response({'error': 'Rate required'}, status=400)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def check_deposits_webhook(request):
    from django.contrib.auth import get_user_model
    from apps.yield_earnings.services.yield_service import YieldService
    User = get_user_model()
    credited_count = 0
    call_command('check_credits')
    for user in User.objects.all():
        try:
            amount = YieldService.credit_hourly_yield(user)
            if amount > 0:
                credited_count += 1
        except Exception as e:
            print(f"Error crediting {user.email}: {e}")
    return JsonResponse({'status': 'success', 'deposits_checked': True, 'yield_users_credited': credited_count})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def credit_yield_only(request):
    from django.contrib.auth import get_user_model
    from apps.yield_earnings.services.yield_service import YieldService
    User = get_user_model()
    credited_count = 0
    for user in User.objects.all():
        try:
            amount = YieldService.credit_hourly_yield(user)
            if amount > 0:
                credited_count += 1
        except Exception as e:
            print(f"Error crediting {user.email}: {e}")
    return JsonResponse({'status': 'success', 'users_credited': credited_count})


@api_view(['GET'])
@permission_classes([AllowAny])
def yield_rate_view(request):
    setting, _ = PlatformSetting.objects.get_or_create(key='monthly_yield_rate', defaults={'value': 10})
    monthly_rate = float(setting.value)
    return Response({'monthly': monthly_rate, 'hourly': monthly_rate / 720})


@csrf_exempt
def send_daily_email_webhook(request):
    """Trigger daily emails in background - returns immediately"""
    import threading
    from apps.tasks.email_tasks import send_daily_email_to_all_users

    # Run in background thread so cron-job.org doesn't timeout
    thread = threading.Thread(target=send_daily_email_to_all_users)
    thread.start()

    return JsonResponse({'status': 'queued', 'message': 'Emails sending in background'})


@csrf_exempt
def sweep_webhook(request):
    from django.core.management import call_command
    call_command('check_credits')
    return JsonResponse({'status': 'success'})