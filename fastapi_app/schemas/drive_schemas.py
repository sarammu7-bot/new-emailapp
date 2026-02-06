from pydantic import BaseModel
from datetime import datetime

class DriveFileRead(BaseModel):
    id: int
    original_name: str
    size: int
    content_type: str
    created_at: datetime
    url: str

    class Config:
        from_attributes = True

