from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from apps.tokens.models import UserTokenBalance
from apps.wallets.models import Wallet, Transaction


class Command(BaseCommand):
    help = 'Check and execute automatic take profit at 20% gain'

    def handle(self, *args, **options):
        # Get all token balances with quantity > 0
        balances = UserTokenBalance.objects.filter(quantity__gt=0)
        triggered_count = 0

        self.stdout.write(f"Checking {balances.count()} positions for 20% take profit...")

        for balance in balances:
            current_price = balance.token.current_price
            avg_price = balance.average_buy_price

            if avg_price <= 0:
                continue

            # Calculate gain percentage
            gain_percent = ((current_price - avg_price) / avg_price) * 100

            # Check if gain reached 20%
            if gain_percent >= 20:
                self.stdout.write(f"\n🔔 Take profit triggered for {balance.user.email} - {balance.token.symbol}")
                self.stdout.write(f"   Purchase price: ${avg_price}")
                self.stdout.write(f"   Current price: ${current_price}")
                self.stdout.write(f"   Gain: {gain_percent:.2f}%")

                # Execute sell of ALL tokens
                quantity_to_sell = balance.quantity
                sale_amount = quantity_to_sell * current_price

                # Get grand wallet
                grand_wallet = Wallet.objects.get(user=balance.user, wallet_type='GRAND')

                # Add to grand wallet
                grand_wallet.balance += sale_amount
                grand_wallet.save()

                # Remove tokens from balance
                balance.quantity = 0
                balance.save()

                # Create transaction record
                Transaction.objects.create(
                    user=balance.user,
                    transaction_type='SALE',
                    amount=sale_amount,
                    fee=0,
                    status='COMPLETED',
                    metadata={
                        'token_id': str(balance.token.id),
                        'token_symbol': balance.token.symbol,
                        'quantity': str(quantity_to_sell),
                        'price': str(current_price),
                        'average_buy_price': str(avg_price),
                        'type': 'AUTO_TAKE_PROFIT',
                        'gain_percent': str(gain_percent)
                    },
                    completed_at=timezone.now()
                )

                triggered_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Sold {quantity_to_sell} {balance.token.symbol} for ${sale_amount}"))

        if triggered_count == 0:
            self.stdout.write(self.style.SUCCESS("No take profit triggers found."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Take profit executed for {triggered_count} position(s)"))