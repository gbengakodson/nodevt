from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.referrals.models import ReferralRelationship, ReferralEarning
from apps.wallets.models import Wallet, Transaction


class ReferralService:

    @classmethod
    def get_referral_chain(cls, user, max_depth=7):
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
        """Distribute node fee: 50% of remaining to each level, top gets final 50%"""
        if node_fee <= 0:
            return []

        # Get referral chain (from bottom to top)
        chain = cls.get_referral_chain(user)
        distributions = []

        # Calculate total generations (including top if not in chain)
        total_generations = len(chain)

        # Start with full node fee
        remaining_fee = node_fee

        # Distribute to each level in the chain (50% of remaining)
        for level_info in chain:
            distribution_amount = remaining_fee * Decimal('0.5')  # 50% of remaining

            if distribution_amount > 0:
                # Create referral earning record
                earning = ReferralEarning.objects.create(
                    user=level_info['user'],
                    from_user=user,
                    purchase=purchase,
                    level=level_info['level'],
                    amount=distribution_amount
                )

                # Credit to referrer's grand wallet
                referrer_wallet, _ = Wallet.objects.get_or_create(
                    user=level_info['user'],
                    wallet_type='GRAND',
                    defaults={'balance': 0}
                )
                referrer_wallet.balance += distribution_amount
                referrer_wallet.save()

                # Create transaction record
                Transaction.objects.create(
                    user=level_info['user'],
                    transaction_type='REFERRAL',
                    amount=distribution_amount,
                    fee=0,
                    status='COMPLETED',
                    metadata={
                        'from_user': user.email,
                        'level': level_info['level'],
                        'purchase_id': str(purchase.id)
                    },
                    completed_at=timezone.now()
                )

                distributions.append(earning)

            # Reduce remaining fee
            remaining_fee -= distribution_amount

        # The final remaining fee goes to the top (platform owner)
        if remaining_fee > 0:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            top_user = User.objects.filter(is_superuser=True).first()

            if top_user:
                # Create earning for top user
                earning = ReferralEarning.objects.create(
                    user=top_user,
                    from_user=user,
                    purchase=purchase,
                    level=7,  # Top level
                    amount=remaining_fee
                )

                # Credit to top user's grand wallet
                top_wallet, _ = Wallet.objects.get_or_create(
                    user=top_user,
                    wallet_type='GRAND',
                    defaults={'balance': 0}
                )
                top_wallet.balance += remaining_fee
                top_wallet.save()

                # Create transaction record
                Transaction.objects.create(
                    user=top_user,
                    transaction_type='REFERRAL',
                    amount=remaining_fee,
                    fee=0,
                    status='COMPLETED',
                    metadata={
                        'from_user': user.email,
                        'level': 'TOP',
                        'purchase_id': str(purchase.id)
                    },
                    completed_at=timezone.now()
                )

                distributions.append(earning)

        return distributions

    @classmethod
    @transaction.atomic
    def create_referral(cls, referrer, referred):
        """Create referral relationship"""
        if ReferralRelationship.objects.filter(referred=referred).exists():
            raise ValueError("User already has a referrer")

        # Get the level of the referrer
        level = 1
        current = referrer

        while current:
            try:
                parent_rel = ReferralRelationship.objects.get(referred=current)
                current = parent_rel.referrer
                level += 1
            except ReferralRelationship.DoesNotExist:
                break

        if level > 7:
            raise ValueError("Cannot refer beyond 7 generations")

        relationship = ReferralRelationship.objects.create(
            referrer=referrer,
            referred=referred,
            level=level
        )

        return relationship