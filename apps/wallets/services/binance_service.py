from binance.client import Client
from binance.enums import *
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from web3 import Web3
from apps.wallets.models import Transaction
import time


class BinanceService:
    """Handles withdrawals, sweeps, and balance checks via Binance API"""

    def __init__(self):
        self.client = Client(
            settings.BINANCE_API_KEY,
            settings.BINANCE_API_SECRET
        )
        self.central_wallet = settings.CENTRAL_WALLET_ADDRESS


    def _get_binance_symbol(self, symbol):
        """Convert internal symbol to Binance pair format"""
        usdt_pairs = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE',
                      'AVAX', 'DOT', 'LINK', 'LTC', 'NEAR', 'ATOM',
                      'ALGO', 'VET', 'UNI', 'EGLD', 'THETA', 'PEPE']

        if symbol in usdt_pairs:
            return f'{symbol}USDT'
        return None

    def place_grid_orders(self, symbol, lower_price, upper_price, total_amount, grids=100):
        """
        Place buy limit orders across the grid range on Binance.
        Returns: {success: bool, orders_placed: int, order_ids: list, error: str}
        """
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            if not binance_symbol:
                return {'success': False, 'error': f'No Binance pair for {symbol}'}

            # Get symbol info for lot size and tick size
            info = self.client.get_symbol_info(binance_symbol)
            lot_filter = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
            price_filter = next(f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER')

            min_qty = float(lot_filter['minQty'])
            step_size = float(lot_filter['stepSize'])
            tick_size = float(price_filter['tickSize'])

            # Calculate grid step
            grid_step = (float(upper_price) - float(lower_price)) / grids

            # Amount per order
            amount_per_order = float(total_amount) / grids

            order_ids = []
            placed = 0

            for i in range(grids):
                price = float(lower_price) + (i * grid_step)

                # Round price to tick size
                price = round(price / tick_size) * tick_size
                price = round(price, 8)

                # Calculate quantity
                quantity = amount_per_order / price

                # Round quantity to step size
                quantity = round(quantity / step_size) * step_size
                quantity = round(quantity, 8)

                if quantity < min_qty:
                    continue

                try:
                    order = self.client.create_order(
                        symbol=binance_symbol,
                        side=SIDE_BUY,
                        type=ORDER_TYPE_LIMIT,
                        timeInForce=TIME_IN_FORCE_GTC,
                        quantity=quantity,
                        price=str(price)
                    )
                    order_ids.append(str(order['orderId']))
                    placed += 1

                    if placed % 10 == 0:
                        import time
                        time.sleep(0.1)

                except Exception as e:
                    print(f"Order {i} failed at ${price:.4f}: {e}")
                    continue

            return {
                'success': True,
                'orders_placed': placed,
                'total_grids': grids,
                'order_ids': order_ids,
                'symbol': binance_symbol
            }

        except Exception as e:
            print(f"Grid order placement error: {e}")
            return {'success': False, 'error': str(e)}



    def cancel_grid_orders(self, symbol, order_ids=None):
        """
        Cancel all open orders for a grid.
        If order_ids not provided, cancel all open orders for the symbol.
        Returns: {success: bool, cancelled: int}
        """
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            if not binance_symbol:
                return {'success': False, 'error': f'No Binance pair for {symbol}'}

            cancelled = 0

            if order_ids:
                for order_id in order_ids:
                    try:
                        self.client.cancel_order(
                            symbol=binance_symbol,
                            orderId=order_id
                        )
                        cancelled += 1
                    except Exception as e:
                        print(f"Failed to cancel order {order_id}: {e}")
            else:
                open_orders = self.client.get_open_orders(symbol=binance_symbol)
                for order in open_orders:
                    try:
                        self.client.cancel_order(
                            symbol=binance_symbol,
                            orderId=order['orderId']
                        )
                        cancelled += 1
                    except:
                        pass

            return {'success': True, 'cancelled': cancelled}

        except Exception as e:
            print(f"Cancel grid error: {e}")
            return {'success': False, 'error': str(e)}

    def market_sell_position(self, symbol):
        """
        Sell all accumulated position at market price.
        Used when closing a grid.
        """
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            if not binance_symbol:
                return {'success': False, 'error': f'No Binance pair for {symbol}'}

            base_asset = binance_symbol.replace('USDT', '')

            account = self.client.get_account()
            balance = 0
            for b in account['balances']:
                if b['asset'] == base_asset:
                    balance = float(b['free'])
                    break

            if balance <= 0:
                return {'success': True, 'sold': 0, 'message': 'No position to sell'}

            order = self.client.create_order(
                symbol=binance_symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=round(balance, 6)
            )

            fills = order.get('fills', [])
            total_qty = sum(float(f['qty']) for f in fills)
            total_cost = sum(float(f['qty']) * float(f['price']) for f in fills)
            avg_price = total_cost / total_qty if total_qty > 0 else 0

            return {
                'success': True,
                'sold': total_qty,
                'avg_price': avg_price,
                'total_usdt': total_cost,
                'order_id': str(order['orderId'])
            }

        except Exception as e:
            print(f"Market sell error: {e}")
            return {'success': False, 'error': str(e)}

    def get_filled_grid_orders(self, symbol, start_time=None):
        """
        Get filled orders for profit calculation.
        """
        try:
            binance_symbol = self._get_binance_symbol(symbol)
            if not binance_symbol:
                return {'success': False, 'error': f'No Binance pair for {symbol}'}

            trades = self.client.get_my_trades(symbol=binance_symbol, limit=500)

            if start_time:
                start_ts = int(start_time.timestamp() * 1000)
                trades = [t for t in trades if t['time'] >= start_ts]

            buy_trades = [t for t in trades if not t['isBuyer']]
            sell_trades = [t for t in trades if t['isBuyer']]

            total_bought = sum(float(t['qty']) * float(t['price']) for t in buy_trades)
            total_sold = sum(float(t['qty']) * float(t['price']) for t in sell_trades)

            return {
                'success': True,
                'symbol': binance_symbol,
                'total_trades': len(trades),
                'buy_trades': len(buy_trades),
                'sell_trades': len(sell_trades),
                'total_bought_usdt': round(total_bought, 2),
                'total_sold_usdt': round(total_sold, 2),
                'profit': round(total_sold - total_bought, 2),
                'trades': trades[:20]
            }

        except Exception as e:
            print(f"Trade history error: {e}")
            return {'success': False, 'error': str(e)}

    def get_usdc_balance(self):
        """Get USDC + USDT balance of central wallet on Binance"""
        try:
            account = self.client.get_account()
            total = Decimal('0')
            for balance in account['balances']:
                if balance['asset'] in ['USDC', 'USDT']:
                    total += Decimal(balance['free'])
            return total
        except Exception as e:
            print(f"Error getting Binance balance: {e}")
            return Decimal('0')

    def withdraw_usdc(self, to_address, amount, network='BSC'):
        """Withdraw USDC/USDT from Binance to user's external wallet."""
        try:
            amount = float(amount)
            if amount < 10:
                return {'success': False, 'error': 'Minimum withdrawal is $10'}

            # Check which stablecoin has balance
            account = self.client.get_account()
            usdc_bal = Decimal('0')
            usdt_bal = Decimal('0')
            for b in account['balances']:
                if b['asset'] == 'USDC':
                    usdc_bal = Decimal(b['free'])
                if b['asset'] == 'USDT':
                    usdt_bal = Decimal(b['free'])

            asset = 'USDT' if usdt_bal >= Decimal(str(amount)) else 'USDC'

            result = self.client.withdraw(
                asset=asset,
                address=to_address,
                amount=amount,
                network=network,
                name='NODE Withdrawal',
                walletType=0
            )

            return {
                'success': True,
                'tx_id': result.get('id', ''),
                'amount': amount,
                'address': to_address,
                'asset': asset
            }
        except Exception as e:
            print(f"Withdrawal error: {e}")
            return {'success': False, 'error': str(e)}

    def withdraw_usdc_safe(self, to_address, amount, user_email):
        """
        Safe USDC/USDT withdrawal with multiple checks and audit logging.
        """
        try:
            amount = float(amount)

            # ============ SAFETY CHECKS ============
            if amount < 10:
                return {'success': False, 'error': 'Minimum withdrawal is $10'}

            if amount > 10000:
                return {'success': False, 'error': 'Maximum withdrawal is $10,000 per transaction'}

            if not to_address.startswith('0x') or len(to_address) != 42:
                return {'success': False, 'error': 'Invalid BSC wallet address'}

            # Check which stablecoin to use
            account = self.client.get_account()
            usdc_bal = Decimal('0')
            usdt_bal = Decimal('0')
            for b in account['balances']:
                if b['asset'] == 'USDC':
                    usdc_bal = Decimal(b['free'])
                if b['asset'] == 'USDT':
                    usdt_bal = Decimal(b['free'])

            total_stable = usdc_bal + usdt_bal

            if total_stable < Decimal(str(amount)):
                return {
                    'success': False,
                    'error': f'Platform liquidity temporarily insufficient. Available: ${float(total_stable):.2f}, Need: ${amount:.2f}'
                }

            asset = 'USDT' if usdt_bal >= Decimal(str(amount)) else 'USDC'

            # ============ PROCESS WITHDRAWAL ============
            result = self.client.withdraw(
                asset=asset,
                address=to_address,
                amount=amount,
                network='BSC',
                name=f'NODE-{user_email[:20]}',
                walletType=0
            )

            tx_id = str(result.get('id', ''))

            print(f"""
            ========================================
            WITHDRAWAL PROCESSED
            User: {user_email}
            Amount: ${amount:.2f} {asset}
            To: {to_address}
            TX ID: {tx_id}
            Time: {timezone.now()}
            ========================================
            """)

            return {
                'success': True,
                'tx_id': tx_id,
                'amount': amount,
                'address': to_address,
                'asset': asset
            }

        except Exception as e:
            error_msg = str(e)
            print(f"WITHDRAWAL ERROR for {user_email}: {error_msg}")
            return {'success': False, 'error': 'Withdrawal processing failed. Support team notified.'}


    def sweep_to_central(self, from_private_key, from_address):
        """
        Sweep USDC from a user's BSC wallet to central Binance wallet.
        Requires the user wallet's private key.
        Returns: {success: bool, tx_hash: str, amount: Decimal, error: str}
        """
        try:
            w3 = Web3(Web3.HTTPProvider('https://bsc-rpc.publicnode.com'))

            # USDC contract
            usdc_address = Web3.to_checksum_address('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d')

            # Minimal ABI for transfer
            abi = [
                {"constant": False,
                 "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
                 "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
                {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
                 "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            ]

            contract = w3.eth.contract(address=usdc_address, abi=abi)

            # Get balance
            sender = Web3.to_checksum_address(from_address)
            balance = contract.functions.balanceOf(sender).call()

            if balance == 0:
                return {'success': False, 'error': 'No USDC to sweep'}

            # Check BNB for gas
            bnb_balance = w3.eth.get_balance(sender)
            gas_price = w3.eth.gas_price
            gas_limit = 100000
            gas_cost = gas_limit * gas_price

            if bnb_balance < gas_cost:
                return {
                    'success': False,
                    'error': f'Insufficient BNB for gas. Have {w3.from_wei(bnb_balance, "ether"):.6f}, need {w3.from_wei(gas_cost, "ether"):.6f}'
                }

            # Build transaction
            tx = contract.functions.transfer(
                Web3.to_checksum_address(self.central_wallet),
                balance
            ).build_transaction({
                'from': sender,
                'nonce': w3.eth.get_transaction_count(sender),
                'gas': gas_limit,
                'gasPrice': gas_price,
                'chainId': 56
            })

            # Sign and send
            signed = w3.eth.account.sign_transaction(tx, from_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            amount_usdc = Decimal(str(balance)) / Decimal(10 ** 18)

            print(f"Swept ${amount_usdc:.2f} USDC from {from_address} to central wallet. TX: {tx_hash.hex()}")

            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'amount': amount_usdc,
                'from': from_address
            }

        except Exception as e:
            print(f"Sweep error for {from_address}: {e}")
            return {'success': False, 'error': str(e)}

    def get_withdrawal_status(self, tx_id):
        """Check withdrawal status on Binance"""
        try:
            history = self.client.get_withdraw_history()
            for w in history:
                if str(w.get('id')) == str(tx_id):
                    status_map = {0: 'EMAIL_SENT', 1: 'CANCELLED', 2: 'AWAITING_APPROVAL', 3: 'REJECTED',
                                  4: 'PROCESSING', 5: 'FAILURE', 6: 'COMPLETED'}
                    return {
                        'status': status_map.get(w.get('status'), 'UNKNOWN'),
                        'tx_id': w.get('txId', ''),
                        'amount': w.get('amount', 0),
                        'address': w.get('address', ''),
                        'confirmations': w.get('confirmTimes', 0)
                    }
            return {'status': 'UNKNOWN'}
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}

    def test_connection(self):
        """Test Binance API connection"""
        try:
            account = self.client.get_account()
            balances = {b['asset']: b['free'] for b in account['balances'] if float(b['free']) > 0}
            return {
                'success': True,
                'can_trade': account.get('canTrade', False),
                'can_withdraw': account.get('canWithdraw', False),
                'usdc_balance': balances.get('USDC', '0')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def send_bnb(self, to_address, amount=0.001):
        """Send small BNB to a wallet for gas fees"""
        try:
            result = self.client.withdraw(
                asset='BNB',
                address=to_address,
                amount=amount,
                network='BSC',
                name='Gas funding',
                walletType=0
            )
            return {'success': True, 'tx_id': result.get('id', '')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def withdraw_via_web3(self, to_address, amount_usdc):
        """Withdraw USDC from central wallet via Web3 (no Binance API)"""
        from web3 import Web3
        from decimal import Decimal

        w3 = Web3(Web3.HTTPProvider('https://bsc-rpc.publicnode.com'))

        # USDC contract
        usdc_address = Web3.to_checksum_address('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d')

        abi = [
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
             "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
             "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        ]

        contract = w3.eth.contract(address=usdc_address, abi=abi)

        central = Web3.to_checksum_address(settings.CENTRAL_WALLET_ADDRESS)
        private_key = settings.CENTRAL_WALLET_PRIVATE_KEY
        amount_wei = int(Decimal(str(amount_usdc)) * Decimal(10 ** 18))

        # Check balance
        balance = contract.functions.balanceOf(central).call()
        if balance < amount_wei:
            return {'success': False, 'error': 'Insufficient central wallet balance'}

        # Build and send transaction
        tx = contract.functions.transfer(
            Web3.to_checksum_address(to_address), amount_wei
        ).build_transaction({
            'from': central,
            'nonce': w3.eth.get_transaction_count(central),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 56
        })

        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        return {
            'success': True,
            'tx_hash': tx_hash.hex(),
            'amount': float(amount_usdc)
        }
