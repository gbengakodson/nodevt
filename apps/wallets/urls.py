from django.urls import path
from .views import DepositRequestView, WithdrawalRequestView, AdminDepositsView, AdminWithdrawalsView, AdminUsersView

urlpatterns = [
    path('deposit-request/', DepositRequestView.as_view(), name='deposit_request'),
    path('withdrawal-request/', WithdrawalRequestView.as_view(), name='withdrawal_request'),
    path('admin/deposits/', AdminDepositsView.as_view(), name='admin_deposits'),
    path('admin/withdrawals/', AdminWithdrawalsView.as_view(), name='admin_withdrawals'),
    path('admin/users/', AdminUsersView.as_view(), name='admin_users'),
]