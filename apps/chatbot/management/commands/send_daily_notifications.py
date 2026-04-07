from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Send daily notifications to all users'

    def handle(self, *args, **options):
        self.stdout.write('Sending daily notifications...')

        try:
            from apps.chatbot.services.chatbot_service import NotificationService
            from apps.wallets.models import Wallet

            users = User.objects.filter(is_active=True)
            sent_count = 0

            for user in users:
                try:
                    # Send portfolio update
                    NotificationService.send_daily_portfolio_update(user)

                    # Check for zero balance reminder
                    grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
                    if grand_wallet and grand_wallet.balance == 0:
                        NotificationService.send_zero_balance_reminder(user)

                    # Send random yield tip (20% chance)
                    import random
                    if random.random() < 0.2:
                        NotificationService.send_yield_tip(user)

                    sent_count += 1
                    self.stdout.write(f'✓ Notifications sent to {user.email}')

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error for user {user.email}: {e}'))

            self.stdout.write(self.style.SUCCESS(f'Done! Notifications sent to {sent_count} users'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            self.stdout.write('Make sure chatbot_service.py exists in apps/chatbot/services/')