from celery import shared_task
from django.utils import timezone
from datetime import datetime
from .services.yield_service import YieldService
from apps.tokens.models import UserTokenBalance
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task
def create_monthly_yield_distributions():
    """Create yield distributions for all users at the start of each month"""
    current_month = timezone.now().strftime('%Y-%m')
    users = User.objects.filter(is_active=True)

    for user in users:
        try:
            YieldService.create_yield_distributions(user, current_month)
        except Exception as e:
            print(f"Error creating distributions for {user.email}: {str(e)}")

    return f"Created distributions for {users.count()} users"


@shared_task
def credit_hourly_yield():
    """Credit yield distributions every hour"""
    credited = YieldService.credit_yield_distributions()
    return f"Credited {credited} distributions"


@shared_task
def update_token_prices():
    """Update token prices from external API"""
    # This would integrate with a price feed API like CoinGecko, Binance, etc.
    # Implement your price update logic here
    pass