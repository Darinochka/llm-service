import httpx
from app.worker import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Message
from sqlalchemy.orm import Session

@celery_app.task
def process_llm_request(message_id: int):
    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            return

        with httpx.Client() as client:
            response = client.post(
                f"{settings.VLLM_API_URL}/v1/chat/completions",
                json={
                    "model": settings.VLLM_MODEL_NAME,
                    "messages": [{"role": "user", "content": message.content}],
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                message.response = result["choices"][0]["message"]["content"]
                db.commit()
            else:
                message.response = "Sorry, I encountered an error processing your request."
                db.commit()
    finally:
        db.close() 