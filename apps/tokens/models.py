from django.db import models
from django.conf import settings
import uuid


class CryptoToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    contract_address = models.CharField(max_length=100, blank=True, null=True)
    current_price = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    def update_price(self, new_price):
        self.current_price = new_price
        self.save()


class UserTokenBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='token_balances')
    token = models.ForeignKey(CryptoToken, on_delete=models.CASCADE, related_name='user_balances')
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    average_buy_price = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    highest_price_since_purchase = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    take_profit_triggered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'token']

    def __str__(self):
        return f"{self.user.email} - {self.token.symbol}: {self.quantity}"

    @property
    def current_value(self):
        return self.quantity * self.token.current_price

    def add_tokens(self, quantity, price):
        total_quantity = self.quantity + quantity
        total_cost = (self.quantity * self.average_buy_price) + (quantity * price)
        self.average_buy_price = total_cost / total_quantity if total_quantity > 0 else 0
        self.quantity = total_quantity
        self.highest_price_since_purchase = max(self.highest_price_since_purchase, price)
        self.take_profit_triggered = False
        self.save()

    def remove_tokens(self, quantity):
        if self.quantity >= quantity:
            self.quantity -= quantity
            if self.quantity == 0:
                self.average_buy_price = 0
                self.highest_price_since_purchase = 0
                self.take_profit_triggered = False
            self.save()
            return True
        return False

    def update_highest_price(self, current_price):
        if current_price > self.highest_price_since_purchase:
            self.highest_price_since_purchase = current_price
            self.save()
            return True
        return False

    def should_take_profit(self):
        """Check if price has gained 20% from purchase price"""
        if self.quantity <= 0 or self.take_profit_triggered:
            return False

        # Calculate gain from purchase price
        gain_percent = ((self.token.current_price - self.average_buy_price) / self.average_buy_price) * 100

        # If gain is 20% or more, trigger take profit
        return gain_percent >= 20


class Purchase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.ForeignKey(CryptoToken, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price_per_token = models.DecimalField(max_digits=20, decimal_places=8)
    total_amount = models.DecimalField(max_digits=20, decimal_places=8)
    node_fee = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.token.symbol} - {self.quantity}"


