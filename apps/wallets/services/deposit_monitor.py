import requests
from decimal import Decimal
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction, WalletKey
from django.contrib.auth import get_user_model

User = get_user_model()


class DepositMonitor:
    """Monitors BSC for incoming USDC deposits to user wallets"""

    USDC_CONTRACT = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
    BSCSCAN_API = 'https://api.bscscan.com/api'

    # Use BSCScan API key if you have one, otherwise rate limited
    API_KEY = ''  # Add your BSCScan API key for faster checks

    @classmethod
    def check_all_users(cls):
        """Check all users for new deposits"""
        wallet_keys = WalletKey.objects.select_related('user').all()
        total_deposited = 0

        for wk in wallet_keys:
            try:
                result = cls.check_deposits(wk.address, wk.user)
                if result.get('amount', 0) > 0:
                    total_deposited += result['amount']
                    print(f"Deposit: {result['amount']} USDC to {wk.user.email}")
            except Exception as e:
                print(f"Error checking {wk.user.email}: {e}")

        return total_deposited

    @classmethod
    def check_deposits(cls, address, user):
        """Check USDC deposits for a specific address"""
        try:
            params = {
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': cls.USDC_CONTRACT,
                'address': address,
                'sort': 'desc',
                'offset': 5
            }
            if cls.API_KEY:
                params['apikey'] = cls.API_KEY

            response = requests.get(cls.BSCSCAN_API, params=params, timeout=10)
            data = response.json()

            if data.get('status') != '1':
                return {'amount': 0, 'deposits': []}

            deposits = []
            total_amount = Decimal('0')

            for tx in data.get('result', []):
                # Only count incoming transfers (to user's address)
                if tx['to'].lower() != address.lower():
                    continue

                tx_hash = tx['hash']

                # Check if already processed
                already = Transaction.objects.filter(
                    user=user,
                    tx_hash=tx_hash,
                    transaction_type='DEPOSIT'
                ).exists()

                if already:
                    continue

                amount = Decimal(tx['value']) / Decimal(10 ** 18)

                # Credit the user
                grand_wallet, _ = Wallet.objects.get_or_create(
                    user=user,
                    wallet_type='GRAND',
                    defaults={'balance': Decimal('0')}
                )

                grand_wallet.balance += amount
                grand_wallet.save()

                Transaction.objects.create(
                    user=user,
                    transaction_type='DEPOSIT',
                    amount=amount,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    tx_hash=tx_hash,
                    metadata={
                        'from_address': tx['from'],
                        'to_address': address,
                        'source': 'bsc_auto_detect'
                    },
                    completed_at=timezone.now()
                )

                deposits.append({
                    'tx_hash': tx_hash,
                    'amount': float(amount),
                    'from': tx['from']
                })

                total_amount += amount

            return {
                'amount': float(total_amount),
                'deposits': deposits
            }

        except Exception as e:
            print(f"Error checking deposits for {address}: {e}")
            return {'amount': 0, 'deposits': []}