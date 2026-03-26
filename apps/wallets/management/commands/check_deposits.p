from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.wallets.services.deposit_service import DepositService
from apps.wallets.models import WalletKey

class Command(BaseCommand):
    help = 'Check for new USDC deposits for all users'
    
    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.filter(wallet_address__isnull=False)
        
        self.stdout.write(f"Checking deposits for {users.count()} users...")
        
        total_deposits = 0
        
        for user in users:
            self.stdout.write(f"\nChecking user: {user.email}")
            result = DepositService.check_user_deposits(user)
            
            if result['deposits']:
                self.stdout.write(f"  Found {len(result['deposits'])} new deposits")
                self.stdout.write(f"  Total: ${result['total_deposits']:,.2f}")
                total_deposits += len(result['deposits'])
            else:
                self.stdout.write("  No new deposits")
        
        self.stdout.write(self.style.SUCCESS(f"\nProcessed {total_deposits} new deposits"))