import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.asl_client import AslClient
from app.config import get_settings
from app.handlers import create_router
from app.storage import UserStorage


async def main() -> None:
    settings = get_settings()
    storage = UserStorage(settings.database_path, settings.encryption_key)
    storage.initialize()
    asl = AslClient(
        base_url=settings.asl_base_url,
        api_key_header=settings.asl_api_key_header,
        api_key_prefix=settings.asl_api_key_prefix,
        check_path=settings.asl_api_key_check_path,
        card_path=settings.asl_card_create_path,
        aggregation_path=settings.asl_aggregation_create_path,
        timeout=settings.asl_timeout_seconds,
    )
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(storage, asl))
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
