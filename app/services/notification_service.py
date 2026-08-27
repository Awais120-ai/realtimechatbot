from sqlalchemy.orm import Session
from app.models.notification import Notification
# pyrefly: ignore [missing-import]
from app.core.websocket_manager import manager

async def send_and_save_notification(
    db: Session, 
    user_id: int, 
    title: str, 
    message: str, 
    notif_type: str
):
    # 1. Database mein Save karein
    db_notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type
    )
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)

    # 2. WebSocket par Live Send karein
    await manager.send_personal_message({
        "id": db_notif.id,
        "title": title,
        "message": message,
        "type": notif_type,
        "created_at": str(db_notif.created_at)
    }, user_id)

    return db_notif