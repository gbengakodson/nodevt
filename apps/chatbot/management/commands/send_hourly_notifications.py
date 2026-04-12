from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime
import random
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send hourly portfolio notifications to all users'

    def handle(self, *args, **options):
        self.stdout.write('Sending hourly notifications...')

        try:
            from apps.chatbot.services.chatbot_service import NotificationService, HourlyNotificationService
            from apps.tokens.models import UserTokenBalance
            from apps.wallets.models import Wallet
            from apps.referrals.models import ReferralRelationship

            users = User.objects.filter(is_active=True)
            sent_count = 0
            current_hour = datetime.now().hour

            # Get global stats
            total_market_cap = 0
            total_yield_paid = 125000  # Placeholder
            total_trades = 15000  # Placeholder

            for user in users:
                try:
                    # Get user data
                    grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
                    yield_wallet = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
                    grand_balance = float(grand_wallet.balance) if grand_wallet else 0
                    yield_balance = float(yield_wallet.balance) if yield_wallet else 0

                    # Get portfolio value
                    balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)
                    portfolio_value = 0
                    top_holding = None
                    for balance in balances:
                        value = float(balance.quantity) * float(balance.token.current_price)
                        portfolio_value += value
                        if not top_holding:
                            top_holding = balance.token.symbol

                    # Get referral count
                    referral_count = ReferralRelationship.objects.filter(referrer=user).count()

                    # Prepare user data for message
                    user_data = {
                        'grand_balance': grand_balance,
                        'yield_balance': yield_balance,
                        'portfolio_value': portfolio_value,
                        'referral_count': referral_count,
                        'referral_code': user.referral_code if hasattr(user, 'referral_code') else 'N/A',
                        'top_holding': top_holding or 'BTC',
                        'total_market_cap': total_market_cap,
                        'total_yield_paid': total_yield_paid,
                        'total_trades': total_trades,
                        'daily_yield': (portfolio_value * 0.10) / 30,
                        'daily_change': random.uniform(-5, 8),
                        'trades_today': random.randint(8, 25),
                        'grid_profit': random.uniform(15, 65),
                        'grid_level': random.randint(30, 70),
                        'daily_volume': random.randint(150000, 500000),
                        'buy_sell_ratio': f"{random.uniform(0.8, 1.5):.1f}:1",
                        'top_traded_token': random.choice(['BTC', 'ETH', 'SOL']),
                        'market_sentiment': random.choice(['Bullish 📈', 'Bearish 📉', 'Neutral 📊']),
                        'next_target': 500 if grand_balance < 500 else (1000 if grand_balance < 1000 else 5000),
                        'yield_earned': (portfolio_value * 0.10) / 30,
                        'referral_earned': referral_count * 5,
                        'grid_earned': random.uniform(30, 80),
                        'total_passive': (portfolio_value * 0.10) / 30 + referral_count * 5 + random.uniform(30, 80),
                        'drop_percent': random.uniform(1.5, 8.5),
                        'bot_trades': random.randint(30, 70),
                        'bot_profit': random.uniform(80, 200),
                        'win_rate': random.randint(55, 85),
                        'start_balance': grand_balance,
                        'weekly_growth': random.uniform(-2, 12),
                    }

                    # Get hourly message
                    message_data = HourlyNotificationService.get_hourly_message(current_hour, user_data)

                    # Create notification
                    NotificationService.create_notification(
                        user=user,
                        title=message_data["title"],
                        message=message_data["message"],
                        notification_type='HOURLY'
                    )

                    sent_count += 1

                    if sent_count % 50 == 0:
                        self.stdout.write(f'  Processed {sent_count} users...')

                except Exception as e:
                    logger.error(f"Error for user {user.email}: {e}")

            self.stdout.write(self.style.SUCCESS(f'Hourly notifications sent to {sent_count} users'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))