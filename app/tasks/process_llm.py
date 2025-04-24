import logging
import os
from openai import OpenAI
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import Message
from app.message_broker import MessageBroker
import asyncio

logger = logging.getLogger(__name__)

message_broker = MessageBroker(redis_url=settings.REDIS_URL)

async def process_llm_request(message_id: int) -> None:
    logger.info(f"Starting to process LLM request for message_id: {message_id}")
    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"Message not found with id: {message_id}")
            return

        logger.info(f"Retrieved message content: {message.content[:100]}...")
        
        await message_broker.publish(
            "vllm_requests",
            {
                "message_id": message_id,
                "content": message.content
            }
        )
        
        pubsub = await message_broker.subscribe(f"vllm_response_{message_id}")
        
        while True:
            response = await message_broker.get_message(pubsub)
            if response:
                message.response = response["response"]
                db.commit()
                break
            await asyncio.sleep(0.1)
            
    except Exception as e:
        logger.error(f"Error processing LLM request: {str(e)}", exc_info=True)
        if message:
            message.response = "Error processing request. Please try again later."
            db.commit()
    finally:
        db.close()

async def process_vllm_response(message_id: int, content: str) -> None:
    try:
        vllm_api_url = os.environ.get('VLLM_API_URL', settings.VLLM_API_URL)
        logger.info(f"Using vLLM API URL: {vllm_api_url}")
        
        client = OpenAI(
            base_url=vllm_api_url,
            api_key="not-needed",
            timeout=30.0
        )
        
        response = client.chat.completions.create(
            model=settings.VLLM_MODEL_NAME,
            messages=[
                {"role": "user", "content": content}
            ]
        )
        
        await message_broker.publish(
            f"vllm_response_{message_id}",
            {
                "message_id": message_id,
                "response": response.choices[0].message.content
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting response from VLLM: {str(e)}", exc_info=True)
        await message_broker.publish(
            f"vllm_response_{message_id}",
            {
                "message_id": message_id,
                "response": "Error getting response from LLM. Please try again later."
            }
        ) 