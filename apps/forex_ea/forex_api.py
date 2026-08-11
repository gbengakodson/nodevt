from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ForexCache, ForexForecast

class ForexDailyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        pair = request.GET.get("pair", "").upper()
        if not pair:
            return Response({"error": "No pair provided"}, status=400)

        data = ForexCache.objects.filter(symbol=pair).order_by('-date')[:30]
        if not data.exists():
            return Response({"error": "No data found"}, status=404)

        result = []
        for row in reversed(data):
            result.append({
                "date": row.date.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
            })

        current_price = float(data[0].close)
        return Response({
            "pair": pair,
            "current_price": current_price,
            "data": result,
        })


class ForexForecastDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        pair = request.GET.get('pair', '').upper()
        if not pair:
            return Response({'error': 'No pair'}, status=400)
        forecast = ForexForecast.objects.filter(pair=pair).order_by('-created_at').first()
        if not forecast:
            return Response({'error': 'Not found'}, status=404)

        return Response({
            'pair': forecast.pair,
            'current_price': float(forecast.current_price),
            'trend': forecast.trend,
            'condition': forecast.condition,
            'trigger': forecast.trigger,
            'daily_candle': forecast.daily_candle,
        })