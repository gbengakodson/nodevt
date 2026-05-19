from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

User = get_user_model()


def send_daily_email_to_all_users():
    from apps.wallets.models import Wallet, Purse
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

            # Get purses
            purses = Purse.objects.filter(user=user)
            purse_lines = ''
            purse_suggestions = ''

            if purses.exists():
                # Group purses by type
                purse_groups = {
                    'Emergency': '🆘 Emergency Fund',
                    'Shop Rent': '🏪 Business Account',
                    'Inventory': '📦 Business Account',
                    'Repair': '🔧 Business Account',
                    'School Fees': '🎓 Goal Account',
                    'House Rent': '🏠 Goal Account',
                }

                shown = {}
                for p in purses:
                    group_name = purse_groups.get(p.name, '💰 Other')
                    if group_name not in shown:
                        purse_lines += f'\n{group_name}:\n'
                        shown[group_name] = True
                    purse_lines += f'  {p.name}: ${float(p.balance):,.2f}\n'

                # Add Pension Fund for SALARY and DIASPORA
                user_type = user.user_type or 'MICRO'
                if user_type in ['SALARY', 'DIASPORA']:
                    yw = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
                    if yw and yw.pension_fund:
                        purse_lines += '\n🏦 Pension Fund: Active — Auto-reinvests every 6 months\n'
                    else:
                        purse_lines += '\n🏦 Pension Fund: Available — Activate on your Dashboard\n'

                suggestions = {
                    'MICRO': '💡 Your Emergency Fund auto-sweeps weekly from grid profits. Withdraw anytime, any amount.',
                    'BUSINESS': '💡 Your Business Account auto-sweeps weekly. Protect your business capital.',
                    'SALARY': '💡 Your Goal Account helps you save for what matters. Pension Fund builds your retirement.',
                    'DIASPORA': '💡 Your Goal Account builds your return home. Pension Fund secures your future.',
                    'REFERRAL': '💡 Share your referral link to earn commissions. Your network builds your wealth.'
                }
                purse_suggestions = '\n' + suggestions.get(user_type, '') + '\n'

            # Live clock
            now = datetime.now()
            live_clock = now.strftime('%H:%M:%S.') + str(now.microsecond // 1000).zfill(3)

            subject = f"Daily Portfolio Update - {timezone.now().strftime('%b %d, %Y')}"
            message = f"""Hello {user.username or user.email},

Here's your daily portfolio summary:

💰 Grand Balance: ${grand_balance:,.2f}
💎 Yield Balance: ${yield_balance:,.2f}
📦 Spot Holdings: ${spot_value:,.2f}
🤖 Grid Bots: ${grid_value:,.2f}
━━━━━━━━━━━━━━━━━
📊 Total Portfolio: ${total:,.2f}
{purse_lines}
Active Grid Bots: {active_bots.count()}
Grid Profit Available: ${grid_profit:,.2f}
{purse_suggestions}
⏱️ Report Time: {live_clock}

Visit your dashboard: https://www.nodevt.com/dashboard/

Happy trading! 🚀
NODE! — Crypto Automation on the Go.
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent_count += 1

        except Exception as e:
            print(f"Error sending email to {user.email}: {e}")
            continue

    return f"Sent {sent_count} daily emails"