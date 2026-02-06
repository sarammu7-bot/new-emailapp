import os
import django
from .django_setup import setup_django
setup_django()
from email_project.asgi import application as django_asgi_app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_app.core.socket_manager import manager
import asyncio
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from fastapi_app.routers import (
    auth, users, email, chat, analytics, 
    meet, calendar, notes, notifications, task, profile, drive
)

app = FastAPI()
app.mount("/ws", django_asgi_app)

app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "http://34.208.181.79","http://34.208.181.79:8000",
        # "http://localhost:5173","http://localhost:8000",
        ],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_ROOT = BASE_DIR / "media" 
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

app.include_router(email.router, prefix="/email", tags=["Emails"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(task.router, prefix="/tasks", tags=["Tasks"])                                                
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(meet.router, prefix="/meet", tags=["Meetings"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

app.include_router(notes.router, prefix="/notes", tags=["Notes"])
app.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])
app.include_router(drive.router, prefix="/drive", tags=["Drive"])


@app.on_event("startup")
async def startup_event():
    app.state.redis_listener = asyncio.create_task(manager.start_redis_listener())
    
@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "redis_listener"):
        app.state.redis_listener.cancel()

@app.get("/")
def read_root():
    return {"message": "Django and FastAPI are linked!"}