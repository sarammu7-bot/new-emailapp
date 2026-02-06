from fastapi import APIRouter, Depends
from django.contrib.auth import get_user_model
from django.db.models import Count
from django_backend.models import Email, ChatMessage, ChatRoom 
from fastapi_app.dependencies.permissions import is_admin 

router = APIRouter()
User = get_user_model()

@router.get("/dashboard")
def get_analytics(current_user = Depends(is_admin)):
    """
    Returns system-wide statistics.
    Only accessible by ADMIN users.
    """
    
    # 1. User Stats
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    
    # 2. Email Stats
    total_emails = Email.objects.count()
    sent_emails = Email.objects.filter(status='SENT').count()
    draft_emails = Email.objects.filter(status='DRAFT').count()
    
    # 3. Chat Stats
    total_rooms = ChatRoom.objects.count()
    total_messages = ChatMessage.objects.count()
    
    top_senders_qs = User.objects.annotate(
        email_count=Count('sent_emails')
    ).order_by('-email_count')[:5]
    
    top_senders = [
        {"email": u.email, "count": u.email_count}
        for u in top_senders_qs
        if u.email_count > 0
    ]

    return {
        "users": {
            "total": total_users,
            "active": active_users
        },
        "communication": {
            "emails_sent": sent_emails,
            "drafts_pending": draft_emails,
            "chat_messages": total_messages,
            "active_chat_rooms": total_rooms
        },
        "top_performers": top_senders
    }