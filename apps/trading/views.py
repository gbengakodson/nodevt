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
from .models import CryptoToken, Purchase, GridBot







def update_prices_webhook(request):
    """Webhook endpoint to trigger price updates"""
    from django.core.management import call_command
    call_command('update_prices')
    return JsonResponse({'status': 'success', 'message': 'Prices updated'})





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
        """Buy crypto tokens - Market Order (1% fee) or Grid Bot (10% fee)"""
        serializer = PurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        amount_usdc = serializer.validated_data['amount_usdc']
        order_type = request.data.get('order_type', 'market')

        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

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
            # Market order: add to spot wallet (UserTokenBalance)
            user_balance, created = request.user.token_balances.get_or_create(
                token=token,
                defaults={'quantity': 0, 'average_buy_price': 0}
            )

            total_quantity = user_balance.quantity + token_quantity
            total_cost = (user_balance.quantity * user_balance.average_buy_price) + (
                        token_quantity * token.current_price)
            user_balance.average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
            user_balance.quantity = total_quantity
            user_balance.save()

        else:
            # GRID BOT: Create GridBot record with 80% range


            # Upper price = current price + 80% (× 1.8)
            # Lower price = current price - 80% (× 0.2)
            upper_price = token.current_price * Decimal('1.8')
            lower_price = token.current_price * Decimal('0.2')

            GridBot.objects.create(
                user=request.user,
                token=token,
                amount=amount_after_fee,
                lower_price=lower_price,
                upper_price=upper_price,
                grids=100,
                status='ACTIVE'
            )

        # Create purchase record
        purchase = Purchase.objects.create(
            user=request.user,
            token=token,
            quantity=token_quantity,
            price_per_token=token.current_price,
            total_amount=amount_after_fee,
            node_fee=node_fee
        )

        # Distribute node fee to referrals (only for grid bot orders)
        referral_count = 0
        if order_type == 'grid':
            from apps.referrals.services.referral_service import ReferralService
            try:
                distributions = ReferralService.distribute_node_fee(request.user, node_fee, purchase)
                referral_count = len(distributions)
            except Exception as e:
                print(f"Error distributing referral fees: {e}")
                referral_count = 0

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
    def my_grids(self, request):
        """Get user's active grid bots"""
        from .models import GridBot

        grid_bots = GridBot.objects.filter(user=request.user, status='ACTIVE')

        data = []
        for bot in grid_bots:
            data.append({
                'id': str(bot.id),
                'token_symbol': bot.token.symbol,
                'token_name': bot.token.name,
                'amount': float(bot.amount),
                'lower_price': float(bot.lower_price),
                'upper_price': float(bot.upper_price),
                'grids': bot.grids,
                'current_grid_level': bot.current_grid_level,
                'grid_profit': float(bot.grid_profit),
                'pnl': float(bot.pnl),
                'pnl_percent': float(bot.pnl_percent),
                'status': bot.status,
                'created_at': bot.created_at.isoformat()
            })

        return Response(data)


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
        from decimal import Decimal

        # Count referrals (people this user directly referred)
        total_referrals = ReferralRelationship.objects.filter(referrer=request.user).count()
        active_referrals = ReferralRelationship.objects.filter(
            referrer=request.user,
            referred__is_active=True
        ).count()

        # Calculate total commissions from referral earnings
        earnings = ReferralEarning.objects.filter(user=request.user)
        total_commissions = sum(e.amount for e in earnings)

        # Pending commissions (all are credited immediately, so 0)
        pending_commissions = Decimal('0')

        return Response({
            'total_referrals': total_referrals,
            'active_referrals': active_referrals,
            'total_commissions': float(total_commissions),
            'pending_commissions': float(pending_commissions)
        })

    @action(detail=False, methods=['get'])
    def referral_tree(self, request):
        """Get referral tree for user (up to 7 generations)"""
        from apps.referrals.models import ReferralRelationship, ReferralEarning
        from django.db.models import Sum

        levels = []
        current_users = [request.user]

        for level_num in range(1, 8):
            next_users = []
            level_data = []

            for user in current_users:
                referrals = ReferralRelationship.objects.filter(referrer=user).select_related('referred')
                for ref in referrals:
                    next_users.append(ref.referred)

                    # Calculate actual earnings from this referred user
                    earnings = ReferralEarning.objects.filter(
                        user=request.user,
                        from_user=ref.referred
                    ).aggregate(total=Sum('amount'))['total'] or 0

                    level_data.append({
                        'name': ref.referred.username or ref.referred.email.split('@')[0],
                        'email': ref.referred.email,
                        'earnings': float(earnings)
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

        earnings = ReferralEarning.objects.filter(user=request.user).order_by('-created_at')[:50]

        data = []
        for e in earnings:
            data.append({
                'date': e.created_at.strftime('%Y-%m-%d %H:%M'),
                'from_user': e.from_user.email,
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



    @action(detail=False, methods=['get'])
    def recent_transactions(self, request):
        """Get recent transactions for the user"""
        from apps.wallets.models import Transaction

        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:50]

        data = []
        for tx in transactions:
            data.append({
                'id': str(tx.id),
                'type': tx.transaction_type,
                'amount': str(tx.amount),
                'fee': str(tx.fee),
                'status': tx.status,
                'date': tx.created_at.strftime('%Y-%m-%d %H:%M'),
                'tx_hash': tx.tx_hash
            })

        return Response(data)

    @action(detail=False, methods=['post'])
    def prepare_buy(self, request):
        """Prepare a buy transaction for the user to sign"""
        from apps.wallets.services.transaction_service import TransactionService

        token_id = request.data.get('token_id')
        amount_usdc = Decimal(str(request.data.get('amount_usdc', 0)))

        if not request.user.wallet_address:
            return Response({'error': 'No wallet address found'}, status=400)

        tx_service = TransactionService()
        tx = tx_service.create_buy_transaction(request.user.wallet_address, float(amount_usdc))

        if tx:
            return Response({
                'transaction': {
                    'to': tx['to'],
                    'value': str(tx['value']),
                    'gas': tx['gas'],
                    'gasPrice': str(tx['gasPrice']),
                    'nonce': tx['nonce'],
                    'data': tx['data'].hex() if tx['data'] else '0x'
                }
            })
        return Response({'error': 'Failed to create transaction'}, status=500)

    @action(detail=False, methods=['post'])
    def withdraw(self, request):
        """Withdraw USDC from grand balance to external wallet"""
        from apps.wallets.models import Wallet, Transaction
        from decimal import Decimal
        from django.utils import timezone

        address = request.data.get('address')
        amount = Decimal(str(request.data.get('amount', 0)))

        if not address:
            return Response({'error': 'Wallet address required'}, status=400)

        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=400)

        # Check minimum withdrawal
        if amount < 10:
            return Response({'error': 'Minimum withdrawal is $10 USDC'}, status=400)

        # Get user's grand wallet
        grand_wallet = Wallet.objects.get(user=request.user, wallet_type='GRAND')

        if grand_wallet.balance < amount:
            return Response({'error': 'Insufficient balance'}, status=400)

        # Deduct from grand wallet
        grand_wallet.balance -= amount
        grand_wallet.save()

        # Create transaction record
        Transaction.objects.create(
            user=request.user,
            transaction_type='WITHDRAWAL',
            amount=amount,
            fee=0,
            status='COMPLETED',
            metadata={
                'to_address': address,
                'network': 'BSC (BEP20)',
                'token': 'USDC'
            },
            completed_at=timezone.now()
        )

        # Note: Actual blockchain transfer would go here
        # For now, we just update the database

        return Response({
            'success': True,
            'amount': str(amount),
            'address': address,
            'new_balance': str(grand_wallet.balance),
            'message': f'Withdrawal of ${amount} USDC to {address} initiated'
        })

    @action(detail=False, methods=['post'])
    def stop_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        bot.status = 'STOPPED'
        bot.stopped_at = timezone.now()
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

        if bot.pnl <= 0:
            return Response({'error': 'PNL must be positive to close'}, status=400)

        # Add funds to grand wallet
        grand_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND')
        total_return = bot.amount + bot.grid_profit + bot.pnl
        grand_wallet.balance += Decimal(str(total_return))
        grand_wallet.save()

        bot.status = 'COMPLETED'
        bot.save()

        return Response({'success': True, 'amount': float(total_return)})

    @action(detail=False, methods=['post'])
    def auto_close_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)

        if bot.pnl_percent >= 20:
            grand_wallet, _ = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND')
            total_return = bot.amount + bot.grid_profit + bot.pnl
            grand_wallet.balance += Decimal(str(total_return))
            grand_wallet.save()

            bot.status = 'COMPLETED'
            bot.auto_closed_at = timezone.now()
            bot.save()

            return Response({'success': True, 'amount': float(total_return)})

        return Response({'error': 'PNL not reached 20%'}, status=400)




@csrf_exempt
@require_http_methods(["GET", "POST"])
def check_deposits_webhook(request):
    """Trigger hourly yield credit for all users"""
    from django.contrib.auth import get_user_model
    from apps.yield_earnings.services.yield_service import YieldService
    from django.core.management import call_command

    User = get_user_model()
    credited_count = 0

    # First check deposits
    call_command('check_credits')

    # Then credit hourly yield for all users
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
    """Safe webhook that ONLY credits yield - no deposit checking"""
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


from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def yield_rate_view(request):
    monthly_rate = getattr(settings, 'YIELD_MONTHLY_RATE', 10.0)
    return Response({
        'monthly': monthly_rate,
        'hourly': monthly_rate / 720
    })



