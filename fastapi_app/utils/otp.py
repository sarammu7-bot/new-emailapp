import random
from datetime import timedelta
from django.utils.timezone import now

def generate_otp():
    return str(random.randint(100000, 999999))

def otp_expiry(minutes=5):
    return now() + timedelta(minutes=minutes)
