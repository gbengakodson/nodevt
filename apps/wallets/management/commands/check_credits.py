from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet, Transaction
from apps.wallets.services.web3_service import Web3Service
from apps.wallets.services.deposit_monitor import DepositMonitor
from apps.wallets.services.binance_service import BinanceService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check USDC balances, credit deposits, sweep to central wallet'

    def handle(self, *args, **options):
        User = get_user_model()
        web3_service = Web3Service()
        binance_service = BinanceService()

        # Step 1: BSCScan-based quick deposit check (faster for new deposits)
        self.stdout.write("Step 1: BSCScan deposit check...")
        total = DepositMonitor.check_all_users()
        self.stdout.write(f"BSCScan found ${total:.2f} in new deposits")

        # Step 2: Blockchain comparison (your existing method - more accurate)
        users = User.objects.filter(wallet_address__isnull=False)
        self.stdout.write(f"\nStep 2: Blockchain verification for {users.count()} users...")

        for user in users:
            blockchain_balance = web3_service.get_usdc_balance(user.wallet_address)
            grand_wallet, _ = Wallet.objects.get_or_create(
                user=user, wallet_type='GRAND', defaults={'balance': Decimal('0')}
            )
            database_balance = grand_wallet.balance
            diff = blockchain_balance - database_balance

            if diff > 0:
                self.stdout.write(self.style.SUCCESS(f"  {user.email}: +${diff:,.2f}"))
                grand_wallet.balance += diff
                grand_wallet.save()
                Transaction.objects.create(
                    user=user, transaction_type='DEPOSIT', amount=diff,
                    fee=Decimal('0'), status='COMPLETED',
                    metadata={'wallet_address': user.wallet_address, 'blockchain_balance': str(blockchain_balance)}
                )
            elif diff < 0:
                self.stdout.write(f"  {user.email}: spent ${abs(diff):,.2f}")

        # Step 3: Hourly yield credit
        from apps.yield_earnings.services.yield_service import YieldService
        credited = 0
        for user in User.objects.filter(is_active=True):
            try:
                amount = YieldService.credit_hourly_yield(user)
                if amount > 0: credited += 1
            except: pass
        self.stdout.write(f"\nStep 3: Yield credited to {credited} users")

        # Step 4: Sweep to central wallet (optional - enable when ready)
        # Uncomment when central wallet is set up:
        # self.stdout.write("\nStep 4: Sweeping to central wallet...")
        # from apps.wallets.models import WalletKey
        # for wk in WalletKey.objects.select_related('user').all():
        #     balance = web3_service.get_usdc_balance(wk.address)
        #     if balance > Decimal('1'):
        #         key = wk.get_private_key()
        #         result = binance_service.sweep_to_central(key, wk.address)
        #         self.stdout.write(f"  Swept ${balance:.2f} from {wk.address}")

        self.stdout.write(self.style.SUCCESS("\nDone!"))