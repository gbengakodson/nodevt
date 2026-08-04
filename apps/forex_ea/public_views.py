from rest_framework.views import APIView
from rest_framework.response import Response
from apps.tokens.models import CryptoToken
from apps.forex_ea.models import MarketWeather
from apps.trading.services.fadakka_service import FadakkaService
from django.utils.timezone import now

class MarketIntelligenceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        data = []

        # ----- Crypto / Stock assets using Fadakka -----
        # List of symbols we want to include (can be moved to settings later)
        watchlist = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'LINK', 'UNI', 'MATIC']
        tokens = CryptoToken.objects.filter(symbol__in=watchlist)

        for token in tokens:
            # Fadakka discount
            try:
                k = FadakkaService.get_fadakka_k(token.symbol)   # 99-week EMA
                if k:
                    discount = ((token.current_price - k) / k) * 100
                else:
                    discount = 0
            except Exception:
                discount = 0

            # Weather (if available)
            weather = MarketWeather.objects.filter(symbol=token.symbol, category='crypto').first()
            weather_label = weather.weather if weather else 'No data'
            trend = weather.trend if weather else 'NEUTRAL'

            data.append({
                'symbol': token.symbol,
                'name': token.name,
                'category': 'crypto',
                'price': float(token.current_price),
                'fadakka_discount': round(discount, 1),
                'weather': weather_label,
                'trend': trend,
            })

        # ----- Forex pairs (NodeV16 EA) -----
        forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDNGN']  # extend later
        for pair in forex_pairs:
            weather = MarketWeather.objects.filter(symbol=pair, category='forex').first()
            data.append({
                'symbol': pair,
                'name': pair,
                'category': 'forex',
                'price': None,
                'fadakka_discount': None,
                'weather': weather.weather if weather else 'No data',
                'trend': weather.trend if weather else 'NEUTRAL',
            })

        return Response(data)