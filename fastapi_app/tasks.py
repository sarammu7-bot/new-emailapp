import os
import json
import redis
import logging
from celery import shared_task
import django
from django.core.mail import send_mail
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Emailproject.settings')
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django_backend.models import Event, Notification, EventAttendee, Email

User = get_user_model()
logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Returns a redis client that works in both Docker and Localhost.
    Reads the 'REDIS_HOST' env var, defaults to 'localhost'.
    """
    redis_host = os.environ.get('REDIS_HOST', 'redis')
    return redis.Redis(host=redis_host, port=6379, db=0)

@shared_task
def reset_user_status(user_id: int):

    try:
        user = User.objects.get(id=user_id)
        
        if user.current_status == 'OFFLINE':
            print(f"User {user.email} is OFFLINE. Skipping auto-reset.")
            return

        print(f"Time is up! Resetting {user.email} to AVAILABLE.")
        
        user.current_status = 'AVAILABLE'
        user.status_message = None
        user.status_expiry = None
        user.is_manually_set = False
        user.save()

        try:
            r = get_redis_client()
            
            message = {
                "type": "USER_STATUS_UPDATE",
                "user_id": user.id,
                "status": "AVAILABLE",
                "message": None
            }
            r.publish("status_updates", json.dumps(message))
            print(f"Published update to Redis for {user.email}")
            
        except Exception as e:
            print(f"Failed to publish to Redis: {e}")
        
    except User.DoesNotExist:
        print(f"User {user_id} not found during auto-reset.")
        
@shared_task(bind=True, max_retries=3)
def process_event_invites(self, event_id, creator_id):
    try:
        event = Event.objects.get(id=event_id)
        creator = User.objects.get(id=creator_id)
        attendee_records = EventAttendee.objects.filter(event=event).exclude(user_id=creator_id)
        recipients = [record.user for record in attendee_records]

        logger.info(f"Starting background invites for Event: {event.title}")
        event_content_type = ContentType.objects.get_for_model(Event)

        notifications_created = 0
        for user in recipients:
            meeting_link = event.url if event.url else "Link pending or location provided."
            message_body = (
            f"Hello {user.first_name},\n\n"
            f"You have been invited to '{event.title}'.\n"
            f"Time: {event.start_datetime}\n"
            f"Join here: {meeting_link}\n\n"
            f"See you there!"
        )            
            Notification.objects.create(
                recipient=user,
                message=f"You are invited to {event.title}!",
                notification_type='meet',
                content_type=event_content_type, 
                object_id=event.id
            )
            
            Email.objects.create(
                sender=creator,
                receiver=user,
                subject=f"Invitation: {event.title}",
                body=message_body,
                status='SENT'
            )
            
            # 2. SEND REAL EMAIL (The New Part)
            if user.email: 
                logger.info(f"Sending email to {user.email}...")
                send_mail(
                    subject=f"Invitation: {event.title}",
                    message=message_body,
                    from_email=None,  # Uses the EMAIL_HOST_USER from settings
                    recipient_list=[user.email],
                    fail_silently=False
                )
            
            notifications_created += 1

        logger.info(f"Completed. Sent {notifications_created} invites.")
        return f"Processed {notifications_created} invites for Event {event_id}"

    except Event.DoesNotExist:
        logger.error(f"Event with ID {event_id} not found.")
    except Exception as e:
        logger.error(f"Error processing invites: {e}")
        self.retry(exc=e, countdown=60)