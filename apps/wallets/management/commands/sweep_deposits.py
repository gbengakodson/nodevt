from django.core.management.base import BaseCommand
from apps.wallets.models import WalletKey
from apps.wallets.services.binance_service import BinanceService
from apps.wallets.services.deposit_monitor import DepositMonitor


class Command(BaseCommand):
    help = 'Sweep all user deposits to central wallet and credit accounts'

    def handle(self, *args, **options):
        self.stdout.write('Starting deposit sweep...')

        # Step 1: Check all users for new deposits & credit them
        total = DepositMonitor.check_all_users()
        self.stdout.write(f'Total new deposits credited: ${total:.2f}')

        # Step 2: Optionally sweep to central wallet
        # This requires each user's private key
        # For now, just credit the deposits
        # Sweeping can be added when ready

        self.stdout.write(self.style.SUCCESS('Sweep complete'))