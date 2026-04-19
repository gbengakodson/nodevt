from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random


class ChatbotService:
    # Intent patterns
    INTENTS = {
        'how_to_buy': ['buy', 'purchase', 'how to buy', 'buy tokens', 'buy crypto'],
        'how_to_sell': ['sell', 'how to sell', 'sell tokens', 'sell crypto'],
        'how_to_deposit': ['deposit', 'how to deposit', 'add funds', 'send usdc'],
        'how_to_withdraw': ['withdraw', 'how to withdraw', 'cash out', 'withdrawal'],
        'referral': ['referral', 'refer', 'invite', 'commission', 'earn', 'node fee'],
        'yield': ['yield', 'earn hourly', 'passive income', 'how to earn', 'interest'],
        'balance': ['balance', 'how much', 'my balance', 'check balance'],
        'portfolio': ['portfolio', 'my tokens', 'holdings', 'what do i own'],
        'price': ['price', 'current price', 'token price', 'how much is'],
        'withdraw_yield': ['withdraw yield', 'move yield', 'claim yield'],
        'take_profit': ['take profit', 'stop loss', 'auto sell', 'target'],
        'minimum': ['minimum', 'minimum deposit', 'minimum withdrawal'],
        'network': ['network', 'bsc', 'bep20', 'which network'],
        'fee': ['fee', 'node fee', 'charges', 'cost'],
    }

    @classmethod
    def get_response(cls, user_message, user=None):
        """Get chatbot response based on user message"""
        user_message = user_message.lower().strip()

        # Check each intent
        for intent, keywords in cls.INTENTS.items():
            if any(keyword in user_message for keyword in keywords):
                response = cls.get_intent_response(intent, user)
                return response, intent

        # Default response
        return cls.get_default_response(), 'default'

    @classmethod
    def get_intent_response(cls, intent, user=None):
        """Generate response for specific intent"""

        responses = {
            'how_to_buy': """📈 **How to Buy Tokens:**

1. Go to the **Trading** page
2. Select a token (BTC, ETH, BNB, etc.)
3. Choose **Limit Order** (set your price) or **Market Order** (buy now)
4. Enter amount in USDC
5. Click **Buy**

💰 **Node Fee:** 10% is charged and distributed to your referrers
✅ Tokens appear in your portfolio instantly

Need help? Ask me about specific tokens!""",

            'how_to_sell': """📉 **How to Sell Tokens:**

⚠️ **Selling Condition:** You can only sell if current price > your purchase price

**Steps:**
1. Go to **Trading** page
2. Select the token you own
3. Enter quantity to sell
4. Click **Sell**

💡 **Pro Tip:** Use Take Profit orders to automatically sell at target prices!""",

            'how_to_deposit': """💵 **How to Deposit USDC:**

1. Go to **Deposit** page
2. Copy the platform wallet address:
   `0xD34d4DFceAeF1bB2BeEd3B8937bAB2bFb40d0572`
3. Send USDC from your wallet (MetaMask, Trust Wallet, Binance)
4. **IMPORTANT:** Use BSC (BEP-20) network only
5. Minimum deposit: **$10 USDC**
6. Submit your transaction hash on the deposit page

⏰ Deposits are reviewed within 24 hours""",

            'how_to_withdraw': """🏦 **How to Withdraw USDC:**

1. Go to **Withdraw** page
2. Enter your external wallet address (Binance, MetaMask, etc.)
3. Enter amount (minimum $10 USDC)
4. Submit request

⏰ Withdrawals are processed within 24 hours
✅ Funds are sent to your wallet after admin approval""",

            'referral': cls.get_referral_response(user),
            'yield': """🌟 **Yield Earnings - Passive Income!**

**How it works:**
- You earn yield HOURLY on your token holdings
- Yield is automatically credited to your YIELD wallet
- Withdraw anytime to your GRAND wallet

**Tips to maximize yield:**
1. Hold more tokens = higher earnings
2. Diversify across multiple tokens
3. Reinvest yield to compound returns

📊 Check your yield balance in the Portfolio page!""",

            'balance': cls.get_balance_response(user),
            'portfolio': cls.get_portfolio_response(user),
            'price': """💰 **Current Token Prices (USDC):**

I can show you real-time prices! 
Which token are you interested in? (BTC, ETH, BNB, SOL, etc.)

Or check the Trading page for live prices with charts!""",

            'withdraw_yield': """💸 **How to Withdraw Yield:**

1. Go to **Portfolio** or **Yield** page
2. Check your YIELD wallet balance
3. Click "Withdraw Yield"
4. Enter amount to transfer
5. Funds move to your GRAND wallet

💡 You can then use GRAND balance to buy more tokens or withdraw!""",

            'take_profit': """🎯 **Take Profit Orders - Auto Sell at Target!**

**How to set up:**
1. Go to Trading page
2. Find "Take Profit" section
3. Set target percentage (e.g., 20%)
4. Choose quantity to sell

**Example:** Buy at $100, set 20% target → Auto sells at $120

✅ No need to watch charts constantly!""",

            'minimum': """📋 **Minimum Requirements:**

- **Minimum Deposit:** $10 USDC
- **Minimum Withdrawal:** $10 USDC
- **Minimum Purchase:** No minimum (any amount works!)
- **Referral Commission:** No minimum, credited instantly""",

            'network': """🌐 **Network Information:**

**Supported Network:** BSC (BEP-20) only

**Platform Wallet:** `0xD34d4DFceAeF1bB2BeEd3B8937bAB2bFb40d0572`

⚠️ **IMPORTANT:** Always use BSC (BEP-20) network for deposits!
Sending on other networks (ERC20, TRC20) will result in LOST funds.

**Gas Fees:** Small amount of BNB required for blockchain transactions""",

            'fee': """💸 **Fee Structure:**

**Node Fee:** 10% on every purchase
- Distributed to referrers (up to 7 generations)
- Platform keeps remaining portion

**No fees for:**
- Deposits
- Withdrawals
- Selling tokens
- Yield earnings
- Referral commissions

**Gas Fees:** Small BNB fee for blockchain transactions (not collected by platform)""",
        }

        response = responses.get(intent, cls.get_default_response())
        return response

    @classmethod
    def get_referral_response(cls, user):
        if not user:
            return """🤝 **Referral Program - Earn Commissions!**

**How it works:**
- You get a unique referral code
- Share it with friends
- When they buy tokens, you earn commissions

**Commission Structure (10% node fee distribution):**
- Level 6 (direct referral): 50%
- Level 5: 25%
- Level 4: 12.5%
- Level 3: 6.25%
- Level 2: 3.125%
- Level 1: 1.5625%

**Example:** Friend buys $1000 → You earn up to $50!

Login to see your referral code!"""

        return f"""🤝 **Referral Program - Earn Commissions!**

**How it works:**
- You get a unique referral code
- Share it with friends
- When they buy tokens, you earn commissions

**Commission Structure (10% node fee distribution):**
- Level 6 (direct referral): 50%
- Level 5: 25%
- Level 4: 12.5%
- Level 3: 6.25%
- Level 2: 3.125%
- Level 1: 1.5625%

**Example:** Friend buys $1000 → You earn up to $50!

**Your referral code:** {user.referral_code}

Share link: `/register?ref={user.referral_code}`"""

    @classmethod
    def get_balance_response(cls, user):
        if not user:
            return "Please login to check your balance"

        from apps.wallets.models import Wallet

        try:
            grand_wallet = Wallet.objects.get(user=user, wallet_type='GRAND')
            yield_wallet = Wallet.objects.get(user=user, wallet_type='YIELD')

            return f"""💰 **Your Balance:**

**Grand Wallet (Trading):** ${float(grand_wallet.balance):,.2f} USDC
**Yield Wallet (Earnings):** ${float(yield_wallet.balance):,.2f} USDC

**Total Value:** ${float(grand_wallet.balance + yield_wallet.balance):,.2f} USDC

💡 Want to buy tokens? Use your Grand Wallet balance!
💡 Want to claim earnings? Withdraw from Yield Wallet!"""
        except:
            return "Unable to fetch your balance. Please try again later."

    @classmethod
    def get_portfolio_response(cls, user):
        if not user:
            return "Please login to view your portfolio"

        from apps.tokens.models import UserTokenBalance

        balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)

        if not balances:
            return """📊 **Your Portfolio:**

You don't have any tokens yet!

💡 **Get started:**
1. Deposit USDC to your Grand Wallet
2. Go to Trading page
3. Buy your first token!

🎯 **Tip:** Start with BTC or ETH for beginners"""

        portfolio_text = "📊 **Your Token Portfolio:**\n\n"
        total_value = 0

        for balance in balances:
            value = balance.quantity * balance.token.current_price
            total_value += value
            profit_percent = ((
                                          balance.token.current_price - balance.average_buy_price) / balance.average_buy_price) * 100 if balance.average_buy_price > 0 else 0
            profit_icon = "📈" if profit_percent > 0 else "📉"

            portfolio_text += f"**{balance.token.symbol}:** {balance.quantity:.4f} tokens\n"
            portfolio_text += f"  Value: ${value:,.2f} | Profit: {profit_percent:+.1f}% {profit_icon}\n\n"

        portfolio_text += f"**Total Portfolio Value:** ${total_value:,.2f} USDC"

        return portfolio_text

    @classmethod
    def get_default_response(cls):
        responses = [
            """🤖 **I'm your Crypto Assistant!**

I can help you with:
• 💰 **Buying/Selling tokens**
• 💵 **Deposits & Withdrawals**
• 🤝 **Referral program**
• 🌟 **Yield earnings**
• 📊 **Portfolio tracking**

Just ask me anything! Try:
- "How do I buy tokens?"
- "What's my balance?"
- "How does referral work?""",

            """❓ **Need help?**

Here are some things you can ask me:
• "How to deposit USDC?"
• "Show me my portfolio"
• "How do I earn yield?"
• "What's my referral code?"
• "How to withdraw money?"

What would you like to know?""",

            """💡 **Quick Tips:**

1. **New to crypto?** Start with a small deposit ($10-50)
2. **Want passive income?** Buy tokens and earn hourly yield
3. **Want to earn more?** Invite friends for commission
4. **Need help?** Just ask me anything!

What can I help you with today?"""
        ]
        return random.choice(responses)


class NotificationService:

    @classmethod
    def create_notification(cls, user, title, message, notification_type):
        """Create a notification for a user"""
        from apps.chatbot.models import UserNotification

        return UserNotification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )

    @classmethod
    def get_user_notifications(cls, user, limit=20, unread_only=False):
        """Get user's notifications"""
        from apps.chatbot.models import UserNotification

        queryset = UserNotification.objects.filter(user=user)
        if unread_only:
            queryset = queryset.filter(is_read=False)

        return queryset[:limit]

    @classmethod
    def mark_as_read(cls, notification_id):
        """Mark a notification as read"""
        from apps.chatbot.models import UserNotification

        UserNotification.objects.filter(id=notification_id).update(is_read=True)

    @classmethod
    def send_daily_portfolio_update(cls, user):
        from apps.tokens.models import UserTokenBalance
        from apps.wallets.models import Wallet, Transaction
        from .push_service import PushNotificationService
        from django.db import models

        balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)

        if not balances:
            # Send push notification for zero balance
            PushNotificationService.send_push_notification(
                user,
                "💰 Start Earning!",
                "Deposit $10+ USDC to start trading and earning per hour from daily market volatility.",
                '/deposit/'
            )

            cls.create_notification(
                user=user,
                title="💰 Start Earning!",
                message="Deposit $10 USDC to start trading and earning hourly yield.",
                notification_type='REMINDER'
            )
            return

        total_value = 0
        for balance in balances:
            value = balance.quantity * balance.token.current_price
            total_value += value

        today = timezone.now().date()
        today_yield = Transaction.objects.filter(
            user=user,
            transaction_type='YIELD',
            created_at__date=today
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        # Send push notification
        PushNotificationService.send_push_notification(
            user,
            f"📊 Portfolio: ${total_value:,.2f}",
            f"Yield today: ${float(today_yield):,.2f}. {balances.count()} tokens held.",
            '/portfolio/'
        )

        cls.create_notification(
            user=user,
            title="📊 Daily Portfolio Update",
            message=f"Total Value: ${total_value:,.2f} USDC | Yield Today: ${float(today_yield):,.2f}",
            notification_type='PORTFOLIO'
        )

    @classmethod
    def send_zero_balance_reminder(cls, user):
        """Send reminder to users with zero balance"""
        from apps.wallets.models import Wallet

        grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
        if grand_wallet and grand_wallet.balance == 0:
            cls.create_notification(
                user=user,
                title="💸 Your Wallet is Empty!",
                message=f"""Don't miss out on earning opportunities!

✅ **Deposit $10+ USDC to:**
• Start trading crypto tokens
• Earn hourly yield on holdings
• Refer friends for commission

🚀 **Get started in 3 steps:**
1. Go to Deposit page
2. Send USDC (BEP-20 network)
3. Start trading!

Need help? Ask our chatbot anything!""",
                notification_type='REMINDER'
            )

    @classmethod
    def send_yield_tip(cls, user):
        """Send yield optimization tip"""
        tips = [
            "💡 **Yield Tip:** The more tokens you hold, the more yield you earn! Consider adding to your positions.",
            "💡 **Yield Tip:** Different tokens have different yield rates. Check the Yield page for current rates!",
            "💡 **Yield Tip:** Reinvest your yield earnings to compound your returns over time!",
            "💡 **Yield Tip:** Refer friends - their purchases generate node fees that add to your balance!",
            "💡 **Yield Tip:** Set take-profit orders to lock in gains automatically!",
        ]

        cls.create_notification(
            user=user,
            title="🌟 Boost Your Earnings!",
            message=random.choice(tips),
            notification_type='TIP'
        )

    @classmethod
    def send_evening_summary(cls, user):
        """Send evening performance summary"""
        from apps.tokens.models import UserTokenBalance
        from apps.wallets.models import Wallet

        grand_wallet = Wallet.objects.filter(user=user, wallet_type='GRAND').first()
        balances = UserTokenBalance.objects.filter(user=user, quantity__gt=0)

        if balances.exists():
            total_value = 0
            for balance in balances:
                value = balance.quantity * balance.token.current_price
                total_value += value

            cls.create_notification(
                user=user,
                title="🌙 Evening Portfolio Summary",
                message=f"""**Today's Performance**

    💰 **Portfolio Value:** ${total_value:,.2f} USDC
    💵 **Available Balance:** ${float(grand_wallet.balance if grand_wallet else 0):,.2f} USDC
    📈 **Holdings:** {balances.count()} token(s)

    💡 **Tomorrow's opportunity:**
    • Check for new yield rates
    • Consider rebalancing your portfolio
    • Invite friends for extra commissions

    Rest well and see you tomorrow! 🚀""",
                notification_type='PORTFOLIO'
            )
        else:
            cls.create_notification(
                user=user,
                title="🌙 Start Your Crypto Journey Tomorrow!",
                message=f"""**Get ready to earn!**

    💰 **Your Balance:** ${float(grand_wallet.balance if grand_wallet else 0):,.2f} USDC

    💡 **Tomorrow's plan:**
    1. Deposit USDC to start trading
    2. Buy your first token
    3. Earn hourly yield
    4. Refer friends for commission

    The best time to start is tomorrow morning! 🌅""",
                notification_type='REMINDER'
            )


import random
from datetime import datetime
from decimal import Decimal


class HourlyNotificationService:
    # 24 different messages (one per hour)
    MESSAGES = [
        {
            "title": "💰 Hourly Balance Update",
            "template": "Your current Grand Balance: {grand_balance}\nYield Balance: {yield_balance}\n\nKeep trading to grow your portfolio!"
        },
        {
            "title": "💡 Zero Balance Alert",
            "template": "⚠️ Your balance is empty!\n\n💵 Fund with just $10 USDC to start earning:\n• 10% monthly yield\n• AI Grid trading 24/7\n• Referral commissions\n\nGet started today!"
        },
        {
            "title": "🎯 Your Monthly Target",
            "template": "To reach ${target} in 12 months, you need to invest ${needed} today.\n\nCurrent balance: {grand_balance}\nRemaining: ${remaining}"
        },
        {
            "title": "⏰ Hourly Earnings Update",
            "template": "You're earning ${hourly_yield}/hour from your holdings.\n\n📊 That's ${daily_yield}/day and ${monthly_yield}/month!\n\nKeep holding to maximize returns."
        },
        {
            "title": "💰 $50/Day Goal",
            "template": "Want to earn $50 per day?\n\n💵 Invest ${needed_to_earn_50} at 10% monthly yield.\n\nCurrent balance: {grand_balance}\nProgress: ${progress_to_50}/day"
        },
        {
            "title": "🌍 Total Market Cap",
            "template": "Total NODE Platform Value: ${total_market_cap}\n\n💰 Total Yield Paid: ${total_yield_paid}\n\n🤖 Total AI Trades: {total_trades}\n\nYou're part of something growing!"
        },
        {
            "title": "🚀 $100,000 Goal",
            "template": "Want to reach $100,000?\n\n📈 With 10% monthly compound interest:\n• Start with ${start_amount}\n• Time needed: {years_to_100k} years\n• Monthly contribution: ${monthly_contribution}\n\nStart today and watch it grow!"
        },
        {
            "title": "🤝 Referral Income",
            "template": "If you refer 50 active traders:\n\n💰 You could earn ${referral_income}/month in node fees!\n\n👥 Each active trader generates ~${per_trader}/month\n\nShare your referral code: {referral_code}"
        },
        {
            "title": "📈 $10 Growth Projection",
            "template": "Starting with just $10:\n\n📊 After 5 years with 10% monthly compound interest:\n• Year 1: ${year1}\n• Year 2: ${year2}\n• Year 3: ${year3}\n• Year 4: ${year4}\n• Year 5: ${year5}\n\nImagine what ${grand_balance} could become!"
        },
        {
            "title": "💵 How to Deposit",
            "template": "📝 To deposit USDC:\n\n1️⃣ Go to Wallet → Deposit\n2️⃣ Copy the BSC (BEP-20) address\n3️⃣ Send minimum $10 USDC\n4️⃣ Submit transaction hash\n\n⏰ Deposits credited within 24 hours"
        },
        {
            "title": "📊 Portfolio Performance",
            "template": "Your portfolio: ${portfolio_value}\n\n📈 24h Change: {daily_change}\n\n💪 Top holding: {top_holding}\n\nKeep diversifying!"
        },
        {
            "title": "⚡ AI Trading Update",
            "template": "🤖 AI Grid Bot executed {trades_today} trades in the last 24 hours!\n\n📊 Grid profit: ${grid_profit}\n\n🎯 Current grid level: {grid_level}/100\n\nYour AI is working 24/7!"
        },
        {
            "title": "🏆 Top Earners This Week",
            "template": "🏅 Weekly Leaderboard:\n1️⃣ {top1}: ${earn1}\n2️⃣ {top2}: ${earn2}\n3️⃣ {top3}: ${earn3}\n\nYou're at position #{user_rank} with ${user_earnings}\n\nInvite more to climb the ranks!"
        },
        {
            "title": "📅 Compounding Power",
            "template": "Did you know?\n\n🧮 With 10% monthly compound interest:\n• Your money doubles every ~7.3 months\n• In 5 years, $1,000 becomes ${future_value}\n• In 10 years, $1,000 becomes ${future_value_10}\n\nTime is your greatest asset!"
        },
        {
            "title": "💎 Yield Wallet Tips",
            "template": "💡 Your Yield Wallet: ${yield_balance}\n\n✨ You can:\n• Withdraw anytime to Grand Wallet\n• Reinvest to compound returns\n• Use for more trading\n\nCurrent yield rate: 10% monthly"
        },
        {
            "title": "🔄 Referral Program",
            "template": "🤝 Your referral code: {referral_code}\n\n💰 Each friend who joins earns you:\n• Level 1 (direct): 50% of node fee\n• Up to 7 levels deep!\n\nShare your link: https://www.nodevt.com/register?ref={referral_code}"
        },
        {
            "title": "📊 Daily Trading Volume",
            "template": "📈 24h Trading Volume: ${daily_volume}\n\n🔄 Buy/Sell Ratio: {buy_sell_ratio}\n\n🔥 Most traded: {top_traded_token}\n\nMarket is {market_sentiment}!"
        },
        {
            "title": "🎯 Your Next Milestone",
            "template": "Next target: ${next_target}\n\n📊 Current: {grand_balance}\n\n🚀 Need: ${needed_to_target}\n\n💪 You're {progress_to_target}% there!\n\nKeep going!"
        },
        {
            "title": "💰 Passive Income Report",
            "template": "📊 Your passive income this month:\n\n• Yield earnings: ${yield_earned}\n• Referral commissions: ${referral_earned}\n• AI trading profits: ${grid_earned}\n\n💵 Total: ${total_passive}\n\nThat's ${per_day}/day without lifting a finger!"
        },
        {
            "title": "⚡ Market Opportunity",
            "template": "🔥 {token} is down {drop_percent}% in the last hour!\n\n🎯 This could be a buying opportunity:\n• AI Grid buys at every 1.2% dip\n• Your yield continues regardless\n\nSmart money accumulates during dips!"
        },
        {
            "title": "📈 Compound Interest Calculator",
            "template": "🧮 If you invest ${amount} today:\n\n• In 1 year: ${year1}\n• In 3 years: ${year3}\n• In 5 years: ${year5}\n• In 10 years: ${year10}\n\nStart small, think big!"
        },
        {
            "title": "🤖 AI Bot Performance",
            "template": "Your AI Grid Bot this week:\n\n✅ Trades executed: {bot_trades}\n💰 Profit: ${bot_profit}\n🎯 Win rate: {win_rate}%\n\nBot is actively trading for you 24/7!"
        },
        {
            "title": "💡 Tip of the Hour",
            "template": "💡 {tip}\n\n📊 Your current stats:\n• Balance: ${grand_balance}\n• Portfolio: ${portfolio_value}\n• Yield: ${hourly_yield}/hour\n\nApply this tip to maximize returns!"
        },
        {
            "title": "🌟 Weekly Summary",
            "template": "📊 Your Weekly Performance:\n\n• Starting balance: ${start_balance}\n• Current balance: {grand_balance}\n• Weekly growth: {weekly_growth}%\n• Yield earned: ${weekly_yield}\n\nGreat work! Keep it up! 🚀"
        }
    ]

    TIPS = [
        "The more tokens you hold, the higher your hourly yield!",
        "Reinvest your yield earnings to compound returns faster.",
        "Invite friends - each active trader adds to your passive income.",
        "Diversify across multiple tokens to spread risk.",
        "Set take-profit orders to lock in gains automatically.",
        "Check your portfolio daily to track progress.",
        "Withdraw yield to Grand Wallet for more trading power.",
        "The AI Grid works best in volatile markets - let it run!",
        "Every $1000 invested earns ~$100/month passive income.",
        "Node fee commissions are paid instantly - no waiting!"
    ]

    @classmethod
    def get_hourly_message(cls, hour, user_data):
        """Get message based on hour of day (0-23)"""
        message_index = hour % len(cls.MESSAGES)
        message = cls.MESSAGES[message_index]

        # Format the message with user data
        content = cls._format_message(message["template"], user_data)

        return {
            "title": message["title"],
            "message": content
        }

    @classmethod
    def _format_message(cls, template, data):
        """Format template with user data"""
        try:
            # Calculate various metrics
            hourly_yield = data.get('portfolio_value', 0) * 0.10 / 720
            daily_yield = hourly_yield * 24
            monthly_yield = hourly_yield * 720

            # Calculate referral income (assuming $10 average trade per referred user)
            referral_income = data.get('referral_count', 0) * 10 * 0.10 * 0.50

            # Calculate compound growth
            def compound_growth(principal, months):
                return principal * (1.10) ** months

            # Format all variables
            vars_dict = {
                'grand_balance': f"${data.get('grand_balance', 0):,.2f}",
                'yield_balance': f"${data.get('yield_balance', 0):,.2f}",
                'portfolio_value': f"${data.get('portfolio_value', 0):,.2f}",
                'hourly_yield': f"${hourly_yield:.4f}",
                'daily_yield': f"${daily_yield:.2f}",
                'monthly_yield': f"${monthly_yield:.2f}",
                'target': data.get('target', '1000'),
                'needed': f"${max(0, 1000 - data.get('grand_balance', 0)):.2f}",
                'remaining': f"${max(0, 1000 - data.get('grand_balance', 0)):.2f}",
                'needed_to_earn_50': f"${(50 * 30 / 0.10):.2f}",
                'progress_to_50': f"{(data.get('daily_yield', 0) / 50 * 100):.1f}",
                'total_market_cap': f"${data.get('total_market_cap', 5000000):,.0f}",
                'total_yield_paid': f"${data.get('total_yield_paid', 125000):,.0f}",
                'total_trades': f"{data.get('total_trades', 15000):,}",
                'start_amount': f"${data.get('grand_balance', 100):,.2f}",
                'years_to_100k': f"{compound_growth(data.get('grand_balance', 100), 12) / 100000:.1f}",
                'monthly_contribution': f"${max(0, (100000 - data.get('grand_balance', 0)) / 60):.2f}",
                'referral_income': f"${referral_income:.2f}",
                'per_trader': f"${referral_income / max(1, data.get('referral_count', 0)):.2f}",
                'referral_code': data.get('referral_code', 'N/A'),
                'year1': f"${compound_growth(10, 12):.2f}",
                'year2': f"${compound_growth(10, 24):.2f}",
                'year3': f"${compound_growth(10, 36):.2f}",
                'year4': f"${compound_growth(10, 48):.2f}",
                'year5': f"${compound_growth(10, 60):.2f}",
                'daily_change': f"+{(data.get('daily_change', 2.5)):.1f}%",
                'top_holding': data.get('top_holding', 'BTC'),
                'trades_today': f"{data.get('trades_today', 12)}",
                'grid_profit': f"${data.get('grid_profit', 25.50):.2f}",
                'grid_level': f"{data.get('grid_level', 47)}",
                'future_value': f"${compound_growth(1000, 60):,.2f}",
                'future_value_10': f"${compound_growth(1000, 120):,.2f}",
                'daily_volume': f"${data.get('daily_volume', 250000):,.0f}",
                'buy_sell_ratio': f"{data.get('buy_sell_ratio', '1.2:1')}",
                'top_traded_token': data.get('top_traded_token', 'BTC'),
                'market_sentiment': data.get('market_sentiment', 'Bullish 📈'),
                'next_target': f"${data.get('next_target', 500):,.0f}",
                'needed_to_target': f"${max(0, data.get('next_target', 500) - data.get('grand_balance', 0)):.2f}",
                'progress_to_target': f"{(data.get('grand_balance', 0) / data.get('next_target', 500) * 100):.1f}",
                'yield_earned': f"${data.get('yield_earned', monthly_yield):.2f}",
                'referral_earned': f"${data.get('referral_earned', 25.00):.2f}",
                'grid_earned': f"${data.get('grid_earned', 50.00):.2f}",
                'total_passive': f"${data.get('total_passive', monthly_yield + 25 + 50):.2f}",
                'per_day': f"${(monthly_yield + 25 + 50) / 30:.2f}",
                'token': data.get('token', 'BTC'),
                'drop_percent': f"{data.get('drop_percent', 3.5):.1f}",
                'amount': f"${data.get('grand_balance', 100):.2f}",
                'year1_compound': f"${compound_growth(data.get('grand_balance', 100), 12):.2f}",
                'year3_compound': f"${compound_growth(data.get('grand_balance', 100), 36):.2f}",
                'year5_compound': f"${compound_growth(data.get('grand_balance', 100), 60):.2f}",
                'year10_compound': f"${compound_growth(data.get('grand_balance', 100), 120):.2f}",
                'bot_trades': f"{data.get('bot_trades', 45)}",
                'bot_profit': f"${data.get('bot_profit', 125.00):.2f}",
                'win_rate': f"{data.get('win_rate', 68)}",
                'tip': random.choice(cls.TIPS),
                'start_balance': f"${data.get('start_balance', data.get('grand_balance', 0)):.2f}",
                'weekly_growth': f"{data.get('weekly_growth', 3.5):.1f}",
                'weekly_yield': f"${monthly_yield / 4:.2f}",
            }

            # Replace all placeholders
            for key, value in vars_dict.items():
                template = template.replace(f'{{{key}}}', str(value))

            return template
        except Exception as e:
            return f"📊 Your balance: ${data.get('grand_balance', 0):.2f}\nContinue trading to grow your portfolio!"