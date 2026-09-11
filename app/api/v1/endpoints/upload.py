import cloudinary.uploader

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user
from app.models.user import User


router = APIRouter()





ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

ALLOWED_FILE_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}

ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
}


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required.",
        )

    content_type = file.content_type or "application/octet-stream"

    if (
        content_type not in ALLOWED_IMAGE_TYPES
        and content_type not in ALLOWED_FILE_TYPES
        and content_type not in ALLOWED_AUDIO_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This file type is not allowed.",
        )

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size must not exceed 10 MB.",
        )

    resource_type = "image" if content_type in ALLOWED_IMAGE_TYPES else "auto"

    result = cloudinary.uploader.upload(
        contents,
        folder="realtimechatbot/chat",
        resource_type=resource_type,
    )

    file_url = result["secure_url"]
    file_size = len(contents)

    await file.close()

    if content_type in ALLOWED_IMAGE_TYPES:
        message_type = "image"
    elif content_type in ALLOWED_AUDIO_TYPES:
        message_type = "audio"
    else:
        message_type = "file"   


    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message_type": message_type,
            "file_url": file_url,
            "file_name": file.filename,
            "file_size": file_size,
            "mime_type": content_type,
        },
    )