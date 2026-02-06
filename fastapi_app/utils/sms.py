from twilio.rest import Client
from fastapi_app.core.config import settings

client = Client(
    settings.TWILIO_ACCOUNT_SID,
    settings.TWILIO_AUTH_TOKEN
)

def send_otp_sms(mobile_number: str, otp: str):
    """
    Send OTP via Twilio SMS
    """
    
    if not mobile_number.startswith("+"):
        raise ValueError("Mobile number must be in international format")

    message = client.messages.create(
        body=f"Your OTP is {otp}. Valid for 5 minutes.",
        from_=settings.TWILIO_PHONE_NUMBER,
        to=mobile_number
    )

    return message.sid
