from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenRefreshView
from apps.wallets.views import AdminSendEmailView
from apps.wallets.views import AdminChatMessagesView
from apps.wallets.admin_views import AdminDepositsView, AdminWithdrawalsView, AdminUsersView
from apps.trading.views import yield_rate_view
# Add this import at the top of your config/urls.py
from apps.chatbot.views import ChatbotAPIView, NotificationsAPIView, MarkAllNotificationsReadAPIView, SubscribePushAPIView,UnsubscribePushAPIView

from apps.wallets.views import (
    AdminStatisticsView,
    AdminHoldersView,
    AdminBuySellActivityView
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/trading/', include('apps.trading.urls')),
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
    path('api/admin/send-email/', AdminSendEmailView.as_view(), name='admin_send_email'),
    path('api/admin/chat/', AdminChatMessagesView.as_view(), name='admin_chat'),
    path('api/admin/chat/<uuid:user_id>/', AdminChatMessagesView.as_view(), name='admin_chat_conversation'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='register'),
    path('admin-dashboard/', TemplateView.as_view(template_name='admin_dashboard.html'), name='admin_dashboard'),
    path('api/admin/deposits/', AdminDepositsView.as_view(), name='admin_deposits'),
    path('api/admin/withdrawals/', AdminWithdrawalsView.as_view(), name='admin_withdrawals'),
    path('api/admin/users/', AdminUsersView.as_view(), name='admin_users'),


    path('api/admin/statistics/', AdminStatisticsView.as_view(), name='admin_statistics'),
    path('api/admin/holders/', AdminHoldersView.as_view(), name='admin_holders'),
    path('api/admin/buy-sell-activity/', AdminBuySellActivityView.as_view(), name='admin_buy_sell'),

    path('api/wallets/', include('apps.wallets.urls')),

    # Chatbot URLs
    path('api/chatbot/message/', ChatbotAPIView.as_view(), name='chatbot_message'),
    path('api/chatbot/notifications/', NotificationsAPIView.as_view(), name='chatbot_notifications'),
    path('api/chatbot/notifications/mark-read/', MarkAllNotificationsReadAPIView.as_view(), name='chatbot_mark_read'),
    path('api/chatbot/notifications/mark-all-read/', MarkAllNotificationsReadAPIView.as_view(), name='chatbot_mark_all_read'),


    path('api/notifications/subscribe/', SubscribePushAPIView.as_view(), name='subscribe_push'),
    path('api/notifications/unsubscribe/', UnsubscribePushAPIView.as_view(), name='unsubscribe_push'),

    path('api/portfolio/', include('apps.portfolio.urls')),

    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),

    path('risk-disclosure/', TemplateView.as_view(template_name='risk-disclosure.html'), name='risk_disclosure'),
    path('transparency/', TemplateView.as_view(template_name='transparency.html'), name='transparency'),

    path('api/yield-rate/', yield_rate_view, name='yield_rate'),

]