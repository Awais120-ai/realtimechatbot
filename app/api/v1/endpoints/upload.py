from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user
from app.models.user import User


router = APIRouter()


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This file type is not allowed.",
        )

    extension = Path(file.filename).suffix.lower()

    unique_filename = f"{uuid4().hex}{extension}"

    file_path = UPLOAD_DIR / unique_filename

    file_size = 0

    try:
        with file_path.open("wb") as buffer:

            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > MAX_FILE_SIZE:
                    file_path.unlink(missing_ok=True)

                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size must not exceed 10 MB.",
                    )

                buffer.write(chunk)

    finally:
        await file.close()

    if content_type in ALLOWED_IMAGE_TYPES:
        message_type = "image"
    else:
        message_type = "file"

    file_url = f"/uploads/{unique_filename}"

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