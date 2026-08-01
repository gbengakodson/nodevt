from django.urls import path
from .api_views import (
    AuthenticateView, BalanceView, ReportTradeView,
    ForexProfileView, ActivateForexView
)

urlpatterns = [
    path('authenticate/', AuthenticateView.as_view(), name='ea_authenticate'),
    path('balance/', BalanceView.as_view(), name='ea_balance'),
    path('report-trade/', ReportTradeView.as_view(), name='ea_report_trade'),
    path('profile/', ForexProfileView.as_view(), name='ea_profile'),
    path('activate/', ActivateForexView.as_view(), name='ea_activate'),
]