from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, ExchangeAPIConnection
from django.contrib.auth import authenticate
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from apps.accounts.services.otp_service import OTPService
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework_simplejwt.tokens import RefreshToken
import timezone, Decimal


import logging


logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = []  # Public access

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Save user type
            user.user_type = request.data.get('user_type', 'MICRO')
            user.save()

            # Default to admin if no referrer
            if not user.referrer:
                from django.contrib.auth import get_user_model
                UserModel = get_user_model()
                admin = UserModel.objects.filter(is_superuser=True).first()
                if admin:
                    user.referrer = admin
                    user.save()
                    # Create referral relationship
                    try:
                        from apps.referrals.services.referral_service import ReferralService
                        ReferralService.create_referral(admin, user)
                        print(f"Default referral: admin -> {user.email}")
                    except Exception as e:
                        print(f"Error creating default referral: {e}")

            # Create wallet for user
            from apps.wallets.services.deposit_service import DepositService
            try:
                address = DepositService.get_deposit_address(user)
                print(f"Wallet created for {user.email}: {address}")
            except Exception as e:
                print(f"Error creating wallet: {e}")

            # CREATE REFERRAL RELATIONSHIP IF REFERRAL CODE PROVIDED
            if user.referrer:
                try:
                    from apps.referrals.services.referral_service import ReferralService
                    ReferralService.create_referral(user.referrer, user)
                    print(f"ReferralRelationship created: {user.referrer.email} -> {user.email}")
                except Exception as e:
                    print(f"Error creating ReferralRelationship: {e}")

            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'Registration successful!'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data['email']
                password = serializer.validated_data['password']

                user = authenticate(request, username=email, password=password)
                if user:
                    refresh = RefreshToken.for_user(user)
                    return Response({
                        'user': UserSerializer(user).data,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                        'message': 'Login successful!'
                    })
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        data = request.data

        # If KYC approved, lock all fields except username
        if user.kyc_status == 'APPROVED':
            if 'username' in data:
                user.username = data['username']
                user.save()
            serializer = UserSerializer(user)
            return Response(serializer.data)

        # Normal updates for non-verified users
        if 'email' in data:
            user.email = data['email']
        if 'username' in data:
            user.username = data['username']
        if 'kyc_status' in data:
            user.kyc_status = data['kyc_status']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        if 'country' in data:
            user.country = data['country']
        if 'id_type' in data:
            user.id_type = data['id_type']
        if 'id_number' in data:
            user.id_number = data['id_number']

        user.save()
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def patch(self, request):
        return self.put(request)



@api_view(['POST'])
@permission_classes([AllowAny])
def request_login_otp(request):
    """Step 1: Validate credentials and send OTP"""
    email = request.data.get('email')
    password = request.data.get('password')

    user = authenticate(email=email, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    result = OTPService.generate_otp(user, 'LOGIN')
    return Response({'success': True, 'message': 'OTP sent', 'user_id': str(user.id)})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_otp(request):
    """Step 2: Verify OTP and return tokens"""
    user_id = request.data.get('user_id')
    code = request.data.get('code')

    user = User.objects.get(id=user_id)
    result = OTPService.verify_otp(user, code, 'LOGIN')

    if not result['success']:
        return Response({'error': result['error']}, status=400)

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_login_as_user(request):
    """Admin login as any user without changing password"""
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'email': user.email,
        'username': user.username
    })




class ExchangeConnectionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def list_connections(self, request):
        """List user's exchange connections"""
        connections = ExchangeAPIConnection.objects.filter(user=request.user)
        data = [{
            'id': str(c.id),
            'exchange': c.exchange,
            'label': c.label,
            'is_active': c.is_active,
            'min_capital': float(c.min_capital),
            'fee_per_trade': float(c.fee_per_trade),
            'created_at': c.created_at.isoformat(),
        } for c in connections]
        return Response(data)

    @action(detail=False, methods=['post'])
    def connect_exchange(self, request):
        """Connect a new exchange API"""
        exchange = request.data.get('exchange')
        api_key = request.data.get('api_key')
        api_secret = request.data.get('api_secret')
        label = request.data.get('label', '')
        min_capital = request.data.get('min_capital', 1000)

        if not exchange or not api_key or not api_secret:
            return Response({'error': 'Exchange, API key, and secret required'}, status=400)

        if exchange not in dict(ExchangeAPIConnection.EXCHANGE_CHOICES):
            return Response({'error': 'Invalid exchange'}, status=400)

        conn = ExchangeAPIConnection.objects.create(
            user=request.user,
            exchange=exchange,
            label=label,
            min_capital=min_capital,
        )
        conn.set_api_key(api_key)
        conn.set_api_secret(api_secret)
        conn.save()

        # Test connection
        test = conn.test_connection()

        return Response({
            'success': test['success'],
            'id': str(conn.id),
            'message': 'Connected' if test['success'] else f"Stored but test failed: {test.get('error', '')}",
        })

    @action(detail=False, methods=['post'])
    def disconnect_exchange(self, request):
        """Disconnect an exchange"""
        conn_id = request.data.get('connection_id')
        try:
            conn = ExchangeAPIConnection.objects.get(id=conn_id, user=request.user)
            conn.is_active = False
            conn.save()
            return Response({'success': True})
        except ExchangeAPIConnection.DoesNotExist:
            return Response({'error': 'Connection not found'}, status=404)

    @action(detail=False, methods=['get'])
    def exchange_balance(self, request):
        """Get balance from connected exchange"""
        conn_id = request.GET.get('connection_id')
        try:
            conn = ExchangeAPIConnection.objects.get(id=conn_id, user=request.user, is_active=True)
            client = conn.get_client()
            if conn.exchange == 'BINANCE' and client:
                account = client.get_account()
                balances = {}
                for b in account['balances']:
                    free = float(b['free'])
                    if free > 0:
                        balances[b['asset']] = free
                return Response({'exchange': conn.exchange, 'balances': balances})
            return Response({'error': 'Exchange not supported yet'}, status=400)
        except ExchangeAPIConnection.DoesNotExist:
            return Response({'error': 'Connection not found'}, status=404)

    @action(detail=False, methods=['post'])
    def activate_fadakka_external(self, request):
        """Start Fadakka auto-trading on user's connected exchange"""
        connection_id = request.data.get('connection_id')
        amount = Decimal(str(request.data.get('amount', 0)))

        if not connection_id or amount <= 0:
            return Response({'error': 'Connection and amount required'}, status=400)

        try:
            conn = ExchangeAPIConnection.objects.get(id=connection_id, user=request.user, is_active=True)
        except ExchangeAPIConnection.DoesNotExist:
            return Response({'error': 'Active connection not found'}, status=404)

        if amount < conn.min_capital:
            return Response({
                'error': f'Minimum capital is ${float(conn.min_capital):.2f}'
            }, status=400)

        # Get client
        client = conn.get_client()
        if not client:
            return Response({'error': f'{conn.exchange} not supported yet'}, status=400)

        # Check balance
        try:
            account = client.get_account()
            usdt_balance = Decimal('0')
            for b in account['balances']:
                if b['asset'] == 'USDT':
                    usdt_balance = Decimal(b['free'])
                    break
        except Exception as e:
            return Response({'error': f'Cannot access account: {str(e)}'}, status=400)

        if usdt_balance < amount:
            return Response({
                'error': f'Insufficient balance. Have ${float(usdt_balance):.2f}, need ${float(amount):.2f}'
            }, status=400)

        # Run Fadakka scan on user's exchange
        from apps.trading.services.fadakka_service import FadakkaService
        from apps.tokens.models import CryptoToken
        import requests

        # Fetch current prices from CoinGecko
        cg_ids_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana',
            'XRP': 'ripple', 'ADA': 'cardano', 'DOGE': 'dogecoin', 'AVAX': 'avalanche-2',
            'DOT': 'polkadot', 'LINK': 'chainlink', 'UNI': 'uniswap', 'LTC': 'litecoin',
            'NEAR': 'near', 'ATOM': 'cosmos', 'ALGO': 'algorand', 'VET': 'vechain',
            'FTM': 'fantom', 'EGLD': 'elrond-erd-2', 'THETA': 'theta-token', 'PEPE': 'pepe-token'
        }

        market_data = {}
        try:
            ids = ','.join(set(cg_ids_map.values()))
            resp = requests.get(
                f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&price_change_percentage=24h',
                timeout=10)
            for coin in resp.json():
                symbol = coin['symbol'].upper()
                for s, cg in cg_ids_map.items():
                    if cg == coin['id']:
                        market_data[s] = {
                            'volume': coin.get('total_volume', 0),
                            'change_24h': coin.get('price_change_percentage_24h', 0),
                            'market_cap': coin.get('market_cap', 0),
                            'price': coin.get('current_price', 0)
                        }
                        break
        except:
            pass

        # Find qualifying coins
        actions = []
        for token in CryptoToken.objects.filter(is_active=True):
            if token.symbol not in market_data:
                continue

            mdata = market_data[token.symbol]
            price = Decimal(str(mdata['price']))

            # Update token price
            token.current_price = price
            token.save()

            # Check Fadakka trigger
            trigger = FadakkaService.check_trigger(token.symbol, price)
            if not trigger:
                continue

            # Expanded rules
            vol_ok = mdata['volume'] > 1_000_000
            crash_ok = mdata['change_24h'] > -30
            mcap_ok = mdata['market_cap'] > 10_000_000

            if not (vol_ok and crash_ok and mcap_ok):
                continue

            # Check minimum capital
            min_invest = FadakkaService.get_min_investment(token.symbol)
            if amount < min_invest:
                continue

            # Calculate optimized grid
            max_grids = min(100, int(amount / Decimal('10')))
            if max_grids < 2:
                continue

            grid_pct = min(Decimal('5'), Decimal('200') / Decimal(str(max_grids)))
            total_range = Decimal(str(max_grids)) * grid_pct
            lower_pct = min(total_range * Decimal('0.8'), Decimal('150'))
            upper_pct = min(total_range * Decimal('0.2'), Decimal('50'))

            lower_price = price * (Decimal('1') - lower_pct / Decimal('100'))
            upper_price = price * (Decimal('1') + upper_pct / Decimal('100'))

            # Place orders on user's exchange
            pair = f'{token.symbol}USDT'
            try:
                info = client.get_symbol_info(pair)
                if not info:
                    continue

                lot_filter = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
                price_filter = next(f for f in info['filters'] if f['filterType'] == 'PRICE_FILTER')
                min_qty = float(lot_filter['minQty'])
                step_size = float(lot_filter['stepSize'])
                tick_size = float(price_filter['tickSize'])

                grid_step = (float(upper_price) - float(lower_price)) / max_grids
                amount_per_order = float(amount) / max_grids
                order_ids = []
                placed = 0

                for i in range(max_grids):
                    order_price = float(lower_price) + (i * grid_step)
                    order_price = round(order_price / tick_size) * tick_size

                    qty = amount_per_order / order_price if order_price > 0 else 0
                    qty = round(qty / step_size) * step_size

                    if qty >= min_qty:
                        try:
                            order = client.create_order(
                                symbol=pair,
                                side='BUY',
                                type='LIMIT',
                                timeInForce='GTC',
                                quantity=qty,
                                price=str(round(order_price, 8))
                            )
                            order_ids.append(str(order['orderId']))
                            placed += 1
                        except:
                            pass

                if placed > 0:
                    # Create GridBot record
                    from apps.trading.models import GridBot
                    fee = amount * Decimal('0.01')

                    GridBot.objects.create(
                        user=request.user,
                        token=token,
                        amount=amount - fee,
                        lower_price=lower_price,
                        upper_price=upper_price,
                        grids=placed,
                        status='ACTIVE',
                        grid_profit=Decimal('0'),
                        price_at_creation=price,
                        created_at=timezone.now(),
                        metadata={
                            'exchange': conn.exchange,
                            'connection_id': str(conn.id),
                            'order_ids': order_ids,
                            'fee_paid': float(fee),
                            'level': trigger['level'],
                        }
                    )

                    from apps.wallets.models import Transaction
                    Transaction.objects.create(
                        user=request.user,
                        transaction_type='EXTERNAL_GRID_FEE',
                        amount=fee,
                        fee=0,
                        status='COMPLETED',
                        completed_at=timezone.now()
                    )

                    actions.append({
                        'symbol': token.symbol,
                        'level': trigger['level'],
                        'grids': placed,
                        'fee': float(fee),
                    })

            except Exception as e:
                print(f"Grid error for {token.symbol}: {e}")

        return Response({
            'success': True,
            'exchange': conn.exchange,
            'capital_deployed': float(amount),
            'grids_activated': len(actions),
            'actions': actions
        })

