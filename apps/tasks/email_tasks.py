from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import time

User = get_user_model()


@shared_task
def send_daily_email_to_all_users():
    """Send daily portfolio summary email to all active users in background"""
    from apps.wallets.models import Wallet
    from apps.tokens.models import UserTokenBalance
    from apps.trading.models import GridBot

    users = User.objects.filter(is_active=True)
    sent_count = 0

    for user in users:
        try:
            grand = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
            yield_w = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
            grand_balance = grand.balance if grand else Decimal('0')
            yield_balance = yield_w.balance if yield_w else Decimal('0')

            spot_value = Decimal('0')
            for b in UserTokenBalance.objects.filter(user=user, quantity__gt=0):
                spot_value += b.quantity * b.token.current_price

            active_bots = GridBot.objects.filter(user=user, status='ACTIVE')
            grid_value = sum((b.amount + b.grid_profit + b.pnl for b in active_bots), Decimal('0'))
            grid_profit = sum((b.grid_profit for b in active_bots), Decimal('0'))
            total = spot_value + grid_value + grand_balance + yield_balance

            subject = f"Daily Portfolio Update - {timezone.now().strftime('%b %d, %Y')}"
            message = f"""Hello {user.username or user.email},

Here's your daily portfolio summary:

💰 Grand Balance: ${grand_balance:,.2f}
💎 Yield Balance: ${yield_balance:,.2f}
📦 Spot Holdings: ${spot_value:,.2f}
🤖 Grid Bots: ${grid_value:,.2f}
━━━━━━━━━━━━━━━━━
📊 Total Portfolio: ${total:,.2f}

Active Grid Bots: {active_bots.count()}
Grid Profit Available: ${grid_profit:,.2f}

Visit your dashboard: https://www.nodevt.com/dashboard/

Happy trading! 🚀
NODE Spot Grid Bot
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent_count += 1
            time.sleep(2)  # 2 second delay between emails to avoid rate limits

        except Exception as e:
            print(f"Error sending email to {user.email}: {e}")
            continue

    return f"Sent {sent_count} daily emails"