from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Event
from fastapi_app.tasks import process_event_invites

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_event(request):
    """
    API Endpoint to create an event.
    It saves the event immediately and offloads notifications to Celery.
    """
    # Basic data validation (You can replace this with a Serializer later)
    title = request.data.get('title')
    description = request.data.get('description', '')
    date = request.data.get('date')

    if not title or not date:
        return Response(
            {"error": "Title and Date are required."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # --- STEP 1: Save to DB Immediatey ---
        # The server does this very fast (milliseconds)
        new_event = Event.objects.create(
            title=title,
            description=description,
            date=date,
            creator=request.user 
        )

        # --- STEP 2: Trigger the Background Task ---
        # We use .delay() to send it to Redis/Celery.
        # This does NOT block the code; it happens instantly.
        process_event_invites.delay(new_event.id, request.user.id)

        # --- STEP 3: Return Immediate Response ---
        # The user gets a success message instantly, even if 
        # sending 1000 emails takes 5 minutes in the background.
        return Response(
            {
                "message": "Event created successfully! Invites are being processed in the background.",
                "event_id": new_event.id
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
