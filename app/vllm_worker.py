import asyncio
import logging
from app.core.config import settings
from app.message_broker import MessageBroker
from app.tasks.process_llm import process_vllm_response

logger = logging.getLogger(__name__)

async def process_vllm_requests():
    """Process VLLM requests from the message broker"""
    message_broker = MessageBroker(redis_url=settings.REDIS_URL)
    await message_broker.connect()
    
    # Подписываемся на канал запросов
    pubsub = await message_broker.subscribe("vllm_requests")
    
    logger.info("VLLM worker started and listening for requests")
    
    while True:
        try:
            # Получаем сообщение из канала
            message = await message_broker.get_message(pubsub)
            if message:
                logger.info(f"Received VLLM request for message_id: {message['message_id']}")
                
                # Обрабатываем запрос
                await process_vllm_response(
                    message_id=message["message_id"],
                    content=message["content"]
                )
                
        except Exception as e:
            logger.error(f"Error processing VLLM request: {str(e)}", exc_info=True)
            await asyncio.sleep(1)  # Пауза перед следующей попыткой

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(process_vllm_requests()) 