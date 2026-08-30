from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, date
from apps.wallets.models import Transaction


User = get_user_model()


def send_daily_email_to_all_users():
    from apps.wallets.models import Wallet
    from apps.tokens.models import UserTokenBalance
    from apps.trading.models import GridBot
    from apps.forex_ea.models import FiatBalance
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

            # Total invested capital
            active_bots = GridBot.objects.filter(user=user, status='ACTIVE')
            stopped_bots = GridBot.objects.filter(user=user, status='STOPPED')
            total_invested = sum(b.amount for b in active_bots) + sum(b.amount for b in stopped_bots)

            # Income today
            yesterday = timezone.now() - timedelta(days=1)
            income_today = Transaction.objects.filter(
                user=user, transaction_type='YIELD', created_at__gte=yesterday
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            # Current grid value
            grid_value = sum((b.amount + b.grid_profit + b.pnl) for b in active_bots) or Decimal('0')

            # Forex spot value (from crypto token balances)
            spot_value = Decimal('0')
            for b in UserTokenBalance.objects.filter(user=user, quantity__gt=0):
                spot_value += b.quantity * b.token.current_price

            # Stocks value (temporary 0 until stocks are live)
            stock_value = Decimal('0')

            # Investment funds (forex + commodities from FiatBalance)
            gbp_balance = Decimal('0')
            eur_balance = Decimal('0')
            gold_balance = Decimal('0')
            ng_stocks_value = Decimal('0')
            foreign_stocks_value = Decimal('0')

            fiat_balances = FiatBalance.objects.filter(user=user)
            for fb in fiat_balances:
                if fb.currency == 'GBP':
                    gbp_balance += fb.balance
                elif fb.currency == 'EUR':
                    eur_balance += fb.balance
                elif fb.currency == 'GOLD':
                    gold_balance += fb.balance
                elif fb.currency in ['NGN', 'ZENITHBANK', 'GTCO', 'MTNN', 'DANGCEM', 'ACCESSCORP', 'UBA', 'SEPLAT']:
                    ng_stocks_value += fb.balance
                elif fb.currency in ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'GOOGL', 'META', 'KO', 'VOO', 'NFLX']:
                    foreign_stocks_value += fb.balance

            # Networth
            networth = spot_value + grid_value + grand_balance + yield_balance

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
📊 Forex Spot: ${float(spot_value):,.2f}
🌍 Stocks: ${float(stock_value):,.2f}
━━━━━━━━━━━━━━━━━
📊 Total Portfolio: ${float(networth):,.2f}


            B.  INVESTMENT FUNDS

🇬🇧 GBP: <img src="https://www.nodevt.com/static/UK.png" style="width:18px;height:12px;vertical-align:middle;"> ${float(gbp_balance):,.2f}
🇪🇺 EUR: <img src="https://www.nodevt.com/static/EU.jpg" style="width:18px;height:12px;vertical-align:middle;"> ${float(eur_balance):,.2f}
🥇 GOLD: <img src="https://www.nodevt.com/static/gold.jpg" style="width:18px;height:12px;vertical-align:middle;"> ${float(gold_balance):,.2f}
🇳🇬 Nigerian Stocks: <img src="https://www.nodevt.com/static/NG.jpg" style="width:18px;height:12px;vertical-align:middle;"> ${float(ng_stocks_value):,.2f}
🌍 Foreign Stocks: <img src="https://www.nodevt.com/static/usflag.png" style="width:18px;height:12px;vertical-align:middle;"> ${float(foreign_stocks_value):,.2f}

C. NETWORTH
${float(networth):,.2f}

⏱️ Report Time: {live_clock}

Visit your dashboard: https://www.nodevt.com/dashboard/

Have a wonderful Investing Experience! 🚀
NODE! — Asset Automation Engine on the Go.
"""

            # Send as HTML so flag images show
            html_content = f"<div style='font-family:Arial; max-width:600px; white-space:pre-line;'>{message}</div>"

            send_mail(
                subject=subject,
                message='',
                html_message=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent_count += 1

        except Exception as e:
            print(f"Error sending email to {user.email}: {e}")
            continue

    return f"Sent {sent_count} daily emails"


from apps.forex_ea.models import ForexForecast
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

def send_daily_forecast_email_to_all_users():
    """Send EURUSD, WTI, GOLD forecast — only if data is from today."""
    from datetime import date
    today = date.today()
    symbols = ['EURUSD', 'WTI', 'GOLD']
    forecasts = {}

    for sym in symbols:
        f = ForexForecast.objects.filter(pair=sym, created_at__date=today).first()
        if f:
            forecasts[sym] = f

    if not forecasts:
        # No fresh data at all — do nothing (or send a simple note if you prefer)
        return

    today_str = today.strftime('%B %d, %Y')
    users = User.objects.filter(is_active=True)
    for user in users:
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>📊 Daily Market Forecast – {today_str}</h2>
            <p>Good morning! Here's what our NodeV16 engine predicts for today.</p>
        """
        for sym in symbols:
            f = forecasts.get(sym)
            if not f:
                continue
            html_body += f"""
            <div style="background: #F8F9FA; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
                <h3 style="margin-top:0;">{sym}</h3>
                <p><strong>Current Price:</strong> {f.current_price}</p>
                <p><strong>Market Sentiment & Trend:</strong> {f.trend}</p>
                <p><strong>Key Technical Conditions:</strong> {f.condition}</p>
                <p><strong>Strategic Execution Trigger:</strong> {f.trigger}</p>
                <p><strong>Daily Candle Prediction:</strong> {f.daily_candle}</p>
            </div>
            """
        html_body += f"""
            <p style="margin-top: 20px; color: #707A8A; font-size: 12px;">
                Powered by NodeV16 • Updated daily at 6 AM UTC
            </p>
        </div>
        """
        send_mail(
            subject=f'📊 Daily Market Forecast – {today_str}',
            message='',
            html_message=html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )



import threading
from django.core.mail import send_mail
from django.conf import settings

def send_email_notification(user, subject, message):
    """Send a simple email in a background thread (non-blocking)."""
    def _send():
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Email notification error for {user.email}: {e}")

    threading.Thread(target=_send).start()