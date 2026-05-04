from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import TradingViewSet, check_deposits_webhook, update_prices_webhook, credit_yield_only
from .grid_views import StopGridView, StartGridView, CloseGridView


router = DefaultRouter()
router.register('', TradingViewSet, basename='trading')

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
    path('check-deposits/', check_deposits_webhook, name='check_deposits'),
    path('update-prices/', update_prices_webhook, name='update_prices'),
    path('credit-yield/', credit_yield_only, name='credit_yield'),

# Grid bot actions
    path('stop-grid/', StopGridView.as_view(), name='stop_grid'),
    path('start-grid/', StartGridView.as_view(), name='start_grid'),
    path('close-grid/', CloseGridView.as_view(), name='close_grid'),

]