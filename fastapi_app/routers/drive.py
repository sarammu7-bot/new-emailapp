from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from asgiref.sync import sync_to_async
from django_backend.models import DriveFile
from fastapi_app.schemas.drive_schemas import DriveFileRead
from fastapi_app.routers.auth import get_current_user
from django.core.files.base import ContentFile


router = APIRouter(prefix="/drive", tags=["Drive"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    try:
        content = await file.read()

     
        drive_file = await sync_to_async(DriveFile.objects.create)(
            owner=current_user,
            original_name=file.filename,
            size=len(content),
            content_type=file.content_type or "application/octet-stream",
        )

        
        await sync_to_async(drive_file.file.save)(
            file.filename,
            ContentFile(content),
        )

        return {
            "message": "File uploaded successfully",
            "file_id": drive_file.id,
            "file_name": drive_file.original_name,
        }

    except Exception as e:
        print("UPLOAD ERROR:", e)
        raise HTTPException(
            status_code=500,
            detail="File upload failed"
        )


@router.get("/my-files", response_model=list[DriveFileRead])
async def my_files(current_user=Depends(get_current_user)):
    files = await sync_to_async(list)(
        DriveFile.objects.filter(owner=current_user).order_by("-created_at")
    )

    return [
        {
            "id": f.id,
            "original_name": f.original_name,
            "size": f.size,
            "content_type": f.content_type,
            "created_at": f.created_at,
            "url": f.file.url,
        }
        for f in files
    ]
