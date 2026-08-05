import logging
from django.utils import timezone
from datetime import date
from .models import DailyIntelligence, MarketWeather
from apps.tokens.models import CryptoToken

logger = logging.getLogger(__name__)

def generate_daily_intelligence_if_needed():
    """Create today's intelligence cards if they don't exist yet."""
    today = date.today()
    if DailyIntelligence.objects.filter(created_at=today).exists():
        return  # already generated for today

    # ── Forex cards (from MarketWeather / EA) ──
    forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDNGN']
    for pair in forex_pairs:
        weather = MarketWeather.objects.filter(symbol=pair, category='forex').first()
        caption = f"{weather.weather} – {weather.trend}" if weather else "No data"
        trend = weather.trend if weather else 'CONSOLIDATION'
        DailyIntelligence.objects.create(
            symbol=pair,
            category='forex',
            caption=caption,
            trend=trend,
            image_url=None   # can add a chart image later
        )

    # ── Crypto cards (Fadakka discount) ──
    crypto_watch = ['BTC', 'ETH', 'BNB', 'SOL']
    for sym in crypto_watch:
        token = CryptoToken.objects.filter(symbol=sym).first()
        if not token:
            continue
        # Compute discount (you can replace with FadakkaService later)
        # For MVP, use a simple placeholder: 10% random discount
        import random
        discount = random.randint(-30, 5)   # placeholder
        if discount <= -20:
            caption = f"Deep Discount {discount}%"
            trend = 'UPTREND'   # oversold may rebound
        elif discount >= 20:
            caption = f"Overvalued +{discount}%"
            trend = 'DOWNTREND'
        else:
            caption = "Fair Value"
            trend = 'CONSOLIDATION'
        DailyIntelligence.objects.create(
            symbol=sym,
            category='crypto',
            caption=caption,
            trend=trend,
            image_url=None
        )

    # ── Economic cards (placeholder until economic cycle algorithm is ready) ──
    econ_countries = ['NGN', 'US', 'CN']
    for country in econ_countries:
        DailyIntelligence.objects.create(
            symbol=country,
            category='economic',
            caption="Data pending",
            trend='CONSOLIDATION',
            image_url=None
        )

    logger.info(f"Daily intelligence generated for {today}")