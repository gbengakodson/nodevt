from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet, Transaction
from apps.wallets.services.web3_service import Web3Service
from decimal import Decimal

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
            balance = web3_service.get_usdc_balance(user.wallet_address)
            self.stdout.write(f"  Blockchain balance: ${balance:,.2f}")
            
            # Get recorded balance from database
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
            self.stdout.write(f"  Database balance: ${grand_wallet.balance:,.2f}")
            
            # Calculate difference
            diff = balance - grand_wallet.balance
            
            if diff > 0:
                self.stdout.write(self.style.SUCCESS(f"  New deposit found: ${diff:,.2f}"))
                
                # Credit to user's grand wallet
                grand_wallet.balance = balance
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
                        'blockchain_balance': str(balance),
                        'previous_balance': str(grand_wallet.balance - diff)
                    }
                )
                self.stdout.write(f"  Credited ${diff:,.2f} to {user.email}")
            elif diff < 0:
                self.stdout.write(self.style.WARNING(f"  Negative difference? ${diff:,.2f}"))
            else:
                self.stdout.write("  No new deposits")
        
        self.stdout.write(self.style.SUCCESS("\nDone!"))