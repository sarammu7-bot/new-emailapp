from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from django.contrib.auth import get_user_model
from fastapi_app.core.security import decode_access_token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_backend.models import User as DjangoUser


User = get_user_model()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)

    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    email = payload["sub"]

    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        raise HTTPException(status_code=401, detail="User not found")
