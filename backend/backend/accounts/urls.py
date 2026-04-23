from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [

    # ── Standard Auth ──────────────────────────────────────────
    path('register/',        views.RegisterView.as_view(),       name='register'),
    path('login/',           views.LoginView.as_view(),          name='login'),
    path('logout/',          views.LogoutView.as_view(),         name='logout'),
    path('token/refresh/',   TokenRefreshView.as_view(),         name='token_refresh'),

    # ── Profile ────────────────────────────────────────────────
    path('profile/',         views.ProfileView.as_view(),        name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    # ── Email OTP — Registration ───────────────────────────────
    path('otp/email/send/',   views.SendEmailOTPView.as_view(),   name='send_email_otp'),
    path('otp/email/verify/', views.VerifyEmailOTPView.as_view(), name='verify_email_otp'),

    # ── Email OTP — Forgot/Reset Password ─────────────────────
    path('password/forgot/',       views.ForgotPasswordEmailView.as_view(), name='forgot_password_email'),
    path('password/reset/email/',  views.ResetPasswordEmailView.as_view(),  name='reset_password_email'),

    # ── Google OAuth ───────────────────────────────────────────
    path('google/',          views.GoogleLoginView.as_view(),    name='google_login'),

    # ── Addresses ──────────────────────────────────────────────
    path('addresses/',          views.AddressListCreateView.as_view(), name='addresses'),
    path('addresses/<int:pk>/', views.AddressDetailView.as_view(),     name='address_detail'),
]