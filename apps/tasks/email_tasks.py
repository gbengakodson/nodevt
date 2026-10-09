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

            # Total invested capital (active + stopped, not completed)
            active_bots = GridBot.objects.filter(user=user, status='ACTIVE')
            stopped_bots = GridBot.objects.filter(user=user, status='STOPPED')
            completed_bots = GridBot.objects.filter(user=user, status='COMPLETED')
            total_invested = sum(b.amount for b in active_bots) + sum(b.amount for b in stopped_bots)

            # Income yesterday — accrued grid_profit from the last snapshot
            income_yesterday = Decimal('0')
            for b in active_bots:
                income_yesterday += b.grid_profit_yesterday or Decimal('0')

            # Current grid value — active bots + unswept capital from completed bots
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

            # Purse balances
            from apps.wallets.models import Purse
            purse_total = sum(
                (p.balance or Decimal('0')) for p in Purse.objects.filter(user=user)
            ) or Decimal('0')

            # Networth — includes fiat, stocks, purses
            networth = (
                    spot_value
                    + grid_value
                    + grand_balance
                    + yield_balance
                    + gbp_balance
                    + eur_balance
                    + gold_balance
                    + ng_stocks_value
                    + foreign_stocks_value
                    + purse_total
            )

            # Live clock
            now = datetime.now()
            live_clock = now.strftime('%H:%M:%S.') + str(now.microsecond // 1000).zfill(3)

            subject = f"Daily Portfolio Update - {timezone.now().strftime('%b %d, %Y')}"

            # ── Promo banner (active Oct 10-20, 2026 only) ──
            from datetime import date as _date
            today = _date.today()
            promo_active = _date(2026, 10, 9) <= today <= _date(2026, 10, 20)

            if promo_active:
                promo_html = """
            <div style="background:linear-gradient(90deg,#F0B90B 0%,#FCD535 100%);
                        padding:14px 18px;border-radius:10px;margin-bottom:18px;text-align:center;">
                <div style="font-size:15px;font-weight:700;color:#1B1E21;margin-bottom:4px;">
                    🎁 LIMITED PROMO
                </div>
                <div style="font-size:13px;color:#1B1E21;line-height:1.5;">
                    Get <strong>20% CASH BACK</strong> on new investments of $100 or more.<br>
                    Valid October 10th – 20th.
                </div>
                <a href="https://www.nodevt.com/trading/"
                   style="display:inline-block;margin-top:10px;padding:8px 20px;
                          background:#1B1E21;color:#F0B90B;text-decoration:none;
                          border-radius:6px;font-weight:700;font-size:12px;">
                    Invest Now →
                </a>
            </div>
            """
            else:
                promo_html = ""

            message = f"""Hello {user.username or user.email},

{days_active} days have passed, ${float(total_invested):,.2f} has been working for you.
Your income yesterday was ${float(income_yesterday):,.2f}.
Your current Total Portfolio is ${float(networth):,.2f}.

Here is the breakdown:

           A.  INCOME

💰 Wallet Balance: ${float(grand_balance):,.2f}
💎 Yield Balance: ${float(yield_balance):,.2f}
🤖 Active Trackers: ${float(grid_value):,.2f}
📊 Forex Spot: ${float(spot_value):,.2f}
🌍 Stocks: ${float(stock_value):,.2f}
━━━━━━━━━━━━━━━━━
📊 Total Portfolio: ${float(networth):,.2f}


            B.  INVESTMENT FUNDS

<img src="https://www.nodevt.com/static/UK.png" style="width:18px;height:12px;vertical-align:middle;"> GBP: ${float(gbp_balance):,.2f}
<img src="https://www.nodevt.com/static/EU.jpg" style="width:18px;height:12px;vertical-align:middle;"> EUR: ${float(eur_balance):,.2f}
<img src="https://www.nodevt.com/static/gold.jpg" style="width:18px;height:12px;vertical-align:middle;"> GOLD: ${float(gold_balance):,.2f}
<img src="https://www.nodevt.com/static/NG.jpg" style="width:18px;height:12px;vertical-align:middle;"> Nigerian Stocks: ${float(ng_stocks_value):,.2f}
<img src="https://www.nodevt.com/static/usflag.png" style="width:18px;height:12px;vertical-align:middle;"> Foreign Stocks: ${float(foreign_stocks_value):,.2f}

C. TOTAL PORTFOLIO
${float(networth):,.2f}

⏱️ Report Time: {live_clock}

Visit your dashboard: https://www.nodevt.com/dashboard/

Have a wonderful Investing Experience! 🚀
NODE! — Asset Management Automation on the Go.
"""

            # Send as HTML so flag images show
            html_content = (
                    promo_html +
                    f"<div style='font-family:Arial; max-width:600px; white-space:pre-line;'>{message}</div>"
            )

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



def send_independence_day_email():
    """
    One-off Independence Day campaign email.
    Idempotent: will not send twice. Uses TaskCampaignLog to prevent re-sends.
    """
    from apps.chatbot.models import TaskCampaignLog
    from django.utils import timezone

    campaign_key = 'independence_day_2026'

    # Prevent double-send
    log, created = TaskCampaignLog.objects.get_or_create(
        key=campaign_key,
        defaults={'status': 'RUNNING', 'started_at': timezone.now()}
    )
    if not created and log.status == 'COMPLETED':
        return f'Already sent at {log.completed_at}. Skipping.'

    log.status = 'RUNNING'
    log.started_at = timezone.now()
    log.save()

    users = User.objects.filter(is_active=True)
    sent = 0
    failed = 0

    for user in users:
        try:
            greeting_name = user.username or user.email.split('@')[0]

            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#ffffff;">
                <img src="https://www.nodevt.com/static/independence.jpg"
                     alt="Happy Independence Day"
                     style="width:100%;border-radius:12px;margin-bottom:24px;display:block;">

                <p style="font-size:15px;color:#1E2329;line-height:1.7;">
                    Dear {greeting_name},
                </p>

                <p style="font-size:14px;color:#1E2329;line-height:1.7;">
                    On this 66th Independence Day, we at NODE want to take a moment
                    to wish you and your family a joyful and peaceful celebration.
                </p>

                <p style="font-size:14px;color:#1E2329;line-height:1.7;">
                    Nigeria's journey has been one of resilience, ambition, and the
                    relentless pursuit of a better future. Those are the same values
                    we try to live by at NODE every day — building tools that help
                    you grow your wealth with discipline and patience.
                </p>

                <p style="font-size:14px;color:#1E2329;line-height:1.7;">
                    Thank you for being part of the NODE community. We are proud
                    to grow with you.
                </p>

                <p style="font-size:14px;color:#1E2329;line-height:1.7;">
                    From all of us at NODE — <strong>Happy Independence Day.</strong>
                </p>

                <p style="font-size:14px;color:#1E2329;font-weight:700;margin-top:24px;">
                    🇳🇬 NODE Team
                </p>

                <hr style="border:none;border-top:1px solid #E2E4E8;margin:24px 0;">
                <p style="font-size:11px;color:#848E9C;text-align:center;">
                    NODE — Asset Automation Engine on the Go.<br>
                    <a href="https://www.nodevt.com/dashboard/" style="color:#F0B90B;">Visit your dashboard</a>
                </p>
            </div>
            """

            send_mail(
                subject='Happy Independence Day from NODE 🇳🇬',
                message='Happy Independence Day from NODE. Visit https://www.nodevt.com/dashboard/ to continue.',
                html_message=html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent += 1
        except Exception as e:
            print(f"Failed for {user.email}: {e}")
            failed += 1
            continue

    log.status = 'COMPLETED'
    log.completed_at = timezone.now()
    log.sent_count = sent
    log.failed_count = failed
    log.save()

    return f"Sent {sent} independence day emails, {failed} failed"