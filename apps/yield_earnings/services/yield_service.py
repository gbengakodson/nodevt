from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from apps.yield_earnings.models import YieldDistribution
from apps.tokens.models import UserTokenBalance
from apps.wallets.models import Wallet, Transaction


class YieldService:
    YIELD_PERCENTAGE = Decimal('20')  # 20% monthly
    DISTRIBUTIONS_PER_MONTH = 720  # Hourly distributions

    @classmethod
    def calculate_monthly_yield(cls, token_balance):
        """Calculate monthly yield for a token balance"""
        token_value = token_balance.current_value
        monthly_yield = token_value * (cls.YIELD_PERCENTAGE / Decimal('100'))
        return monthly_yield

    @classmethod
    def calculate_hourly_yield(cls, token_balance):
        """Calculate hourly yield for a token balance"""
        monthly_yield = cls.calculate_monthly_yield(token_balance)
        hourly_yield = monthly_yield / Decimal(str(cls.DISTRIBUTIONS_PER_MONTH))
        return hourly_yield

    @classmethod
    @transaction.atomic
    def create_yield_distributions(cls, user, month_year):
        """Create yield distributions for a user for the entire month"""
        token_balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)
        distributions = []

        for token_balance in token_balances:
            hourly_yield = cls.calculate_hourly_yield(token_balance)

            # Check if distributions already exist for this month
            existing = YieldDistribution.objects.filter(
                user=user,
                token_balance=token_balance,
                month_year=month_year
            ).exists()

            if existing:
                continue

            # Create 720 distributions
            for i in range(1, cls.DISTRIBUTIONS_PER_MONTH + 1):
                distribution = YieldDistribution.objects.create(
                    user=user,
                    token_balance=token_balance,
                    amount=hourly_yield,
                    distribution_number=i,
                    month_year=month_year
                )
                distributions.append(distribution)

        return distributions

    @classmethod
    @transaction.atomic
    def credit_yield_distributions(cls):
        """Credit due yield distributions to yield wallets"""
        # Get distributions that haven't been credited yet
        distributions = YieldDistribution.objects.filter(
            is_credited=False,
            created_at__lte=timezone.now()
        )

        credited_count = 0
        for distribution in distributions:
            try:
                # Get or create yield wallet
                yield_wallet, created = Wallet.objects.get_or_create(
                    user=distribution.user,
                    wallet_type='YIELD',
                    defaults={'balance': 0}
                )

                # Credit amount to yield wallet
                yield_wallet.add_balance(distribution.amount)

                # Create transaction record
                Transaction.objects.create(
                    user=distribution.user,
                    transaction_type='YIELD',
                    amount=distribution.amount,
                    fee=0,
                    status='COMPLETED',
                    metadata={
                        'token_symbol': distribution.token_balance.token.symbol,
                        'distribution_number': distribution.distribution_number,
                        'month_year': distribution.month_year
                    },
                    completed_at=timezone.now()
                )

                # Mark as credited
                distribution.is_credited = True
                distribution.credited_at = timezone.now()
                distribution.save()

                credited_count += 1

            except Exception as e:
                print(f"Error crediting distribution {distribution.id}: {str(e)}")
                continue

        return credited_count

    @classmethod
    @transaction.atomic
    def withdraw_yield_to_grand(cls, user, amount):
        """Withdraw yield from yield wallet to grand wallet"""
        yield_wallet = Wallet.objects.get(user=user, wallet_type='YIELD')
        grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')

        if yield_wallet.balance < amount:
            raise ValueError("Insufficient yield balance")

        # Transfer from yield to grand
        yield_wallet.subtract_balance(amount)
        grand_wallet.add_balance(amount)

        # Create transaction record
        transaction_obj = Transaction.objects.create(
            user=user,
            transaction_type='WITHDRAWAL',
            amount=amount,
            fee=0,
            status='COMPLETED',
            metadata={'from_wallet': 'YIELD', 'to_wallet': 'GRAND'},
            completed_at=timezone.now()
        )

        return transaction_obj