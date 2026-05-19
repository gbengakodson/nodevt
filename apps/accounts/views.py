from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User
from django.contrib.auth import authenticate
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from apps.accounts.services.otp_service import OTPService
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken

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


