from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.referrals.models import ReferralRelationship, ReferralEarning
from apps.wallets.models import Wallet, Transaction
from apps.core.notifications import notify_user


class ReferralService:

    @classmethod
    def get_referral_chain(cls, user, max_depth=3):
        """Get referral chain from bottom (buyer) up to top (7 generations)"""
        chain = []
        current_user = user
        depth = 0

        while current_user and depth < max_depth:
            try:
                referral_rel = ReferralRelationship.objects.select_related('referrer').get(referred=current_user)
                current_user = referral_rel.referrer
                depth += 1
                chain.append({
                    'user': current_user,
                    'level': depth  # 1 = direct referrer (6th gen from buyer), 7 = top
                })
            except ReferralRelationship.DoesNotExist:
                break

        return chain

    @classmethod
    @transaction.atomic
    def distribute_node_fee(cls, user, node_fee, purchase):
        """Split 10% management fee across up to 3 referral levels using half-of-remaining rule.
        Remainder goes to platform admin."""
        if node_fee <= 0:
            return []

        distributions = []
        remaining = node_fee
        chain = cls.get_referral_chain(user, max_depth=3)

        for level_info in chain[:3]:
            # Special case: soludero gets 100% of node fee from direct referrals
            if referrer.email == 'soludero2017@gmail.com' and level_info['level'] == 1:
                share = remaining  # 100% of the remaining fee
            else:
                share = remaining * Decimal('0.5')
            if share <= 0:
                break

            referrer = level_info['user']

            # Sweep to referrer's real wallet
            from apps.wallets.models import WalletKey
            from apps.trading.views import TradingViewSet
            from django.conf import settings

            try:
                wallet_key = WalletKey.objects.get(user=referrer)
                sweep_result = TradingViewSet._sweep_from_user_wallet(
                    settings.CENTRAL_WALLET_ADDRESS,
                    settings.CENTRAL_WALLET_PRIVATE_KEY,
                    wallet_key.address,
                    share
                )
                if sweep_result.get('success'):
                    # Record earning only if sweep succeeded
                    earning = ReferralEarning.objects.create(
                        user=referrer,
                        from_user=user,
                        purchase=purchase,
                        level=level_info['level'],
                        amount=share
                    )
                    Transaction.objects.create(
                        user=referrer,
                        transaction_type='REFERRAL',
                        amount=share,
                        fee=0,
                        status='COMPLETED',
                        tx_hash=sweep_result.get('tx_hash', ''),
                        metadata={
                            'from_user': user.email,
                            'level': level_info['level'],
                            'purchase_id': str(purchase.id)
                        },
                        completed_at=timezone.now()
                    )
                    distributions.append(earning)
                    # Award NODE tokens to referrer (pending, 10% of referred user's tracker tokens)
                    from apps.tokens.services.token_service import TokenService
                    tracker_tokens = TokenService.get_tracker_reward(purchase.total_amount)
                    if tracker_tokens > 0:
                        TokenService.award_referral_tokens(referrer, user, tracker_tokens)
            except WalletKey.DoesNotExist:
                pass  # Skip if referrer has no wallet yet

            remaining -= share

        # Remainder goes to platform admin
        if remaining > 0:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin = User.objects.filter(is_superuser=True).first()
            if admin:
                earning = ReferralEarning.objects.create(
                    user=admin,
                    from_user=user,
                    purchase=purchase,
                    level=0,
                    amount=remaining
                )
                distributions.append(earning)

        return distributions


    @classmethod
    @transaction.atomic
    def create_referral(cls, referrer, referred):
        """Create referral relationship (1 level only)"""
        if ReferralRelationship.objects.filter(referred=referred).exists():
            raise ValueError("User already has a referrer")

        relationship = ReferralRelationship.objects.create(
            referrer=referrer,
            referred=referred,
            level=1
        )
        return relationship
