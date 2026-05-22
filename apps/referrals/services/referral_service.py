from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.referrals.models import ReferralRelationship, ReferralEarning
from apps.wallets.models import Wallet, Transaction
from apps.core.notifications import notify_user


class ReferralService:

    @classmethod
    def get_referral_chain(cls, user, max_depth=1):
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
        """Split node fee: 50% swept to referrer's real wallet, 50% stays in NODE Web3"""
        if node_fee <= 0:
            return []

        distributions = []
        referrer_share = node_fee * Decimal('0.5')
        platform_share = node_fee - referrer_share

        chain = cls.get_referral_chain(user)

        # 50% to direct referrer - sweep to their real wallet
        if chain:
            referrer = chain[0]['user']

            # Get referrer's wallet address
            from apps.wallets.models import WalletKey
            try:
                wallet_key = WalletKey.objects.get(user=referrer)
                referrer_address = wallet_key.address
            except WalletKey.DoesNotExist:
                referrer_address = None

            if referrer_address:
                # Sweep from NODE Web3 to referrer's wallet
                from django.conf import settings
                from apps.trading.views import TradingViewSet
                sweep_result = TradingViewSet._sweep_from_user_wallet(
                    settings.CENTRAL_WALLET_ADDRESS,
                    settings.CENTRAL_WALLET_PRIVATE_KEY,
                    referrer_address,
                    referrer_share
                )

                if sweep_result['success']:
                    earning = ReferralEarning.objects.create(
                        user=referrer, from_user=user, purchase=purchase,
                        level=1, amount=referrer_share
                    )

                    Transaction.objects.create(
                        user=referrer, transaction_type='REFERRAL',
                        amount=referrer_share, fee=0, status='COMPLETED',
                        tx_hash=sweep_result.get('tx_hash', ''),
                        metadata={
                            'from_user': user.email, 'level': 1,
                            'purchase_id': str(purchase.id),
                            'to_address': referrer_address
                        },
                        completed_at=timezone.now()
                    )
                    distributions.append(earning)

                    # After distributions.append(earning)
                    notify_user(
                        referrer,
                        '🤝 Referral Commission',
                        f'${float(referrer_share):.2f} earned from a new activation and sent to your wallet.',
                        'PORTFOLIO'
                    )

        # 50% stays in NODE Web3 - track for admin dashboard
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).first()
        if admin and platform_share > 0:
            earning = ReferralEarning.objects.create(
                user=admin, from_user=user, purchase=purchase,
                level=0, amount=platform_share
            )

            Transaction.objects.create(
                user=admin, transaction_type='PLATFORM_FEE',
                amount=platform_share, fee=0, status='COMPLETED',
                metadata={
                    'from_user': user.email,
                    'purchase_id': str(purchase.id),
                    'source': 'node_fee_share'
                },
                completed_at=timezone.now()
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
