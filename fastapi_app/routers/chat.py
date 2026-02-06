from django.db.models import Q
from jose import JWTError, jwt
from fastapi import status
from fastapi_app.core.config import settings
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Query
import json
import re
import secrets
from django.core.files.base import ContentFile
from typing import List, Optional
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from fastapi_app.routers.notifications import create_notification
from django_backend.models import ChatRoom, ChatMessage, Email, MessageReaction
from fastapi_app.schemas.chat_schemas import ChatRoomCreate, ChatRoomRead, MessageRead, ChatMemberUpdate, MessageUpdate, ForwardRequest
from fastapi_app.core.socket_manager import manager
from fastapi_app.dependencies.auth import get_current_user

router = APIRouter()
User = get_user_model()

async def get_current_user_ws(token: str = Query(...)):
    """
    Validates the token passed in the WebSocket URL.
    """
    credentials_exception = status.WS_1008_POLICY_VIOLATION
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise WebSocketDisconnect(code=credentials_exception)
    except JWTError:
        raise WebSocketDisconnect(code=credentials_exception)
    
    try:
        user = await sync_to_async(User.objects.get)(email=email)
        return user
    except User.DoesNotExist:
        raise WebSocketDisconnect(code=credentials_exception)
    

@router.post("/rooms", response_model=ChatRoomRead)
def create_room(data: ChatRoomCreate, current_user = Depends(get_current_user)):
    related_email_obj = None
    initial_participants = list(data.participant_emails) 

    if data.email_id:
        try:
            related_email_obj = Email.objects.get(id=data.email_id)
            
            if related_email_obj.sender.email not in initial_participants:
                initial_participants.append(related_email_obj.sender.email)
            
            if related_email_obj.receiver and related_email_obj.receiver.email not in initial_participants:
                initial_participants.append(related_email_obj.receiver.email)
                
        except Email.DoesNotExist:
            raise HTTPException(status_code=404, detail="Linked email not found")

    room = ChatRoom.objects.create(
        name=data.name,
        is_group=data.is_group,
        related_email=related_email_obj
    )
    
    if current_user.email not in initial_participants:
        initial_participants.append(current_user.email)
        
    for email in initial_participants:
        try:
            u = User.objects.get(email=email)
            room.participants.add(u)
        except User.DoesNotExist:
            continue 
            
    return format_room_response(room)

@router.get("/search", response_model=List[MessageRead])
def search_messages(
    q: str = Query(..., min_length=1, description="Search term"),
    current_user = Depends(get_current_user)
):
    """
    Search for messages across ALL rooms. Includes Parent info and Reactions.
    """
    user_room_ids = current_user.chat_rooms.values_list('id', flat=True)
    
    msgs = ChatMessage.objects.filter(
        room__id__in=user_room_ids,   
        is_deleted=False,             
        content__icontains=q         
    ).select_related('parent', 'parent__sender').prefetch_related('reactions', 'reactions__user').order_by("-timestamp")
    
    results = []
    for m in msgs:
        url = None
        if m.attachment:
            try:
                url = m.attachment.url
            except ValueError:
                url = None  

        reaction_map = {}
        for r in m.reactions.all():
            if r.emoji not in reaction_map:
                reaction_map[r.emoji] = {"count": 0, "emails": []}
            reaction_map[r.emoji]["count"] += 1
            reaction_map[r.emoji]["emails"].append(r.user.email)

        reactions_list = [
            {"emoji": k, "count": v["count"], "user_emails": v["emails"]}
            for k, v in reaction_map.items()
        ]

        results.append({
            "id": m.id,
            "sender_email": m.sender.email,
            "content": m.content,
            "attachment_url": url,
            "timestamp": m.timestamp,
            "read_count": m.read_by.count(),
            "is_starred": m.starred_by.filter(id=current_user.id).exists(),
            "parent_id": m.parent.id if m.parent else None,
            "parent_content": m.parent.content if m.parent else None,
            "parent_sender": m.parent.sender.email if m.parent else None,
            "reactions": reactions_list,
            "is_forwarded": m.is_forwarded
        })

    return results

@router.get("/rooms", response_model=List[ChatRoomRead])
def list_rooms(current_user = Depends(get_current_user)):
    """
    List rooms with Unread Count AND Last Message Preview.
    """
    rooms = current_user.chat_rooms.all().prefetch_related('messages', 'participants')

    results = []
    for room in rooms:
        unread_count = room.messages.filter(is_deleted=False).exclude(read_by=current_user).count()

        last_msg_obj = room.messages.filter(is_deleted=False).order_by("-timestamp").first()
        
        last_message_data = None
        if last_msg_obj:
            last_message_data = {
                "id": last_msg_obj.id,
                "sender_email": last_msg_obj.sender.email,
                "content": last_msg_obj.content,
                "attachment_url": last_msg_obj.attachment.url if last_msg_obj.attachment else None,
                "timestamp": last_msg_obj.timestamp,
                "read_count": last_msg_obj.read_by.count(),
                "is_starred": last_msg_obj.starred_by.filter(id=current_user.id).exists()
            }

        results.append({
            "id": room.id,
            "name": room.name,
            "is_group": room.is_group,
            "unread_count": unread_count,       
            "last_message": last_message_data,
            "participants": [u.email for u in room.participants.all()] 
        })

    return results


@router.get("/online", response_model=List[int])
def get_online_users(current_user = Depends(get_current_user)):
    return manager.get_online_users()

@router.get("/rooms/{room_id}/messages", response_model=List[MessageRead])
def get_messages(
    room_id: int, 
    q: Optional[str] = Query(None, description="Search within this room"), 
    current_user = Depends(get_current_user)
):
    try:
        room = ChatRoom.objects.get(id=room_id)
        if current_user not in room.participants.all():
             raise HTTPException(status_code=403, detail="Not a participant")
    except ChatRoom.DoesNotExist:
        raise HTTPException(status_code=404, detail="Room not found")

    msgs = room.messages.filter(is_deleted=False).select_related('parent', 'parent__sender').prefetch_related('reactions', 'reactions__user')
    
    if q:
        msgs = msgs.filter(content__icontains=q)
        
    msgs = msgs.order_by("timestamp")
    
    results = []
    for m in msgs:
        url = None
        if m.attachment:
            try:
                url = m.attachment.url
            except ValueError:
                url = None  

        reaction_map = {}
        for r in m.reactions.all():
            if r.emoji not in reaction_map:
                reaction_map[r.emoji] = {"count": 0, "emails": []}
            reaction_map[r.emoji]["count"] += 1
            reaction_map[r.emoji]["emails"].append(r.user.email)

        reactions_list = [
            {"emoji": k, "count": v["count"], "user_emails": v["emails"]}
            for k, v in reaction_map.items()
        ]

        results.append({
            "id": m.id,
            "sender_email": m.sender.email,
            "content": m.content,
            "attachment_url": url,
            "timestamp": m.timestamp,
            "read_count": m.read_by.count(),
            "is_starred": m.starred_by.filter(id=current_user.id).exists(),
            
            "parent_id": m.parent.id if m.parent else None,
            "parent_content": m.parent.content if m.parent else None,
            "parent_sender": m.parent.sender.email if m.parent else None,
            "reactions": reactions_list,
            "is_forwarded": m.is_forwarded    
        })

    return results

@router.patch("/messages/{message_id}", response_model=MessageRead)
async def edit_message(
    message_id: int,
    data: MessageUpdate,
    current_user = Depends(get_current_user)
):
    try:
        msg = await sync_to_async(ChatMessage.objects.get)(id=message_id)
    except ChatMessage.DoesNotExist:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")

    msg.content = data.content
    await sync_to_async(msg.save)()

    socket_message = {
        "type": "MESSAGE_UPDATE",
        "id": msg.id,
        "room_id": msg.room_id,
        "content": msg.content,
        "timestamp": str(msg.timestamp)
    }
    await manager.broadcast(socket_message, msg.room_id)

    @sync_to_async
    def get_response_data():
        return {
            "id": msg.id,
            "sender_email": msg.sender.email,  
            "content": msg.content,
            "attachment_url": msg.attachment.url if msg.attachment else None,
            "timestamp": msg.timestamp,
            "read_count": msg.read_by.count(), 
            "is_starred": msg.starred_by.filter(id=current_user.id).exists() 
        }

    return await get_response_data()

@router.post("/rooms/{room_id}/read")
async def mark_room_as_read(
    room_id: int, 
    current_user = Depends(get_current_user)
):
    """
    Marks all messages in the room as 'Read' by the current user.
    """
    @sync_to_async
    def process_read_receipts():
        try:
            room = ChatRoom.objects.get(id=room_id)
            if current_user not in room.participants.all():
                raise PermissionError("Not a participant")
            
            unread_msgs = room.messages.exclude(read_by=current_user)
            count = unread_msgs.count()
            
            for msg in unread_msgs:
                msg.read_by.add(current_user)
                
            return count
            
        except ChatRoom.DoesNotExist:
            return None

    try:
        count = await process_read_receipts()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not a participant")

    if count is None:
        raise HTTPException(status_code=404, detail="Room not found")

    return {"message": "Messages marked as read", "updated_count": count}


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int, current_user: User = Depends(get_current_user)):
    try:
        msg = ChatMessage.objects.get(id=message_id)
    except ChatMessage.DoesNotExist:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.sender != current_user:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")

    msg.is_deleted = True
    msg.save()
    
    return None


@router.get("/trash", response_model=List[MessageRead])
def chat_trash(current_user = Depends(get_current_user)):
    msgs = ChatMessage.objects.filter(
        sender=current_user, 
        is_deleted=True
    ).select_related('parent', 'parent__sender').prefetch_related('reactions', 'reactions__user').order_by("-timestamp")

    results = []
    for m in msgs:
        reaction_map = {}
        for r in m.reactions.all():
            if r.emoji not in reaction_map:
                reaction_map[r.emoji] = {"count": 0, "emails": []}
            reaction_map[r.emoji]["count"] += 1
            reaction_map[r.emoji]["emails"].append(r.user.email)
        
        reactions_list = [
            {"emoji": k, "count": v["count"], "user_emails": v["emails"]}
            for k, v in reaction_map.items()
        ]

        results.append({
            "id": m.id,
            "sender_email": m.sender.email,
            "content": m.content,
            "attachment_url": m.attachment.url if m.attachment else None,
            "timestamp": m.timestamp,
            "read_count": m.read_by.count(),
            "is_starred": m.starred_by.filter(id=current_user.id).exists(),
            "parent_id": m.parent.id if m.parent else None,
            "parent_content": m.parent.content if m.parent else None,
            "parent_sender": m.parent.sender.email if m.parent else None,
            "reactions": reactions_list,
            "is_forwarded": m.is_forwarded
        })
    return results


@router.post("/messages/{message_id}/star")
def star_message(message_id: int, current_user: User = Depends(get_current_user)):
    try:
        msg = ChatMessage.objects.get(id=message_id)
    except ChatMessage.DoesNotExist:
        raise HTTPException(status_code=404, detail="Message not found")

    if current_user not in msg.room.participants.all():
        raise HTTPException(status_code=403, detail="Not authorized")

    if msg.starred_by.filter(id=current_user.id).exists():
        msg.starred_by.remove(current_user)
        is_starred = False
    else:
        msg.starred_by.add(current_user)
        is_starred = True

    return {"message": "Star updated", "is_starred": is_starred}

def format_room_response(room):
    
    last_msg_obj = room.messages.order_by("-timestamp").first()
    last_msg = None
    if last_msg_obj:
        last_msg = {
            "id": last_msg_obj.id,
            "sender_email": last_msg_obj.sender.email,
            "content": last_msg_obj.content,
            "timestamp": last_msg_obj.timestamp
        }

    return {
        "id": room.id,
        "name": room.name,
        "is_group": room.is_group,
        "participants": [u.email for u in room.participants.all()],
        "last_message": last_msg
    }


@router.get("/starred", response_model=List[MessageRead])
def get_my_starred_messages(current_user: User = Depends(get_current_user)):
    msgs = current_user.starred_chat_messages.all().order_by("-timestamp")
    return [
        {
            "id": m.id,
            "sender_email": m.sender.email,
            "content": m.content,
            "attachment_url": m.attachment.url if m.attachment else None,
            "timestamp": m.timestamp,
            "read_count": m.read_by.count(),
            "is_starred": True 
        }
        for m in msgs
    ]
 
@router.post("/rooms/{room_id}/upload")
async def upload_chat_attachment(
    room_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    @sync_to_async
    def save_attachment_to_db():
        try:
            room = ChatRoom.objects.get(id=room_id)
            if current_user not in room.participants.all():
                raise PermissionError("Not a participant")
            
            file_content = file.file.read()
            
            msg = ChatMessage.objects.create(
                room=room,
                sender=current_user,
                content=f"Sent a file: {file.filename}", 
                attachment=None 
            )
        
            msg.attachment.save(file.filename, ContentFile(file_content))
            msg.save()

            for participant in room.participants.all():
                if participant != current_user:
                    create_notification(
                        recipient=participant,
                        message=f"{current_user.email} sent a file in {room.name or 'Chat'}",
                        type_choice="chat",
                        related_id=room.id
                    )

            return msg, room
        except ChatRoom.DoesNotExist:
            return None, None

    try:
        msg_obj, room = await save_attachment_to_db()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not a participant")
        
    if not msg_obj:
        raise HTTPException(status_code=404, detail="Room not found")

    socket_message = {
        "id": msg_obj.id,
        "sender": current_user.email,
        "content": msg_obj.content,
        "attachment_url": msg_obj.attachment.url, 
        "timestamp": str(msg_obj.timestamp)
    }
    
    await manager.broadcast(socket_message, room_id)

    return {"message": "File uploaded", "url": msg_obj.attachment.url}


class TextMessageCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None

@router.post("/messages/{message_id}/react")
async def toggle_reaction(
    message_id: int, 
    emoji: str = Query(..., min_length=1, description="The emoji character"),
    current_user: User = Depends(get_current_user)
):

    @sync_to_async
    def toggle_db_reaction():
        try:
            msg = ChatMessage.objects.get(id=message_id)
        except ChatMessage.DoesNotExist:
            return None, None

        existing = MessageReaction.objects.filter(message=msg, user=current_user, emoji=emoji).first()
        
        if existing:
            existing.delete()
            action = "removed"
        else:
            MessageReaction.objects.create(message=msg, user=current_user, emoji=emoji) # Add
            action = "added"
            
            if msg.sender != current_user:
                create_notification(
                    recipient=msg.sender,
                    message=f"{current_user.email} reacted {emoji} to your message",
                    type_choice="chat",
                    related_id=msg.room.id
                )
        
        return msg, action

    msg_obj, action = await toggle_db_reaction()
    
    if not msg_obj:
        raise HTTPException(status_code=404, detail="Message not found")

    socket_message = {
        "type": "REACTION_UPDATE",
        "message_id": msg_obj.id,
        "emoji": emoji,
        "action": action, 
        "user_email": current_user.email
    }
    await manager.broadcast(socket_message, msg_obj.room.id)

    return {"message": f"Reaction {action}", "emoji": emoji}

@router.post("/messages/{message_id}/forward")
async def forward_message(
    message_id: int,
    request: ForwardRequest,
    current_user: User = Depends(get_current_user)
):
    from django_backend.models import ChatMessage, ChatRoom 

    @sync_to_async
    def process_forward():
        try:
            original_msg = ChatMessage.objects.get(id=message_id)
            
            target_room = ChatRoom.objects.get(id=request.target_room_id)
            
            if current_user not in target_room.participants.all():
                raise PermissionError("You are not a member of the target room")

            new_msg = ChatMessage.objects.create(
                room=target_room,
                sender=current_user,
                content=original_msg.content, 
                attachment=original_msg.attachment, 
                is_forwarded=True
            )
            
            for participant in target_room.participants.all():
                if participant != current_user:
                    create_notification(
                        recipient=participant,
                        message=f"Forwarded message from {current_user.email}",
                        type_choice="chat",
                        related_id=target_room.id
                    )

            return new_msg, target_room.id

        except ChatMessage.DoesNotExist:
            return None, None
        except ChatRoom.DoesNotExist:
            return "Room not found", None

    try:
        new_msg_obj, target_room_id = await process_forward()
    except PermissionError:
         raise HTTPException(status_code=403, detail="You are not a member of the target room")
         
    if new_msg_obj == "Room not found":
        raise HTTPException(status_code=404, detail="Target room not found")
    if not new_msg_obj:
        raise HTTPException(status_code=404, detail="Original message not found")

    socket_message = {
        "id": new_msg_obj.id,
        "sender": current_user.email,
        "content": new_msg_obj.content,
        "attachment_url": new_msg_obj.attachment.url if new_msg_obj.attachment else None,
        "timestamp": str(new_msg_obj.timestamp),
        "parent_id": None, 
        "is_forwarded": True 
    }
    await manager.broadcast(socket_message, target_room_id)

    return {"message": "Message forwarded", "new_message_id": new_msg_obj.id}

@router.post("/rooms/{room_id}/message")
async def send_text_message(
    room_id: int,
    data: TextMessageCreate,
    current_user: User = Depends(get_current_user)
):
    @sync_to_async
    def save_text_message():
        try:
            room = ChatRoom.objects.get(id=room_id)
            if current_user not in room.participants.all():
                raise PermissionError("Not a participant")
            
            parent_msg = None
            if data.parent_id:
                try:
                    parent_msg = ChatMessage.objects.get(id=data.parent_id, room=room)
                except ChatMessage.DoesNotExist:
                    pass 

            msg = ChatMessage.objects.create(
                room=room,
                sender=current_user,
                content=data.content,
                parent=parent_msg
            )
            process_mentions(msg)

            for participant in room.participants.all():
                if participant != current_user:
                    create_notification(
                        recipient=participant,
                        message=f"New message from {current_user.email}",
                        type_choice="chat",
                        related_id=room.id
                    )

            parent_info = None
            if parent_msg:
                parent_info = {
                    "id": parent_msg.id,
                    "content": parent_msg.content,
                    "sender": parent_msg.sender.email
                }

            return msg, parent_info 
        except ChatRoom.DoesNotExist:
            return None, None

    try:
        msg_obj, parent_info = await save_text_message()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not a participant")
        
    if not msg_obj:
        raise HTTPException(status_code=404, detail="Room not found")

    socket_message = {
        "id": msg_obj.id,
        "sender": current_user.email,
        "content": msg_obj.content,
        "timestamp": str(msg_obj.timestamp),
        "parent_id": parent_info["id"] if parent_info else None,
        "parent_content": parent_info["content"] if parent_info else None,
        "parent_sender": parent_info["sender"] if parent_info else None
    }
    await manager.broadcast(socket_message, room_id)

    return {"message": "Message sent", "id": msg_obj.id}


@router.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, user_id: int):
    await manager.connect(websocket, room_id, user_id)
    
    @sync_to_async
    def save_message(room_id, user_id, content, parent_id=None):
        room = ChatRoom.objects.get(id=room_id)
        sender = User.objects.get(id=user_id)
        
        parent_msg = None
        if parent_id:
            try:
                parent_msg = ChatMessage.objects.get(id=parent_id, room=room)
            except ChatMessage.DoesNotExist:
                pass

        msg = ChatMessage.objects.create(
            room=room, 
            sender=sender, 
            content=content,
            parent=parent_msg 
        )
        process_mentions(msg)

        parent_info = None
        if parent_msg:
            parent_info = {
                "id": parent_msg.id,
                "content": parent_msg.content,
                "sender": parent_msg.sender.email
            }

        return msg, sender.email, parent_info

    try:
        while True:
            text_data = await websocket.receive_text()
            
            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                payload = {"content": text_data}

            if payload.get("type") == "typing":
                await manager.broadcast({
                    "type": "typing",
                    "user_id": user_id,
                    "room_id": room_id
                }, room_id)
                continue 
            
            if payload.get("type") == "SCREEN_SHARE_STATUS":
                is_sharing = payload.get("is_sharing")
                
                user = await sync_to_async(User.objects.get)(id=user_id)
                action_text = "started sharing their screen" if is_sharing else "stopped sharing"
                content = f" {user.first_name} {action_text}"

                msg_obj = await sync_to_async(ChatMessage.objects.create)(
                    room_id=room_id,
                    sender=user,
                    content=content,
                    message_type='SYSTEM' 
                )

                response = {
                    "type": "system_alert",
                    "content": content,
                    "is_sharing": is_sharing,
                    "sharer_id": user_id,
                    "timestamp": str(msg_obj.timestamp)
                }
                await manager.broadcast(response, room_id)
                continue
            
            content = payload.get("content")
            parent_id = payload.get("parent_id")
            
            if not content:
                continue

            msg_obj, sender_email, parent_info = await save_message(room_id, user_id, content, parent_id)
    
            response = {
                "type": "new_message", 
                "id": msg_obj.id,
                "sender": sender_email,
                "content": content,
                "timestamp": str(msg_obj.timestamp),
                "parent_id": parent_info["id"] if parent_info else None,
                "parent_content": parent_info["content"] if parent_info else None,
                "parent_sender": parent_info["sender"] if parent_info else None,
                "is_forwarded": False 
            }
            await manager.broadcast(response, room_id)
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id, user_id) 
             
@router.post("/rooms/{room_id}/members")
def add_members(
    room_id: int,
    data: ChatMemberUpdate,
    current_user: User = Depends(get_current_user)
):
    try:
        room = ChatRoom.objects.get(id=room_id)
    except ChatRoom.DoesNotExist:
        raise HTTPException(status_code=404, detail="Room not found")

    if current_user not in room.participants.all():
        raise HTTPException(status_code=403, detail="Not a participant")

    added_users = []
    for email in data.user_emails:
        try:
            u = User.objects.get(email=email)
            if u not in room.participants.all():
                room.participants.add(u)
                added_users.append(u.email)
        except User.DoesNotExist:
            continue

    return {"message": "Members added", "added": added_users}

@router.post("/rooms/{room_id}/leave")
def leave_room(
    room_id: int,
    current_user: User = Depends(get_current_user)
):
    try:
        room = ChatRoom.objects.get(id=room_id)
    except ChatRoom.DoesNotExist:
        raise HTTPException(status_code=404, detail="Room not found")

    if current_user in room.participants.all():
        room.participants.remove(current_user)
        
    return {"message": "You have left the group"}     

@router.post("/rooms/{room_id}/call")
async def start_call(
    room_id: int,
    current_user: User = Depends(get_current_user)
):
    @sync_to_async
    def get_room_and_check_access():
        try:
            r = ChatRoom.objects.get(id=room_id)
            if current_user not in r.participants.all():
                raise PermissionError("Not a participant")
            return r
        except ChatRoom.DoesNotExist:
            return None

    try:
        room = await get_room_and_check_access()
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not a participant")
        
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    code = secrets.token_urlsafe(8)
    join_url = f"https://meet.jit.si/Stackly-Chat-{code}"

    @sync_to_async
    def create_call_message():
        msg = ChatMessage.objects.create(
            room=room,
            sender=current_user,
            content=f" started a call. Click to join: {join_url}"
        )
        return msg

    msg_obj = await create_call_message()

    socket_message = {
        "id": msg_obj.id,
        "sender": current_user.email,
        "content": msg_obj.content,
        "type": "CALL", 
        "link": join_url,
        "timestamp": str(msg_obj.timestamp)
    }
    
    await manager.broadcast(socket_message, room_id)

    return {"message": "Call started", "link": join_url}


def process_mentions(message_obj):
    """
    Scans content for @Firstname and tags the user.
    """
    if not message_obj.content:
        return

    potential_names = re.findall(r"@(\w+)", message_obj.content)

    for name in potential_names:
        users = User.objects.filter(first_name__iexact=name)
        for u in users:
            message_obj.mentions.add(u)
            

@router.get("/mentions", response_model=List[MessageRead])
def get_my_mentions(current_user: User = Depends(get_current_user)):
    """
    Returns all messages where the current user was tagged (@Name).
    """
    msgs = current_user.mentioned_in_messages.filter(is_deleted=False).order_by("-timestamp")
    
    results = []
    for m in msgs:
        url = None
        if m.attachment:
            try:
                url = m.attachment.url
            except ValueError:
                pass

        results.append({
            "id": m.id,
            "sender_email": m.sender.email,
            "content": m.content,
            "attachment_url": url,
            "timestamp": m.timestamp,
            "read_count": m.read_by.count(),
            "is_starred": m.starred_by.filter(id=current_user.id).exists()
        })
    return results            

@router.websocket("/ws/{user_id}")
async def status_websocket(
    websocket: WebSocket, 
    user_id: int, 
    current_user: User = Depends(get_current_user_ws) 
):
    
    if current_user.id != user_id:
        print(f"Security Alert: User {current_user.id} tried to listen to User {user_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id, user_id)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
       await manager.disconnect(websocket, user_id, user_id)