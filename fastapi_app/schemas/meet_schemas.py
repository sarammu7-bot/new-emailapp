from pydantic import BaseModel, computed_field
from datetime import datetime

class MeetingCreate(BaseModel):
    title: str = "New Meeting" 

class MeetingRead(BaseModel):
    id: int
    title: str
    meeting_code: str
    created_at: datetime
    is_active: bool
    call_type: str
    
    @computed_field
    def join_url(self) -> str:
        base_url = f"https://meet.jit.si/Stackly-Meeting-{self.meeting_code}"
        
        if self.call_type == 'audio':
            return base_url + "#config.startWithVideoMuted=true"
        return base_url
    class Config:
        from_attributes = True