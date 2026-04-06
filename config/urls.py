from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenRefreshView
from apps.wallets.admin_views import AdminDepositsView, AdminWithdrawalsView, AdminUsersView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.trading.urls')),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/chat/', include('apps.chat.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('coins/', TemplateView.as_view(template_name='coins.html'), name='coins'),
    path('trading/', TemplateView.as_view(template_name='trading.html'), name='trading'),
    path('portfolio/', TemplateView.as_view(template_name='portfolio.html'), name='portfolio'),
    path('profile/', TemplateView.as_view(template_name='profile.html'), name='profile'),
    path('yield/', TemplateView.as_view(template_name='yield.html'), name='yield'),
    path('deposit/', TemplateView.as_view(template_name='deposit.html'), name='deposit'),
    path('withdraw/', TemplateView.as_view(template_name='withdraw.html'), name='withdraw'),
    path('referral/', TemplateView.as_view(template_name='referral.html'), name='referral'),
    path('chat/', TemplateView.as_view(template_name='chat.html'), name='chat'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='register'),
    path('admin-dashboard/', TemplateView.as_view(template_name='admin_dashboard.html'), name='admin_dashboard'),
    path('api/admin/deposits/', AdminDepositsView.as_view(), name='admin_deposits'),
    path('api/admin/withdrawals/', AdminWithdrawalsView.as_view(), name='admin_withdrawals'),
    path('api/admin/users/', AdminUsersView.as_view(), name='admin_users'),
    path('api/wallets/', include('apps.wallets.urls')),
]