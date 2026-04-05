from web3 import Web3
from decimal import Decimal
import os

class TransactionService:
    BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
    USDC_CONTRACT = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
    
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(self.BSC_RPC_URL))
        self.platform_wallet = os.environ.get('PLATFORM_WALLET_ADDRESS')
        self.platform_private_key = os.environ.get('PLATFORM_PRIVATE_KEY')
        
        self.usdc_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_CONTRACT),
            abi=self.usdc_abi
        )
    
    def create_buy_transaction(self, user_address, amount_usdc):
        """Create transaction for user to send USDC to platform"""
        try:
            amount_wei = int(amount_usdc * 10**18)
            
            tx = self.usdc_contract.functions.transfer(
                Web3.to_checksum_address(self.platform_wallet),
                amount_wei
            ).build_transaction({
                'from': Web3.to_checksum_address(user_address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(user_address)
            })
            
            return tx
        except Exception as e:
            print(f"Error creating transaction: {e}")
            return None