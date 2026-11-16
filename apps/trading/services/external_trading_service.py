import logging
from apps.accounts.models import ExchangeAPIConnection

logger = logging.getLogger(__name__)


class ExternalTradingService:
    @staticmethod
    def broadcast_buy_order(symbol, quantity, price):
        """Loop through all active user connections and place a limit buy."""
        connections = ExchangeAPIConnection.objects.filter(is_active=True)

        for conn in connections:
            try:
                client = conn.get_client()
                if not client:
                    continue

                ccxt_symbol = f"{symbol}/USDT"

                # Place limit buy order
                order = client.create_order(
                    symbol=ccxt_symbol,
                    type='limit',
                    side='buy',
                    amount=quantity,
                    price=price
                )

                logger.info(f"✅ Broadcasted BUY for {conn.exchange} ({conn.user.email}): {quantity} {symbol} @ {price}")

            except Exception as e:
                logger.error(f"❌ Failed to broadcast BUY to {conn.exchange} ({conn.user.email}): {str(e)}")
                continue

    @staticmethod
    def broadcast_sell_order(symbol, quantity, price):
        """Loop through all active user connections and place a limit sell."""
        connections = ExchangeAPIConnection.objects.filter(is_active=True)

        for conn in connections:
            try:
                client = conn.get_client()
                if not client:
                    continue

                ccxt_symbol = f"{symbol}/USDT"

                order = client.create_order(
                    symbol=ccxt_symbol,
                    type='limit',
                    side='sell',
                    amount=quantity,
                    price=price
                )

                logger.info(
                    f"✅ Broadcasted SELL for {conn.exchange} ({conn.user.email}): {quantity} {symbol} @ {price}")

            except Exception as e:
                logger.error(f"❌ Failed to broadcast SELL to {conn.exchange} ({conn.user.email}): {str(e)}")
                continue