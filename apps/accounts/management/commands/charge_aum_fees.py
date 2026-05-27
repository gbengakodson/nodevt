from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from apps.accounts.models import ExchangeAPIConnection
from apps.wallets.models import Wallet
from apps.core.notifications import notify_user


class Command(BaseCommand):
    help = 'Charge monthly AUM fees for external exchange connections'

    def handle(self, *args, **options):
        now = timezone.now()
        connections = ExchangeAPIConnection.objects.filter(is_active=True)
        charged = 0
        warned = 0
        liquidated = 0

        for conn in connections:
            # Calculate AUM from active grids on this connection
            from apps.trading.models import GridBot
            grids = GridBot.objects.filter(
                user=conn.user,
                status='ACTIVE'
            )
            # Filter by connection_id in Python
            grids = [g for g in grids if g.metadata.get('connection_id') == str(conn.id)]

            total_aum = sum(g.amount for g in grids)
            conn.aum_amount = total_aum

            # Calculate monthly fee (1% annual = 0.083% monthly)
            if total_aum >= 100000:
                annual_rate = Decimal('0.005')
            elif total_aum >= 10000:
                annual_rate = Decimal('0.0075')
            else:
                annual_rate = Decimal('0.01')

            monthly_rate = annual_rate / Decimal('12')
            conn.monthly_fee = total_aum * monthly_rate
            conn.save()

            if conn.monthly_fee <= 0:
                continue

            # Check if fee is due (not charged in last 30 days)
            if conn.fee_last_charged and (now - conn.fee_last_charged).days < 30:
                continue

            # Get user's NODE wallet
            grand = Wallet.objects.filter(user=conn.user, wallet_type='GRAND').first()
            wallet_balance = grand.balance if grand else Decimal('0')

            if wallet_balance >= conn.monthly_fee:
                # Charge fee
                grand.balance -= conn.monthly_fee
                grand.save()
                conn.fee_last_charged = now
                conn.warning_sent_at = None
                conn.grids_paused = False
                conn.save()
                charged += 1

                notify_user(
                    conn.user,
                    '💳 Monthly Fee Charged',
                    f'${float(conn.monthly_fee):.2f} deducted from your NODE wallet for external grid management.',
                    'INFO'
                )
                self.stdout.write(f'Charged {conn.user.email}: ${float(conn.monthly_fee):.2f}')

            else:
                # Insufficient balance - warning/liquidation logic
                days_since_warning = 0
                if conn.warning_sent_at:
                    days_since_warning = (now - conn.warning_sent_at).days

                if days_since_warning >= 7 and not conn.grids_paused:
                    # Liquidate all positions
                    self._liquidate_grids(conn)
                    conn.grids_paused = True
                    conn.save()
                    liquidated += 1
                    notify_user(
                        conn.user,
                        '⏸️ Grids Paused - Insufficient Balance',
                        f'Your external grids have been converted to USDT and paused. Deposit ${float(conn.monthly_fee):.2f} to resume.',
                        'ALERT'
                    )

                elif days_since_warning >= 4:
                    warned += 1
                    notify_user(
                        conn.user,
                        '⚠️ Final Warning - Grid Pause Imminent',
                        f'Your NODE wallet balance (${float(wallet_balance):.2f}) is below the monthly fee (${float(conn.monthly_fee):.2f}). Your external grids will be liquidated and paused in 3 days unless topped up.',
                        'ALERT'
                    )

                elif days_since_warning >= 0:
                    warned += 1
                    notify_user(
                        conn.user,
                        '⚠️ Insufficient Balance for Monthly Fee',
                        f'Your NODE wallet (${float(wallet_balance):.2f}) cannot cover the monthly fee (${float(conn.monthly_fee):.2f}). Please deposit within 7 days to avoid grid liquidation.',
                        'ALERT'
                    )

                else:
                    # First warning
                    conn.warning_sent_at = now
                    conn.save()
                    warned += 1
                    notify_user(
                        conn.user,
                        '⚠️ Insufficient Balance for Monthly Fee',
                        f'Your NODE wallet (${float(wallet_balance):.2f}) cannot cover the monthly fee (${float(conn.monthly_fee):.2f}). Please deposit within 7 days to avoid grid liquidation.',
                        'ALERT'
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Done: {charged} charged, {warned} warned, {liquidated} liquidated'
        ))

    def _liquidate_grids(self, conn):
        """Convert all positions to USDT and pause grids"""
        from apps.trading.models import GridBot

        grids = GridBot.objects.filter(
            user=conn.user,
            status='ACTIVE'
        )
        # Filter by connection_id in Python
        grids = [g for g in grids if g.metadata.get('connection_id') == str(conn.id)]

        client = conn.get_client()
        if not client:
            return

        for grid in grids:
            symbol = grid.token.symbol
            pair = f'{symbol}USDT'

            try:
                # Cancel all open orders
                open_orders = client.get_open_orders(symbol=pair)
                for order in open_orders:
                    client.cancel_order(symbol=pair, orderId=order['orderId'])

                # Sell all holdings at market
                account = client.get_account()
                for b in account['balances']:
                    if b['asset'] == symbol:
                        qty = float(b['free'])
                        if qty > 0:
                            client.create_order(
                                symbol=pair,
                                side='SELL',
                                type='MARKET',
                                quantity=round(qty, 6)
                            )
                        break

                grid.status = 'STOPPED'
                grid.save()

            except Exception as e:
                self.stdout.write(f'Error liquidating {symbol}: {e}')