from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from django.contrib.auth.hashers import check_password, make_password
from .config import settings

RESET_TOKEN_EXPIRE_MINUTES = 15
def get_password_hash(password: str):
    return make_password(password)

def verify_password(plain_password: str, hashed_password: str):
    return check_password(plain_password, hashed_password)

# CREATE ACCESS TOKEN
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)   
    return encoded_jwt

# DECODE ACCESS TOKEN
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
    
  # 2. Add this specific generator
def create_password_reset_token(email: str):
    """
    Generates a short-lived JWT specifically for password recovery.
    """
    expires_delta = timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    data = {"sub": email, "type": "reset"} 
    
    return create_access_token(data, expires_delta)  
