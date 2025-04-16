import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import models
from app.tasks import process_llm_request

# Configure logging
logger = logging.getLogger(__name__)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"Received /start command from user {message.from_user.id}")
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            # Create new user
            logger.info(f"Creating new user with telegram_id: {message.from_user.id}")
            user = models.User(
                telegram_id=str(message.from_user.id),
                role=models.UserRole.USER
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            await message.answer(
                "Welcome! You've been registered. Use /subscribe to get access to the LLM service."
            )
            logger.info(f"New user created with id: {user.id}")
        else:
            logger.info(f"Existing user {user.id} returned to the bot")
            await message.answer(
                "Welcome back! You can send any message to interact with the LLM."
            )
    except Exception as e:
        logger.error(f"Error in cmd_start: {str(e)}", exc_info=True)
        await message.answer("An error occurred. Please try again later.")
    finally:
        db.close()

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    logger.info(f"Received /subscribe command from user {message.from_user.id}")
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            logger.warning(f"User {message.from_user.id} tried to subscribe without registration")
            await message.answer("Please use /start first to register.")
            return

        # Check if user already has an active subscription
        active_subscription = db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.end_date > datetime.utcnow()
        ).first()
        
        if active_subscription:
            logger.info(f"User {user.id} already has an active subscription until {active_subscription.end_date}")
            await message.answer(
                f"You already have an active subscription until {active_subscription.end_date.strftime('%Y-%m-%d')}."
            )
            return

        # Create subscription
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
        
        logger.info(f"Creating new subscription for user {user.id} from {start_date} to {end_date}")
        subscription = models.Subscription(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date
        )
        db.add(subscription)

        # Create transaction
        logger.info(f"Creating transaction for user {user.id} with amount {settings.SUBSCRIPTION_PRICE_RUB}")
        transaction = models.Transaction(
            user_id=user.id,
            amount=settings.SUBSCRIPTION_PRICE_RUB,
            type=models.TransactionType.SUBSCRIPTION
        )
        db.add(transaction)
        
        db.commit()
        logger.info(f"Successfully created subscription and transaction for user {user.id}")
        
        await message.answer(
            f"Subscription created successfully! You now have access until {end_date.strftime('%Y-%m-%d')}."
        )
    except Exception as e:
        logger.error(f"Error in cmd_subscribe: {str(e)}", exc_info=True)
        await message.answer("An error occurred while processing your subscription. Please try again later.")
    finally:
        db.close()

@dp.message()
async def handle_message(message: Message):
    logger.info(f"Received message from user {message.from_user.id}: {message.text[:50]}...")
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            logger.warning(f"Unregistered user {message.from_user.id} tried to send a message")
            await message.answer("Please use /start first to register.")
            return

        # Check subscription
        active_subscription = db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.end_date > datetime.utcnow()
        ).first()
        
        if not active_subscription:
            logger.warning(f"User {user.id} tried to use the service without an active subscription")
            await message.answer(
                "You need an active subscription to use the service. Use /subscribe to get access."
            )
            return

        # Create message record
        logger.info(f"Creating message record for user {user.id}")
        db_message = models.Message(
            user_id=user.id,
            content=message.text,
            response="Processing..."
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        logger.info(f"Created message record with id: {db_message.id}")

        # Send processing message
        processing_msg = await message.answer("Processing your request...")
        logger.info(f"Sent processing message for message_id: {db_message.id}")

        # Process message synchronously
        logger.info(f"Processing message_id: {db_message.id}")
        process_llm_request(db_message.id)
        
        # Wait for response with timeout
        max_wait_time = 60  # seconds
        start_time = time.time()
        
        while db_message.response == "Processing...":
            if time.time() - start_time > max_wait_time:
                logger.warning(f"Timeout waiting for response for message_id: {db_message.id}")
                await processing_msg.edit_text("The request is taking longer than expected. We'll notify you when it's ready.")
                break
                
            await asyncio.sleep(1)
            db.refresh(db_message)

        # Update the processing message with the actual response if we have one
        if db_message.response != "Processing...":
            logger.info(f"Updating message with response for message_id: {db_message.id}")
            await processing_msg.edit_text(db_message.response)
            logger.info(f"Successfully processed message_id: {db_message.id}")
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
        await message.answer("An error occurred while processing your message. Please try again later.")
    finally:
        db.close()

async def start_bot():
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)
    logger.info("Telegram bot started successfully") 