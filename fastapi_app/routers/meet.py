from asgiref.sync import sync_to_async
from fastapi_app.core.status_manager import StatusManager
from fastapi import APIRouter, Depends, Body, HTTPException
from django.contrib.auth import get_user_model
import secrets 
from django_backend.models import Meeting
from fastapi_app.schemas.meet_schemas import MeetingCreate, MeetingRead
from fastapi_app.dependencies.auth import get_current_user
from fastapi_app.routers.notifications import create_notification

router = APIRouter()
User = get_user_model()


def _generate_meeting(user, title, type_choice):
    code = secrets.token_urlsafe(8)
    return Meeting.objects.create(
        host=user,
        title=title,
        meeting_code=code,
        call_type=type_choice 
    )

@router.post("/audio", response_model=MeetingRead)
def create_audio_call(
    data: MeetingCreate, 
    current_user: User = Depends(get_current_user)
):
    return _generate_meeting(current_user, data.title, "audio")

@router.post("/video", response_model=MeetingRead)
def create_video_call(
    data: MeetingCreate, 
    current_user: User = Depends(get_current_user)
):
    return _generate_meeting(current_user, data.title, "video")

@router.post("/group", response_model=MeetingRead)
def create_group_call(
    data: MeetingCreate, 
    current_user: User = Depends(get_current_user)
):
    return _generate_meeting(current_user, data.title, "group")

@router.post("/invite")
def invite_to_meeting(
    meeting_id: int = Body(..., embed=True),
    email: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    
    try:
        meeting = Meeting.objects.get(id=meeting_id)
    except Meeting.DoesNotExist:
        raise HTTPException(status_code=404, detail="Meeting not found")

    try:
        invitee = User.objects.get(email=email)
    except User.DoesNotExist:
        raise HTTPException(status_code=404, detail="User not found")

    join_url = f"https://meet.jit.si/Stackly-Meeting-{meeting.meeting_code}"
    
    if meeting.call_type == 'audio':
        join_url += "#config.startWithVideoMuted=true"

    create_notification(
        recipient=invitee,
        message=f"{current_user.email} invited you to a {meeting.call_type} call.",
        type_choice="meet",
        related_id=meeting.id
    )

    return {"message": f"Invitation sent to {invitee.email}", "link": join_url}


@router.get("/list", response_model=list[MeetingRead])
def list_my_meetings(current_user: User = Depends(get_current_user)):
    meetings = Meeting.objects.filter(host=current_user).order_by("-created_at")

    return meetings

@router.post("/{meeting_id}/join")
async def join_meeting(
    meeting_id: int, 
    current_user: User = Depends(get_current_user)
):
 
    try:
        meeting = await sync_to_async(Meeting.objects.get)(id=meeting_id)
    except Meeting.DoesNotExist:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meet_link = f"https://meet.jit.si/Stackly-Meeting-{meeting.meeting_code}"

    await StatusManager.request_status_change(
        current_user.id, 
        "IN_MEETING", 
        message=f"In a Meeting: {meeting.title}"  
    )

    return {
        "message": "Status updated to IN_MEETING", 
        "link": meet_link
    }

@router.post("/{meeting_id}/leave")
async def leave_meeting(
    meeting_id: int, 
    current_user: User = Depends(get_current_user)
):
    """
    User clicks 'Hang Up' or closes the tab.
    We immediately revert them to AVAILABLE.
    """
    
    await StatusManager.request_status_change(current_user.id, 'AVAILABLE')

    return {"message": "You are now marked as AVAILABLE"}