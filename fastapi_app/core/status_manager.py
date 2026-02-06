from datetime import datetime
from typing import Optional
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from fastapi_app.core.socket_manager import manager

User = get_user_model()

class StatusManager:
    """
    Central Brain for handling User Presence.
    Enforces Priority Rules: OFFLINE > DND > IN_MEETING > AVAILABLE
    """

    PRIORITY_MAP = {
        'OFFLINE': 100,
        'DND': 90,       
        'IN_MEETING': 80,
        'BRB': 50,       
        'AWAY': 40,      
        'AVAILABLE': 0   
    }

    @staticmethod
    async def request_status_change(user_id: int, new_status: str, message: str = None, is_manual: bool = False):
        """
        The Master Async Function.
        Now accepts an optional 'message' (e.g., "In a meeting").
        """
        success = await StatusManager._update_user_status(user_id, new_status, message, is_manual)

        if success:
            await manager.broadcast_to_all({
                "type": "USER_STATUS_UPDATE",
                "user_id": user_id,
                "status": new_status,
                "message": message  
            })

    @staticmethod
    @sync_to_async
    def _update_user_status(user_id: int, new_status: str, message: str, is_manual: bool):
        try:
            user = User.objects.get(id=user_id)
            current_status = user.current_status
            
            if current_status == 'OFFLINE' and new_status != 'AVAILABLE' and new_status != 'OFFLINE':
                return False

            if user.is_manually_set and user.current_status == 'DND' and not is_manual:
                return False

            if new_status == 'AVAILABLE' and current_status == 'IN_MEETING':
                pass
            
            user.current_status = new_status
            user.is_manually_set = is_manual
            
            if new_status in ['AVAILABLE', 'OFFLINE']:
                user.status_message = None
            else:
                
                if message is not None:
                     user.status_message = message

            user.save()
            print(f"✅ Status: {user.email} -> {new_status} | Msg: {user.status_message}")
            return True

        except User.DoesNotExist:
            return False