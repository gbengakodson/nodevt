from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.referrals.models import ReferralRelationship, ReferralEarning
from apps.wallets.models import Wallet, Transaction

class ReferralService:
    # Referral distribution percentages (50% of remaining at each level)
    DISTRIBUTION_RATES = [0.5] * 7  # 50% for each of 7 generations
    
    @classmethod
    def get_referral_chain(cls, user, max_depth=7):
        """Get referral chain up to specified depth"""
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
                    'level': depth
                })
            except ReferralRelationship.DoesNotExist:
                break
                
        return chain
    
    @classmethod
    @transaction.atomic
    def distribute_node_fee(cls, user, node_fee, purchase):
        """Distribute node fee through referral network"""
        if node_fee <= 0:
            return []
        
        # Get referral chain
        chain = cls.get_referral_chain(user)
        distributions = []
        remaining_fee = node_fee
        
        # Distribute according to referral levels
        for level_info in chain:
            level = level_info['level']
            if level > 7:  # Only up to 7 generations
                break
            
            # Calculate distribution amount (50% of remaining)
            distribution_amount = remaining_fee * Decimal('0.5')
            
            # Create referral earning record
            earning = ReferralEarning.objects.create(
                user=level_info['user'],
                from_user=user,
                purchase=purchase,
                level=level,
                amount=distribution_amount
            )
            
            # Credit to user's grand wallet
            grand_wallet = Wallet.objects.get(user=level_info['user'], wallet_type='GRAND')
            grand_wallet.balance += distribution_amount
            grand_wallet.save()
            
            # Create transaction record
            Transaction.objects.create(
                user=level_info['user'],
                transaction_type='REFERRAL',
                amount=distribution_amount,
                fee=0,
                status='COMPLETED',
                metadata={
                    'from_user': user.email,
                    'level': level,
                    'purchase_id': str(purchase.id)
                },
                completed_at=timezone.now()
            )
            
            distributions.append(earning)
            remaining_fee -= distribution_amount
        
        # The remaining amount goes to the top (system owner)
        if remaining_fee > 0:
            # Get system owner (admin user with is_superuser=True)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system_owner = User.objects.filter(is_superuser=True).first()
            
            if system_owner:
                grand_wallet = Wallet.objects.get(user=system_owner, wallet_type='GRAND')
                grand_wallet.balance += remaining_fee
                grand_wallet.save()
                
                Transaction.objects.create(
                    user=system_owner,
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
        
        return distributions
    
    @classmethod
    @transaction.atomic
    def create_referral(cls, referrer, referred):
        """Create referral relationship"""
        # Check if referred user already has a referrer
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
        
        # Create relationship
        relationship = ReferralRelationship.objects.create(
            referrer=referrer,
            referred=referred,
            level=level
        )
        
        return relationship