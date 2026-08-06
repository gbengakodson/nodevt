import logging
from django.utils import timezone
from datetime import date
from .models import DailyIntelligence, MarketWeather
from apps.tokens.models import CryptoToken

logger = logging.getLogger(__name__)

def generate_daily_intelligence_if_needed():
    """Daily cards are now posted manually. Auto‑generation disabled."""
    return

def generate_daily_forecast_cards():
    from .models import ForexForecast, DailyIntelligence
    from datetime import date
    today = date.today()
    forecasts = ForexForecast.objects.filter(created_at__date=today)

    for f in forecasts:
        # Simple prediction caption
        if 'Bullish' in f.trend:
            prediction = 'Bullish'
        elif 'Bearish' in f.trend:
            prediction = 'Bearish'
        else:
            prediction = 'Neutral'

        caption = f"{f.pair}: {prediction} – {f.trigger}"

        DailyIntelligence.objects.update_or_create(
            symbol=f.pair,
            category='forex',
            created_at__date=today,
            defaults={
                'caption': caption,
                'trend': f.trend.replace(' ', '')[:20].upper(),
                'image_url': None   # we can add chart thumbnails later
            }
        )