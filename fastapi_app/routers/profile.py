import pyotp
import io
import base64
from fastapi import APIRouter, Depends, HTTPException
from asgiref.sync import sync_to_async
from typing import List
from django_backend.models import UserProfile, LoginActivity
from fastapi_app.schemas.profile_schemas import (
    ProfileCreate, ProfileRead, ActivityRead,
    ProfileSettingsUpdate, TwoFactorSetupResponse, TwoFactorVerifyRequest
)
from fastapi_app.routers.auth import get_current_user
from django_backend.models import User

router = APIRouter(prefix="/profile", tags=["Profile"])



@router.post("/", response_model=ProfileRead)
async def create_profile(
    data: ProfileCreate,
    current_user: User = Depends(get_current_user),
):
    existing = await sync_to_async(UserProfile.objects.filter(user=current_user).first)()

    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")

    profile = await sync_to_async(UserProfile.objects.create)(
        user=current_user,
        **data.dict()
    )

    return profile



@router.get("/", response_model=ProfileRead)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    profile = await sync_to_async(UserProfile.objects.filter(user=current_user).first)()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


@router.get("/activity", response_model=List[ActivityRead])
def get_account_activity(
    current_user: User = Depends(get_current_user)
):
    activities = LoginActivity.objects.filter(user=current_user).order_by("-timestamp")[:10]
    return list(activities)



@router.patch("/settings", response_model=ProfileRead)
async def update_settings(
    data: ProfileSettingsUpdate,
    current_user: User = Depends(get_current_user)
):
    try:
        profile = await sync_to_async(UserProfile.objects.get)(user=current_user)
    except UserProfile.DoesNotExist:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(profile, key, value)

    await sync_to_async(profile.save)()
    
    return profile



@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(current_user: User = Depends(get_current_user)):
    @sync_to_async
    def get_or_create_profile(user):
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": user.first_name + " " + user.last_name,
                "display_name": user.first_name,
                "language": "English"
            }
        )
        return profile

    profile = await get_or_create_profile(current_user)

    secret = pyotp.random_base32()
    profile.two_factor_secret = secret
    await sync_to_async(profile.save)()


    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="Stackly"
    )

  
    qr_bytes = uri.encode("utf-8")
    qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")

    return {
        "secret": secret,
        "qr_code": qr_base64
    }



@router.post("/2fa/verify")
async def verify_two_factor(
    data: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user)
):
    profile = await sync_to_async(UserProfile.objects.get)(user=current_user)

    if not profile.two_factor_secret:
        raise HTTPException(status_code=400, detail="Please run setup first")

    totp = pyotp.TOTP(profile.two_factor_secret)
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Invalid code. Try again.")

    profile.is_2fa_enabled = True
    await sync_to_async(profile.save)()

    return {"message": "2FA Enabled Successfully"}
