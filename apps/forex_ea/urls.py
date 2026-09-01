from django.urls import path
from .swap_views import ForexSwapView, ForexBalancesView, SpotRatesView
from .stock_views import StockBalancesView
from .stock_order_views import StockOrderView
from .api_views import (
    AuthenticateView, BalanceView, ReportTradeView,
    ForexProfileView, ActivateForexView, ForexForecastView,
    TradeOpenedView, TradeClosedView, SlaveDeleteView,
    SlaveAccountView, SlaveTradeStatusView, SignalView
)



urlpatterns = [
    path('authenticate/', AuthenticateView.as_view(), name='ea_authenticate'),
    path('balance/', BalanceView.as_view(), name='ea_balance'),
    path('report-trade/', ReportTradeView.as_view(), name='ea_report_trade'),
    path('profile/', ForexProfileView.as_view(), name='ea_profile'),
    path('activate/', ActivateForexView.as_view(), name='ea_activate'),
    path('trade/opened/', TradeOpenedView.as_view(), name='ea_trade_opened'),
    path('trade/closed/', TradeClosedView.as_view(), name='ea_trade_closed'),
    path('slave/', SlaveAccountView.as_view(), name='ea_slave_account'),
    path('slave/trades/', SlaveTradeStatusView.as_view(), name='ea_slave_trades'),
    path('signal/', SignalView.as_view(), name='ea_signal'),
    path('slave/<uuid:pk>/delete/', SlaveDeleteView.as_view(), name='ea_slave_delete'),
    path('forecast/', ForexForecastView.as_view(), name='forex_forecast'),
    path('swap/', ForexSwapView.as_view(), name='forex_swap'),
    path('balances/', ForexBalancesView.as_view(), name='forex_balances'),
    path('spot-rates/', SpotRatesView.as_view(), name='spot_rates'),
    path('stocks/', StockBalancesView.as_view(), name='stock_balances'),
    path('stock-order/', StockOrderView.as_view(), name='stock_order'),
]