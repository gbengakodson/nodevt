from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.wallets.models import Wallet


class Command(BaseCommand):
    help = 'Check NVT bonus reserve coverage ratio'

    def handle(self, *args, **options):
        from apps.wallets.models import Wallet

        # Total accrued liability = sum of all YIELD wallet balances
        from django.db.models import Sum
        liability = Wallet.objects.filter(
            wallet_type='YIELD'
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0')

        # Reserve balance: wherever you hold the fee reserve.
        # UPDATE THE FILTER BELOW TO MATCH YOUR SETUP.
        # Example: if reserve is a PlatformSetting or a dedicated wallet.
        from apps.core.models import PlatformSetting
        reserve_setting = PlatformSetting.objects.filter(key='nvt_reserve_balance').first()
        reserve = Decimal(str(reserve_setting.value)) if reserve_setting else Decimal('0')

        if liability == 0:
            self.stdout.write(self.style.SUCCESS(
                f'Reserve: ${reserve:,.2f} | Liability: $0.00 | No liability yet.'
            ))
            return

        coverage = reserve / liability

        if coverage >= 2.0:
            status = self.style.SUCCESS('EXCELLENT')
        elif coverage >= 1.5:
            status = self.style.SUCCESS('HEALTHY')
        elif coverage >= 1.0:
            status = self.style.SUCCESS('OK')
        elif coverage >= 0.8:
            status = self.style.WARNING('CAUTION')
        elif coverage >= 0.5:
            status = self.style.WARNING('WARNING')
        else:
            status = self.style.ERROR('EMERGENCY')

        self.stdout.write(self.style.SUCCESS(
            f'Reserve: ${reserve:,.2f} | Liability: ${liability:,.2f} | '
            f'Coverage: {coverage:.2f}x'
        ))
        self.stdout.write(f'Status: {status}')