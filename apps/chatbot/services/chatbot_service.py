from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random


class ChatbotService:
    """Intelligent chatbot with 60+ FAQs and keyword-based intent matching"""

    # Comprehensive FAQ database with keywords and responses
    FAQS = [
        # ============ DEPOSITS ============
        {
            "keywords": ["deposit", "add funds", "send usdc", "fund account", "how to deposit", "funding", "add money"],
            "response": """📥 **How to Deposit USDC**

**Step 1:** Go to the **Deposit** page
**Step 2:** Copy your unique BSC wallet address
**Step 3:** Send USDC from any BSC wallet (Binance, MetaMask, Trust Wallet)
**Step 4:** Deposit detected automatically within 5 minutes

⚠️ **Important:**
• Network: **BSC (BEP20)** only
• Token: **USDC** only
• Minimum: **$10 USDC**
• No manual submission needed — it's automatic!

💡 Your deposit address is unique to you. Never share it publicly."""
        },
        {
            "keywords": ["deposit time", "how long deposit", "deposit pending", "deposit not showing", "deposit delay",
                         "where is my deposit"],
            "response": """⏰ **Deposit Processing Time**

Deposits are detected **automatically within 5 minutes** of confirmation on BSC.

**Timeline:**
• 0-1 min: Transaction submitted on BSC
• 1-3 min: BSC confirmation (12 blocks)
• 3-5 min: Auto-detected and credited to your Grand Balance

🔍 If it's been more than 10 minutes:
• Check the transaction on BSCScan
• Ensure you used BSC (BEP20) network
• Verify the correct wallet address
• Contact support if still pending

No admin approval needed — fully automatic!"""
        },
        {
            "keywords": ["deposit min", "minimum deposit", "min deposit", "smallest deposit", "deposit requirement"],
            "response": """💵 **Minimum Deposit: $10 USDC**

• Minimum: **$10 USDC**
• Maximum: No limit
• Network: BSC (BEP20)
• Fee: None (platform charges no deposit fee)
• Processing: Automatic (within 5 minutes)

💡 Start with as little as $10 to test the platform!"""
        },
        {
            "keywords": ["deposit address", "my wallet", "my address", "where to send", "wallet address",
                         "bsc address"],
            "response": """🔑 **Your Deposit Address**

Every user gets a **unique BSC wallet address** generated just for you.

📍 Find it on the **Deposit** page or in your **Profile**.

Key points:
• It's a real BSC address (not shared)
• All deposits go directly to your Grand Balance
• Your address is permanent — use it anytime
• Never share your private key with anyone

Need to see it? Go to Deposit page now!"""
        },
        {
            "keywords": ["wrong network", "wrong chain", "erc20", "trc20", "sent wrong", "lost funds", "recover"],
            "response": """⚠️ **Wrong Network = Lost Funds**

If you sent USDC on the wrong network (ERC20, TRC20, etc.):

Unfortunately, funds sent on wrong networks **cannot be recovered** by the platform.

🚨 **Always use BSC (BEP20) network!**

**Recovery options (limited):**
• If you control the sending wallet, you may have the private key to the same address on BSC
• BSC addresses are compatible with Ethereum addresses
• Contact the sending exchange/wallet support

**Prevention:**
✅ Always double-check "BSC" or "BEP20" before sending
✅ Send a small test amount first ($10)"""
        },

        # ============ WITHDRAWALS ============
        {
            "keywords": ["withdraw", "cash out", "withdrawal", "take out", "send to wallet", "how to withdraw"],
            "response": """🏦 **How to Withdraw USDC**

**Step 1:** Go to **Withdraw** page
**Step 2:** Enter your external BSC wallet address (starts with 0x)
**Step 3:** Enter amount (minimum $10)
**Step 4:** Click **Withdraw**

⚡ Processing is **instant and automatic** via Binance API.

**Requirements:**
• Minimum: $10 USDC
• Maximum: $10,000 per transaction
• Network: BSC (BEP20)
• Processing: 1-10 minutes
• No admin approval needed!

💰 Funds sent directly from the platform's central wallet to yours."""
        },
        {
            "keywords": ["withdraw time", "withdrawal time", "how long withdraw", "withdraw pending",
                         "when will i receive"],
            "response": """⏰ **Withdrawal Processing Time**

Withdrawals are **instant and automatic** — no admin approval needed!

**Timeline:**
• Instant: Amount deducted from Grand Balance
• 1-5 min: Transaction broadcast on BSC
• 1-10 min: Funds arrive in your wallet

🚀 Most withdrawals complete within 5 minutes.

If it takes longer:
• Check the TX ID on BSCScan
• Ensure your wallet supports BSC (BEP20) USDC
• Contact support if pending over 30 minutes"""
        },
        {
            "keywords": ["withdraw min", "minimum withdraw", "min withdrawal"],
            "response": """💵 **Minimum Withdrawal: $10 USDC**

• Minimum: **$10 USDC**
• Maximum: **$10,000** per transaction
• Fee: **Free** (platform covers network fee)
• Network: BSC (BEP20)

Need to withdraw less? Your balance stays safe until you reach $10."""
        },

        # ============ TRADING ============
        {
            "keywords": ["buy", "purchase", "how to buy", "buy token", "buy crypto", "buy btc", "buy eth"],
            "response": """🛒 **How to Buy Tokens**

**Market Order (Spot):**
1. Go to **Trading** page
2. Select your token (BTC, ETH, SOL, etc.)
3. Choose **Market Order** tab
4. Enter amount in USDC
5. Click **Buy**

📊 **Fee:** 1% for market orders
✅ Tokens appear in Portfolio instantly
✅ Sell anytime at market price

**Grid Bot (Automated):**
1. Choose **Spot Grid Bot** tab
2. Enter investment amount (min $10)
3. Click **Activate Grid Bot**

🤖 Bot trades automatically 24/7
📊 Fee: 10% (includes yield & referrals)
🌟 Earns hourly yield on investment"""
        },
        {
            "keywords": ["sell", "how to sell", "sell token", "sell crypto", "cash out token", "sell btc"],
            "response": """📉 **How to Sell Tokens**

**Spot Selling (Market Order):**
1. Go to **Trading** page
2. Select the token you own
3. Enter USDC amount to sell
4. Click **Sell Market**

✅ Sell anytime — no price restrictions
✅ Funds go to Grand Balance instantly
✅ Withdraw to external wallet anytime

💡 **Pro Tip:** Monitor your PNL in Portfolio to choose the right time to sell."""
        },
        {
            "keywords": ["grid bot", "spot grid", "automated trading", "bot trading", "grid trading", "activate bot"],
            "response": """🤖 **Spot Grid Bot — Automated Trading**

A Grid Bot automatically buys low and sells high within a price range.

**How it works:**
1. You set an investment amount (min $10)
2. Bot creates 100 grid orders between -80% and +80% of current price
3. Bot trades automatically 24/7
4. You earn hourly yield on the investment

**Benefits:**
🌟 Earns **10% monthly yield** on current value
💰 Profit from market volatility automatically
😴 No need to watch charts — fully automated

**Fee:** 10% (distributed to referrals + platform)

Activate one on the Trading page!"""
        },
        {
            "keywords": ["market order", "spot buy", "instant buy", "buy now"],
            "response": """📊 **Market Order (Spot Buy)**

Buy tokens instantly at the current market price.

**How it works:**
1. Select token on Trading page
2. Choose **Market Order** tab
3. Enter USDC amount
4. Click **Buy**

✅ Instant execution
✅ Tokens go to your Portfolio
✅ Sell anytime
📊 Fee: Only 1%

Best for: Quick purchases you want to hold or sell later."""
        },
        {
            "keywords": ["fee", "node fee", "charge", "cost", "trading fee", "how much fee", "commission"],
            "response": """💸 **Fee Structure**

| Order Type | Fee |
|-----------|-----|
| Market Order (Spot) | **1%** |
| Grid Bot Activation | **10%** |

**No fees for:**
• Deposits ✅
• Withdrawals ✅
• Selling tokens ✅
• Yield collection ✅
• Referral earnings ✅

**Where does the 10% go?**
• Distributed to your referrers (up to 7 levels)
• 50% to direct referrer, scaling down
• Remaining goes to platform operations"""
        },

        # ============ YIELD ============
        {
            "keywords": ["yield", "earn", "passive income", "hourly earn", "interest", "how to earn", "passive"],
            "response": """🌟 **Yield Earnings — Passive Income**

Earn passive income hourly on your active Grid Bots!

**How it works:**
• Each active Grid Bot earns **10% monthly yield** on its current value
• Yield is calculated: `current_value × 10% ÷ 720 hours`
• The more your bot is worth, the more you earn
• Yield accrues automatically every hour

**Example:**
• $100 bot → ~$0.014/hour → ~$10/month
• $1,000 bot → ~$0.14/hour → ~$100/month

💰 **Collect your profit** anytime from the Dashboard!"""
        },
        {
            "keywords": ["collect yield", "claim yield", "withdraw yield", "move yield", "grid profit",
                         "collect profit"],
            "response": """💎 **How to Collect Grid Profit**

1. Go to **Dashboard**
2. Find your active Grid Bot card
3. Click the **Grid Profit** amount (it's clickable!)
4. Click **"Collect to Yield Wallet"**

The profit moves from the bot to your **Yield Wallet**.

Then from Yield Wallet:
• Must be ≥ **10% of your portfolio** to transfer to Grand Balance
• Go to Dashboard → Yield Wallet → Transfer

💡 This prevents you from withdrawing small amounts frequently."""
        },
        {
            "keywords": ["yield rate", "how much yield", "yield percentage", "monthly yield", "yield calculation"],
            "response": """📊 **Yield Rate: 10% Monthly**

• Monthly rate: **10%**
• Hourly rate: **0.0139%** (10% ÷ 720 hours)
• Calculated on current bot value (investment + profit + PNL)

**Formula:**
`Hourly Yield = Current Bot Value × 0.00013888...`

**Examples:**
| Bot Value | Hourly | Daily | Monthly |
|-----------|--------|-------|---------|
| $100 | $0.014 | $0.33 | $10 |
| $500 | $0.069 | $1.67 | $50 |
| $1,000 | $0.139 | $3.33 | $100 |

📈 Yield compounds as your bot value grows!"""
        },

        # ============ REFERRALS ============
        {
            "keywords": ["referral", "refer", "invite", "commission", "referral code", "share", "friend"],
            "response": """🤝 **Referral Program — Earn by Sharing!**

Share your unique referral link and earn commissions when your referrals trade.

**How it works:**
1. Get your referral link from **Profile** or **Referral** page
2. Share with friends
3. When they activate a Grid Bot, you earn from the 10% node fee

**Commission Structure (7 levels):**
| Level | You Earn |
|-------|----------|
| 1 (Direct) | 50% of node fee |
| 2 | 25% |
| 3 | 12.5% |
| 4 | 6.25% |
| 5 | 3.125% |
| 6 | 1.5625% |
| 7 | 0.78125% |

💰 **Example:** Friend buys $1000 Grid Bot → $100 node fee → You earn $50!"""
        },
        {
            "keywords": ["referral code", "my referral", "where is my code", "share link"],
            "response": """🔗 **Your Referral Code**

Find it on your **Profile** page or **Referral** page.

Your unique link looks like:
`https://www.nodevt.com/register?ref=XXXXX`

Share this link with friends. When they register and activate a Grid Bot, you earn commissions automatically!

📤 Share via:
• Social media
• Messaging apps
• Email
• Your website or blog"""
        },
        {
            "keywords": ["referral earning", "referral commission", "how much referral", "referral income"],
            "response": """💰 **Referral Earnings**

You earn commissions when your referrals activate Grid Bots (10% fee).

**Example earnings per referral:**
| Their Investment | Node Fee | Your Commission (L1) |
|-----------------|----------|----------------------|
| $100 | $10 | $5.00 |
| $500 | $50 | $25.00 |
| $1,000 | $100 | $50.00 |

Commissions are credited **instantly** to your Grand Balance.

📊 Track your referrals on the **Referral** page!"""
        },

        # ============ ACCOUNT ============
        {
            "keywords": ["balance", "my balance", "how much", "check balance", "grand balance"],
            "response": """💰 **Check Your Balance**

Your balances are visible on multiple pages:

• **Dashboard** — Grand, Yield, Portfolio, Total Value
• **Profile** — Quick stats
• **Trading page** — Available balance

**Wallet types:**
💳 **Grand Balance** — For trading, deposits, withdrawals
💎 **Yield Wallet** — Grid profit collections (transfer to Grand when ≥10% portfolio)
📦 **Portfolio** — Spot tokens from market orders"""
        },
        {
            "keywords": ["portfolio", "my token", "holdings", "what do i own", "my assets"],
            "response": """📦 **Your Portfolio**

View your spot token holdings on the **Portfolio** page.

Shows for each token:
• Quantity held
• Average buy price
• Current market price
• Total value
• Profit/Loss (PNL)

Green PNL = profit 📈
Red PNL = loss 📉

Only **Market Order** purchases appear here. Grid Bots are on the Dashboard."""
        },
        {
            "keywords": ["change password", "reset password", "update password", "new password"],
            "response": """🔒 **Change Password**

1. Go to **Profile** page
2. Click **"Change"** next to Password
3. Enter current password
4. Enter new password
5. Confirm new password
6. Click **Update**

Password must be strong and secure. You'll be logged out after changing."""
        },
        {
            "keywords": ["edit profile", "update email", "change email", "change username", "profile settings"],
            "response": """👤 **Edit Profile**

1. Go to **Profile** page
2. Update your email or username
3. Click **Save**

Your referral code cannot be changed.
Profile picture can be uploaded by clicking the avatar."""
        },
        {
            "keywords": ["delete account", "close account", "remove account"],
            "response": """⚠️ **Delete Account**

Go to Profile → **Danger Zone** → **Delete Account**

This permanently removes:
• All your data
• Token holdings (sell first!)
• Balance (withdraw first!)

Type "DELETE" to confirm. This action is irreversible."""
        },

        # ============ PLATFORM ============
        {
            "keywords": ["how it works", "platform", "node", "node ai", "what is node", "about"],
            "response": """🚀 **About NODE AI Autotrader**

NODE is a crypto trading platform with automated grid trading.

**What we offer:**
🤖 **Grid Bots** — Automated 24/7 trading
📊 **Spot Trading** — Buy & hold tokens
🌟 **Passive Yield** — 10% monthly on bots
🤝 **Referrals** — Earn from 7 levels
⏰ **Fully Automated** — Deposits & withdrawals

**How to start:**
1. Register (get $10 welcome bonus)
2. Deposit USDC (min $10)
3. Activate a Grid Bot or buy spot tokens
4. Earn yield hourly
5. Refer friends for commissions"""
        },
        {
            "keywords": ["network", "bsc", "bep20", "blockchain", "which chain"],
            "response": """🌐 **Network: BSC (BEP20)**

All transactions use **Binance Smart Chain (BSC)**.

• Fast: 3-second block time
• Cheap: ~$0.10 gas fees
• Token: USDC (BEP20)
• Compatible with: MetaMask, Trust Wallet, Binance

⚠️ Always use BSC network for deposits and withdrawals.
Other networks (ERC20, TRC20) will result in lost funds."""
        },
        {
            "keywords": ["security", "safe", "is it safe", "secure", "trust"],
            "response": """🔒 **Platform Security**

• **Custodial wallets** — Each user gets a unique BSC address
• **Binance API** — Withdrawals processed via secure Binance API
• **Encrypted keys** — Private keys stored encrypted
• **Auto-refund** — Failed withdrawals automatically refunded
• **Audit trail** — Every transaction logged
• **No custody of funds** — Deposits swept to secure central wallet

Your funds are safe. Always keep your login credentials secure."""
        },
        {
            "keywords": ["support", "help", "contact", "issue", "problem", "bug", "report"],
            "response": """📞 **Need Support?**

• 💬 **Chat with me!** — I can answer most questions instantly
• 📧 **Email notifications** — Daily portfolio updates
• 📊 **Transparency page** — View all platform activity

For urgent issues, describe your problem and I'll help troubleshoot. Include:
• Your action (deposit, withdrawal, trade)
• Error message (if any)
• Time of issue"""
        },
        {
            "keywords": ["transparency", "proof", "audit", "verify", "platform activity"],
            "response": """🔍 **Platform Transparency**

Visit the **Transparency** page to see:
• Total platform users
• Platform balance
• Recent deposits & withdrawals
• Token holders
• Buy/Sell activity chart
• Community discussion

All data is real-time and public. User identities are anonymized."""
        },

        # ============ ERRORS ============
        {
            "keywords": ["error", "failed", "not working", "issue", "problem with", "stuck"],
            "response": """🔧 **Troubleshooting**

Common issues and solutions:

**Deposit not showing?**
• Wait 5 minutes for auto-detection
• Check BSCScan for confirmation
• Ensure BSC (BEP20) network was used

**Can't sell tokens?**
• Ensure you own the token (check Portfolio)
• Check you have enough quantity

**Withdrawal failed?**
• Funds are automatically refunded
• Check address format (must start with 0x)
• Minimum $10 required

Still stuck? Tell me exactly what error you see."""
        },
        {
            "keywords": ["insufficient", "not enough", "balance too low", "minimum not met"],
            "response": """⚠️ **Insufficient Balance**

This means you don't have enough USDC for this action.

**Solutions:**
• Deposit more USDC (min $10)
• Reduce the amount you're trying to use
• Check your Grand Balance on the Dashboard

💡 Remember:
• Minimum deposit: $10
• Minimum withdrawal: $10
• Minimum Grid Bot: $10"""
        },
        {
            "keywords": ["session", "logged out", "login again", "expired", "token"],
            "response": """🔐 **Session Expired**

Your login session has expired for security reasons.

**Solution:** Simply log in again. Your balances and data are safe.

Sessions expire after a period of inactivity to protect your account."""
        },

        # ============ BONUS TIPS ============
        {
            "keywords": ["best strategy", "strategy", "how to profit", "maximize", "best way"],
            "response": """🎯 **Best Strategy for NODE**

1. **Diversify** — Run multiple Grid Bots on different tokens
2. **Compound** — Collect grid profit and reinvest
3. **Hold spot** — Some tokens for long-term gains
4. **Refer** — Build your referral network for passive commissions
5. **Be patient** — Grid bots perform best over weeks/months

**Sample allocation:**
• 60% in Grid Bots (earn yield)
• 30% in spot tokens (growth)
• 10% in Grand Balance (ready to trade)"""
        },
        {
            "keywords": ["newbie", "beginner", "new user", "first time", "getting started", "start"],
            "response": """👋 **Welcome to NODE!**

**Quick start guide:**
1. ✅ **Registered?** Great! You have a unique wallet.
2. 💵 **Deposit** $10+ USDC on BSC network
3. 🛒 **Buy tokens** or activate a Grid Bot
4. 🌟 **Earn yield** every hour
5. 🤝 **Refer friends** for commissions

**Try this first:**
• Deposit $10
• Activate a $10 Grid Bot on BTC
• Watch it trade and earn hourly
• Collect your first profit!

Any questions? I'm here 24/7!"""
        },
        {
            "keywords": ["daily email", "email notification", "portfolio email", "daily update"],
            "response": """📧 **Daily Portfolio Emails**

Every day at 8 AM, you receive an email summary with:
• Grand Balance
• Yield Balance
• Spot holdings value
• Grid Bot value
• Total portfolio
• Active bots count

💡 Check your inbox daily to track progress!
📩 Emails come from: nodevt.notify@gmail.com"""
        },
        {
            "keywords": ["benefits", "why node", "advantage", "feature"],
            "response": """🌟 **Why NODE?**

• 🤖 **Automated Trading** — Grid Bots work 24/7
• 💰 **Passive Yield** — 10% monthly on bots
• 🚀 **Instant Withdrawals** — No admin approval
• 🤝 **7-Level Referrals** — Earn from your network
• 🔒 **Secure** — Encrypted wallets, Binance-backed
• 📊 **Transparent** — Public platform activity
• 📱 **Mobile Friendly** — Trade anywhere
• ⚡ **Auto Deposit Detection** — No manual claims"""
        },
        {
            "keywords": ["price", "token price", "current price", "btc price", "eth price"],
            "response": """📈 **Token Prices**

Real-time prices are available on the **Trading** page with live charts.

Prices update continuously from CoinGecko API.
Select any token to see:
• Current price
• 24h price change
• Interactive chart (24h, 7d, 30d, 90d, 1y)
• Order book
• Top 10 coins list"""
        },
        {
            "keywords": ["chart", "graph", "price chart", "trend"],
            "response": """📊 **Price Charts**

Available on the **Trading** page:

**Timeframes:**
• 24 hours
• 7 days
• 30 days
• 90 days
• 1 year

Click any timeframe button to switch. The chart updates automatically with live price data."""
        },
        {
            "keywords": ["pnl", "profit loss", "how much profit", "am i winning", "return"],
            "response": """📊 **Understanding PNL (Profit/Loss)**

**PNL = Current Value - Amount Invested**

• 🟢 **Positive PNL** = You're in profit
• 🔴 **Negative PNL** = Current price below your buy price

**Where to see PNL:**
• **Portfolio** — For spot tokens
• **Dashboard** — For Grid Bots

💡 PNL changes with market price. It's unrealized until you sell."""
        },
        {
            "keywords": ["compound", "compounding", "reinvest", "growth", "long term"],
            "response": """🧮 **Power of Compounding**

When you reinvest your yield, your earnings grow exponentially.

**Example: $100 at 10% monthly, reinvested:**
• Month 1: $110
• Month 3: $133
• Month 6: $177
• Month 12: $314
• Year 2: $985

💡 Use the **Compound Growth Projector** on the Dashboard to plan your goals!"""
        },

        # ============ FAQ SHORTCUTS ============
        {
            "keywords": ["hi", "hello", "hey", "good morning", "good evening", "sup"],
            "response": """👋 Hello! I'm your NODE assistant.

I can help with:
• 💰 Deposits & Withdrawals
• 🛒 Trading (Market & Grid Bot)
• 🌟 Yield Earnings
• 🤝 Referral Program
• 📊 Portfolio & Balance

What can I help you with today?"""
        },
        {
            "keywords": ["thanks", "thank you", "appreciate", "helpful", "great"],
            "response": """😊 You're welcome! Happy to help.

Is there anything else you'd like to know about NODE?

Happy trading! 🚀"""
        },
        {
            "keywords": ["bye", "goodbye", "see you", "later"],
            "response": """👋 Goodbye! I'm here anytime you need help.

Happy trading on NODE! 🚀"""
        },
    ]

    @classmethod
    def get_response(cls, user_message, user=None):
        """Get intelligent chatbot response based on keyword matching"""
        user_message = user_message.lower().strip()

        best_match = None
        best_score = 0

        # Score each FAQ based on keyword matches
        for faq in cls.FAQS:
            score = 0
            for keyword in faq["keywords"]:
                if keyword in user_message:
                    score += len(keyword)  # Longer keyword match = higher score

            if score > best_score:
                best_score = score
                best_match = faq

        if best_match and best_score > 0:
            response = best_match["response"]
            intent = best_match["keywords"][0]
            return response, intent

        # If no match, use personalized suggestions
        return cls.get_fallback_response(user_message, user), "fallback"

    @classmethod
    def get_fallback_response(cls, user_message, user=None):
        """Generate helpful fallback when no FAQ matches"""
        suggestions = [
            "📥 How to deposit USDC?",
            "🛒 How to buy tokens?",
            "🤖 What is a Grid Bot?",
            "🌟 How do I earn yield?",
            "🏦 How to withdraw?",
            "🤝 How does referral work?",
            "📊 Check my balance",
        ]

        response = f"""🤔 I'm not sure I understand "{user_message}".

**Try asking one of these:**
• {suggestions[0]}
• {suggestions[1]}
• {suggestions[2]}
• {suggestions[3]}
• {suggestions[4]}
• {suggestions[5]}
• {suggestions[6]}

Or type your question differently — I'm learning!"""

        return response

    @classmethod
    def get_quick_suggestions(cls):
        """Get quick suggestion buttons for the chatbot widget"""
        return [
            {"text": "🛒 How to buy?", "question": "How do I buy tokens?"},
            {"text": "💰 How to deposit?", "question": "How do I deposit USDC?"},
            {"text": "🤝 Referral program", "question": "How does referral work?"},
            {"text": "🌟 Yield earnings", "question": "How do I earn yield?"},
            {"text": "🏦 Withdraw funds", "question": "How to withdraw?"},
            {"text": "🤖 Grid Bot", "question": "What is a grid bot?"},
            {"text": "💸 Fees", "question": "What are the fees?"},
            {"text": "📊 My balance", "question": "Check my balance"},
        ]