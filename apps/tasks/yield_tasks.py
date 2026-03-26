from celery import shared_task
from datetime import datetime
from decimal import Decimal

@shared_task
def create_monthly_yield_distributions():
    """Create yield distributions for all users at the start of each month"""
    from apps.yield_earnings.services import YieldService
    
    current_month = datetime.now().strftime('%Y-%m')
    print(f"Creating yield distributions for {current_month}...")
    
    total = YieldService.create_yield_distributions_for_all_users(current_month)
    print(f"Created {total} distributions")
    return total

@shared_task
def credit_hourly_yield():
    """Credit yield distributions every hour"""
    from apps.yield_earnings.services import YieldService
    
    print("Crediting hourly yield distributions...")
    credited = YieldService.credit_yield_distributions()
    print(f"Credited {credited} distributions")
    return credited