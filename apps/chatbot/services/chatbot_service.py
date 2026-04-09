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
   `0x3183f4c0a08D91717127534cFeF0ABDF320D2ca4`
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

**Platform Wallet:** `0x3183f4c0a08D91717127534cFeF0ABDF320D2ca4`

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