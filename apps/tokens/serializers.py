from rest_framework import serializers
from .models import CryptoToken, UserTokenBalance, Purchase

class CryptoTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoToken
        fields = ['id', 'symbol', 'name', 'current_price', 'is_active']

class UserTokenBalanceSerializer(serializers.ModelSerializer):
    token_symbol = serializers.CharField(source='token.symbol', read_only=True)
    token_name = serializers.CharField(source='token.name', read_only=True)
    current_price = serializers.DecimalField(source='token.current_price', read_only=True, max_digits=20, decimal_places=8)
    current_value = serializers.DecimalField(read_only=True, max_digits=20, decimal_places=8)
    
    class Meta:
        model = UserTokenBalance
        fields = ['id', 'token', 'token_symbol', 'token_name', 'quantity', 'average_buy_price', 'current_price', 'current_value']

class PurchaseSerializer(serializers.Serializer):
    token_id = serializers.UUIDField()
    amount_usdc = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=0.01)
    
class SellSerializer(serializers.Serializer):
    token_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=0.00000001)