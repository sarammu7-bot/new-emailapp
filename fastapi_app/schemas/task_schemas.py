from __future__ import annotations
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List


class UserTiny(BaseModel):
    id: int
    email: str
    first_name: str | None = None  
    
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    due_date: datetime | None = None
    assigned_to_email: str | None = None 
    project_id: int | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assigned_to_email: str | None = None

class TagRead(BaseModel):
    id: int
    name: str
    color: str
    class Config:
        from_attributes = True

class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    priority: str
    due_date: datetime | None = None
    created_at: datetime
    
    tags: List[TagRead] = []
    project: Optional["ProjectRead"] = None

    
    created_by: UserTiny
    assigned_to: UserTiny | None = None

    class Config:
        from_attributes = True

    @field_validator('tags', mode='before', check_fields=False)
    @classmethod
    def serialize_tags(cls, v):
        if hasattr(v, "all"):
            return list(v.all())
        return v

class CommentCreate(BaseModel):
    content: str

class CommentRead(BaseModel):
    id: int
    content: str
    created_at: datetime
    author: UserTiny  
    class Config:
        from_attributes = True
        
class ActivityRead(BaseModel):
    id: int
    action_type: str
    details: str
    created_at: datetime
    actor: UserTiny

    class Config:
        from_attributes = True      
        
class AddTagRequest(BaseModel):
    tag_name: str
    
class ProjectCreate(BaseModel):
    name: str
    description: str | None = None

class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner: UserTiny
    class Config:
        from_attributes = True    