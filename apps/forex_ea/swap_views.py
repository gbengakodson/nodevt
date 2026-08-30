from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from .models import FiatBalance
from .rates_service import get_fiat_rate, get_commodity_price, get_spot_rates
from apps.wallets.models import Wallet

SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'NGN', 'GOLD', 'USOIL']
FEE_PERCENT = Decimal('0.01')   # 1% fee

class ForexSwapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from_currency = request.data.get('from_currency', '').upper()
        to_currency = request.data.get('to_currency', '').upper()
        try:
            amount = Decimal(str(request.data.get('amount', '0')))
        except:
            return Response({'error': 'Invalid amount'}, status=400)

        if from_currency not in SUPPORTED_CURRENCIES or to_currency not in SUPPORTED_CURRENCIES:
            return Response({'error': 'Unsupported currency'}, status=400)
        if from_currency == to_currency:
            return Response({'error': 'Same currency'}, status=400)
        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)

        # 1. Fetch source balance
        if from_currency == 'USD':
            from apps.wallets.models import WalletKey
            from apps.wallets.services.web3_service import Web3Service
            try:
                wallet_key = WalletKey.objects.get(user=request.user)
                ws = Web3Service()
                source_balance = Decimal(str(ws.get_usdc_balance(wallet_key.address)))
            except WalletKey.DoesNotExist:
                return Response({'error': 'No wallet found'}, status=400)
        else:
            fiat, _ = FiatBalance.objects.get_or_create(user=request.user, currency=from_currency)
            source_balance = fiat.balance

        if source_balance < amount:
            return Response({'error': f'Insufficient {from_currency} balance'}, status=400)

        # 2. Compute conversion rate
        try:
            if to_currency in ['GOLD', 'USOIL']:
                # Convert from fiat to commodity: quote in USD per unit
                if from_currency == 'USD':
                    rate_to_usd = Decimal('1.0')
                else:
                    rate_to_usd = get_fiat_rate(from_currency, 'USD')
                commodity_usd_price = get_commodity_price(to_currency)
                # amount_currency -> USD -> units of commodity
                amount_usd = amount * rate_to_usd
                converted_amount = amount_usd / commodity_usd_price
            elif from_currency in ['GOLD', 'USOIL']:
                # Convert from commodity to fiat
                commodity_usd_price = get_commodity_price(from_currency)
                amount_usd = amount * commodity_usd_price
                if to_currency == 'USD':
                    converted_amount = amount_usd
                else:
                    rate = get_fiat_rate('USD', to_currency)
                    converted_amount = amount_usd * rate
            else:
                rate = get_fiat_rate(from_currency, to_currency)
                converted_amount = amount * rate
        except Exception as e:
            return Response({'error': f'Rate fetch failed: {str(e)}'}, status=500)

        # 3. Apply 1% fee on the converted amount
        fee = converted_amount * FEE_PERCENT
        final_amount = converted_amount - fee

        # 4. Deduct source balance
        if from_currency != 'USD':
            fiat.balance -= amount
            fiat.save()
        # For USD, sweep the USDC from user's wallet to central
        if from_currency == 'USD':
            from apps.trading.views import TradingViewSet
            from django.conf import settings
            user_private_key = wallet_key.get_private_key()
            sweep = TradingViewSet._sweep_from_user_wallet(
                wallet_key.address,
                user_private_key,
                settings.CENTRAL_WALLET_ADDRESS,
                amount
            )
            if not sweep['success']:
                return Response({'error': f'Sweep failed: {sweep.get("error")}'}, status=400)

        # 5. Credit target balance
        if to_currency == 'USD':
            wallet = Wallet.objects.get_or_create(user=request.user, wallet_type='GRAND', defaults={'balance': Decimal('0')})[0]
            wallet.balance += final_amount
            wallet.save()
        else:
            target_fiat, _ = FiatBalance.objects.get_or_create(user=request.user, currency=to_currency)
            target_fiat.balance += final_amount
            target_fiat.save()



        return Response({
            'success': True,
            'from_currency': from_currency,
            'to_currency': to_currency,
            'amount': float(amount),
            'converted_amount': float(converted_amount),
            'fee': float(fee),
            'final_amount': float(final_amount),
        })


class ForexBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        balances = {}
        for currency, _ in FiatBalance.ASSET_CHOICES:
            if currency == 'USD':
                wallet = Wallet.objects.filter(user=request.user, wallet_type='GRAND').first()
                balance = wallet.balance if wallet else Decimal('0')
            else:
                fiat, _ = FiatBalance.objects.get_or_create(user=request.user, currency=currency)
                balance = fiat.balance
            balances[currency] = float(balance)

        return Response({'balances': balances})

    from .rates_service import get_spot_rates

    class SpotRatesView(APIView):
        permission_classes = [IsAuthenticated]

        def get(self, request):
            return Response({'rates': get_spot_rates()})


class SpotRatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'rates': get_spot_rates()})