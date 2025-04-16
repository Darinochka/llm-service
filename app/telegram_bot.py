import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
import asyncio
import time
import httpx
from typing import Optional

from app.core.config import settings
from app.models import models

# Configure logging
logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self._access_token: Optional[str] = None
    
    async def get_token(self, telegram_id: str) -> str:
        """Get or refresh JWT token for user authentication"""
        response = await self.client.post(
            f"{self.base_url}/token",
            json={"telegram_id": telegram_id}
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        return self._access_token

    async def create_message(self, content: str) -> dict:
        """Create a new message through the API"""
        response = await self.client.post(
            f"{self.base_url}/message",
            json={"content": content},
            headers={"Authorization": f"Bearer {self._access_token}"}
        )
        response.raise_for_status()
        return response.json()

    async def get_wallet(self) -> dict:
        """Get wallet information"""
        response = await self.client.get(
            f"{self.base_url}/wallet",
            headers={"Authorization": f"Bearer {self._access_token}"}
        )
        response.raise_for_status()
        return response.json()

    async def create_subscription(self) -> dict:
        """Create a new subscription"""
        response = await self.client.post(
            f"{self.base_url}/subscribe",
            headers={"Authorization": f"Bearer {self._access_token}"}
        )
        response.raise_for_status()
        return response.json()

    async def add_coins(self, amount: int) -> dict:
        """Add coins to user's wallet"""
        response = await self.client.post(
            f"{self.base_url}/add_coins",
            json={"amount": amount},
            headers={"Authorization": f"Bearer {self._access_token}"}
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
api_client = APIClient(base_url=settings.API_URL)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"Received /start command from user {message.from_user.id}")
    try:
        # Get token for the user
        await api_client.get_token(str(message.from_user.id))
        await message.answer(
            "Welcome! You've been registered. Use /subscribe to get access to the LLM service."
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            await message.answer("Welcome back! You can send any message to interact with the LLM.")
        else:
            logger.error(f"Error in cmd_start: {str(e)}", exc_info=True)
            await message.answer("An error occurred. Please try again later.")
    except Exception as e:
        logger.error(f"Error in cmd_start: {str(e)}", exc_info=True)
        await message.answer("An error occurred. Please try again later.")

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    logger.info(f"Received /subscribe command from user {message.from_user.id}")
    try:
        await api_client.get_token(str(message.from_user.id))
        result = await api_client.create_subscription()
        await message.answer(
            f"Subscription created successfully!\n"
            f"Coins spent: {result['coins_spent']}\n"
            f"Remaining coins: {result['remaining_coins']}"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_data = e.response.json()
            await message.answer(error_data["detail"])
        else:
            logger.error(f"Error in cmd_subscribe: {str(e)}", exc_info=True)
            await message.answer("An error occurred while processing your subscription. Please try again later.")
    except Exception as e:
        logger.error(f"Error in cmd_subscribe: {str(e)}", exc_info=True)

        await message.answer("An error occurred while processing your subscription. Please try again later.")

@dp.message(Command("wallet"))
async def cmd_wallet(message: Message):
    logger.info(f"Received /wallet command from user {message.from_user.id}")
    try:
        await api_client.get_token(str(message.from_user.id))
        wallet_info = await api_client.get_wallet()
        
        # Create inline keyboard for adding coins
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add 10 coins", callback_data="add_coins_10")],
            [InlineKeyboardButton(text="🕐 Subscribe", callback_data="subscribe")]
        ])

        await message.answer(
            f"💰 Your Wallet Balance: {wallet_info['balance']} coins\n\n"
            f"💡 Each minute of subscription costs {wallet_info['subscription_cost_per_minute']} coins\n"
            f"🔄 Use the button below to add more coins!",
            reply_markup=keyboard
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Error in cmd_wallet: {str(e)}", exc_info=True)
        await message.answer("An error occurred while checking your wallet. Please try again later.")
    except Exception as e:
        logger.error(f"Error in cmd_wallet: {str(e)}", exc_info=True)
        await message.answer("An error occurred while checking your wallet. Please try again later.")

@dp.callback_query(lambda c: c.data.startswith('add_coins_'))
async def process_add_coins(callback_query: CallbackQuery):
    logger.info(f"Received add coins callback from user {callback_query.from_user.id}")
    try:
        # Extract amount from callback data (e.g., "add_coins_10" -> 10)
        amount = int(callback_query.data.split('_')[-1])
        
        await api_client.get_token(str(callback_query.from_user.id))
        result = await api_client.add_coins(amount)

        # Update the message with new balance
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add 10 coins", callback_data="add_coins_10")],
            [InlineKeyboardButton(text="🕐 Subscribe", callback_data="subscribe")]
        ])

        await callback_query.message.edit_text(
            f"💰 Your Wallet Balance: {result['new_balance']} coins\n\n"
            f"💡 Each minute of subscription costs 10 coins\n"
            f"🔄 Use the button below to add more coins!",
            reply_markup=keyboard
        )
        
        await callback_query.answer(f"✅ {amount} coins added to your wallet!")
    except Exception as e:
        logger.error(f"Error in process_add_coins: {str(e)}", exc_info=True)
        await callback_query.answer("An error occurred while adding coins. Please try again later.")

@dp.callback_query(lambda c: c.data == "subscribe")
async def process_subscribe(callback_query: CallbackQuery):
    logger.info(f"Received subscribe callback from user {callback_query.from_user.id}")
    try:
        await api_client.get_token(str(callback_query.from_user.id))
        result = await api_client.create_subscription()
        
        # Update the message with subscription result
        await callback_query.message.edit_text(
            f"✅ Subscription created successfully!\n\n"
            f"💰 Coins spent: {result['coins_spent']}\n"
            f"💳 Remaining coins: {result['remaining_coins']}\n\n"
            f"🔄 You can now use the LLM service. Send any message to interact with it."
        )
        
        await callback_query.answer("Subscription created successfully!")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_data = e.response.json()
            await callback_query.answer(error_data["detail"])
        else:
            logger.error(f"Error in process_subscribe: {str(e)}", exc_info=True)
            await callback_query.answer("An error occurred while processing your subscription. Please try again later.")
    except Exception as e:
        logger.error(f"Error in process_subscribe: {str(e)}", exc_info=True)
        await callback_query.answer("An error occurred while processing your subscription. Please try again later.")

@dp.message()
async def handle_message(message: Message):
    logger.info(f"Received message from user {message.from_user.id}: {message.text[:50]}...")
    try:
        await api_client.get_token(str(message.from_user.id))
        
        processing_msg = await message.answer("Processing your request...")
        
        result = await api_client.create_message(message.text)
        logger.info(f"Result: {result}")
        
        await processing_msg.edit_text(result["response"])
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            await message.answer("You need an active subscription to use the service. Use /subscribe to get access.")
        else:
            logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
            await message.answer("An error occurred while processing your message. Please try again later.")
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
        await message.answer("An error occurred while processing your message. Please try again later.")

async def start_bot():
    logger.info("Starting Telegram bot")
    try:
        await dp.start_polling(bot)
    finally:
        await api_client.close()
    logger.info("Telegram bot started successfully")