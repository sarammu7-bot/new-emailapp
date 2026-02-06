from fastapi import APIRouter, Depends, HTTPException, status
from asgiref.sync import sync_to_async

from django_backend.models import Note
from ..schemas.note_schemas import NoteCreate, NoteUpdate, NoteRead
from .auth import get_current_user

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.post("/", response_model=NoteRead)
async def create_note(data: NoteCreate, user=Depends(get_current_user)):
    note = await sync_to_async(Note.objects.create)(
        user=user,
        title=data.title,
        content=data.content
    )
    return note


@router.get("/", response_model=list[NoteRead])
async def list_notes(user=Depends(get_current_user)):
    notes = await sync_to_async(list)(
        Note.objects.filter(user=user).order_by("-is_pinned", "-updated_at")
    )
    return notes


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, user=Depends(get_current_user)):
    note = await sync_to_async(Note.objects.filter(id=note_id, user=user).first)()
    if not note:
        raise HTTPException(404, "Note not found")
    return note


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(note_id: int, data: NoteUpdate, user=Depends(get_current_user)):
    note = await sync_to_async(Note.objects.filter(id=note_id, user=user).first)()
    if not note:
        raise HTTPException(404, "Note not found")

    if data.title is not None:
        note.title = data.title
    if data.content is not None:
        note.content = data.content
    if data.is_pinned is not None:
        note.is_pinned = data.is_pinned

    await sync_to_async(note.save)()
    return note


@router.delete("/{note_id}")
async def delete_note(note_id: int, user=Depends(get_current_user)):
    note = await sync_to_async(Note.objects.filter(id=note_id, user=user).first)()
    if not note:
        raise HTTPException(404, "Note not found")

    await sync_to_async(note.delete)()
    return {"message": "Note deleted successfully"}
