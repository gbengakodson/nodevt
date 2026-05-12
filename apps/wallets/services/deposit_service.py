from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction
from .web3_service import Web3Service

class DepositService:
    @classmethod
    @transaction.atomic
    def process_usdc_deposit(cls, user, tx_hash, amount=None):
        """
        Process USDC deposit after verification
        """
        try:
            web3_service = Web3Service()
            
            # Get user's wallet address
            if not user.wallet_address:
                # Create a wallet for user if they don't have one
                wallet = web3_service.create_deposit_wallet()
                user.wallet_address = wallet['address']
                user.save()
            
            # Verify deposit
            if amount:
                verified = web3_service.verify_deposit(
                    user.wallet_address, 
                    Decimal(str(amount))
                )
            else:
                verified = web3_service.verify_deposit(
                    user.wallet_address,
                    Decimal('0'),
                    tx_hash
                )
            
            if not verified:
                return {
                    'success': False,
                    'error': 'Deposit verification failed'
                }
            
            # Get amount from transaction if not provided
            if not amount:
                amount = web3_service.get_usdc_balance(user.wallet_address)
            
            # Get or create grand wallet
            grand_wallet, created = Wallet.objects.get_or_create(
                user=user,
                wallet_type='GRAND',
                defaults={'balance': Decimal('0')}
            )
            
            # Add to grand wallet
            grand_wallet.balance += Decimal(str(amount))
            grand_wallet.save()
            
            # Create transaction record
            transaction_obj = Transaction.objects.create(
                user=user,
                transaction_type='DEPOSIT',
                amount=Decimal(str(amount)),
                fee=Decimal('0'),
                status='COMPLETED',
                tx_hash=tx_hash,
                metadata={
                    'wallet_address': user.wallet_address,
                    'token': 'USDC',
                    'network': 'BEP20'
                },
                completed_at=timezone.now()
            )
            
            return {
                'success': True,
                'amount': amount,
                'transaction': transaction_obj,
                'new_balance': grand_wallet.balance
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @classmethod
    def get_deposit_address(cls, user):
        """Get or create deposit address for user"""
        from apps.wallets.models import WalletKey

        try:
            wallet_key = WalletKey.objects.get(user=user)
            return wallet_key.address
        except WalletKey.DoesNotExist:
            pass

        # Create new wallet
        web3_service = Web3Service()
        wallet = web3_service.create_deposit_wallet()

        # Store wallet
        wallet_key = WalletKey.objects.create(
            user=user,
            address=wallet['address'],
            encrypted_key=''
        )
        wallet_key.set_private_key(wallet['private_key'])
        wallet_key.save()

        user.wallet_address = wallet['address']
        user.save()

        # Fund with BNB for gas (0.001 BNB ~$0.60)
        try:
            from apps.wallets.services.binance_service import BinanceService
            bs = BinanceService()
            result = bs.send_bnb(wallet['address'], 0.001)
            if result['success']:
                print(f"Funded {wallet['address']} with 0.001 BNB for gas")
            else:
                print(f"BNB funding failed: {result.get('error')}")
        except Exception as e:
            print(f"Error funding BNB: {e}")

        return wallet_key.address

    
    @classmethod
    def check_user_deposits(cls, user, last_block=None):
        """Check for new USDC deposits for a user"""
        try:
            web3_service = Web3Service()
            
            # Get user's wallet address
            if not user.wallet_address:
                return {'deposits': [], 'last_block': 0, 'total_deposits': 0}
            
            # Check for new deposits
            result = web3_service.check_new_deposits(user.wallet_address, last_block)
            
            # Process each deposit
            for deposit in result['deposits']:
                # Check if this transaction was already processed
                from apps.wallets.models import Transaction
                exists = Transaction.objects.filter(
                    user=user,
                    tx_hash=deposit['tx_hash'],
                    transaction_type='DEPOSIT'
                ).exists()
                
                if not exists:
                    # Process new deposit
                    cls.process_usdc_deposit(
                        user,
                        deposit['tx_hash'],
                        deposit['amount']
                    )
                    print(f"Processed deposit: {deposit['amount']} USDC from {deposit['from']}")
            
            return result
            
        except Exception as e:
            print(f"Error checking user deposits: {e}")
            return {'deposits': [], 'last_block': 0, 'total_deposits': 0}

 
   
