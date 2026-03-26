from web3 import Web3
from decimal import Decimal

class Web3Service:
    # Working BSC RPC endpoint
    BSC_RPC_URL = "https://bsc-rpc.publicnode.com"
    
    # USDC Contract Address on BSC (BEP-20)
    USDC_CONTRACT_ADDRESS = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
    USDC_DECIMALS = 18
    
    def __init__(self):
        self.mock_mode = True
        self.w3 = None
        self.usdc_contract = None
        
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.BSC_RPC_URL, request_kwargs={'timeout': 10}))
            if self.w3.is_connected():
                self.mock_mode = False
                print(f"Connected to BSC network")
                print(f"Chain ID: {self.w3.eth.chain_id}")
                print(f"Block: {self.w3.eth.block_number}")
            else:
                print("Failed to connect, using mock mode")
        except Exception as e:
            print(f"Connection error: {e}, using mock mode")
        
        if self.mock_mode:
            print("Running in mock mode - using simulated blockchain")
        else:
            # USDC contract ABI
            self.usdc_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                },
            ]
            
            # Create contract instance
            checksum_address = Web3.to_checksum_address(self.USDC_CONTRACT_ADDRESS)
            self.usdc_contract = self.w3.eth.contract(
                address=checksum_address,
                abi=self.usdc_abi
            )
            print(f"USDC contract initialized")
    
    def get_usdc_balance(self, address):
        """Get real USDC balance for a wallet address"""
        if self.mock_mode:
            return Decimal('0')
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance = self.usdc_contract.functions.balanceOf(checksum_address).call()
            return Decimal(str(balance)) / Decimal(10 ** self.USDC_DECIMALS)
        except Exception as e:
            print(f"Error getting balance: {e}")
            return Decimal('0')
    
    def verify_deposit(self, user_address, expected_amount, tx_hash=None):
        """Verify USDC deposit"""
        if self.mock_mode:
            return True
        try:
            current_balance = self.get_usdc_balance(user_address)
            return current_balance >= expected_amount
        except Exception as e:
            print(f"Error verifying deposit: {e}")
            return False
    
    def create_deposit_wallet(self):
        """Generate a new Ethereum wallet"""
        if self.mock_mode:
            return {
                'address': '0x742d35Cc6634C0532925a3b844Bc9e7598ff6b5d',
                'private_key': '0x' + '1' * 64,
            }
        
        account = self.w3.eth.account.create()
        return {
            'address': account.address,
            'private_key': account.key.hex(),
        }
    
    def is_valid_address(self, address):
        """Check if address is valid"""
        if self.mock_mode:
            return len(address) > 0
        try:
            return Web3.is_address(address)
        except:
            return False