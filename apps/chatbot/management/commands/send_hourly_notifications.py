from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send hourly portfolio notifications to all users'

    def handle(self, *args, **options):
        self.stdout.write('Sending hourly portfolio notifications...')

        try:
            from apps.chatbot.services.chatbot_service import NotificationService
            from apps.tokens.models import UserTokenBalance
            from apps.wallets.models import Wallet

            users = User.objects.filter(is_active=True)
            sent_count = 0

            for user in users:
                try:
                    # Get user's token holdings
                    balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)

                    if balances.exists():
                        # Calculate portfolio value
                        total_value = 0
                        portfolio_summary = []

                        for balance in balances:
                            value = float(balance.quantity) * float(balance.token.current_price)
                            total_value += value
                            profit_percent = ((float(balance.token.current_price) - float(
                                balance.average_buy_price)) / float(balance.average_buy_price)) * 100 if float(
                                balance.average_buy_price) > 0 else 0
                            profit_icon = "📈" if profit_percent > 0 else "📉"
                            portfolio_summary.append(
                                f"{balance.token.symbol}: ${value:,.2f} ({profit_percent:+.1f}% {profit_icon})")

                        # Get yield balance
                        yield_wallet = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
                        yield_balance = float(yield_wallet.balance) if yield_wallet else 0

                        # Calculate hourly yield earned (0.014% of portfolio value)
                        hourly_yield = total_value * 0.00014

                        tips = [
                            "The more tokens you hold, the higher your hourly yield!",
                            "Set take-profit orders to lock in gains automatically.",
                            "Invite friends to earn node fee commissions up to 7 levels!",
                            "Reinvest your yield earnings to compound returns.",
                            "Diversify across multiple tokens to spread risk.",
                            "AI Grid trading buys at dips and sells at rises automatically.",
                            "Your hourly yield is paid directly to your YIELD wallet.",
                            "Withdraw yield anytime to your GRAND wallet for more trading."
                        ]

                        message = f"""📊 **Hourly Portfolio Update**

💰 **Total Value:** ${total_value:,.2f} USDC
✨ **Yield Earned (last hour):** ${hourly_yield:.4f} USDC
💎 **Yield Balance:** ${yield_balance:,.2f} USDC

**Your Holdings:**
{chr(10).join(portfolio_summary[:5])}

💡 *Tip: {random.choice(tips)}*

---
🤖 Node AI Autotrader - Trading 24/7"""

                        NotificationService.create_notification(
                            user=user,
                            title="📊 Hourly Portfolio Update",
                            message=message,
                            notification_type='PORTFOLIO'
                        )

                    else:
                        # User has no tokens - remind to invest
                        grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
                        grand_balance = float(grand_wallet.balance) if grand_wallet else 0

                        if grand_balance > 0:
                            message = f"""💡 **Your balance is ready to invest!**

💰 **Available Balance:** ${grand_balance:,.2f} USDC

🚀 **Start earning today:**
1. Buy your first token
2. AI Autotrader activates automatically
3. Earn hourly yield on your holdings

**Minimum investment:** $10 USDC

---
Don't let your crypto sit idle!"""

                            NotificationService.create_notification(
                                user=user,
                                title="💡 Ready to Start Earning?",
                                message=message,
                                notification_type='REMINDER'
                            )
                        else:
                            # User has zero balance - remind to deposit
                            message = f"""💰 **Start Your Crypto Journey!**

💡 Deposit at least $10 USDC to:
• Start trading crypto tokens
• Earn hourly yield on holdings
• AI Autotrader works 24/7 for you

**Your referral code:** {user.referral_code}

Share and earn commissions from 7 generations!

---
Join the Node community today!"""

                            NotificationService.create_notification(
                                user=user,
                                title="💰 Start Earning with Node",
                                message=message,
                                notification_type='REMINDER'
                            )

                    sent_count += 1
                    self.stdout.write(f'✓ Notification sent to {user.email}')

                except Exception as e:
                    logger.error(f"Error for user {user.email}: {e}")

            self.stdout.write(self.style.SUCCESS(f'Hourly notifications sent to {sent_count} users'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))