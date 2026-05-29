from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from apps.trading.models import GridBot
from apps.core.notifications import notify_user


class Command(BaseCommand):
    help = 'Audit all active Position Trackers for profit inflation and correct if needed'

    THRESHOLD = Decimal('1.00')  # $1 minimum discrepancy to trigger correction

    def handle(self, *args, **options):
        bots = GridBot.objects.filter(status='ACTIVE').select_related('token', 'user')
        corrected = 0
        skipped = 0

        for bot in bots:
            hours = (timezone.now() - bot.created_at).total_seconds() / 3600
            earning_hours = max(0, hours - 24)  # 24h delay

            if earning_hours <= 0:
                skipped += 1
                continue

            # Correct formula: current_value × hourly_rate × earning_hours × 90% user share
            current_value = bot.amount + bot.pnl
            hourly_rate = Decimal('0.0001388888888888889')
            expected_profit = current_value * hourly_rate * Decimal(str(int(earning_hours))) * Decimal('0.9')

            # Subtract what user already collected
            from apps.wallets.models import Transaction
            from django.db.models import Sum
            collected = Transaction.objects.filter(
                user=bot.user,
                transaction_type='YIELD',
                metadata__grid_bot_id=str(bot.id)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            already_collected = max(collected, bot.total_yield_earned or Decimal('0'))
            correct_remaining = expected_profit - already_collected
            if correct_remaining < 0:
                correct_remaining = Decimal('0')

            deviation = bot.grid_profit - correct_remaining

            if abs(deviation) > self.THRESHOLD:
                old = bot.grid_profit
                bot.grid_profit = correct_remaining
                bot.save()

                self.stdout.write(
                    f'🔧 {bot.user.email}: {bot.token.symbol} — '
                    f'\${float(old):.2f} → \${float(correct_remaining):.2f} '
                    f'(deviation: \${float(deviation):+.2f})'
                )
                corrected += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Audit complete: {corrected} corrected, {skipped} within threshold'
            )
        )