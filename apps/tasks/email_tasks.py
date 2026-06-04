from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
from apps.wallets.models import Transaction

User = get_user_model()


def send_daily_email_to_all_users():
    from apps.wallets.models import Wallet, Purse
    from apps.tokens.models import UserTokenBalance
    from apps.trading.models import GridBot
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum
    from decimal import Decimal

    users = User.objects.filter(is_active=True)
    sent_count = 0

    for user in users:
        try:
            grand = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
            yield_w = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
            grand_balance = grand.balance if grand else Decimal('0')
            yield_balance = yield_w.balance if yield_w else Decimal('0')

            # Days since joining
            days_active = (timezone.now() - user.date_joined).days

            # Total invested capital (all bots: active + stopped)
            active_bots = GridBot.objects.filter(user=user, status='ACTIVE')
            stopped_bots = GridBot.objects.filter(user=user, status='STOPPED')
            total_invested = sum(b.amount for b in active_bots) + sum(b.amount for b in stopped_bots)

            # Income today (yield earned in last 24 hours)
            yesterday = timezone.now() - timedelta(days=1)
            income_today = Transaction.objects.filter(
                user=user, transaction_type='YIELD', created_at__gte=yesterday
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            # Current grid value
            grid_value = sum((b.amount + b.grid_profit + b.pnl) for b in active_bots) or Decimal('0')

            # Spot holdings value
            spot_value = Decimal('0')
            for b in UserTokenBalance.objects.filter(user=user, quantity__gt=0):
                spot_value += b.quantity * b.token.current_price

            # External wallet automation balance (capital deployed on connected exchanges)
            # External wallet automation balance — filter in Python (JSONField can't use ORM exclude)
            external_balance = Decimal('0')

            # Networth
            networth = spot_value + grid_value + grand_balance + yield_balance

            # Purses section with fixed format
            purses = Purse.objects.filter(user=user)
            if purses.exists():
                emergency = sum(p.balance for p in purses if p.name == 'Reserve')
                education = sum(p.balance for p in purses if p.name == 'Education')
                house_rent = sum(p.balance for p in purses if p.name == 'Housing')
                business = sum(p.balance for p in purses if p.name in ['Operations', 'Supply Chain', 'Maintenance'])

                purse_lines = (
                    f'\n🆘 Emergency Fund: ${float(emergency):,.2f}\n'
                    f'🎓 Education: ${float(education):,.2f}\n'
                    f'🏠 House Rent: ${float(house_rent):,.2f}\n'
                    f'💰 Business: ${float(business):,.2f}'
                )

                # Pension status
                user_type = user.user_type or 'MICRO'
                if user_type in ['SALARY', 'DIASPORA']:
                    yw = Wallet.objects.filter(user=user, wallet_type='YIELD').first()
                    if yw and yw.pension_fund:
                        pension_bal = yw.balance if yw else Decimal('0')
                        purse_lines += f'\n🏦 Pension Fund: ${float(pension_bal):,.2f} (Active)'
                    else:
                        purse_lines += '\n🏦 Pension Fund: $0.00 (Available — Activate on Dashboard)'
                else:
                    purse_lines += '\n🏦 Pension Fund: $0.00 (Not applicable for your plan)'

                purse_suggestions = '\n💡 Your Reserve Account helps you save for what matters. Pension Fund builds your retirement.\n'
            else:
                purse_lines = (
                    '\n🆘 Emergency Fund: $0.00\n'
                    '🎓 Education: $0.00\n'
                    '🏠 House Rent: $0.00\n'
                    '💰 Business: $0.00\n'
                    '🏦 Pension Fund: $0.00\n'
                )
                purse_suggestions = '\n💡 Your Reserve Account helps you save for what matters. Pension Fund builds your retirement.\n'

            # Live clock
            now = datetime.now()
            live_clock = now.strftime('%H:%M:%S.') + str(now.microsecond // 1000).zfill(3)

            subject = f"Daily Portfolio Update - {timezone.now().strftime('%b %d, %Y')}"
            message = f"""Hello {user.username or user.email},

{days_active} days have passed, ${float(total_invested):,.2f} has been working for you.
Your income today is ${float(income_today):,.2f}.
Your current Networth is ${float(networth):,.2f}.

Here is the breakdown:

           A.  INCOME

💰 Wallet Balance: ${float(grand_balance):,.2f}
💎 Yield Balance: ${float(yield_balance):,.2f}
🤖 Position Tracker (active): ${float(grid_value):,.2f}
🔗 External wallet automation balance: ${float(external_balance):,.2f}
━━━━━━━━━━━━━━━━━
📊 Total Portfolio: ${float(networth):,.2f}


      B.  RESERVED FUNDS
{purse_lines}
{purse_suggestions}

C. NETWORTH
${float(networth):,.2f}

⏱️ Report Time: {live_clock}

Visit your dashboard: https://www.nodevt.com/dashboard/

Have a wonderful Investing Experience with NODE! 🚀
NODE! — The Crypto Automation Engine on the Go.
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