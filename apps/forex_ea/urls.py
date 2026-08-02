from .api_views import (
    AuthenticateView, BalanceView, ReportTradeView,
    ForexProfileView, ActivateForexView,
    TradeOpenedView, TradeClosedView,
    SlaveAccountView, SlaveTradeStatusView
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
]