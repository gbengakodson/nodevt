from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.services.deposit_monitor import DepositMonitor
from apps.yield_earnings.services.yield_service import YieldService
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-detect deposits, credit yield, sweep to central wallet'

    def handle(self, *args, **options):
        User = get_user_model()

        # Step 1: Detect NEW deposits by tx_hash
        self.stdout.write("Step 1: Checking deposits...")
        total = DepositMonitor.check_all_users()
        self.stdout.write(self.style.SUCCESS(f"  Deposits: ${total:.2f}"))

        # Step 2: Credit hourly yield
        self.stdout.write("Step 2: Crediting yield...")
        credited = 0
        for user in User.objects.filter(is_active=True):
            try:
                amount = YieldService.credit_hourly_yield(user)
                if amount > 0:
                    credited += 1
            except Exception as e:
                logger.warning(f"Yield error for {user.email}: {e}")
        self.stdout.write(self.style.SUCCESS(f"  Yield credited to {credited} users"))

        # Step 3: Sweep to central wallet
        self.stdout.write("Step 3: Sweeping to central wallet...")
        call_command('sweep_to_central')

        self.stdout.write(self.style.SUCCESS("Done!"))