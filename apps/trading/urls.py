from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import TradingViewSet
from .views import check_deposits_webhook

router = DefaultRouter()
router.register('trading', TradingViewSet, basename='trading')

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
    path('check-deposits/', check_deposits_webhook, name='check_deposits'),
    path('update-prices/', update_prices_webhook, name='update_prices'),

]