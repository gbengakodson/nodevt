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
        """Distribute 100% of node fee to direct referrer only (1 level)"""
        if node_fee <= 0:
            return []

        chain = cls.get_referral_chain(user)
        distributions = []

        if chain:
            referrer = chain[0]['user']

            earning = ReferralEarning.objects.create(
                user=referrer,
                from_user=user,
                purchase=purchase,
                level=1,
                amount=node_fee
            )

            referrer_wallet, _ = Wallet.objects.get_or_create(
                user=referrer,
                wallet_type='GRAND',
                defaults={'balance': 0}
            )
            referrer_wallet.balance += node_fee
            referrer_wallet.save()

            Transaction.objects.create(
                user=referrer,
                transaction_type='REFERRAL',
                amount=node_fee,
                fee=0,
                status='COMPLETED',
                metadata={
                    'from_user': user.email,
                    'level': 1,
                    'purchase_id': str(purchase.id)
                },
                completed_at=timezone.now()
            )

            distributions.append(earning)
        else:
            # No referrer — fee goes to platform
            from django.contrib.auth import get_user_model
            User = get_user_model()
            top_user = User.objects.filter(is_superuser=True).first()

            if top_user:
                earning = ReferralEarning.objects.create(
                    user=top_user,
                    from_user=user,
                    purchase=purchase,
                    level=0,
                    amount=node_fee
                )

                top_wallet, _ = Wallet.objects.get_or_create(
                    user=top_user,
                    wallet_type='GRAND',
                    defaults={'balance': 0}
                )
                top_wallet.balance += node_fee
                top_wallet.save()

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
