from rest_framework.views import APIView
from rest_framework.response import Response
from apps.tokens.models import CryptoToken
from apps.forex_ea.models import MarketWeather
from apps.trading.services.fadakka_service import FadakkaService
from .models import DailyIntelligence
from datetime import date


class MarketIntelligenceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        data = []
        watchlist = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'LINK', 'UNI', 'MATIC']
        tokens = CryptoToken.objects.filter(symbol__in=watchlist)

        for token in tokens:
            # Fadakka discount
            try:
                k = FadakkaService.get_fadakka_k(token.symbol)
                discount = ((token.current_price - k) / k) * 100 if k else 0
            except Exception:
                discount = 0

            # Weather
            weather = MarketWeather.objects.filter(symbol=token.symbol, category='crypto').first()
            weather_label = weather.weather if weather else 'No data'
            trend = weather.trend if weather else 'NEUTRAL'

            data.append({
                'id': str(token.id),
                'symbol': token.symbol,
                'name': token.name,
                'current_price': float(token.current_price),
                'change_24h': float(token.change_24h) if token.change_24h else 0,
                'market_cap': float(token.market_cap) if token.market_cap else 0,
                'fadakka_discount': round(discount, 1),
                'weather': weather_label,
                'trend': trend,
            })

        return Response(data)



class DailyIntelligenceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        today = date.today()
        items = DailyIntelligence.objects.filter(created_at=today)
        data = [{
            'symbol': i.symbol,
            'category': i.category,
            'caption': i.caption,
            'trend': i.trend,
            'image_url': i.image_url,
            'name': i.symbol,           # display name (can be expanded)
        } for i in items]
        return Response(data)


class FadakkaDiscountsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'LINK', 'UNI', 'MATIC', 'AVAX', 'DOT', 'LTC', 'NEAR', 'ATOM', 'ALGO', 'VET', 'FTM', 'EGLD', 'THETA']
        data = {}
        for sym in symbols:
            token = CryptoToken.objects.filter(symbol=sym).first()
            if not token:
                continue
            k = FadakkaService.get_fadakka_k(sym)
            if k and k > 0:
                discount = ((token.current_price - k) / k) * 100
                data[sym] = {
                    'discount': round(discount, 1),
                    'fair_value': float(k)
                }
            else:
                data[sym] = None
        return Response(data)