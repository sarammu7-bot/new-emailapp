from django.urls import re_path
from django_backend import consumers

websocket_urlpatterns = [
    # Matches ws://127.0.0.1:8000/ws/chat/12/
    re_path(r'chat/(?P<room_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]