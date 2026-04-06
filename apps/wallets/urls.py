# wallets/urls.py
from django.urls import path
from .views import (
    SubmitDepositRequestView,
    SubmitWithdrawalRequestView,
    AdminDepositRequestsView,
    AdminWithdrawalRequestsView
)

urlpatterns = [
    path('deposit-request/', SubmitDepositRequestView.as_view(), name='deposit_request'),
    path('withdrawal-request/', SubmitWithdrawalRequestView.as_view(), name='withdrawal_request'),
    path('admin/deposits/', AdminDepositRequestsView.as_view(), name='admin_deposits'),
    path('admin/withdrawals/', AdminWithdrawalRequestsView.as_view(), name='admin_withdrawals'),
]