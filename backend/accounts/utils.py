from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import OTPVerification


# ─── OTP CREATION ────────────────────────────────────────────────

def create_otp(otp_type, email=None, user=None, expires_minutes=10):
    qs = OTPVerification.objects.filter(otp_type=otp_type, is_used=False)
    if email:
        qs = qs.filter(email=email)
    qs.update(is_used=True)

    return OTPVerification.objects.create(
        user=user, email=email,
        otp=OTPVerification.generate_otp(),
        otp_type=otp_type,
        expires_at=timezone.now() + timedelta(minutes=expires_minutes),
    )


def verify_otp(otp_code, otp_type, email=None, user=None):
    qs = OTPVerification.objects.filter(
        otp=otp_code, otp_type=otp_type,
        is_used=False, expires_at__gt=timezone.now(),
    )

    if user:
        qs = qs.filter(user=user)
    elif email:
        qs = qs.filter(email=email)

    record = qs.first()
    if record:
        record.is_used = True
        record.save()
        return record
    return None


# ─── EMAIL OTP ───────────────────────────────────────────────────

def send_otp_email(email, otp_code, subject, purpose_text):
    message = (
        f"Assalam o Alaikum!\n\n"
        f"Your {purpose_text} code for Aslivo Store is:\n\n"
        f"  ━━━━━━━━━━━━━━━\n"
        f"       {otp_code}\n"
        f"  ━━━━━━━━━━━━━━━\n\n"
        f"This code expires in 10 minutes.\n"
        f"Do not share it with anyone.\n\n"
        f"— Aslivo Store Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f'[Email OTP Error] {e}')
        return False


def send_registration_otp_email(email, otp_code):
    return send_otp_email(
        email, otp_code,
        subject='Your Aslivo Store Verification Code',
        purpose_text='email verification',
    )


def send_password_reset_otp_email(email, otp_code):
    return send_otp_email(
        email, otp_code,
        subject='Aslivo Store — Password Reset Code',
        purpose_text='password reset',
    )