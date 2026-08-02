import os
import sys
import time
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

# ---------- HARD-CODE YOUR DATABASE URL HERE ----------
DATABASE_URL = "postgresql://postgres.bbjfetsgourtnywqzjqw:2Methylpropane%23@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
# ------------------------------------------------------

os.environ['DATABASE_URL'] = DATABASE_URL

# Set up Django (must be done before importing models)
PROJECT_DIR = r"C:\Users\easyf\Crypto_platform"   # CHANGE THIS TO YOUR ACTUAL PROJECT FOLDER PATH
sys.path.append(PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.forex_ea.models import MasterTrade, SlaveAccount, SlaveTrade
from apps.wallets.security.encryption import EncryptionService
import MetaTrader5 as mt5

# ------------------------ Copier Logic ------------------------
class Copier:
    def __init__(self, log_func):
        self.running = False
        self.log = log_func

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        self.log("Copier started.")
        while self.running:
            try:
                self._process_pending_trades()
                self._close_completed_trades()
            except Exception as e:
                self.log(f"Error: {e}")
            time.sleep(5)

    def _process_pending_trades(self):
        pending = MasterTrade.objects.filter(status='pending')
        for trade in pending:
            self.log(f"Processing master trade {trade.ticket} ({trade.symbol} {trade.direction})")
            trade.status = 'executing'
            trade.save()

            slaves = SlaveAccount.objects.filter(is_active=True)
            for slave in slaves:
                password = EncryptionService.decrypt(slave.mt5_password_encrypted)
                if not password:
                    continue

                if not mt5.initialize(login=int(slave.mt5_account), password=password, server=slave.broker_server):
                    self.log(f"  Login failed for {slave.mt5_account}")
                    continue

                tick = mt5.symbol_info_tick(trade.symbol)
                if not tick:
                    mt5.shutdown()
                    continue

                if trade.direction == 'BUY':
                    price = tick.ask
                    order_type = mt5.ORDER_TYPE_BUY
                else:
                    price = tick.bid
                    order_type = mt5.ORDER_TYPE_SELL

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": trade.symbol,
                    "volume": trade.volume,
                    "type": order_type,
                    "price": price,
                    "deviation": 10,
                    "magic": trade.magic_number,
                    "comment": "NODE Copier",
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    SlaveTrade.objects.create(
                        master_trade=trade,
                        slave_account=slave,
                        slave_ticket=result.order
                    )
                    self.log(f"  ✅ Copied to {slave.mt5_account} (ticket {result.order})")
                else:
                    self.log(f"  ❌ Failed for {slave.mt5_account}: {result.comment}")
                mt5.shutdown()

            trade.status = 'copied'
            trade.save()

    def _close_completed_trades(self):
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

                position = mt5.positions_get(ticket=slave_trade.slave_ticket)
                if position:
                    pos = position[0]
                    tick = mt5.symbol_info_tick(pos.symbol)
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        price = tick.bid
                        order_type = mt5.ORDER_TYPE_SELL
                    else:
                        price = tick.ask
                        order_type = mt5.ORDER_TYPE_BUY
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": pos.ticket,
                        "symbol": pos.symbol,
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
                        self.log(f"  ✅ Closed slave {slave.mt5_account} ticket {slave_trade.slave_ticket}")
                mt5.shutdown()


# ------------------------ GUI ------------------------
class CopierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NODE Forex Copier")
        self.root.geometry("500x400")
        self.copier = Copier(self.add_log)

        # Start / Stop buttons
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=5)
        self.start_btn = tk.Button(self.btn_frame, text="Start Copier", command=self.start_copier, bg="#4CAF50", fg="white", width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = tk.Button(self.btn_frame, text="Stop Copier", command=self.stop_copier, bg="#f44336", fg="white", width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Log area
        self.log_area = ScrolledText(root, state='disabled', wrap=tk.WORD)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.add_log("GUI ready. Click 'Start Copier' to begin.")

    def start_copier(self):
        self.copier.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.add_log("Copier started.")

    def stop_copier(self):
        self.copier.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.add_log("Copier stopped.")

    def add_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')


if __name__ == '__main__':
    root = tk.Tk()
    app = CopierApp(root)
    root.mainloop()