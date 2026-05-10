from binance.client import Client
from binance.enums import *
from decimal import Decimal
from django.conf import settings
import time


class BinanceService:
    """Handles withdrawals and sweeps via Binance API"""

    def __init__(self):
        self.client = Client(
            settings.BINANCE_API_KEY,
            settings.BINANCE_API_SECRET
        )
        self.central_wallet = settings.CENTRAL_WALLET_ADDRESS

    def get_usdc_balance(self):
        """Get USDC BEP20 balance of central wallet"""
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == 'USDC':
                    return Decimal(balance['free'])
            return Decimal('0')
        except Exception as e:
            print(f"Error getting Binance balance: {e}")
            return Decimal('0')

    def withdraw_usdc(self, to_address, amount, network='BSC'):
        """
        Withdraw USDC from Binance to user's external wallet
        Returns: {success: bool, tx_id: str, error: str}
        """
        try:
            amount = float(amount)

            # Minimum withdrawal check
            if amount < 10:
                return {'success': False, 'error': 'Minimum withdrawal is $10 USDC'}

            # Get withdrawal fee
            fee_info = self.client.get_withdraw_fee(asset='USDC')
            fee = Decimal('0')
            for f in fee_info:
                if f['asset'] == 'USDC':
                    fee = Decimal(f['fee'])
                    break

            # Process withdrawal
            result = self.client.withdraw(
                asset='USDC',
                address=to_address,
                amount=amount,
                network=network,
                name='NODE Withdrawal',
                walletType=0  # 0 = spot wallet
            )

            return {
                'success': True,
                'tx_id': result.get('id', ''),
                'amount': amount,
                'fee': float(fee),
                'address': to_address
            }

        except Exception as e:
            print(f"Withdrawal error: {e}")
            return {'success': False, 'error': str(e)}

    def sweep_to_central(self, from_private_key, from_address):
        """
        Sweep USDC from a user's BSC wallet to central Binance wallet
        This requires the user wallet's private key
        """
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider('https://bsc-rpc.publicnode.com'))

        # USDC contract
        usdc_address = Web3.to_checksum_address('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d')

        # Simplified ABI for transfer
        abi = [
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
             "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
             "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}
        ]

        contract = w3.eth.contract(address=usdc_address, abi=abi)

        # Get balance
        sender = Web3.to_checksum_address(from_address)
        balance = contract.functions.balanceOf(sender).call()

        if balance == 0:
            return {'success': False, 'error': 'No USDC to sweep'}

        # Get BNB for gas
        bnb_balance = w3.eth.get_balance(sender)
        if bnb_balance < w3.to_wei(0.001, 'ether'):
            print(f"Low BNB for gas on {from_address}")

        # Build transaction
        tx = contract.functions.transfer(
            Web3.to_checksum_address(self.central_wallet),
            balance
        ).build_transaction({
            'from': sender,
            'nonce': w3.eth.get_transaction_count(sender),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign and send
        signed = w3.eth.account.sign_transaction(tx, from_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        return {
            'success': True,
            'tx_hash': tx_hash.hex(),
            'amount': Decimal(str(balance)) / Decimal(10 ** 18),
            'from': from_address
        }

    def get_withdrawal_status(self, tx_id):
        """Check withdrawal status"""
        try:
            history = self.client.get_withdraw_history()
            for w in history:
                if str(w.get('id')) == str(tx_id):
                    return {
                        'status': 'COMPLETED' if w.get('status') == 6 else 'PENDING',
                        'tx_id': w.get('txId', ''),
                        'amount': w.get('amount', 0),
                        'address': w.get('address', '')
                    }
            return {'status': 'UNKNOWN'}
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}