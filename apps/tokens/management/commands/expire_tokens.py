from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.tokens.models import TokenTransaction, NODEToken


class Command(BaseCommand):
    help = 'Expire pending NODE tokens that are older than 60 days'

    def handle(self, *args, **options):
        now = timezone.now()

        # Find all pending transactions past their expiry date
        expired_txns = TokenTransaction.objects.filter(
            status='PENDING',
            expires_at__lt=now
        )

        expired_count = expired_txns.count()
        total_burned = 0

        for txn in expired_txns:
            # Mark as expired
            txn.status = 'EXPIRED'
            txn.save()

            # Reduce user's pending balance
            wallet = NODEToken.objects.filter(user=txn.user).first()
            if wallet:
                wallet.pending_balance -= txn.amount
                wallet.save()

            total_burned += txn.amount

        self.stdout.write(
            self.style.SUCCESS(
                f'Expired {expired_count} transactions | {total_burned} tokens burned'
            )
        )