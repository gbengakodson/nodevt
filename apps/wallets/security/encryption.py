from cryptography.fernet import Fernet
import os

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    @classmethod
    def get_key(cls):
        """Get encryption key from environment"""
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            # For development only - generate a key
            # In production, you MUST set ENCRYPTION_KEY in environment
            key = Fernet.generate_key().decode()
            print(f"WARNING: Using temporary encryption key. Set ENCRYPTION_KEY in .env file")
            print(f"Add this to your .env: ENCRYPTION_KEY={key}")
        return key.encode()
    
    @classmethod
    def encrypt(cls, data):
        """Encrypt sensitive data"""
        if not data:
            return None
        
        try:
            key = cls.get_key()
            f = Fernet(key)
            encrypted = f.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return None
    
    @classmethod
    def decrypt(cls, encrypted_data):
        """Decrypt sensitive data"""
        if not encrypted_data:
            return None
        
        try:
            key = cls.get_key()
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return None