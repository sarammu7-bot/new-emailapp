from pydantic import BaseModel, Field, computed_field
from datetime import datetime, date
from user_agents import parse

class ProfileCreate(BaseModel):
    full_name: str
    display_name: str
    phone_number: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    language: str = "English"

  
    date_format: date = Field(default_factory=date.today)

class ProfileSettingsUpdate(BaseModel):
    store_activity: bool | None = None
    is_2fa_enabled: bool | None = None
    
class ProfileRead(ProfileCreate):
    id: int
    store_activity: bool
    is_2fa_enabled: bool
    class Config:
        from_attributes = True
        
class ActivityRead(BaseModel):
    id: int
    ip_address: str | None
    user_agent: str | None
    timestamp: datetime
    
    @computed_field
    def device_details(self) -> str:
        """
        Parses the ugly user_agent string into a readable format.
        Example: "Mobile Safari on iOS"
        """
        if not self.user_agent:
            return "Unknown Device"
        
        try:
            ua = parse(self.user_agent)
            return f"{ua.browser.family} on {ua.os.family}"
        except Exception:
            return "Unknown Device"
    class Config:
        from_attributes = True  
        
class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code: str 

class TwoFactorVerifyRequest(BaseModel):
    code: str              
