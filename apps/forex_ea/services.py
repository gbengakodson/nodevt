import logging
from django.utils import timezone
from datetime import date
from .models import DailyIntelligence, MarketWeather
from apps.tokens.models import CryptoToken

logger = logging.getLogger(__name__)

def generate_daily_intelligence_if_needed():
    """Daily cards are now posted manually. Auto‑generation disabled."""
    return