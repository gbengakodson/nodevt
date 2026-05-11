from decimal import Decimal
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction, WalletKey
from django.contrib.auth import get_user_model
from django.conf import settings
from web3 import Web3
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class DepositMonitor:
    """Monitors BSC for incoming USDC deposits using Web3, auto-sweeps to central"""

    USDC_ADDRESS = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
    BSC_RPC = 'https://bsc-rpc.publicnode.com'
    TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
    CENTRAL_WALLET = settings.CENTRAL_WALLET_ADDRESS
    PRIVATE_KEY = settings.CENTRAL_WALLET_PRIVATE_KEY
    GAS_BNB = Decimal('0.0005')  # BNB to send for gas

    @classmethod
    def check_all_users(cls):
        wallet_keys = WalletKey.objects.select_related('user').all()
        total = 0
        for wk in wallet_keys:
            try:
                result = cls.check_deposits(wk.address, wk.user)
                if result.get('amount', 0) > 0:
                    total += result['amount']
            except Exception as e:
                pass
        return total

    @classmethod
    def check_deposits(cls, address, user):
        try:
            w3 = Web3(Web3.HTTPProvider(cls.BSC_RPC))
            if not w3.is_connected():
                return {'amount': 0, 'deposits': []}

            # Check USDC balance directly
            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(cls.USDC_ADDRESS),
                abi=[{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
                      "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]
            )

            balance = usdc_contract.functions.balanceOf(Web3.to_checksum_address(address)).call()

            if balance == 0:
                return {'amount': 0, 'deposits': []}

            amount = Decimal(str(balance)) / Decimal(10 ** 18)

            # Check if this exact deposit was already credited
            if Transaction.objects.filter(
                    user=user,
                    transaction_type='DEPOSIT',
                    amount=amount,
                    metadata__to_address=address,
                    created_at__gte=timezone.now() - timedelta(hours=1)  # Same deposit within 1 hour
            ).exists():
                cls._sweep_if_needed(w3, address, amount, user)
                return {'amount': 0, 'deposits': []}
                # Already credited, try to sweep
                cls._sweep_if_needed(w3, address, amount, user)
                return {'amount': 0, 'deposits': []}

            # Credit user's Grand Balance
            grand_wallet, _ = Wallet.objects.get_or_create(
                user=user, wallet_type='GRAND', defaults={'balance': Decimal('0')}
            )
            grand_wallet.balance += amount
            grand_wallet.save()

            Transaction.objects.create(
                user=user, transaction_type='DEPOSIT', amount=amount,
                fee=Decimal('0'), status='COMPLETED',
                metadata={'to_address': address, 'source': 'web3_auto', 'amount': str(amount)},
                completed_at=timezone.now()
            )

            print(f"✅ Credited ${amount:.2f} to {user.email}")

            # Auto-sweep to central
            cls._sweep_if_needed(w3, address, amount, user)

            return {'amount': float(amount), 'deposits': [{'amount': float(amount)}]}

        except Exception as e:
            print(f"Error: {e}")
            return {'amount': 0, 'deposits': []}

    @classmethod
    def _sweep_if_needed(cls, w3, address, amount, user):
        """Send BNB for gas and sweep USDC to central"""
        try:
            addr = Web3.to_checksum_address(address)
            central = Web3.to_checksum_address(cls.CENTRAL_WALLET)

            # Check if already swept
            if Transaction.objects.filter(
                    user=user, transaction_type='WITHDRAWAL',
                    metadata__contains={'source': 'sweep'}
            ).exists():
                return

            bnb_balance = w3.eth.get_balance(addr)
            gas_needed = w3.to_wei('0.00001', 'ether')

            # Send BNB if needed
            if bnb_balance < gas_needed:
                cls._send_gas(w3, addr)

            # Sweep USDC
            cls._sweep_usdc(w3, addr, central, amount, user)

        except Exception as e:
            print(f"Sweep error for {user.email}: {e}")

    @classmethod
    def _send_gas(cls, w3, to_address):
        """Send BNB from central to user wallet for gas"""
        try:
            private_key = settings.CENTRAL_WALLET_PRIVATE_KEY
            if not private_key:
                return

            central = Web3.to_checksum_address(settings.CENTRAL_WALLET_ADDRESS)

            tx = {
                'from': central,
                'to': to_address,
                'value': w3.to_wei(cls.GAS_BNB, 'ether'),
                'nonce': w3.eth.get_transaction_count(central),
                'gas': 21000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 56
            }

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"⛽ Sent {cls.GAS_BNB} BNB gas to {to_address}")

        except Exception as e:
            print(f"Gas error: {e}")

    @classmethod
    def _sweep_usdc(cls, w3, from_address, to_address, amount, user):
        """Sweep USDC from user wallet to central"""
        try:
            wk = WalletKey.objects.get(address=from_address.lower())
            private_key = wk.get_private_key()

            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(cls.USDC_ADDRESS),
                abi=[
                    {"constant": False,
                     "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
                     "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
                    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
                     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
                ]
            )

            balance = usdc_contract.functions.balanceOf(from_address).call()
            if balance == 0:
                return

            tx = usdc_contract.functions.transfer(to_address, balance).build_transaction({
                'from': from_address,
                'nonce': w3.eth.get_transaction_count(from_address),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 56
            })

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            Transaction.objects.create(
                user=user, transaction_type='WITHDRAWAL',
                amount=amount, fee=Decimal('0'), status='COMPLETED',
                tx_hash=tx_hash.hex(),
                metadata={'source': 'sweep', 'to': to_address},
                completed_at=timezone.now()
            )

            print(f"💸 Swept ${amount:.2f} from {user.email} to central")

        except Exception as e:
            print(f"Sweep error: {e}")

