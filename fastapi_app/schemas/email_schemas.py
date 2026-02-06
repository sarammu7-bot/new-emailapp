from pydantic import BaseModel
from typing import List

class EmailCreate(BaseModel):
    receiver_email: str
    subject: str
    body: str


class EmailReply(BaseModel):
    email_id: int
    body: str

class EmailUpdate(BaseModel):
    is_important: bool | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None
    is_spam: bool | None = None   
    is_read: bool | None = None

class DraftCreate(BaseModel):
    receiver_email: str | None = None
    subject: str | None = None
    body: str | None = None


class EmailRead(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    subject: str
    body: str

    is_important: bool = False
    is_favorite: bool = False
    is_archived: bool = False
    is_spam: bool = False
    is_read: bool = False

    class Config:
        from_attributes = True
        
class BulkReadRequest(BaseModel):
    ids: List[int]        

