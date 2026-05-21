from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from apps.wallets.models import Transaction
from apps.wallets.services.binance_service import BinanceService
from apps.wallets.services.web3_service import Web3Service
from web3 import Web3


class TreasuryController:
    """
    Manages automated fund flow between Web3 (deposits/withdrawals)
    and Binance (grid trading).

    Flow:
    - Web3 receives deposits → sweep to Binance for grid trading
    - Binance generates profits → sweep to Web3 for withdrawals
    - Maintain minimum reserves on both sides
    """

    # Minimum reserves
    MIN_BINANCE_RESERVE = Decimal('200')  # Keep at least $200 on Binance for grids
    MIN_WEB3_RESERVE = Decimal('50')  # Keep at least $50 on Web3 for withdrawals

    @classmethod
    def get_balances(cls):
        """Get current balances on both sides"""
        bs = BinanceService()
        ws = Web3Service()

        binance_balance = bs.get_usdc_balance()
        web3_balance = ws.get_usdc_balance(settings.CENTRAL_WALLET_ADDRESS)

        return {
            'binance': binance_balance,
            'web3': web3_balance,
            'total': binance_balance + web3_balance,
        }

    @classmethod
    def sweep_web3_to_binance(cls, amount=None):
        """
        Sweep USDC from Web3 central wallet to Binance.
        Called when Web3 has excess funds or Binance needs capital.
        """
        try:
            balances = cls.get_balances()

            if balances['web3'] <= cls.MIN_WEB3_RESERVE:
                return {
                    'success': False,
                    'error': f"Web3 balance (${float(balances['web3']):.2f}) below minimum reserve (${float(cls.MIN_WEB3_RESERVE)})"
                }

            # Calculate sweepable amount
            max_sweep = balances['web3'] - cls.MIN_WEB3_RESERVE

            if amount is None:
                amount = max_sweep
            else:
                amount = min(Decimal(str(amount)), max_sweep)

            if amount <= 0:
                return {'success': False, 'error': 'No funds available to sweep'}

            # Send USDC from Web3 to Binance deposit address
            # Note: Binance doesn't have a direct deposit address via API
            # We use Binance's internal transfer or just track it
            # For now, we'll transfer from Web3 central to Binance via BSC

            ws = Web3Service()
            w3 = Web3(Web3.HTTPProvider(ws.BSC_RPC_URL))

            # Get Binance USDC deposit address (you'll need to set this)
            binance_deposit_address = getattr(settings, 'BINANCE_USDC_DEPOSIT_ADDRESS', None)

            if not binance_deposit_address:
                return {
                    'success': False,
                    'error': 'BINANCE_USDC_DEPOSIT_ADDRESS not configured in settings'
                }

            central = Web3.to_checksum_address(settings.CENTRAL_WALLET_ADDRESS)
            private_key = settings.CENTRAL_WALLET_PRIVATE_KEY

            usdc_address = Web3.to_checksum_address('0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d')

            # USDC transfer ABI
            abi = [
                {"constant": False,
                 "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
                 "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            ]

            contract = w3.eth.contract(address=usdc_address, abi=abi)

            amount_wei = int(Decimal(str(amount)) * Decimal(10 ** 18))

            tx = contract.functions.transfer(
                Web3.to_checksum_address(binance_deposit_address),
                amount_wei
            ).build_transaction({
                'from': central,
                'nonce': w3.eth.get_transaction_count(central),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 56
            })

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            # Log transaction
            Transaction.objects.create(
                user=None,
                transaction_type='SWEEP',
                amount=amount,
                fee=Decimal('0'),
                status='COMPLETED',
                tx_hash=tx_hash.hex(),
                metadata={
                    'from': 'WEB3',
                    'to': 'BINANCE',
                    'from_address': settings.CENTRAL_WALLET_ADDRESS,
                    'to_address': binance_deposit_address,
                },
                completed_at=timezone.now()
            )

            print(f"💸 Swept ${float(amount):.2f} from Web3 to Binance. TX: {tx_hash.hex()[:20]}...")

            return {
                'success': True,
                'amount': float(amount),
                'tx_hash': tx_hash.hex(),
            }

        except Exception as e:
            print(f"Web3 to Binance sweep error: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def sweep_binance_to_web3(cls, amount=None):
        """
        Sweep profits from Binance to Web3 central wallet.
        Called when Binance has excess profits or Web3 needs withdrawal funds.
        """
        try:
            balances = cls.get_balances()

            if balances['binance'] <= cls.MIN_BINANCE_RESERVE:
                return {
                    'success': False,
                    'error': f"Binance balance (${float(balances['binance']):.2f}) below minimum reserve (${float(cls.MIN_BINANCE_RESERVE)})"
                }

            # Calculate sweepable amount
            max_sweep = balances['binance'] - cls.MIN_BINANCE_RESERVE

            if amount is None:
                amount = max_sweep
            else:
                amount = min(Decimal(str(amount)), max_sweep)

            if amount <= 0:
                return {'success': False, 'error': 'No profits available to sweep'}

            # Withdraw from Binance to Web3 central wallet
            bs = BinanceService()
            result = bs.withdraw_usdc(
                to_address=settings.CENTRAL_WALLET_ADDRESS,
                amount=float(amount),
                network='BSC'
            )

            if result['success']:
                # Log transaction
                Transaction.objects.create(
                    user=None,
                    transaction_type='SWEEP',
                    amount=amount,
                    fee=Decimal('0'),
                    status='COMPLETED',
                    tx_hash=result.get('tx_id', ''),
                    metadata={
                        'from': 'BINANCE',
                        'to': 'WEB3',
                        'to_address': settings.CENTRAL_WALLET_ADDRESS,
                    },
                    completed_at=timezone.now()
                )

                print(f"💸 Swept ${float(amount):.2f} from Binance to Web3")

            return result

        except Exception as e:
            print(f"Binance to Web3 sweep error: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def auto_balance(cls):
        """
        Automatic balancing run:
        1. Check if Web3 has excess → sweep to Binance
        2. Check if Binance has excess profits → sweep to Web3
        3. Ensure both sides maintain minimum reserves
        """
        actions = []
        balances = cls.get_balances()

        print(f"\n=== Treasury Auto-Balance ===")
        print(f"Binance: ${float(balances['binance']):.2f} (min: ${float(cls.MIN_BINANCE_RESERVE)})")
        print(f"Web3: ${float(balances['web3']):.2f} (min: ${float(cls.MIN_WEB3_RESERVE)})")

        # If Binance is below minimum, sweep from Web3
        if balances['binance'] < cls.MIN_BINANCE_RESERVE:
            needed = cls.MIN_BINANCE_RESERVE - balances['binance']
            result = cls.sweep_web3_to_binance(amount=needed)
            if result['success']:
                actions.append(f"Swept ${result['amount']:.2f} Web3→Binance")

        # If Web3 is below minimum, sweep from Binance
        if balances['web3'] < cls.MIN_WEB3_RESERVE:
            needed = cls.MIN_WEB3_RESERVE - balances['web3']
            result = cls.sweep_binance_to_web3(amount=needed)
            if result['success']:
                actions.append(f"Swept ${result['amount']:.2f} Binance→Web3")

        # If both are above minimum, sweep excess Web3 to Binance for trading
        if balances['web3'] > cls.MIN_WEB3_RESERVE and balances['binance'] >= cls.MIN_BINANCE_RESERVE:
            result = cls.sweep_web3_to_binance()
            if result['success']:
                actions.append(f"Swept excess ${result['amount']:.2f} Web3→Binance for trading")

        if not actions:
            actions.append("No balancing needed — both sides above minimum")

        print(f"Actions: {', '.join(actions)}")

        return {
            'balances': {k: float(v) for k, v in balances.items()},
            'actions': actions,
        }