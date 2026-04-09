from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Send daily notifications to all users (runs 3 times per day)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--time-slot',
            type=str,
            help='Time slot: morning, afternoon, evening'
        )

    def handle(self, *args, **options):
        time_slot = options.get('time_slot', 'morning')
        self.stdout.write(f'Sending {time_slot} notifications...')

        try:
            from apps.chatbot.services.chatbot_service import NotificationService
            from apps.wallets.models import Wallet

            users = User.objects.filter(is_active=True)
            sent_count = 0

            for user in users:
                try:
                    # Send different notifications based on time of day
                    if time_slot == 'morning':
                        # Morning: Portfolio update and zero balance reminder
                        NotificationService.send_daily_portfolio_update(user)

                        # Check for zero balance reminder
                        grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
                        if grand_wallet and grand_wallet.balance == 0:
                            NotificationService.send_zero_balance_reminder(user)

                    elif time_slot == 'afternoon':
                        # Afternoon: Yield tip (50% chance)
                        if random.random() < 0.5:
                            NotificationService.send_yield_tip(user)

                    elif time_slot == 'evening':
                        # Evening: Performance summary and encouragement
                        NotificationService.send_evening_summary(user)

                    sent_count += 1
                    self.stdout.write(f'✓ {time_slot} notifications sent to {user.email}')

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error for user {user.email}: {e}'))

            self.stdout.write(self.style.SUCCESS(f'Done! {time_slot} notifications sent to {sent_count} users'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))