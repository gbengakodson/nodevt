from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

from apps.trading.models import GridBot
from apps.wallets.models import Transaction


class Command(BaseCommand):
    help = 'READ-ONLY audit of grid_profit. Reports deviations only, never modifies.'

    HOURLY_RATE = Decimal('0.0000277777777777778')  # 2% / 720
    THRESHOLD = Decimal('1.00')

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default=None)

    def handle(self, *args, **options):
        qs = GridBot.objects.filter(status='ACTIVE').select_related('token', 'user').order_by('user__email', 'created_at')
        if options['email']:
            qs = qs.filter(user__email=options['email'])

        total_exp = Decimal('0')
        total_act = Decimal('0')
        total_dev = Decimal('0')
        over = under = ok = 0

        self.stdout.write('=' * 90)
        self.stdout.write('GRID PROFIT AUDIT — READ-ONLY (no data modified)')
        self.stdout.write('=' * 90)

        for bot in qs:
            hours = (timezone.now() - bot.created_at).total_seconds() / 3600
            earning_hours = max(0, hours - 24)
            if earning_hours <= 0:
                continue

            current_value = (bot.amount or Decimal('0')) + (bot.pnl or Decimal('0'))
            expected_lifetime = current_value * self.HOURLY_RATE * Decimal(str(int(earning_hours)))

            manual = Transaction.objects.filter(
                user=bot.user, transaction_type='YIELD',
                metadata__source='grid_profit_collection',
                metadata__grid_bot_id=str(bot.id),
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            cycle = Transaction.objects.filter(
                user=bot.user, transaction_type='YIELD',
                metadata__reason='auto_reactivate_grid_profit',
                metadata__grid_bot_id=str(bot.id),
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            lifetime = bot.total_yield_earned or Decimal('0')
            already_out = max(manual + cycle, lifetime)

            correct_remaining = max(Decimal('0'), expected_lifetime - already_out)
            actual = bot.grid_profit or Decimal('0')
            dev = actual - correct_remaining

            total_exp += correct_remaining
            total_act += actual
            total_dev += dev

            if abs(dev) < self.THRESHOLD:
                ok += 1
                continue

            if dev > 0:
                over += 1
                flag = 'OVER '
            else:
                under += 1
                flag = 'UNDER'

            self.stdout.write(
                f'{flag} | {bot.user.email[:26]:26} | {bot.token.symbol:6} | '
                f'exp ${float(correct_remaining):>10.4f} | act ${float(actual):>10.4f} | dev ${float(dev):>+10.4f}'
            )

        self.stdout.write('=' * 90)
        self.stdout.write(f'Bots: {qs.count()} | OK: {ok} | OVER: {over} | UNDER: {under}')
        self.stdout.write(f'Expected: ${float(total_exp):,.4f} | Actual: ${float(total_act):,.4f} | Deviation: ${float(total_dev):+,.4f}')
        self.stdout.write('⚠️  READ-ONLY. No data modified.')
        self.stdout.write('=' * 90)