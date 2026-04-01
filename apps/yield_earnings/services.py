from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from apps.yield_earnings.models import YieldDistribution
from apps.tokens.models import UserTokenBalance
from apps.wallets.models import Wallet, Transaction

class YieldService:
    YIELD_PERCENTAGE = Decimal('10')  # Up to 20% monthly
    DISTRIBUTIONS_PER_MONTH = 720  # Hourly distributions
    
    @classmethod
    def calculate_current_token_value(cls, token_balance):
        """Calculate current value of token holdings"""
        return token_balance.quantity * token_balance.token.current_price
    
    @classmethod
    def calculate_monthly_yield(cls, token_balance):
        """Calculate monthly yield based on CURRENT token value"""
        current_value = cls.calculate_current_token_value(token_balance)
        monthly_yield = current_value * (cls.YIELD_PERCENTAGE / Decimal('100'))
        return monthly_yield
    
    @classmethod
    def calculate_hourly_yield(cls, token_balance):
        """Calculate hourly yield based on CURRENT token value"""
        monthly_yield = cls.calculate_monthly_yield(token_balance)
        hourly_yield = monthly_yield / Decimal(str(cls.DISTRIBUTIONS_PER_MONTH))
        return hourly_yield
    
    @classmethod
    def create_yield_distributions_for_user(cls, user, month_year):
        """Create yield distributions for all tokens held by user for the month"""
        # Get all token balances with positive quantity
        token_balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)
        distributions_created = []
        
        for token_balance in token_balances:
            # Check if distributions already exist for this month
            existing = YieldDistribution.objects.filter(
                user=user,
                token_balance=token_balance,
                month_year=month_year
            ).exists()
            
            if existing:
                continue
            
            # Calculate hourly yield based on CURRENT value
            hourly_yield = cls.calculate_hourly_yield(token_balance)
            
            # Create 720 distributions for the month
            for i in range(1, cls.DISTRIBUTIONS_PER_MONTH + 1):
                distribution = YieldDistribution.objects.create(
                    user=user,
                    token_balance=token_balance,
                    amount=hourly_yield,
                    distribution_number=i,
                    month_year=month_year
                )
                distributions_created.append(distribution)
        
        return distributions_created
    
    @classmethod
    def create_yield_distributions_for_all_users(cls, month_year):
        """Create yield distributions for all users with token holdings"""
        users_with_tokens = UserTokenBalance.objects.filter(
            quantity__gt=0
        ).values_list('user', flat=True).distinct()
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        total_distributions = 0
        for user_id in users_with_tokens:
            user = User.objects.get(id=user_id)
            distributions = cls.create_yield_distributions_for_user(user, month_year)
            total_distributions += len(distributions)
        
        return total_distributions
    
    @classmethod
    @transaction.atomic
    def credit_yield_distributions(cls):
        """Credit due yield distributions to yield wallets"""
        # Get distributions that haven't been credited yet
        distributions = YieldDistribution.objects.filter(
            is_credited=False
        ).select_related('user', 'token_balance__token')
        
        credited_count = 0
        
        for distribution in distributions:
            try:
                # Recalculate yield based on CURRENT token value
                token_balance = distribution.token_balance
                
                # Skip if token balance is zero (user sold all tokens)
                if token_balance.quantity <= 0:
                    distribution.is_credited = True
                    distribution.save()
                    continue
                
                # Calculate current hourly yield
                current_hourly_yield = cls.calculate_hourly_yield(token_balance)
                
                # Use the current yield amount (not the stored one)
                amount_to_credit = current_hourly_yield
                
                # Get or create yield wallet
                yield_wallet, created = Wallet.objects.get_or_create(
                    user=distribution.user,
                    wallet_type='YIELD',
                    defaults={'balance': Decimal('0')}
                )
                
                # Credit amount to yield wallet
                yield_wallet.balance += amount_to_credit
                yield_wallet.save()
                
                # Create transaction record
                Transaction.objects.create(
                    user=distribution.user,
                    transaction_type='YIELD',
                    amount=amount_to_credit,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    metadata={
                        'token_symbol': token_balance.token.symbol,
                        'distribution_number': distribution.distribution_number,
                        'month_year': distribution.month_year,
                        'token_quantity': str(token_balance.quantity),
                        'token_price': str(token_balance.token.current_price),
                        'token_value': str(cls.calculate_current_token_value(token_balance))
                    },
                    completed_at=timezone.now()
                )
                
                # Mark as credited
                distribution.is_credited = True
                distribution.credited_at = timezone.now()
                distribution.amount = amount_to_credit  # Update to actual amount credited
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
        yield_wallet.balance -= amount
        yield_wallet.save()
        grand_wallet.balance += amount
        grand_wallet.save()
        
        # Create transaction record
        transaction_obj = Transaction.objects.create(
            user=user,
            transaction_type='WITHDRAWAL',
            amount=amount,
            fee=Decimal('0'),
            status='COMPLETED',
            metadata={'from_wallet': 'YIELD', 'to_wallet': 'GRAND'},
            completed_at=timezone.now()
        )
        
        return transaction_obj
    
    @classmethod
    def get_user_yield_summary(cls, user):
        """Get yield summary for a user"""
        # Get total yield earned (credited)
        total_credited = Transaction.objects.filter(
            user=user,
            transaction_type='YIELD'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        # Get current yield wallet balance
        try:
            yield_wallet = Wallet.objects.get(user=user, wallet_type='YIELD')
            current_balance = yield_wallet.balance
        except Wallet.DoesNotExist:
            current_balance = Decimal('0')
        
        # Get pending distributions
        pending_distributions = YieldDistribution.objects.filter(
            user=user,
            is_credited=False
        ).count()
        
        # Get current token holdings and their yield potential
        token_balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)
        current_monthly_yield = Decimal('0')
        
        for tb in token_balances:
            current_monthly_yield += cls.calculate_monthly_yield(tb)
        
        return {
            'total_yield_earned': total_credited,
            'current_yield_balance': current_balance,
            'pending_distributions': pending_distributions,
            'current_monthly_yield_rate': current_monthly_yield,
            'hourly_yield_rate': current_monthly_yield / Decimal(str(cls.DISTRIBUTIONS_PER_MONTH))
        }