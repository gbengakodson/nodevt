from django.urls import path
from apps.wallets.views import (
    SubmitDepositRequestView,
    SubmitWithdrawalRequestView,
    AdminDepositRequestsView,
    AdminWithdrawalRequestsView,
    AdminStatisticsView,           # New import
    AdminHoldersView,              # New import
    AdminBuySellActivityView
)

urlpatterns = [
    path('deposit-request/', SubmitDepositRequestView.as_view(), name='deposit_request'),
    path('withdrawal-request/', SubmitWithdrawalRequestView.as_view(), name='withdrawal_request'),
    path('admin/deposits/', AdminDepositRequestsView.as_view(), name='admin_deposits'),
    path('admin/withdrawals/', AdminWithdrawalRequestsView.as_view(), name='admin_withdrawals'),

    # Add to wallets/urls.py
    path('admin/statistics/', AdminStatisticsView.as_view(), name='admin_statistics'),
    path('admin/holders/', AdminHoldersView.as_view(), name='admin_holders'),
    path('admin/buy-sell-activity/', AdminBuySellActivityView.as_view(), name='admin_buy_sell'),
]