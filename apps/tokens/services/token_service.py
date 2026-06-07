from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class TokenService:
    """Handles all NODE Token operations — awarding, activation, expiry, conversion"""

    # Token reward tiers based on tracker capital
    TRACKER_REWARDS = [
        (Decimal('10'), Decimal('49.99'), Decimal('500')),
        (Decimal('50'), Decimal('99.99'), Decimal('2500')),
        (Decimal('100'), Decimal('499.99'), Decimal('5000')),
        (Decimal('500'), Decimal('999.99'), Decimal('25000')),
        (Decimal('1000'), None, Decimal('50000')),  # None = unlimited upper
    ]

    KYC_REWARD = Decimal('100')  # Pending tokens for KYC completion
    REFERRAL_PERCENT = Decimal('0.10')  # 10% of referred user's tracker tokens

    @classmethod
    def get_or_create_wallet(cls, user):
        """Get or create a NODEToken wallet for a user"""
        from apps.tokens.models import NODEToken
        wallet, _ = NODEToken.objects.get_or_create(
            user=user,
            defaults={'balance': 0, 'pending_balance': 0, 'total_earned': 0}
        )
        return wallet

    @classmethod
    def award_tokens(cls, user, amount, source, metadata=None, auto_activate=False):
        """
        Award tokens to a user.
        - auto_activate=True: tokens are immediately activated (for tracker activations)
        - auto_activate=False: tokens are pending, expire in 60 days (for KYC, referrals, promos)
        """
        from apps.tokens.models import NODEToken, TokenTransaction

        wallet = cls.get_or_create_wallet(user)
        amount = Decimal(str(amount))

        expires_at = None
        status = 'ACTIVATED' if auto_activate else 'PENDING'

        if not auto_activate:
            expires_at = timezone.now() + timedelta(days=60)

        # Create transaction record
        txn = TokenTransaction.objects.create(
            user=user,
            amount=amount,
            source=source,
            status=status,
            expires_at=expires_at,
            activated_at=timezone.now() if auto_activate else None,
            metadata=metadata or {},
        )

        # Update wallet balances
        if auto_activate:
            wallet.balance += amount
        else:
            wallet.pending_balance += amount

        wallet.total_earned += amount
        wallet.save()

        return txn

    @classmethod
    def get_tracker_reward(cls, capital):
        """Get token reward amount based on tracker capital"""
        capital = Decimal(str(capital))
        for lower, upper, reward in cls.TRACKER_REWARDS:
            if upper is None:
                if capital >= lower:
                    return reward
            elif lower <= capital <= upper:
                return reward
        return Decimal('0')

    @classmethod
    def award_tracker_tokens(cls, user, capital):
        """Award tokens for activating a Position Tracker — auto-activated"""
        amount = cls.get_tracker_reward(capital)
        if amount > 0:
            return cls.award_tokens(
                user=user,
                amount=amount,
                source='TRACKER',
                metadata={'capital': str(capital)},
                auto_activate=True
            )
        return None

    @classmethod
    def award_kyc_tokens(cls, user):
        """Award pending tokens for completing KYC"""
        # Check if already awarded
        from apps.tokens.models import TokenTransaction
        already_awarded = TokenTransaction.objects.filter(
            user=user, source='KYC'
        ).exists()
        if already_awarded:
            return None

        return cls.award_tokens(
            user=user,
            amount=cls.KYC_REWARD,
            source='KYC',
            auto_activate=False
        )

    @classmethod
    def award_referral_tokens(cls, referrer, referred_user, referred_tracker_amount):
        """Award pending tokens to referrer (10% of referred user's tracker tokens)"""
        amount = Decimal(str(referred_tracker_amount)) * cls.REFERRAL_PERCENT
        if amount > 0:
            return cls.award_tokens(
                user=referrer,
                amount=amount,
                source='REFERRAL',
                metadata={'referred_user': referred_user.email},
                auto_activate=False
            )
        return None

    @classmethod
    def activate_pending_tokens(cls, user):
        """Activate all pending tokens for a user (called when they close a tracker + withdraw)"""
        from apps.tokens.models import TokenTransaction
        from django.utils import timezone

        now = timezone.now()
        pending_txns = TokenTransaction.objects.filter(
            user=user,
            status='PENDING',
            expires_at__gt=now  # Only activate non-expired
        )

        total_activated = Decimal('0')
        wallet = cls.get_or_create_wallet(user)

        for txn in pending_txns:
            txn.status = 'ACTIVATED'
            txn.activated_at = now
            txn.save()
            total_activated += txn.amount

        if total_activated > 0:
            wallet.pending_balance -= total_activated
            wallet.balance += total_activated
            wallet.save()

        return total_activated

    @classmethod
    def get_token_price(cls):
        """Calculate current token price based on active management fees"""
        from apps.trading.models import GridBot
        from decimal import Decimal

        TOTAL_SUPPLY = Decimal('10000000')  # 10 million

        # Sum management fees from active trackers
        active_bots = GridBot.objects.filter(status='ACTIVE')
        total_fees = Decimal('0')
        for bot in active_bots:
            # 10% management fee on activation
            total_fees += bot.amount * Decimal('0.10')

        if TOTAL_SUPPLY == 0:
            return Decimal('0.0005')  # Starting price

        price = total_fees / TOTAL_SUPPLY
        # Floor at starting price
        if price < Decimal('0.0005'):
            price = Decimal('0.0005')

        return price