from django.core.management.base import BaseCommand
from apps.wallets.models import WalletKey, Transaction
from apps.wallets.services.web3_service import Web3Service
from django.conf import settings
from web3 import Web3
from decimal import Decimal
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sweep USDC from user wallets to central Binance wallet'

    USDC_ADDRESS = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
    BSC_RPC = 'https://bsc-rpc.publicnode.com'
    GAS_LIMIT = 100000
    MIN_SWEEP = Decimal('1.00')  # Only sweep if balance > $1

    def handle(self, *args, **options):
        central_wallet = settings.CENTRAL_WALLET_ADDRESS

        if not central_wallet:
            self.stdout.write(self.style.ERROR("CENTRAL_WALLET_ADDRESS not set!"))
            return

        w3 = Web3(Web3.HTTPProvider(self.BSC_RPC))

        # USDC Transfer ABI
        usdc_abi = [
            {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
             "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
             "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}],
             "type": "function"},
        ]

        usdc_contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_ADDRESS),
            abi=usdc_abi
        )

        total_swept = Decimal('0')
        wallet_keys = WalletKey.objects.select_related('user').all()

        for wk in wallet_keys:
            try:
                address = Web3.to_checksum_address(wk.address)

                # Get USDC balance
                balance = usdc_contract.functions.balanceOf(address).call()
                balance_usdc = Decimal(str(balance)) / Decimal(10 ** 18)

                if balance_usdc < self.MIN_SWEEP:
                    continue

                self.stdout.write(f"{wk.user.email}: ${balance_usdc:.2f} USDC")

                # Decrypt private key
                private_key = wk.get_private_key()

                # Get BNB for gas
                bnb_balance = w3.eth.get_balance(address)
                gas_price = w3.eth.gas_price
                gas_cost = Decimal(str(self.GAS_LIMIT)) * Decimal(str(gas_price)) / Decimal(10 ** 18)

                if bnb_balance < (self.GAS_LIMIT * gas_price):
                    self.stdout.write(self.style.WARNING(f"  Low BNB for gas. Need {gas_cost:.6f} BNB"))
                    continue

                # Build transfer transaction
                tx = usdc_contract.functions.transfer(
                    Web3.to_checksum_address(central_wallet),
                    balance
                ).build_transaction({
                    'from': address,
                    'nonce': w3.eth.get_transaction_count(address),
                    'gas': self.GAS_LIMIT,
                    'gasPrice': gas_price,
                    'chainId': 56
                })

                # Sign and send
                signed_tx = w3.eth.account.sign_transaction(tx, private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                self.stdout.write(self.style.SUCCESS(f"  Swept to central: {tx_hash.hex()}"))

                # Record sweep transaction
                Transaction.objects.create(
                    user=wk.user,
                    transaction_type='WITHDRAWAL',
                    amount=balance_usdc,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    tx_hash=tx_hash.hex(),
                    metadata={
                        'type': 'sweep_to_central',
                        'from_address': wk.address,
                        'to_address': central_wallet
                    },
                    completed_at=timezone.now()
                )

                total_swept += balance_usdc

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))
                continue

        self.stdout.write(self.style.SUCCESS(f"\nTotal swept: ${total_swept:.2f} USDC"))
