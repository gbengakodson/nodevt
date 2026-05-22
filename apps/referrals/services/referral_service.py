from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.referrals.models import ReferralRelationship, ReferralEarning
from apps.wallets.models import Wallet, Transaction


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
        """Split node fee: 50% to direct referrer, 50% to platform"""
        if node_fee <= 0:
            return []

        distributions = []
        referrer_share = node_fee * Decimal('0.5')
        platform_share = node_fee - referrer_share

        chain = cls.get_referral_chain(user)

        # 50% to direct referrer
        if chain:
            referrer = chain[0]['user']
            earning = ReferralEarning.objects.create(
                user=referrer, from_user=user, purchase=purchase,
                level=1, amount=referrer_share
            )
            referrer_wallet, _ = Wallet.objects.get_or_create(
                user=referrer, wallet_type='GRAND', defaults={'balance': 0}
            )
            referrer_wallet.balance += referrer_share
            referrer_wallet.save()
            Transaction.objects.create(
                user=referrer, transaction_type='REFERRAL',
                amount=referrer_share, fee=0, status='COMPLETED',
                metadata={'from_user': user.email, 'level': 1, 'purchase_id': str(purchase.id)},
                completed_at=timezone.now()
            )
            distributions.append(earning)

        # 50% to platform admin
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).first()
        if admin and platform_share > 0:
            earning = ReferralEarning.objects.create(
                user=admin, from_user=user, purchase=purchase,
                level=0, amount=platform_share
            )
            admin_wallet, _ = Wallet.objects.get_or_create(
                user=admin, wallet_type='GRAND', defaults={'balance': 0}
            )
            admin_wallet.balance += platform_share
            admin_wallet.save()
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
