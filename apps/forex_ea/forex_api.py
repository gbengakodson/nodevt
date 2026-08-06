from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ForexCache

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