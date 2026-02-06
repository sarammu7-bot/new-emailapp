from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ReactionRead(BaseModel):
    emoji: str
    count: int
    user_emails: List[str]

class MessageRead(BaseModel):
    id: int
    sender_email: str
    content: str | None
    attachment_url: str | None = None
    timestamp: datetime
    read_count: int = 0 
    is_starred: bool = False
    parent_id: Optional[int] = None
    parent_content: Optional[str] = None
    parent_sender: Optional[str] = None
    reactions: List[ReactionRead] = []
    is_forwarded: bool = False

    class Config:
        from_attributes = True

class ChatRoomRead(BaseModel):
    id: int
    name: str | None
    is_group: bool
    unread_count: int = 0
    participants: List[str] 
    last_message: Optional[MessageRead] = None

    class Config:
        from_attributes = True

class ChatRoomCreate(BaseModel):
    participant_emails: List[str]
    name: str | None = None 
    is_group: bool = False
    email_id: int | None = None
    
class ChatMemberUpdate(BaseModel):
    user_emails: List[str]    
    
class MessageUpdate(BaseModel):
    content: str    
    
class ForwardRequest(BaseModel):
    target_room_id: int    