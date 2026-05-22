from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.services.deposit_monitor import DepositMonitor
from apps.yield_earnings.services.yield_service import YieldService
from apps.wallets.models import Purse, Wallet
from apps.trading.models import GridBot
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-detect deposits, credit yield, auto-sweep to purses'

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

        # Step 3: Auto-sweep grid profits to purses
        self.stdout.write("Step 3: Auto-sweeping to purses...")
        swept = self.auto_sweep_to_purses()
        self.stdout.write(self.style.SUCCESS(f"  Swept to {swept} purses"))

        # Step 4: Sweep to central wallet
        self.stdout.write("Step 4: Sweeping to central wallet...")
        from django.core.management import call_command
        call_command('sweep_to_central')

        # Step 5: Pension auto-reinvest
        self.stdout.write("Step 5: Checking pension reinvestments...")
        reinvested = self.process_pension_reinvest()
        self.stdout.write(self.style.SUCCESS(f"  Pension reinvested for {reinvested} users"))

        self.stdout.write(self.style.SUCCESS("Done!"))



    def auto_sweep_to_purses(self):
        """Divert configured % of grid profit to user purses as grid earns"""
        swept_count = 0
        now = timezone.now()

        active_purses = Purse.objects.filter(
            auto_sweep_enabled=True,
            is_active=True
        ).select_related('user')

        for purse in active_purses:
            try:
                user = purse.user

                # Check sweep schedule
                should_sweep = False
                if purse.sweep_schedule == 'daily':
                    should_sweep = True
                elif purse.sweep_schedule == 'weekly':
                    should_sweep = now.weekday() == 0
                elif purse.sweep_schedule == 'monthly':
                    should_sweep = now.day == 1

                if not should_sweep:
                    continue

                # Get active grid bots for this user
                bots = GridBot.objects.filter(user=user, status='ACTIVE')
                if not bots.exists():
                    continue

                total_swept = Decimal('0')
                for bot in bots:
                    if bot.grid_profit <= 0:
                        continue

                    # Calculate sweep amount based on configured %
                    sweep_amount = bot.grid_profit * (Decimal(str(purse.sweep_percentage)) / Decimal('100'))

                    if sweep_amount <= 0:
                        continue

                    # Move from grid profit to purse
                    bot.grid_profit -= sweep_amount
                    bot.save()

                    purse.balance += sweep_amount
                    total_swept += sweep_amount

                if total_swept > 0:
                    purse.save()
                    swept_count += 1
                    print(f"  💰 Swept ${total_swept:.4f} from grid profits to {user.email}'s {purse.name} purse")

            except Exception as e:
                print(f"  Error sweeping purse {purse.name} for {purse.user.email}: {e}")
                continue

        return swept_count



    def process_pension_reinvest(self):
        """Auto-reinvest pension funds every 6 months"""
        reinvested = 0
        now = timezone.now()

        pension_wallets = Wallet.objects.filter(
            wallet_type='YIELD',
            pension_fund=True,
            lock_enabled=True
        ).select_related('user')

        for wallet in pension_wallets:
            try:
                # Check if it's time to reinvest (6 months since last reinvest)
                # We track this by checking if the wallet was created/updated 6 months ago
                six_months_ago = now - timedelta(days=180)

                # Check if there was a recent pension reinvest transaction
                from apps.wallets.models import Transaction
                last_reinvest = Transaction.objects.filter(
                    user=wallet.user,
                    transaction_type='PENSION_REINVEST',
                    created_at__gte=six_months_ago
                ).first()

                if last_reinvest:
                    continue  # Already reinvested within 6 months

                if wallet.balance <= 0:
                    continue

                # Create a new Grid Bot with the yield wallet balance
                # Use the first available token (BTC)
                from apps.tokens.models import CryptoToken
                token = CryptoToken.objects.filter(symbol='BTC', is_active=True).first()
                if not token:
                    continue

                amount = wallet.balance

                # Create grid bot
                upper_price = token.current_price * Decimal('1.8')
                lower_price = token.current_price * Decimal('0.2')

                GridBot.objects.create(
                    user=wallet.user,
                    token=token,
                    amount=amount,
                    lower_price=lower_price,
                    upper_price=upper_price,
                    grids=100,
                    status='ACTIVE',
                    grid_profit=Decimal('0'),
                    price_at_creation=token.current_price,
                    created_at=timezone.now()
                )

                # Record the reinvestment
                Transaction.objects.create(
                    user=wallet.user,
                    transaction_type='PENSION_REINVEST',
                    amount=amount,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    metadata={'source': 'pension_auto_reinvest', 'token': 'BTC'},
                    completed_at=timezone.now()
                )

                # Reset yield wallet balance
                wallet.balance = Decimal('0')
                wallet.save()

                reinvested += 1
                print(f"  Pension reinvested ${amount:.2f} for {wallet.user.email}")

            except Exception as e:
                print(f"  Pension reinvest error for {wallet.user.email}: {e}")
                continue

        return reinvested