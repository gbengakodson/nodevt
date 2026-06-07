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
from datetime import timedelta
from apps.core.notifications import notify_user



def update_prices_webhook(request):
    """Webhook endpoint to trigger price updates"""
    from django.core.management import call_command
    call_command('update_prices')
    return JsonResponse({'status': 'success', 'message': 'Prices updated'})


class TradingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _sweep_from_user_wallet(from_address, private_key, to_address, amount):
        """Sweep exact USDC amount from user wallet to NODE central. Auto-funds gas if needed."""
        from web3 import Web3
        from django.conf import settings

        try:
            w3 = Web3(Web3.HTTPProvider('https://bsc-rpc.publicnode.com'))

            from_addr = Web3.to_checksum_address(from_address)
            to_addr = Web3.to_checksum_address(to_address)

            # Check if user has enough BNB for gas
            gas_price = w3.eth.gas_price
            gas_limit = 150000  # Higher limit for USDC transfers
            required_gas = gas_price * gas_limit
            user_bnb = w3.eth.get_balance(from_addr)

            if user_bnb < required_gas:
                # Send BNB from NODE central to user for gas
                central_addr = Web3.to_checksum_address(settings.CENTRAL_WALLET_ADDRESS)
                central_pk = settings.CENTRAL_WALLET_PRIVATE_KEY
                gas_fund = w3.to_wei(0.0005, 'ether')

                fund_tx = {
                    'from': central_addr,
                    'to': from_addr,
                    'value': gas_fund,
                    'nonce': w3.eth.get_transaction_count(central_addr),
                    'gas': 21000,
                    'gasPrice': gas_price,
                    'chainId': 56
                }
                signed_fund = w3.eth.account.sign_transaction(fund_tx, central_pk)
                fund_hash = w3.eth.send_raw_transaction(signed_fund.raw_transaction)
                print(f"⛽ Sent 0.0005 BNB gas to {from_address[:10]}... TX: {fund_hash.hex()[:20]}...")

                # Wait for BNB to arrive (a few seconds)
                import time
                time.sleep(5)

            # Now sweep the USDC
            usdc_address = Web3.to_checksum_address('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d')
            abi = [
                {"constant": False,
                 "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
                 "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            ]
            contract = w3.eth.contract(address=usdc_address, abi=abi)

            amount_wei = int(Decimal(str(amount)) * Decimal(10 ** 18))

            tx = contract.functions.transfer(to_addr, amount_wei).build_transaction({
                'from': from_addr,
                'nonce': w3.eth.get_transaction_count(from_addr),
                'gas': gas_limit,
                'gasPrice': gas_price,
                'chainId': 56
            })

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'amount': float(amount)
            }

        except Exception as e:
            print(f"Sweep error: {e}")
            return {'success': False, 'error': str(e)}



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
        """Activate a Position Tracker — 10% management fee, sweeps from user wallet"""
        serializer = PurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_id = serializer.validated_data['token_id']
        amount_usdc = serializer.validated_data['amount_usdc']

        token = get_object_or_404(CryptoToken, id=token_id, is_active=True)

        # 10% management fee
        fee_percent = Decimal('0.10')
        node_fee = amount_usdc * fee_percent
        amount_after_fee = amount_usdc - node_fee
        token_quantity = amount_after_fee / token.current_price

        # Sweep from user wallet to NODE central
        from apps.wallets.models import WalletKey
        from apps.wallets.services.web3_service import Web3Service

        try:
            wallet_key = WalletKey.objects.get(user=request.user)
            user_address = wallet_key.address
        except WalletKey.DoesNotExist:
            return Response({
                'error': 'No wallet found. Please deposit first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        ws = Web3Service()
        real_balance = ws.get_usdc_balance(user_address)
        if real_balance < amount_usdc:
            return Response({
                'error': 'Insufficient wallet balance',
                'your_wallet_balance': str(real_balance),
                'required': str(amount_usdc)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create GridBot BEFORE sweep
        upper_price = token.current_price * Decimal('1.8')
        lower_price = token.current_price * Decimal('0.2')
        bot = GridBot.objects.create(
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

        # Sweep
        user_private_key = wallet_key.get_private_key()
        sweep_result = TradingViewSet._sweep_from_user_wallet(
            user_address, user_private_key,
            settings.CENTRAL_WALLET_ADDRESS,
            amount_usdc
        )

        if not sweep_result['success']:
            bot.delete()
            return Response({
                'error': f"Sweep failed: {sweep_result.get('error', 'Unknown error')}"
            }, status=status.HTTP_400_BAD_REQUEST)

        bot.metadata = {'sweep_tx': sweep_result.get('tx_hash', '')}
        bot.save()
        # Award NODE tokens for activation (auto-activated)
        from apps.tokens.services.token_service import TokenService
        TokenService.award_tracker_tokens(request.user, amount_usdc)

        notify_user(
            request.user,
            f'🤖 {token.symbol} Position Tracker Activated',
            f'Your {token.symbol} tracker is live with ${float(amount_after_fee):.2f}. Profits start in 24 hours.',
            'PORTFOLIO'
        )

        # Purchase record
        purchase = Purchase.objects.create(
            user=request.user,
            token=token,
            quantity=token_quantity,
            price_per_token=token.current_price,
            total_amount=amount_after_fee,
            node_fee=node_fee,
            order_type='GRID'
        )

        # Distribute node fee to referrals (3 levels, half-of-remaining)
        referral_count = 0
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
                'order_type': 'GRID',
                'referrals_credited': referral_count
            },
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'message': f'Position Tracker activated for {token.symbol}',
            'purchase': {
                'token': token.symbol,
                'quantity': str(token_quantity),
                'price_per_token': str(token.current_price),
                'total_amount': str(amount_after_fee),
                'node_fee': str(node_fee),
                'order_type': 'GRID'
            },
            'referral_commission': {
                'total_fee': str(node_fee),
                'referrers_count': referral_count,
                'distributed': referral_count > 0
            } if referral_count > 0 else None
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
        """Close Position Tracker and sweep funds to user's real wallet"""
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)

        # Correct return: investment + uncollected profit + market PNL
        total_return = (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0)



        # Check platform liquidity
        from apps.wallets.services.web3_service import Web3Service
        ws = Web3Service()
        central_balance = ws.get_usdc_balance(settings.CENTRAL_WALLET_ADDRESS)

        if central_balance < total_return:
            return Response({
                'error': 'Liquidity Gap! Please try again in 24 hours.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get user's wallet address
        from apps.wallets.models import WalletKey
        try:
            wallet_key = WalletKey.objects.get(user=request.user)
            user_address = wallet_key.address
        except WalletKey.DoesNotExist:
            return Response({'error': 'No wallet found'}, status=status.HTTP_400_BAD_REQUEST)

        # Sweep from NODE Web3 to user's real wallet
        from django.conf import settings
        sweep_result = TradingViewSet._sweep_from_user_wallet(
            settings.CENTRAL_WALLET_ADDRESS,
            settings.CENTRAL_WALLET_PRIVATE_KEY,
            user_address,
            total_return
        )

        if not sweep_result['success']:
            return Response({
                'error': f"Sweep failed: {sweep_result.get('error', 'Unknown error')}"
            }, status=status.HTTP_400_BAD_REQUEST)

        Transaction.objects.create(
            user=request.user,
            transaction_type='GRID_CLOSE',
            amount=total_return,
            fee=0,
            status='COMPLETED',
            tx_hash=sweep_result.get('tx_hash', ''),
            metadata={
                'grid_bot_id': str(bot.id),
                'token': bot.token.symbol,
                'investment': str(bot.amount),
                'grid_profit': str(bot.grid_profit),
                'pnl': str(bot.pnl),
                'to_address': user_address
            },
            completed_at=timezone.now()
        )
        from apps.tokens.services.token_service import TokenService
        activated = TokenService.activate_pending_tokens(request.user)
        if activated > 0:
            notify_user(
                request.user,
                '🎉 Tokens Activated!',
                f'{int(activated)} NODE tokens have been activated and are now permanent.',
                'PORTFOLIO'
            )

        bot.status = 'COMPLETED'
        bot.save()

        return Response({
            'success': True,
            'total_return': float(total_return),
            'tx_hash': sweep_result.get('tx_hash', ''),
            'breakdown': {
                'investment': float(bot.amount),
                'grid_profit': float(bot.grid_profit),
                'pnl': float(bot.pnl)
            }
        })

    @action(detail=False, methods=['post'])
    def auto_close_grid(self, request):
        bot_id = request.data.get('bot_id')
        bot = GridBot.objects.get(id=bot_id, user=request.user)
        if bot.pnl_percent >= 20:
            total_return = (bot.amount or 0) + (bot.grid_profit or 0) + (bot.pnl or 0)



            from apps.wallets.models import WalletKey
            try:
                wallet_key = WalletKey.objects.get(user=request.user)
                user_address = wallet_key.address
            except WalletKey.DoesNotExist:
                return Response({'error': 'No wallet found'}, status=400)

            from django.conf import settings
            sweep_result = TradingViewSet._sweep_from_user_wallet(
                settings.CENTRAL_WALLET_ADDRESS,
                settings.CENTRAL_WALLET_PRIVATE_KEY,
                user_address,
                total_return
            )

            if not sweep_result['success']:
                return Response({'error': f"Sweep failed: {sweep_result.get('error')}"}, status=400)

            Transaction.objects.create(
                user=request.user,
                transaction_type='GRID_CLOSE',
                amount=total_return, fee=0, status='COMPLETED',
                tx_hash=sweep_result.get('tx_hash', ''),
                metadata={'grid_bot_id': str(bot.id), 'token': bot.token.symbol, 'to_address': user_address},
                completed_at=timezone.now()
            )

            bot.status = 'COMPLETED'
            bot.save()
            return Response(
                {'success': True, 'amount': float(total_return), 'tx_hash': sweep_result.get('tx_hash', '')})
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
            'grand_balance': str(blockchain_balance),  # Mirror wallet balance
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

                # Place notification BEFORE the return
                notify_user(
                    request.user,
                    f'📤 Withdrawal Processed',
                    f'${float(amount):.2f} USDC sent. TX: {sweep_result.get("tx_hash", "")[:20]}...',
                    'ALERT'
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
        """Withdraw yield - sweep from NODE Web3 to user's real wallet. Min 10% of portfolio (unless pension)."""
        amount = Decimal(str(request.data.get('amount', 0)))
        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            yield_wallet = Wallet.objects.get(user=request.user, wallet_type='YIELD')
        except Wallet.DoesNotExist:
            return Response({'error': 'Yield wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

        if yield_wallet.balance < amount:
            return Response({'error': 'Insufficient yield balance'}, status=status.HTTP_400_BAD_REQUEST)

        # 10% minimum rule (skipped for pension fund)
        if not yield_wallet.pension_fund:
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
            grand_balance = grand_wallet.balance if grand_wallet else Decimal('0')

            total_portfolio = token_value + grid_value + grand_balance + yield_wallet.balance
            min_required = total_portfolio * Decimal('0.10')

            if amount < min_required:
                return Response({
                    'error': f'Minimum withdrawal is 10% of portfolio (${float(min_required):.2f})',
                    'min_required': float(min_required),
                    'your_yield_balance': float(yield_wallet.balance),
                    'portfolio_value': float(total_portfolio),
                }, status=status.HTTP_400_BAD_REQUEST)

        # Check pension lock
        if yield_wallet.pension_fund and yield_wallet.locked_until:
            if timezone.now() < yield_wallet.locked_until:
                days_left = (yield_wallet.locked_until - timezone.now()).days
                return Response({
                    'error': f'Pension fund locked for {days_left} more days',
                    'locked_until': yield_wallet.locked_until.isoformat(),
                }, status=status.HTTP_400_BAD_REQUEST)

        # Get user's wallet address
        from apps.wallets.models import WalletKey
        try:
            wallet_key = WalletKey.objects.get(user=request.user)
            user_address = wallet_key.address
        except WalletKey.DoesNotExist:
            return Response({'error': 'No wallet found. Please deposit first.'}, status=status.HTTP_400_BAD_REQUEST)

        # Deduct yield wallet first
        yield_wallet.balance -= amount
        yield_wallet.save()

        # Sweep from NODE Web3 to user wallet
        from django.conf import settings
        sweep_result = TradingViewSet._sweep_from_user_wallet(
            settings.CENTRAL_WALLET_ADDRESS,
            settings.CENTRAL_WALLET_PRIVATE_KEY,
            user_address,
            amount
        )

        if not sweep_result['success']:
            # Refund if sweep fails
            yield_wallet.balance += amount
            yield_wallet.save()
            return Response({
                'error': f"Sweep failed: {sweep_result.get('error', 'Unknown error')}"
            }, status=status.HTTP_400_BAD_REQUEST)

        Transaction.objects.create(
            user=request.user, transaction_type='YIELD_WITHDRAW',
            amount=amount, fee=0, status='COMPLETED',
            tx_hash=sweep_result.get('tx_hash', ''),
            metadata={'from_wallet': 'YIELD', 'to_address': user_address},
            completed_at=timezone.now()
        )

        return Response({
            'success': True, 'amount': float(amount),
            'tx_hash': sweep_result.get('tx_hash', ''),
            'new_yield_balance': float(yield_wallet.balance)
        })





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
        """Get direct referrals only (1 level)"""
        from apps.referrals.models import ReferralRelationship, ReferralEarning

        referrals = ReferralRelationship.objects.filter(
            referrer=request.user, level=1
        ).select_related('referred')

        data = []
        for ref in referrals:
            referred = ref.referred
            has_purchased = Purchase.objects.filter(user=referred).exists()
            has_grid = GridBot.objects.filter(user=referred).exclude(status='COMPLETED').exists()
            earnings = ReferralEarning.objects.filter(
                user=request.user, from_user=referred
            ).aggregate(total=Sum('amount'))['total'] or 0

            data.append({
                'name': referred.username or (referred.email.split('@')[0] if referred.email else 'User'),
                'email': referred.email or '',
                'status': "Active" if (has_purchased or has_grid) else "Registered",
                'earnings': float(earnings),
                'joined_at': referred.date_joined.strftime('%Y-%m-%d') if hasattr(referred, 'date_joined') else 'N/A'
            })

        return Response({'referrals': data, 'total': len(data)})



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
    def wallet_key(self, request):
        """Return user's wallet address and decrypted private key"""
        from apps.wallets.models import WalletKey

        try:
            wallet_key = WalletKey.objects.get(user=request.user)
            return Response({
                'address': wallet_key.address,
                'private_key': wallet_key.get_private_key(),
            })
        except WalletKey.DoesNotExist:
            return Response({
                'error': 'No wallet found. Please deposit first to generate a wallet.'
            }, status=status.HTTP_404_NOT_FOUND)




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

    # ============ PURSE ENDPOINTS ============

    @action(detail=False, methods=['get'])
    def purse(self, request):
        """Get purse balance by name"""
        from apps.wallets.models import Purse
        name = request.GET.get('name', '')
        if not name:
            return Response({'error': 'Purse name required'}, status=400)

        purse, created = Purse.objects.get_or_create(
            user=request.user,
            name=name,
            defaults={'balance': Decimal('0')}
        )

        return Response({
            'name': purse.name,
            'balance': float(purse.balance),
            'auto_sweep_enabled': purse.auto_sweep_enabled,
            'sweep_percentage': purse.sweep_percentage,
            'withdraw_schedule': purse.withdraw_schedule,
            'is_active': purse.is_active
        })

    @action(detail=False, methods=['post'])
    def purse_toggle(self, request):
        """Toggle auto-sweep for a purse"""
        from apps.wallets.models import Purse
        name = request.data.get('name', '')
        purse = Purse.objects.get(user=request.user, name=name)
        purse.auto_sweep_enabled = not purse.auto_sweep_enabled
        purse.save()
        return Response({'success': True, 'auto_sweep_enabled': purse.auto_sweep_enabled})

    @action(detail=False, methods=['post'])
    def purse_withdraw(self, request):
        """Withdraw from purse to user's real USDC wallet"""
        from apps.wallets.models import Purse, WalletKey
        name = request.data.get('name', '')
        amount = Decimal(str(request.data.get('amount', 0)))

        if not name or amount <= 0:
            return Response({'error': 'Purse name and valid amount required'}, status=400)

        try:
            purse = Purse.objects.get(user=request.user, name=name, is_active=True)
        except Purse.DoesNotExist:
            return Response({'error': 'Purse not found'}, status=404)

        if purse.balance < amount:
            return Response({'error': 'Insufficient purse balance'}, status=400)

        # Check withdraw schedule
        now = timezone.now()

        if purse.withdraw_schedule == 'monthly':
            last_withdraw = Transaction.objects.filter(
                user=request.user,
                transaction_type='PURSE_WITHDRAW',
                metadata__purse_name=name,
                created_at__month=now.month
            ).first()
            if last_withdraw:
                return Response({'error': f'{name} can only be withdrawn once per month'}, status=400)

        elif purse.withdraw_schedule == 'quarterly':
            three_months_ago = now - timedelta(days=90)
            last_withdraw = Transaction.objects.filter(
                user=request.user,
                transaction_type='PURSE_WITHDRAW',
                metadata__purse_name=name,
                created_at__gte=three_months_ago
            ).first()
            if last_withdraw:
                return Response({'error': f'{name} can only be withdrawn every 3 months'}, status=400)

        elif purse.withdraw_schedule == 'annually':
            year_ago = now - timedelta(days=365)
            last_withdraw = Transaction.objects.filter(
                user=request.user,
                transaction_type='PURSE_WITHDRAW',
                metadata__purse_name=name,
                created_at__gte=year_ago
            ).first()
            if last_withdraw:
                return Response({'error': f'{name} can only be withdrawn once per year'}, status=400)

        # Get user's wallet
        try:
            wallet_key = WalletKey.objects.get(user=request.user)
            user_address = wallet_key.address
        except WalletKey.DoesNotExist:
            return Response({'error': 'No wallet found'}, status=400)

        # Deduct purse first
        purse.balance -= amount
        purse.save()

        # Sweep from NODE Web3 to user wallet
        from django.conf import settings
        sweep_result = TradingViewSet._sweep_from_user_wallet(
            settings.CENTRAL_WALLET_ADDRESS,
            settings.CENTRAL_WALLET_PRIVATE_KEY,
            user_address,
            amount
        )

        if not sweep_result['success']:
            purse.balance += amount
            purse.save()
            return Response({'error': f"Sweep failed: {sweep_result.get('error')}"}, status=400)

        Transaction.objects.create(
            user=request.user,
            transaction_type='PURSE_WITHDRAW',
            amount=amount,
            fee=Decimal('0'),
            status='COMPLETED',
            tx_hash=sweep_result.get('tx_hash', ''),
            metadata={'purse_name': name, 'to_address': user_address},
            completed_at=timezone.now()
        )

        return Response({
            'success': True,
            'amount': float(amount),
            'purse_balance': float(purse.balance),
            'tx_hash': sweep_result.get('tx_hash', '')
        })

    @action(detail=False, methods=['post'])
    def pension_activate(self, request):
        """Activate pension fund with custom lock duration (2-30 years)"""
        years = int(request.data.get('years', 5))
        if years < 2:
            years = 2
        if years > 30:
            years = 30

        yield_wallet = Wallet.objects.get(user=request.user, wallet_type='YIELD')

        if yield_wallet.pension_fund:
            return Response({'error': 'Pension fund already active'}, status=400)

        yield_wallet.pension_fund = True
        yield_wallet.lock_enabled = True
        yield_wallet.locked_until = timezone.now() + timedelta(days=365 * years)
        yield_wallet.pension_reinvest_months = 6
        yield_wallet.pension_reinvest_years = years
        yield_wallet.save()

        return Response({
            'success': True,
            'message': f'Pension fund activated. Locked for {years} years. Auto-reinvest every 6 months.'
        })

    @action(detail=False, methods=['get'])
    def pension_status(self, request):
        """Check pension fund status"""
        yield_wallet = Wallet.objects.get(user=request.user, wallet_type='YIELD')

        return Response({
            'active': yield_wallet.pension_fund,
            'lock_enabled': yield_wallet.lock_enabled,
            'locked_until': yield_wallet.locked_until.isoformat() if yield_wallet.locked_until else None,
            'reinvest_months': yield_wallet.pension_reinvest_months,
            'reinvest_years': yield_wallet.pension_reinvest_years
        })

    @action(detail=False, methods=['get'])
    def binance_monitor(self, request):
        """Fetch live Binance data for public monitoring"""
        from binance.client import Client
        from django.conf import settings

        try:
            client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
            acct = client.get_account()
            balances = {}
            for b in acct['balances']:
                if b['asset'] in ['USDC', 'USDT', 'BNB']:
                    balances[b['asset']] = float(b['free'])

            open_orders = client.get_open_orders()

            trades = []
            for pair in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']:
                try:
                    pair_trades = client.get_my_trades(symbol=pair, limit=5)
                    trades.extend(pair_trades)
                except:
                    pass
            trades.sort(key=lambda x: x['time'], reverse=True)

            return Response({
                'balances': balances,
                'open_orders': len(open_orders),
                'trades': trades[:20]
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def fadakka_status(self, request):
        """Get Fadakka Index status for all coins"""
        from apps.trading.services.fadakka_service import FadakkaService
        from apps.tokens.models import CryptoToken

        data = []
        for token in CryptoToken.objects.filter(is_active=True):
            alpha = FadakkaService.get_alpha_levels(token.symbol)
            trigger = FadakkaService.check_trigger(token.symbol, token.current_price)
            has_grid = FadakkaService.has_active_grid(token.symbol)
            should_exit = FadakkaService.should_exit(token.symbol, token.current_price)

            data.append({
                'symbol': token.symbol,
                'current_price': float(token.current_price),
                'fadakka_k': alpha['k'] if alpha else None,
                'a1': alpha['a1'] if alpha else None,
                'a2': alpha['a2'] if alpha else None,
                'a3': alpha['a3'] if alpha else None,
                'exit_price': alpha['exit_price'] if alpha else None,
                'trigger': trigger['level'] if trigger else None,
                'tier': trigger.get('level', None) if trigger else None,
                'discount': trigger['discount'] if trigger else None,
                'has_active_grid': has_grid,
                'should_exit': should_exit,
            })

        return Response(data)



    @action(detail=False, methods=['get'])
    def grid_performance(self, request):
        """Get real Master Grid Bot performance data from Binance"""
        from apps.trading.models import MasterGridBot
        from apps.trading.services.fadakka_service import FadakkaService
        from apps.wallets.services.binance_service import BinanceService

        grids = MasterGridBot.objects.filter(status='ACTIVE').select_related('token')

        bs = BinanceService()
        performance_data = []
        total_invested = Decimal('0')
        total_profit = Decimal('0')
        total_trades = 0

        for grid in grids:
            # Get real Binance trade data
            trades = bs.get_filled_grid_orders(grid.token.symbol, start_time=grid.created_at)

            # Get current open orders
            binance_symbol = bs._get_binance_symbol(grid.token.symbol)
            open_orders = 0
            try:
                orders = bs.client.get_open_orders(symbol=binance_symbol)
                open_orders = len(orders)
            except:
                pass

            invested = grid.total_amount
            profit = Decimal(str(trades.get('profit', 0)))
            profit_percent = (profit / invested * 100) if invested > 0 else Decimal('0')

            total_invested += invested
            total_profit += profit
            total_trades += trades.get('total_trades', 0)

            performance_data.append({
                'id': str(grid.id),
                'symbol': grid.token.symbol,
                'invested': float(invested),
                'entry_price': float(grid.price_at_creation),
                'current_price': float(grid.token.current_price),
                'profit': float(profit),
                'profit_percent': float(profit_percent),
                'total_trades': trades.get('total_trades', 0),
                'buy_trades': trades.get('buy_trades', 0),
                'sell_trades': trades.get('sell_trades', 0),
                'open_orders': open_orders,
                'grids': grid.grids,
                'lower_price': float(grid.lower_price),
                'upper_price': float(grid.upper_price),
                'activated_at': grid.metadata.get('fadakka_level', 'unknown'),
                'created_at': grid.created_at.isoformat(),
                'last_trades': trades.get('trades', [])[:10],
            })

        # Aggregate stats
        grid_count = len(performance_data)
        avg_profit_percent = float(total_profit / total_invested * 100) if total_invested > 0 else 0

        return Response({
            'grids': performance_data,
            'stats': {
                'active_grids': grid_count,
                'total_invested': float(total_invested),
                'total_profit': float(total_profit),
                'avg_profit_percent': round(avg_profit_percent, 2),
                'total_trades': total_trades,
                'monthly_yield_rate': round(avg_profit_percent * 4, 2),  # Annualized estimate
            }
        })

    @action(detail=False, methods=['get'])
    def master_grid_live(self, request):
        """Get live Binance data for active Master Grids"""
        from apps.trading.models import MasterGridBot
        from apps.wallets.services.binance_service import BinanceService
        from decimal import Decimal

        bs = BinanceService()
        grids = MasterGridBot.objects.filter(status='ACTIVE').select_related('token')

        data = []
        for grid in grids:
            symbol = grid.token.symbol
            pair = bs._get_binance_symbol(symbol)
            if not pair:
                continue

            base_asset = pair.replace('USDT', '')

            # Open orders
            try:
                open_orders = bs.client.get_open_orders(symbol=pair)
            except:
                open_orders = []

            # All orders
            try:
                all_orders = bs.client.get_all_orders(symbol=pair, limit=50)
            except:
                all_orders = []

            # Trade history
            try:
                all_trades = bs.client.get_my_trades(symbol=pair, limit=50)
                grid_start = int(grid.created_at.timestamp() * 1000)
                trades = [t for t in all_trades if t['time'] >= grid_start]
            except:
                trades = []

            # Current holding
            holding = Decimal('0')
            try:
                account = bs.client.get_account()
                for b in account['balances']:
                    if b['asset'] == base_asset:
                        holding = Decimal(b['free'])
                        break
            except:
                pass

            current_price = grid.token.current_price
            holding_value = holding * current_price

            # Actual Binance balance = source of truth
            usdt_free = Decimal('0')
            usdt_locked = Decimal('0')
            for b in account['balances']:
                if b['asset'] == 'USDT':
                    usdt_free = Decimal(b['free'])
                    usdt_locked = Decimal(b['locked'])
                if b['asset'] == 'USDC':
                    usdt_free += Decimal(b['free'])
                    usdt_locked += Decimal(b['locked'])

            usdt_total = usdt_free + usdt_locked
            current_value = usdt_total + holding_value
            total_pnl = current_value - grid.total_amount

            # Calculate matched PNL per trade (FIFO)
            buy_queue = []
            trades_with_pnl = []

            for t in sorted(trades, key=lambda x: x['time']):
                qty = float(t['qty'])
                price = float(t['price'])
                is_buy = not t['isBuyer']

                if is_buy:
                    buy_queue.append({'qty': qty, 'price': price})
                    trades_with_pnl.append({**t, 'matched_pnl': 0})
                else:
                    sell_qty = qty
                    pnl = 0
                    while sell_qty > 0 and buy_queue:
                        buy = buy_queue[0]
                        matched = min(sell_qty, buy['qty'])
                        pnl += matched * (price - buy['price'])
                        sell_qty -= matched
                        buy['qty'] -= matched
                        if buy['qty'] <= 0:
                            buy_queue.pop(0)
                    trades_with_pnl.append({**t, 'matched_pnl': round(pnl, 4)})

            data.append({
                'symbol': symbol,
                'pair': pair,
                'invested': float(grid.total_amount),
                'current_price': float(current_price),
                'current_value': float(current_value),
                'entry_price': float(grid.price_at_creation),
                'grids': grid.grids,
                'level': grid.metadata.get('fadakka_level', ''),
                'exit_price': grid.metadata.get('exit_price', 0),
                'holding': float(holding),
                'holding_value': float(holding_value),
                'realized_pnl': 0,
                'unrealized_pnl': round(float(total_pnl), 2),
                'total_pnl': round(float(total_pnl), 2),
                'open_orders': [{
                    'order_id': str(o['orderId']),
                    'price': float(o['price']),
                    'quantity': float(o['origQty']),
                    'total': float(o['price']) * float(o['origQty']),
                    'side': o['side'],
                    'status': o['status'],
                    'time': o.get('time', 0),
                } for o in open_orders],
                'order_history': [{
                    'order_id': str(o['orderId']),
                    'price': float(o['price']),
                    'quantity': float(o['origQty']),
                    'side': o['side'],
                    'status': o['status'],
                    'time': o.get('time', 0),
                } for o in all_orders[:20]],
                'recent_trades': [{
                    'id': str(t['id']),
                    'price': float(t['price']),
                    'quantity': float(t['qty']),
                    'total': float(t['price']) * float(t['qty']),
                    'side': 'BUY' if not t['isBuyer'] else 'SELL',
                    'time': t['time'],
                    'matched_pnl': t.get('matched_pnl', 0),
                } for t in trades_with_pnl[:20]],
                'grid_config': grid.metadata.get('grid_config', {}),
            })

        return Response({'grids': data, 'count': len(data)})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], authentication_classes=[])
    def public_grid_live(self, request):
        """Public version of master grid live data - no auth required"""
        return self.master_grid_live(request)

    @action(detail=False, methods=['get'])
    def token_wallet(self, request):
        """Get user's NODE token balance"""
        from apps.tokens.services.token_service import TokenService
        from apps.tokens.models import NODEToken

        wallet, _ = NODEToken.objects.get_or_create(user=request.user, defaults={'balance': 0, 'pending_balance': 0})
        price = TokenService.get_token_price()

        return Response({
            'activated_tokens': float(wallet.balance),
            'pending_tokens': float(wallet.pending_balance),
            'token_price': float(price),
            'activated_value': float(wallet.balance * price),
            'pending_value': float(wallet.pending_balance * price),
        })





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


def sweep_webhook(request):
    from apps.tokens.services import PriceService
    PriceService.update_token_prices()

    from django.core.management import call_command
    call_command('update_pnl')

    # Record weekly closes every Sunday
    from datetime import datetime
    if datetime.utcnow().weekday() == 6:
        _record_weekly_closes()

    # Run heavy tasks in background to avoid worker timeout
    import threading
    def background_tasks():
        try:
            call_command('check_credits')
            from apps.wallets.services.treasury_controller import TreasuryController
            TreasuryController.auto_balance()

            from apps.wallets.services.binance_service import BinanceService
            bs = BinanceService()

            # Monitor grids and place sell orders for filled buys
            from apps.trading.models import MasterGridBot
            for grid in MasterGridBot.objects.filter(status='ACTIVE'):
                bs.check_and_place_sells(
                    grid.token.symbol,
                    spread_pct=grid.metadata.get('spread_pct', 1.5)
                )

            # Run Fadakka grid activation
            from apps.trading.services.fadakka_service import FadakkaService
            available = float(bs.get_usdc_balance())
            if available >= 100:
                actions = FadakkaService.scan_and_activate(available)
                for action in actions:
                    print(f"Fadakka: {action['action']} {action['symbol']} ({action.get('level', '')})")

            # Expire pending tokens daily
            from datetime import datetime
            if datetime.utcnow().hour == 0:  # Run at midnight
                call_command('expire_tokens')
        except Exception as e:
            print(f"Background task error: {e}")



    thread = threading.Thread(target=background_tasks)
    thread.start()

    return JsonResponse({'status': 'success'})


def _record_weekly_closes():
    """Save Sunday closing prices for all active tokens"""
    from apps.tokens.models import CryptoToken, WeeklyClose
    from datetime import date

    today = date.today()
    tokens = CryptoToken.objects.filter(is_active=True)
    saved = 0

    for token in tokens:
        if token.current_price > 0:
            _, created = WeeklyClose.objects.get_or_create(
                token=token,
                week_end=today,
                defaults={'close_price': token.current_price}
            )
            if created:
                saved += 1

    print(f"📊 Recorded weekly closes for {saved} coins ({today})")


@csrf_exempt
def platform_report_webhook(request):
    """Trigger daily platform report"""
    from apps.tasks.platform_report import send_daily_platform_report
    send_daily_platform_report()
    return JsonResponse({'status': 'success'})

def audit_profits_webhook(request):
    from django.core.management import call_command
    call_command('audit_grid_profits')
    return JsonResponse({'status': 'success'})




