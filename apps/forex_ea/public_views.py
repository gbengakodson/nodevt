from rest_framework.views import APIView
from rest_framework.response import Response
from apps.tokens.models import CryptoToken
from apps.forex_ea.models import MarketWeather
from apps.trading.services.fadakka_service import FadakkaService
from .models import DailyIntelligence
from datetime import date
from rest_framework.permissions import AllowAny, IsAuthenticated


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
        items = DailyIntelligence.objects.filter(created_at__date=today)
        data = [{
            'symbol': i.symbol,
            'category': i.category,
            'caption': i.caption,
            'trend': i.trend,
            'image_url': i.image_url,
            'name': i.symbol,
            'created_at': i.created_at.isoformat() if i.created_at else None   # ← new
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


from .models import CoinReaction
from django.db.models import Count

class CoinReactionView(APIView):
    """Handle like/love toggling (requires login)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        symbol = request.data.get('symbol')
        reaction = request.data.get('reaction')   # 'like' or 'love'
        if not symbol or reaction not in ('like', 'love'):
            return Response({'error': 'Invalid'}, status=400)

        obj, created = CoinReaction.objects.get_or_create(
            user=request.user, coin_symbol=symbol, reaction=reaction
        )
        if not created:
            obj.delete()   # toggle off

        # Return updated counts for this coin
        likes = CoinReaction.objects.filter(coin_symbol=symbol, reaction='like').count()
        loves = CoinReaction.objects.filter(coin_symbol=symbol, reaction='love').count()
        return Response({'symbol': symbol, 'likes': likes, 'loves': loves})


class CoinReactionCountsView(APIView):
    """Public: get reaction counts for all coins."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'LINK', 'UNI', 'MATIC', 'AVAX', 'DOT', 'LTC', 'NEAR', 'ATOM', 'ALGO', 'VET', 'FTM', 'EGLD', 'THETA']
        counts = {}
        for sym in symbols:
            likes = CoinReaction.objects.filter(coin_symbol=sym, reaction='like').count()
            loves = CoinReaction.objects.filter(coin_symbol=sym, reaction='love').count()
            counts[sym] = {'likes': likes, 'loves': loves}
        return Response(counts)