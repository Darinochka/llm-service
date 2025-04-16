import logging
import os
from openai import OpenAI
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Message

# Configure logging
logger = logging.getLogger(__name__)

def process_llm_request(message_id: int) -> None:
    """Process an LLM request for a given message ID.
    
    Args:
        message_id (int): The ID of the message to process
        
    Returns:
        None
    """
    logger.info(f"Starting to process LLM request for message_id: {message_id}")
    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"Message not found with id: {message_id}")
            return

        logger.info(f"Retrieved message content: {message.content[:100]}...")
        
        # Log the vLLM API URL for debugging
        vllm_api_url = os.environ.get('VLLM_API_URL', settings.VLLM_API_URL)
        logger.info(f"Using vLLM API URL: {vllm_api_url}")
        
        client = OpenAI(
            base_url=vllm_api_url,
            api_key="not-needed",  # vLLM doesn't require API key
            timeout=30.0  # Add timeout to prevent hanging
        )
        
        try:
            logger.info("Sending request to LLM API")
            # Log the request details
            logger.info(f"Request details: model={settings.VLLM_MODEL_NAME}, content={message.content[:50]}...")
            
            response = client.chat.completions.create(
                model=settings.VLLM_MODEL_NAME,
                messages=[{"role": "user", "content": message.content}],
                temperature=0.7,
                max_tokens=1000
            )
            
            logger.info("Successfully received response from LLM API")
            logger.info(f"Response content: {response.choices[0].message.content[:100]}...")
            
            message.response = response.choices[0].message.content
            db.commit()
            logger.info("Successfully updated message with LLM response")
            
        except Exception as e:
            logger.error(f"Error during LLM API call: {str(e)}", exc_info=True)
            message.response = f"Sorry, I encountered an error processing your request: {str(e)}"
            db.commit()
            
    except Exception as e:
        logger.error(f"Unexpected error in process_llm_request: {str(e)}", exc_info=True)
        if db and message:
            message.response = "Sorry, the service is temporarily unavailable. Please try again later."
            db.commit()
    finally:
        if db:
            db.close()
        logger.info(f"Completed processing for message_id: {message_id}") 