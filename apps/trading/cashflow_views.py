from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from apps.wallets.models import Transaction
from decimal import Decimal

TEST_ACCOUNTS = [
    'trading@qualityservice.com',
    'mtcnetwork2020@gmail.com',
    'soludero2017@gmail.com',
    'nodevt.notify@gmail.com',
    'gbengha2016@gmail.com',
]

INCOMING_TYPES = ['PURCHASE']
OUTGOING_TYPES = ['GRID_CLOSE', 'REFERRAL', 'YIELD_WITHDRAW', 'PURSE_WITHDRAW', 'SWEEP']

class CashflowAuditView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from collections import defaultdict

        incoming_monthly = Transaction.objects.filter(
            transaction_type__in=INCOMING_TYPES
        ).exclude(user__email__in=TEST_ACCOUNTS).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')

        outgoing_monthly = Transaction.objects.filter(
            transaction_type__in=OUTGOING_TYPES
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')

        data = defaultdict(lambda: {'incoming': 0, 'outgoing': 0})

        for row in incoming_monthly:
            data[row['month']]['incoming'] = float(row['total'] or 0)

        for row in outgoing_monthly:
            data[row['month']]['outgoing'] = float(row['total'] or 0)

        months = sorted(data.keys())
        labels = [m.strftime('%b %Y') for m in months]
        incoming = [data[m]['incoming'] for m in months]
        outgoing = [data[m]['outgoing'] for m in months]

        total_incoming = sum(incoming)
        total_outgoing = sum(outgoing)

        return Response({
            'labels': labels,
            'incoming': incoming,
            'outgoing': outgoing,
            'total_incoming': total_incoming,
            'total_outgoing': total_outgoing,
        })