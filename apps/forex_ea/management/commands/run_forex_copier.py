import time
import MetaTrader5 as mt5
from django.core.management.base import BaseCommand
from apps.forex_ea.models import MasterTrade, SlaveAccount, SlaveTrade
from apps.wallets.security.encryption import EncryptionService
from django.utils import timezone

class Command(BaseCommand):
    help = 'Runs the trade copier worker loop'

    def handle(self, *args, **options):
        self.stdout.write('Starting Forex Trade Copier...')
        while True:
            self.process_pending_trades()
            self.close_completed_slave_trades()
            time.sleep(5)

    def process_pending_trades(self):
        """Copy pending master trades to all active slaves."""
        pending = MasterTrade.objects.filter(status='pending')
        for trade in pending:
            trade.status = 'executing'
            trade.save()

            slaves = SlaveAccount.objects.filter(is_active=True)
            for slave in slaves:
                # Decrypt password
                password = EncryptionService.decrypt(slave.mt5_password_encrypted)
                if not password:
                    self.stdout.write(f'Failed to decrypt password for {slave.mt5_account}')
                    continue

                # Initialize MT5 connection for this slave
                if not mt5.initialize(
                    login=int(slave.mt5_account),
                    password=password,
                    server=slave.broker_server
                ):
                    self.stdout.write(f'MT5 login failed for {slave.mt5_account}')
                    continue

                # Prepare market order (copy master trade exactly)
                symbol = trade.symbol
                direction = trade.direction
                volume = trade.volume  # For now, same volume; scaling can be added later
                magic = trade.magic_number

                # Get current price
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    self.stdout.write(f'Symbol {symbol} not found for {slave.mt5_account}')
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
                    self.stdout.write(f'Copied trade {trade.ticket} to {slave.mt5_account} (ticket {result.order})')
                else:
                    self.stdout.write(f'Failed to copy to {slave.mt5_account}: {result.comment}')

                mt5.shutdown()

            # Mark master trade as distributed
            trade.status = 'copied'
            trade.save()

    def close_completed_slave_trades(self):
        """Close slave trades when the master trade is closed."""
        closed_masters = MasterTrade.objects.filter(status='closed')
        for master in closed_masters:
            open_slaves = SlaveTrade.objects.filter(master_trade=master, closed=False)
            for slave_trade in open_slaves:
                slave = slave_trade.slave_account
                password = EncryptionService.decrypt(slave.mt5_password_encrypted)
                if not password:
                    continue
                if not mt5.initialize(login=int(slave.mt5_account), password=password, server=slave.broker_server):
                    continue

                # Close the slave position using the slave_ticket
                position = mt5.positions_get(ticket=slave_trade.slave_ticket)
                if position:
                    position = position[0]
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": position.ticket,
                        "symbol": position.symbol,
                        "volume": position.volume,
                        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
                        "deviation": 10,
                        "magic": master.magic_number,
                        "comment": "NODE Copier close",
                    }
                    result = mt5.order_send(close_request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        slave_trade.closed = True
                        slave_trade.closed_at = timezone.now()
                        slave_trade.save()
                        self.stdout.write(f'Closed slave trade {slave_trade.slave_ticket}')
                mt5.shutdown()