import pyotp
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import timedelta
from asgiref.sync import sync_to_async
from django_backend.models import LoginActivity
from ..core.security import (
    verify_password, create_access_token,
    create_password_reset_token, decode_access_token
)
from ..core.config import settings
from ..schemas.user_schemas import Token, ForgotPasswordRequest, ResetPasswordWithOTP, ForgotUsernameRequest

from fastapi_app.utils.otp import generate_otp, otp_expiry


from django.contrib.auth import get_user_model
User = get_user_model()

from fastapi_app.utils.sms import send_otp_sms


router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Extracts the logged-in user from the JWT access token.
    Used in authenticated endpoints like:
    - create task
    - create chat room
    - send messages
    """

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await sync_to_async(User.objects.filter(email=email).first)()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


@router.post("/login", response_model=Token)
def login_for_access_token(
    request: Request, 
    form_data: OAuth2PasswordRequestForm = Depends(),
    otp: str | None = Query(default=None, description="2FA Code if enabled") 
):
    User = get_user_model()
    email = form_data.username.strip()

    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    local_part, domain = email.rsplit("@", 1)

    if domain.lower() != "thestackly.com":
        raise HTTPException(
        status_code=400,
        detail="Only thestackly.com emails allowed"
    )

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.check_password(form_data.password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    is_2fa_on = False
    if hasattr(user, 'profile') and user.profile.is_2fa_enabled:
        is_2fa_on = True

    if is_2fa_on:
        if not otp:
            raise HTTPException(
                status_code=401, 
                detail="2FA Required. Please provide the 'otp' parameter."
            )
        
        secret = user.profile.two_factor_secret
        if not secret:
             raise HTTPException(status_code=401, detail="2FA Configuration Error")

        totp = pyotp.TOTP(secret)
        if not totp.verify(otp):
             raise HTTPException(status_code=401, detail="Invalid 2FA Code")


    should_record = True 
    try:
        if hasattr(user, 'profile'):
             should_record = user.profile.store_activity
    except Exception:
        pass

    if should_record:
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent")
        LoginActivity.objects.create(user=user, ip_address=client_ip, user_agent=user_agent)
    
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token (
        data={"sub": user.email},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: ForgotPasswordRequest):
    user = User.objects.filter(mobile_number=data.mobile_number).first()

    if not user:
       
        return {"message": "If this mobile number exists, an OTP has been sent"}

    otp = generate_otp()

    user.otp = otp
    user.otp_expires_at = otp_expiry()
    user.save(update_fields=["otp", "otp_expires_at"])

    send_otp_sms(user.mobile_number, otp)
    

    return {"message": "OTP sent to registered mobile number"}

@router.post("/reset-password")
def reset_password(data: ResetPasswordWithOTP):
    user = User.objects.filter(mobile_number=data.mobile_number).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if not user.otp_expires_at or user.otp_expires_at < now():
        raise HTTPException(status_code=400, detail="OTP expired")

    user.set_password(data.new_password)
    user.otp = None
    user.otp_expires_at = None
    user.save(update_fields=["password", "otp", "otp_expires_at"])

    return {"message": "Password reset successful"}



@router.post("/forgot-username", status_code=200)
def forgot_username(data: ForgotUsernameRequest):
    users = User.objects.filter(mobile_number=data.phone_number)

    if not users.exists():
        return {
            "message": "If this phone number exists, username details have been sent."
        }

    masked_emails = []

    for user in users:
        local, domain = user.email.split("@")
        masked_emails.append(local[:2] + "****@" + domain)

    print("\n==========================================")
    print(" FORGOT USERNAME REQUEST")
    print(f" PHONE: {data.phone_number}")
    print(" USERNAMES:")
    for email in masked_emails:
        print(f"  - {email}")
    print("==========================================\n")

    return {
        "message": "If this phone number exists, username details have been sent.",
        "username_hints": masked_emails,
    }
