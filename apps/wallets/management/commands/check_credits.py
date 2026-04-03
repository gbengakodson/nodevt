from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet, Transaction
from apps.wallets.services.web3_service import Web3Service
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check USDC balances and credit deposits'

    def handle(self, *args, **options):
        User = get_user_model()
        web3_service = Web3Service()

        # Get all users with wallet addresses
        users = User.objects.filter(wallet_address__isnull=False)

        self.stdout.write(f"Checking {users.count()} users...")

        for user in users:
            self.stdout.write(f"\nChecking {user.email}")

            # Get current balance from blockchain
            blockchain_balance = web3_service.get_usdc_balance(user.wallet_address)
            self.stdout.write(f"  Blockchain balance: ${blockchain_balance:,.2f}")

            # Get recorded balance from database
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
            database_balance = grand_wallet.balance
            self.stdout.write(f"  Database balance: ${database_balance:,.2f}")

            # Calculate difference
            diff = blockchain_balance - database_balance

            if diff > 0:
                self.stdout.write(self.style.SUCCESS(f"  New deposit found: ${diff:,.2f}"))

                # Add ONLY the new deposit to user's grand wallet
                grand_wallet.balance += diff
                grand_wallet.save()

                # Record transaction
                Transaction.objects.create(
                    user=user,
                    transaction_type='DEPOSIT',
                    amount=diff,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    metadata={
                        'wallet_address': user.wallet_address,
                        'blockchain_balance': str(blockchain_balance),
                        'previous_balance': str(database_balance),
                        'new_balance': str(grand_wallet.balance)
                    }
                )
                self.stdout.write(f"  Credited ${diff:,.2f} to {user.email}")
            elif diff < 0:
                # User spent money (bought tokens) - do nothing, just log
                self.stdout.write(f"  User spent ${abs(diff):,.2f} on purchases - balance unchanged")
            else:
                self.stdout.write("  No new deposits")

        self.stdout.write(self.style.SUCCESS("\nDone!"))