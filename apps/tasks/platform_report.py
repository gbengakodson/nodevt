from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone


@shared_task
def send_daily_platform_report():
    """Send daily income statement to admin"""
    from apps.wallets.models import Transaction
    from apps.tokens.models import Purchase
    from apps.referrals.models import ReferralEarning
    from apps.trading.models import GridBot
    from apps.accounts.models import User

    # Income
    grid_fees = Purchase.objects.filter(order_type='GRID').aggregate(t=Sum('node_fee'))['t'] or Decimal('0')
    market_fees = Purchase.objects.filter(order_type='MARKET').aggregate(t=Sum('node_fee'))['t'] or Decimal('0')
    total_income = grid_fees + market_fees

    # Expenditure
    referral_paid = ReferralEarning.objects.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    yield_paid = Transaction.objects.filter(transaction_type='YIELD').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_expenditure = referral_paid + yield_paid

    # Net
    net_profit = total_income - total_expenditure

    # Flow
    deposits = Transaction.objects.filter(transaction_type='DEPOSIT').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL').aggregate(t=Sum('amount'))['t'] or Decimal(
        '0')

    # User stats
    total_users = User.objects.filter(is_active=True).count()
    active_bots = GridBot.objects.filter(status='ACTIVE').count()
    total_bots = GridBot.objects.count()

    # Today's activity
    today = timezone.now().date()
    today_deposits = \
    Transaction.objects.filter(transaction_type='DEPOSIT', created_at__date=today).aggregate(t=Sum('amount'))[
        't'] or Decimal('0')
    today_withdrawals = \
    Transaction.objects.filter(transaction_type='WITHDRAWAL', created_at__date=today).aggregate(t=Sum('amount'))[
        't'] or Decimal('0')
    today_yield = \
    Transaction.objects.filter(transaction_type='YIELD', created_at__date=today).aggregate(t=Sum('amount'))[
        't'] or Decimal('0')
    new_users_today = User.objects.filter(date_joined__date=today).count()

    subject = f"NODE Platform Report — {today.strftime('%b %d, %Y')}"
    message = f"""
╔══════════════════════════════════════╗
║   NODE PLATFORM DAILY REPORT       ║
║   {today.strftime('%B %d, %Y')}           ║
╚══════════════════════════════════════╝

📊 PLATFORM SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
🤖 Active Bots: {active_bots} / {total_bots} total

💰 INCOME
━━━━━━━━━━━━━━━━━━━━━━━━━━
Grid Bot Fees (10%):      ${float(grid_fees):>12,.2f}
Market Order Fees (1%):   ${float(market_fees):>12,.2f}
▶ TOTAL INCOME:           ${float(total_income):>12,.2f}

💸 EXPENDITURE
━━━━━━━━━━━━━━━━━━━━━━━━━━
Referral Commissions:     ${float(referral_paid):>12,.2f}
Yield Distributed:        ${float(yield_paid):>12,.2f}
▶ TOTAL EXPENDITURE:      ${float(total_expenditure):>12,.2f}

💎 NET POSITION
━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ NET PROFIT/LOSS:        ${float(net_profit):>12,.2f}

📦 PLATFORM FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Deposits:           ${float(deposits):>12,.2f}
Total Withdrawals:        ${float(withdrawals):>12,.2f}
▶ FUNDS ON PLATFORM:      ${float(deposits - withdrawals):>12,.2f}

📅 TODAY'S ACTIVITY
━━━━━━━━━━━━━━━━━━━━━━━━━━
New Users:                {new_users_today}
New Deposits:             ${float(today_deposits):>12,.2f}
Withdrawals:              ${float(today_withdrawals):>12,.2f}
Yield Credited:           ${float(today_yield):>12,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━
NODE — Crypto Automation on the Go!
Report generated at {timezone.now().strftime('%H:%M:%S')}
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.DEFAULT_FROM_EMAIL],  # Sends to itself
        fail_silently=True,
    )

    return f"Platform report sent"