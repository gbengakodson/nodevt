from django.db import models
from django.conf import settings
import uuid

class Wallet(models.Model):
    WALLET_TYPES = [
        ('GRAND', 'Grand Balance'),
        ('YIELD', 'Yield Wallet'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallets')
    wallet_type = models.CharField(max_length=10, choices=WALLET_TYPES)
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'wallet_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.wallet_type}"
    
    def add_balance(self, amount):
        self.balance += amount
        self.save()
    
    def subtract_balance(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('PURCHASE', 'Purchase'),
        ('SALE', 'Sale'),
        ('YIELD', 'Yield'),
        ('REFERRAL', 'Referral'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    tx_hash = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - {self.amount}"

class WalletKey(models.Model):
    """Stores encrypted wallet private keys"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_key')
    address = models.CharField(max_length=100, unique=True)
    encrypted_key = models.TextField()  # Store encrypted private key
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.address}"
    
    def set_private_key(self, private_key):
        """Encrypt and store private key"""
        from apps.wallets.security.encryption import EncryptionService
        self.encrypted_key = EncryptionService.encrypt(private_key)
    
    def get_private_key(self):
        """Decrypt and return private key"""
        from apps.wallets.security.encryption import EncryptionService
        return EncryptionService.decrypt(self.encrypted_key)