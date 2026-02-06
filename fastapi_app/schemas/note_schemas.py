from pydantic import BaseModel
from datetime import datetime

class NoteBase(BaseModel):
    title: str | None = None
    content: str

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    is_pinned: bool | None = None

class NoteRead(NoteBase):
    id: int
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
