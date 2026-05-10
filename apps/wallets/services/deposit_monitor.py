from decimal import Decimal
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction, WalletKey
from django.contrib.auth import get_user_model
from web3 import Web3

User = get_user_model()


class DepositMonitor:
    """Monitors BSC for incoming USDC deposits using direct Web3 connection"""

    USDC_ADDRESS = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
    BSC_RPC = 'https://bsc-rpc.publicnode.com'

    # USDC Transfer event topic
    TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

    @classmethod
    def check_all_users(cls):
        """Check all users for new deposits via Web3"""
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
        """Check USDC deposits using Web3"""
        try:
            w3 = Web3(Web3.HTTPProvider(cls.BSC_RPC))
            if not w3.is_connected():
                return {'amount': 0, 'deposits': []}

            # Build filter for USDC transfers TO this address
            transfer_filter = {
                'fromBlock': w3.eth.block_number - 20000,  # Last ~20000 blocks (~4 hours)
                'toBlock': 'latest',
                'address': Web3.to_checksum_address(cls.USDC_ADDRESS),
                'topics': [
                    cls.TRANSFER_TOPIC,
                    None,  # From any sender
                    '0x' + address[2:].lower().zfill(64)  # To this user
                ]
            }

            logs = w3.eth.get_logs(transfer_filter)

            total_amount = Decimal('0')
            deposits = []

            for log in logs:
                tx_hash = log['transactionHash'].hex()

                # Check if already processed
                if Transaction.objects.filter(user=user, tx_hash=tx_hash, transaction_type='DEPOSIT').exists():
                    continue

                # Amount is in the data field (uint256)
                amount = Decimal(str(int(log['data'].hex(), 16))) / Decimal(10 ** 18)

                # Credit user
                grand_wallet, _ = Wallet.objects.get_or_create(
                    user=user, wallet_type='GRAND', defaults={'balance': Decimal('0')}
                )
                grand_wallet.balance += amount
                grand_wallet.save()

                Transaction.objects.create(
                    user=user, transaction_type='DEPOSIT', amount=amount,
                    fee=Decimal('0'), status='COMPLETED', tx_hash=tx_hash,
                    metadata={'to_address': address, 'source': 'web3_direct'},
                    completed_at=timezone.now()
                )

                deposits.append({'tx_hash': tx_hash, 'amount': float(amount)})
                total_amount += amount
                print(f"  ✅ ${amount:.2f} — {tx_hash[:20]}...")

            return {'amount': float(total_amount), 'deposits': deposits}

        except Exception as e:
            print(f"Error: {e}")
            return {'amount': 0, 'deposits': []}