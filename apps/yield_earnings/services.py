from decimal import Decimal
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction


class YieldService:
    HOURLY_RATE = Decimal('0.0001388888888888889')  # 10% / 720 = 0.0001388889

    @classmethod
    def credit_hourly_yield(cls, user):
        """Credit hourly yield based on current portfolio value"""
        # Get user's total portfolio value
        holdings = user.token_balances.filter(quantity__gt=0)
        total_value = sum(h.quantity * h.token.current_price for h in holdings)

        if total_value <= 0:
            return 0

        # Calculate hourly yield
        hourly_yield = total_value * cls.HOURLY_RATE

        # Credit to yield wallet
        yield_wallet, _ = Wallet.objects.get_or_create(
            user=user,
            wallet_type='YIELD',
            defaults={'balance': 0}
        )
        yield_wallet.balance += hourly_yield
        yield_wallet.save()

        # Record transaction
        Transaction.objects.create(
            user=user,
            transaction_type='YIELD',
            amount=hourly_yield,
            fee=0,
            status='COMPLETED',
            metadata={'type': 'hourly_yield', 'portfolio_value': str(total_value)},
            completed_at=timezone.now()
        )

        return hourly_yield