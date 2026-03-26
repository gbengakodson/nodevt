from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction
from apps.tokens.models import CryptoToken, UserTokenBalance, Purchase
from apps.referrals.services.referral_service import ReferralService


class TradingService:
    NODE_FEE_PERCENTAGE = Decimal('10')  # 10%

    @classmethod
    @transaction.atomic
    def purchase_tokens(cls, user, token_id, amount_usdc):
        """Purchase tokens using USDC from grand balance"""
        try:
            token = CryptoToken.objects.get(id=token_id, is_active=True)
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')

            # Check sufficient balance
            if grand_wallet.balance < amount_usdc:
                raise ValueError("Insufficient balance in grand wallet")

            # Calculate token quantity
            token_quantity = amount_usdc / token.current_price

            # Calculate node fee
            node_fee = amount_usdc * (cls.NODE_FEE_PERCENTAGE / Decimal('100'))
            net_amount = amount_usdc - node_fee

            # Create purchase record
            purchase = Purchase.objects.create(
                user=user,
                token=token,
                quantity=token_quantity,
                price_per_token=token.current_price,
                total_amount=amount_usdc,
                node_fee=node_fee
            )

            # Deduct from grand wallet
            grand_wallet.subtract_balance(amount_usdc)

            # Create transaction record
            transaction_obj = Transaction.objects.create(
                user=user,
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

            # Update or create user token balance
            user_token_balance, created = UserTokenBalance.objects.get_or_create(
                user=user,
                token=token,
                defaults={'quantity': 0, 'average_buy_price': 0}
            )
            user_token_balance.add_tokens(token_quantity, token.current_price)

            # Distribute node fee through referral system
            if node_fee > 0:
                ReferralService.distribute_node_fee(user, node_fee, purchase)

            return {
                'success': True,
                'purchase': purchase,
                'transaction': transaction_obj,
                'token_quantity': token_quantity,
                'node_fee': node_fee
            }

        except Exception as e:
            raise Exception(f"Purchase failed: {str(e)}")

    @classmethod
    @transaction.atomic
    def sell_tokens(cls, user, token_id, quantity):
        """Sell tokens only if current price >= average buy price"""
        try:
            token = CryptoToken.objects.get(id=token_id, is_active=True)
            user_token_balance = UserTokenBalance.objects.get(user=user, token=token)

            # Check if user has enough tokens
            if user_token_balance.quantity < quantity:
                raise ValueError("Insufficient token balance")

            # Check selling condition: current price >= average buy price
            if token.current_price < user_token_balance.average_buy_price:
                raise ValueError("Cannot sell: Current price is below purchase price")

            # Calculate total sale amount
            sale_amount = quantity * token.current_price

            # Get grand wallet
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')

            # Add to grand wallet
            grand_wallet.add_balance(sale_amount)

            # Remove tokens from user's balance
            user_token_balance.remove_tokens(quantity)

            # Create transaction record
            transaction_obj = Transaction.objects.create(
                user=user,
                transaction_type='SALE',
                amount=sale_amount,
                fee=0,
                status='COMPLETED',
                metadata={
                    'token_id': str(token.id),
                    'token_symbol': token.symbol,
                    'quantity': str(quantity),
                    'price': str(token.current_price),
                    'average_buy_price': str(user_token_balance.average_buy_price)
                },
                completed_at=timezone.now()
            )

            return {
                'success': True,
                'transaction': transaction_obj,
                'sale_amount': sale_amount,
                'remaining_quantity': user_token_balance.quantity
            }

        except Exception as e:
            raise Exception(f"Sale failed: {str(e)}")