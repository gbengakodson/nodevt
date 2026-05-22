from django.core.management.base import BaseCommand
from apps.trading.models import GridBot
from apps.tokens.models import CryptoToken
from decimal import Decimal


class Command(BaseCommand):
    help = 'Update PNL for all active grid bots'

    def handle(self, *args, **options):
        bots = GridBot.objects.filter(status='ACTIVE').select_related('token')
        updated = 0

        for bot in bots:
            token = bot.token
            if not token or token.current_price <= 0:
                continue

            current_price = token.current_price
            entry_price = bot.price_at_creation

            # Calculate quantity based on investment
            if entry_price > 0:
                quantity = bot.amount / entry_price
                current_value = quantity * current_price
                pnl = current_value - bot.amount
                pnl_percent = (pnl / bot.amount * 100) if bot.amount > 0 else Decimal('0')

                bot.pnl = pnl
                bot.pnl_percent = pnl_percent
                bot.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Updated PNL for {updated} bots'))