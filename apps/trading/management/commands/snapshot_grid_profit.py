from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.trading.models import GridBot


class Command(BaseCommand):
    help = (
        'Nightly snapshot of grid_profit on all active bots. '
        'Stores yesterday\'s accrual in grid_profit_yesterday for email reporting.'
    )

    def handle(self, *args, **options):
        now = timezone.now()
        updated = 0
        total_delta = Decimal('0')

        for bot in GridBot.objects.filter(status='ACTIVE'):
            current = bot.grid_profit or Decimal('0')
            previous = bot.grid_profit_snapshot or Decimal('0')

            if bot.grid_profit_snapshot_at:
                # We have a previous snapshot — compute the 24h delta
                delta = current - previous
                if delta < 0:
                    # User collected — no negative income to report
                    delta = Decimal('0')
            else:
                # First snapshot for this bot — no prior value to compare
                delta = Decimal('0')

            bot.grid_profit_yesterday = delta
            bot.grid_profit_snapshot = current
            bot.grid_profit_snapshot_at = now
            bot.save(update_fields=[
                'grid_profit_yesterday',
                'grid_profit_snapshot',
                'grid_profit_snapshot_at',
            ])

            total_delta += delta
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Snapshot complete: {updated} bots | total delta ${float(total_delta):.4f} '
            f'at {now.strftime("%Y-%m-%d %H:%M")}'
        ))