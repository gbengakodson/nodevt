from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.services.deposit_monitor import DepositMonitor
from apps.yield_earnings.services.yield_service import YieldService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-detect new deposits by tx_hash and credit yield (no double credits)'

    def handle(self, *args, **options):
        User = get_user_model()

        # Step 1: Detect NEW deposits by tx_hash (never credits same deposit twice)
        self.stdout.write("Checking for new deposits (by tx_hash)...")
        total = DepositMonitor.check_all_users()
        self.stdout.write(self.style.SUCCESS(f"Credited ${total:.2f} in new deposits"))

        # Step 2: Credit hourly yield
        self.stdout.write("Crediting hourly yield...")
        credited = 0
        for user in User.objects.filter(is_active=True):
            try:
                amount = YieldService.credit_hourly_yield(user)
                if amount > 0:
                    credited += 1
            except Exception as e:
                logger.warning(f"Yield error for {user.email}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Yield credited to {credited} users"))
        self.stdout.write(self.style.SUCCESS("Done!"))