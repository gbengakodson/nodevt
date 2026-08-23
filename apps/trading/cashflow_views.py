from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from apps.wallets.models import Transaction
from decimal import Decimal

INCOMING_TYPES = ['PURCHASE']
OUTGOING_TYPES = ['GRID_CLOSE', 'REFERRAL', 'YIELD_WITHDRAW', 'PURSE_WITHDRAW', 'SWEEP']

class CashflowAuditView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Group by month
        monthly = Transaction.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(
            incoming=Sum('amount', filter=Q(transaction_type__in=INCOMING_TYPES)),
            outgoing=Sum('amount', filter=Q(transaction_type__in=OUTGOING_TYPES)),
        ).order_by('month')

        labels = []
        incoming = []
        outgoing = []

        for row in monthly:
            labels.append(row['month'].strftime('%b %Y'))
            incoming.append(float(row['incoming'] or 0))
            outgoing.append(float(row['outgoing'] or 0))

        total_incoming = Transaction.objects.filter(transaction_type__in=INCOMING_TYPES).aggregate(s=Sum('amount'))[
                             's'] or 0
        total_outgoing = Transaction.objects.filter(transaction_type__in=OUTGOING_TYPES).aggregate(s=Sum('amount'))[
                             's'] or 0

        return Response({
            'labels': labels,
            'incoming': incoming,
            'outgoing': outgoing,
            'total_incoming': float(total_incoming),
            'total_outgoing': float(total_outgoing),
        })