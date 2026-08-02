import os
import sys
import time
import django

# ---------- DJANGO SETUP ----------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from apps.forex_ea.models import MasterTrade, SlaveAccount, SlaveTrade
from apps.wallets.security.encryption import EncryptionService
import MetaTrader5 as mt5


def main():
    print("NODE Forex Copier started...")
    while True:
        try:
            process_pending_trades()
            close_completed_trades()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(5)


def process_pending_trades():
    """Copy every pending master trade to all active slaves."""
    pending = MasterTrade.objects.filter(status='pending')
    for trade in pending:
        print(f"Copying master trade {trade.ticket} ({trade.symbol} {trade.direction})")
        trade.status = 'executing'
        trade.save()

        slaves = SlaveAccount.objects.filter(is_active=True)
        for slave in slaves:
            password = EncryptionService.decrypt(slave.mt5_password_encrypted)
            if not password:
                print(f"  Skipping {slave.mt5_account} – can't decrypt password")
                continue

            # Connect to slave's broker
            if not mt5.initialize(
                login=int(slave.mt5_account),
                password=password,
                server=slave.broker_server
            ):
                print(f"  MT5 login failed for {slave.mt5_account}")
                continue

            # Place a market order identical to the master
            symbol = trade.symbol
            direction = trade.direction
            volume = trade.volume          # you can add lot scaling here later
            magic = trade.magic_number

            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                print(f"  Symbol {symbol} not available for {slave.mt5_account}")
                mt5.shutdown()
                continue

            if direction == 'BUY':
                price = tick.ask
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                order_type = mt5.ORDER_TYPE_SELL

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 10,
                "magic": magic,
                "comment": "NODE Copier",
            }
            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                SlaveTrade.objects.create(
                    master_trade=trade,
                    slave_account=slave,
                    slave_ticket=result.order
                )
                print(f"  ✅ Copied to {slave.mt5_account} (ticket {result.order})")
            else:
                print(f"  ❌ Failed for {slave.mt5_account}: {result.comment}")

            mt5.shutdown()

        trade.status = 'copied'
        trade.save()


def close_completed_trades():
    """Close all slave copies when the master trade is closed."""
    closed_masters = MasterTrade.objects.filter(status='closed')
    for master in closed_masters:
        open_slaves = SlaveTrade.objects.filter(master_trade=master, closed=False)
        for slave_trade in open_slaves:
            slave = slave_trade.slave_account
            password = EncryptionService.decrypt(slave.mt5_password_encrypted)
            if not password:
                continue

            if not mt5.initialize(
                login=int(slave.mt5_account),
                password=password,
                server=slave.broker_server
            ):
                continue

            # Find the position by ticket and close it
            position = mt5.positions_get(ticket=slave_trade.slave_ticket)
            if position:
                pos = position[0]
                symbol = pos.symbol
                tick = mt5.symbol_info_tick(symbol)
                if pos.type == mt5.POSITION_TYPE_BUY:
                    price = tick.bid
                    order_type = mt5.ORDER_TYPE_SELL
                else:
                    price = tick.ask
                    order_type = mt5.ORDER_TYPE_BUY

                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": pos.ticket,
                    "symbol": symbol,
                    "volume": pos.volume,
                    "type": order_type,
                    "price": price,
                    "deviation": 10,
                    "magic": master.magic_number,
                    "comment": "NODE Copier close",
                }
                result = mt5.order_send(close_request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    slave_trade.closed = True
                    slave_trade.closed_at = timezone.now()
                    slave_trade.save()
                    print(f"  ✅ Closed slave {slave.mt5_account} ticket {slave_trade.slave_ticket}")

            mt5.shutdown()


if __name__ == '__main__':
    main()