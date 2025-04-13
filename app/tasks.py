import logging
from openai import OpenAI
from app.worker import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Message
from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

@celery_app.task
def process_llm_request(message_id: int):
    logger.info(f"Starting to process LLM request for message_id: {message_id}")
    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"Message not found with id: {message_id}")
            return

        logger.info(f"Retrieved message content: {message.content[:100]}...")
        
        client = OpenAI(
            base_url=settings.VLLM_API_URL,
            api_key="not-needed"  # vLLM doesn't require API key
        )
        
        try:
            logger.info("Sending request to LLM API")
            response = client.chat.completions.create(
                model=settings.VLLM_MODEL_NAME,
                messages=[{"role": "user", "content": message.content}],
                temperature=0.7,
                max_tokens=1000
            )
            
            logger.info("Successfully received response from LLM API")
            message.response = response.choices[0].message.content
            db.commit()
            logger.info("Successfully updated message with LLM response")
            
        except Exception as e:
            logger.error(f"Error during LLM API call: {str(e)}", exc_info=True)
            message.response = "Sorry, I encountered an error processing your request."
            db.commit()
            
    except Exception as e:
        logger.error(f"Unexpected error in process_llm_request: {str(e)}", exc_info=True)
    finally:
        db.close()
        logger.info(f"Completed processing for message_id: {message_id}") 