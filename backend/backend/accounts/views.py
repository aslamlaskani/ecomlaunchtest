from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from django.conf import settings

from .models import User, Address
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChangePasswordSerializer, UpdateProfileSerializer, AddressSerializer,
    EmailTokenObtainPairSerializer,
    SendEmailOTPSerializer, VerifyEmailOTPSerializer,
    ForgotPasswordEmailSerializer, ResetPasswordEmailSerializer,
    GoogleAuthSerializer,
)
from .utils import (
    create_otp, verify_otp,
    send_registration_otp_email, send_password_reset_otp_email,
)


# ─── HELPERS ─────────────────────────────────────────────────────

def _tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def _user_data(user):
    data = UserSerializer(user).data
    data['is_staff']     = user.is_staff
    data['is_superuser'] = user.is_superuser
    return data


# ─── JWT ─────────────────────────────────────────────────────────

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


# ═══════════════════════════════════════════════════════════════
# STANDARD REGISTER / LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════

class RegisterView(generics.CreateAPIView):
    queryset           = User.objects.all()
    serializer_class   = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        otp_record = create_otp('email_register', email=user.email, user=user)
        send_registration_otp_email(user.email, otp_record.otp)

        return Response({
            'message': 'Account created. Check your email for a verification code.',
            'user':    _user_data(user),
            'tokens':  _tokens(user),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.get_response(), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
# PROFILE / PASSWORD
# ═══════════════════════════════════════════════════════════════

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(_user_data(request.user))

    def put(self, request):
        serializer = UpdateProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Profile updated',
            'user':    _user_data(request.user),
        })


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Password changed successfully'})


# ═══════════════════════════════════════════════════════════════
# EMAIL OTP — REGISTRATION VERIFICATION
# ═══════════════════════════════════════════════════════════════

class SendEmailOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email=email).first()
        otp_record = create_otp('email_register', email=email, user=user)
        sent = send_registration_otp_email(email, otp_record.otp)

        if not sent:
            return Response(
                {'error': 'Failed to send OTP. Try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response({'message': f'OTP sent to {email}'})


class VerifyEmailOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp   = serializer.validated_data['otp']

        record = verify_otp(otp, 'email_register', email=email)
        if not record:
            return Response(
                {'error': 'Invalid or expired OTP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if user:
            user.is_email_verified = True
            user.save()

        return Response({'message': 'Email verified successfully ✅'})


# ═══════════════════════════════════════════════════════════════
# EMAIL OTP — FORGOT / RESET PASSWORD
# ═══════════════════════════════════════════════════════════════

class ForgotPasswordEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user       = User.objects.get(email=email)
        otp_record = create_otp('email_reset', email=email, user=user)
        sent       = send_password_reset_otp_email(email, otp_record.otp)

        if not sent:
            return Response(
                {'error': 'Failed to send reset email. Try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response({'message': f'Password reset code sent to {email}'})


class ResetPasswordEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        record = verify_otp(data['otp'], 'email_reset', email=data['email'])
        if not record:
            return Response(
                {'error': 'Invalid or expired OTP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=data['email']).first()
        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(data['new_password'])
        user.save()

        return Response({
            'message': 'Password reset successfully. You can now log in.',
            'tokens':  _tokens(user),
        })


# ═══════════════════════════════════════════════════════════════
# GOOGLE OAUTH
# ═══════════════════════════════════════════════════════════════

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['id_token']

        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as e:
            return Response(
                {'error': f'Invalid Google token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        google_id = idinfo['sub']
        email     = idinfo.get('email', '')
        first     = idinfo.get('given_name', '')
        last      = idinfo.get('family_name', '')
        avatar    = idinfo.get('picture', '')

        user = User.objects.filter(google_id=google_id).first()

        if not user:
            user = User.objects.filter(email=email).first()
            if user:
                user.google_id  = google_id
                user.avatar_url = avatar
                user.save()
            else:
                user = User.objects.create_user(
                    email=email,
                    first_name=first,
                    last_name=last or '.',
                    password=None,
                )
                user.google_id         = google_id
                user.avatar_url        = avatar
                user.is_email_verified = True
                user.save()

        if not user.is_active:
            return Response(
                {'error': 'Account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'message': 'Google login successful',
            'user':    _user_data(user),
            'tokens':  _tokens(user),
        })


# ═══════════════════════════════════════════════════════════════
# ADDRESSES
# ═══════════════════════════════════════════════════════════════

class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class   = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response({'message': 'Address deleted'}, status=status.HTTP_200_OK)