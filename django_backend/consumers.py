import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("DEBUG: WebSocket Connection Attempted!")
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # 1. Get the user from the scope (Populated by AuthMiddlewareStack)
        self.user = self.scope.get("user")

        # 2. STRICT AUTH CHECK: Reject connection if not logged in
        if not self.user or self.user.is_anonymous:
            print("DEBUG: Rejecting anonymous connection")
            await self.close()
            return

        # 3. Join the "Room Group"
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"DEBUG: Connection Accepted for user: {self.user.email}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_content = text_data_json.get('message')

        if not message_content:
            return

        # 4. Save message using the REAL user
        new_msg = await self.save_message(self.user.id, self.room_id, message_content)

        # 5. Send message to group (Using REAL email)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': new_msg.content,
                'sender_email': self.user.email, # No more "anonymous@example.com"
                'timestamp': str(new_msg.timestamp)
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender_email'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def save_message(self, user_id, room_id, content):
        # We don't need the "User.objects.first()" fallback anymore 
        # because the connect() function guarantees the user exists.
        user = User.objects.get(id=user_id)
        room = ChatRoom.objects.get(id=room_id)
        return ChatMessage.objects.create(sender=user, room=room, content=content)