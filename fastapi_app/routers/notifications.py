from fastapi import APIRouter, Depends, HTTPException
from django.contrib.auth import get_user_model
from django_backend.models import Notification
from fastapi_app.schemas.notification_schemas import NotificationRead, NotificationUpdate
from fastapi_app.dependencies.auth import get_current_user

router = APIRouter()
User = get_user_model()

@router.get("/", response_model=list[NotificationRead])
def get_my_notifications(current_user: User = Depends(get_current_user)):
    return Notification.objects.filter(recipient=current_user).order_by("-created_at")

@router.patch("/{notification_id}", response_model=NotificationRead)
def mark_as_read(
    notification_id: int, 
    data: NotificationUpdate,
    current_user: User = Depends(get_current_user)
):
    try:
        notif = Notification.objects.get(id=notification_id, recipient=current_user)
        notif.is_read = data.is_read
        notif.save()
        return notif
    except Notification.DoesNotExist:
        raise HTTPException(status_code=404, detail="Notification not found")
        
def create_notification(recipient, message, type_choice="general"):
    Notification.objects.create(
        recipient=recipient,
        message=message,
        notification_type=type_choice
    )