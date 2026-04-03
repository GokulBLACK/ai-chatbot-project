from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Conversation, Message

def get_or_create_conversation(db: Session, conversation_id: int | None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv:
            return conv
    conv = Conversation(title="New chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

def add_message(db: Session, conversation_id: int, role: str, content: str, model: str = "") -> None:
    db.add(Message(conversation_id=conversation_id, role=role, content=content, model=model))
    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = datetime.utcnow()
    db.commit()

def get_recent_messages(db: Session, conversation_id: int, limit: int = 20) -> list[dict]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]
