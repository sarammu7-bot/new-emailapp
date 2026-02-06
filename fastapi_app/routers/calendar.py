
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, date, timedelta
import secrets
from asgiref.sync import sync_to_async
from django_backend.models import Event, EventAttendee, EventReminder, Meeting, ChatRoom
from django.contrib.auth import get_user_model
from fastapi_app.schemas.calendar_schemas import EventCreate, EventRead 
from django.contrib.auth import get_user_model
from fastapi_app.schemas.calendar_schemas import EventCreate, EventRead 
from fastapi_app.routers.auth import get_current_user
from fastapi_app.tasks import process_event_invites

User = get_user_model()
router = APIRouter(prefix="/calendar", tags=["Calendar"])

async def _get_event_or_404(event_id: int) -> Event:
    """
    Returns Event instance or raises 404.
    """
    ev = await sync_to_async(Event.objects.filter(id=event_id).select_related("created_by").first)()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev

def _start_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _end_of_week(d: date) -> date:
    return _start_of_week(d) + timedelta(days=6)

@router.post("/events", response_model=EventRead, status_code=201)
async def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    create_meeting_link: bool = Query(False)
):
    """
    Create an event.
    - attendees: list of user IDs
    - reminders: list of minutes before event
    """
    event = await sync_to_async(Event.objects.create)(
        title=payload.title,
        description=payload.description,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        is_all_day=payload.is_all_day,
        location=payload.location,
        url=payload.url,
        color=payload.color or "blue",
        repeat_rule=payload.repeat_rule,
        timezone=payload.timezone or "UTC",
        created_by=current_user,
    )

    if create_meeting_link:
        chat_room = await sync_to_async(ChatRoom.objects.create)(
            name=f"Chat: {payload.title}",
            is_group=True
        )
        await sync_to_async(chat_room.participants.add)(current_user)
        
        if payload.attendees:
            for uid in payload.attendees:
                if uid == current_user.id:
                    continue
                
                u = await sync_to_async(User.objects.filter(id=uid).first)()
                if u:
                    await sync_to_async(chat_room.participants.add)(u)
        
        meeting_code = secrets.token_urlsafe(8)
        meeting = await sync_to_async(Meeting.objects.create)(
            host=current_user,
            title=payload.title,
            meeting_code=meeting_code,
            call_type="video",
            chat_room=chat_room
        )

        event.meeting = meeting
        event.url = f"https://meet.jit.si/Stackly-Meeting-{meeting_code}"
        await sync_to_async(event.save)()
    
    await sync_to_async(EventAttendee.objects.get_or_create)(
        event=event,
        user=current_user,
        defaults={"status": "accepted"}
    )

    if payload.attendees:
        for user_id in payload.attendees:

            if user_id == current_user.id:
                continue

            user = await sync_to_async(User.objects.filter(id=user_id).first)()
            if not user:
                continue  

            await sync_to_async(EventAttendee.objects.get_or_create)(
                event=event,
                user=user,
                defaults={"status": "pending"}
            )

    if payload.reminders:
        for minutes in payload.reminders:
            await sync_to_async(EventReminder.objects.create)(
                event=event,
                minutes_before=minutes
            )

    fresh_event = await sync_to_async(
        Event.objects.select_related("created_by").get
    )(id=event.id)
    process_event_invites.delay(event.id, current_user.id)

    return fresh_event


@router.get("/events/{event_id}", response_model=EventRead)
async def get_event(event_id: int, current_user: User = Depends(get_current_user)):
    event = await _get_event_or_404(event_id)

    is_creator = event.created_by_id == current_user.id
    is_attendee = await sync_to_async(EventAttendee.objects.filter(event=event, user=current_user).exists)()
    if not (is_creator or is_attendee):
        raise HTTPException(status_code=403, detail="Not allowed to view this event")

    return event


@router.patch("/events/{event_id}", response_model=EventRead)
async def update_event(event_id: int, payload: EventCreate, current_user: User = Depends(get_current_user)):
    """
    Update allowed fields. We're re-using EventCreate for simplicity.
    """
    event = await _get_event_or_404(event_id)

    if event.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can edit the event")

    for attr in (
        "title", "description", "start_datetime", "end_datetime", "is_all_day",
        "location", "url", "color", "repeat_rule", "timezone"
    ):
        if hasattr(payload, attr):
            val = getattr(payload, attr)
            if val is not None:
                setattr(event, attr, val)

    await sync_to_async(event.save)()

    updated = await sync_to_async(Event.objects.select_related("created_by").get)(id=event.id)
    return updated


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: int, current_user: User = Depends(get_current_user)):
    event = await _get_event_or_404(event_id)
    if event.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete the event")
    await sync_to_async(event.delete)()
    return {}


@router.get("/events/day", response_model=List[EventRead])
async def list_events_for_day(date_str: Optional[str] = Query(None, description="YYYY-MM-DD"), current_user: User = Depends(get_current_user)):
    """
    Pass date=YYYY-MM-DD to list events for that day. Defaults to today.
    Lists events where user is creator or attendee.
    """
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        d = datetime.utcnow().date()

    start = datetime.combine(d, datetime.min.time())
    end = datetime.combine(d, datetime.max.time())

    qs = Event.objects.filter(start_datetime__lte=end, end_datetime__gte=start).distinct()

    created_qs = qs.filter(created_by=current_user)
    attendee_event_ids = EventAttendee.objects.filter(user=current_user).values_list("event_id", flat=True)
    attendee_qs = qs.filter(id__in=attendee_event_ids)

    final_qs = (created_qs | attendee_qs).select_related("created_by").order_by("start_datetime")

    events = await sync_to_async(list)(final_qs)
    return events


@router.get("/events/week", response_model=List[EventRead])
async def list_events_for_week(start_date: Optional[str] = Query(None, description="YYYY-MM-DD"), current_user: User = Depends(get_current_user)):
    """
    Provide start_date (YYYY-MM-DD) to choose week-start. Defaults to current week.
    """
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        sd = datetime.utcnow().date()

    week_start = _start_of_week(sd)
    week_end = _end_of_week(sd)

    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = datetime.combine(week_end, datetime.max.time())

    qs = Event.objects.filter(start_datetime__lte=end_dt, end_datetime__gte=start_dt).distinct()
    created_qs = qs.filter(created_by=current_user)
    attendee_event_ids = EventAttendee.objects.filter(user=current_user).values_list("event_id", flat=True)
    attendee_qs = qs.filter(id__in=attendee_event_ids)
    final_qs = (created_qs | attendee_qs).select_related("created_by").order_by("start_datetime")

    events = await sync_to_async(list)(final_qs)
    return events


@router.get("/events/month", response_model=List[EventRead])
async def list_events_for_month(year: Optional[int] = Query(None), month: Optional[int] = Query(None), current_user: User = Depends(get_current_user)):
    """
    List events for a given year/month. Defaults to current month.
    """
    today = datetime.utcnow().date()
    if not year:
        year = today.year
    if not month:
        month = today.month

    try:
        month_start = date(year, month, 1)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid year/month")

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    start_dt = datetime.combine(month_start, datetime.min.time())
    end_dt = datetime.combine(next_month - timedelta(days=1), datetime.max.time())

    qs = Event.objects.filter(start_datetime__lte=end_dt, end_datetime__gte=start_dt).distinct()
    created_qs = qs.filter(created_by=current_user)
    attendee_event_ids = EventAttendee.objects.filter(user=current_user).values_list("event_id", flat=True)
    attendee_qs = qs.filter(id__in=attendee_event_ids)
    final_qs = (created_qs | attendee_qs).select_related("created_by").order_by("start_datetime")

    events = await sync_to_async(list)(final_qs)
    return events


@router.post("/events/{event_id}/attendees", status_code=201)
async def add_attendees(event_id: int, user_ids: List[int], current_user: User = Depends(get_current_user)):
    """
    Add attendees by user id array (JSON body). Only creator can add attendees.
    """
    event = await _get_event_or_404(event_id)
    if event.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can add attendees")

    added = []
    for uid in user_ids:
        user = await sync_to_async(User.objects.filter(id=uid).first)()
        if not user:
            continue
        exists = await sync_to_async(EventAttendee.objects.filter(event=event, user=user).exists)()
        if not exists:
            await sync_to_async(EventAttendee.objects.create)(event=event, user=user, status="pending")
            added.append(uid)

    return {"added": added}


@router.post("/events/{event_id}/respond")
async def respond_event(event_id: int, status: str = Query(..., description="accepted|declined|maybe"), current_user: User = Depends(get_current_user)):
    """
    Attendee responds to an invitation.
    """
    if status not in ("accepted", "declined", "maybe"):
        raise HTTPException(status_code=400, detail="Invalid status")

    event = await _get_event_or_404(event_id)
    attendee = await sync_to_async(EventAttendee.objects.filter(event=event, user=current_user).first)()
    if not attendee:
        await sync_to_async(EventAttendee.objects.create)(event=event, user=current_user, status=status)
    else:
        attendee.status = status
        await sync_to_async(attendee.save)()

    return {"status": "ok", "new_state": status}
