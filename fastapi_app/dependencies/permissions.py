from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from django.contrib.auth import get_user_model
from ..core.config import settings

# This tells FastAPI that the token comes from the "/login" URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    The Bouncer:
    1. Takes the token.
    2. Decodes it.
    3. Finds the user in the DB.
    4. Returns the User object (or raises 401 error).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    User = get_user_model()
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise credentials_exception

    return user


def get_current_active_user(current_user = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def is_admin(current_user = Depends(get_current_active_user)):
    """Only allows users who are Superusers (Admins)"""
    if not current_user.is_superuser:
         raise HTTPException(
            status_code=403, 
            detail="You do not have permission to access this resource"
        )
    return current_user