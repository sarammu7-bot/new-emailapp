from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional



class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    is_all_day: bool = False
    location: Optional[str] = None
    url: Optional[str] = None

    attendees: List[int] = []           
    color: Optional[str] = "blue"
    repeat_rule: Optional[str] = None   
    timezone: str = "UTC"

    reminders: List[int] = []           


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    location: Optional[str] = None
    url: Optional[str] = None

    attendees: Optional[List[int]] = None
    color: Optional[str] = None
    repeat_rule: Optional[str] = None
    timezone: Optional[str] = None

    reminders: Optional[List[int]] = None


class EventRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_datetime: datetime
    end_datetime: datetime
    is_all_day: bool
    location: Optional[str]
    url: Optional[str]
    color: Optional[str]
    repeat_rule: Optional[str]
    timezone: str

    created_by_id: int

    class Config:
        from_attributes = True




class AttendeeRead(BaseModel):
    user_id: int
    status: str     

    class Config:
        from_attributes = True


class ReminderRead(BaseModel):
    id: int
    minutes_before: int

    class Config:
        from_attributes = True


class HolidayCreate(BaseModel):
    name: str
    date: date
    description: Optional[str] = None


class HolidayRead(BaseModel):
    id: int
    name: str
    date: date
    description: Optional[str]

    class Config:
        from_attributes = True


class CalendarDayView(BaseModel):
    date: date
    events: List[EventRead]
    holidays: List[HolidayRead]


class CalendarWeekView(BaseModel):
    start_date: date
    end_date: date
    events: List[EventRead]
    holidays: List[HolidayRead]


class CalendarMonthView(BaseModel):
    year: int
    month: int
    events: List[EventRead]
    holidays: List[HolidayRead]
