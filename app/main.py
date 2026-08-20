import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError

from app.asl_client import AslClient
from app.config import get_settings
from app.handlers import create_router
from app.moderation import ModerationServer
from app.storage import UserStorage

logger = logging.getLogger(__name__)


async def run_bot() -> None:
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
    moderation = ModerationServer(
        storage=storage,
        host=settings.moderation_host,
        port=settings.moderation_port,
    )
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(storage, asl))

    # Start moderation server in background
    try:
        await moderation.start()
        logger.info(
            "Moderation server started on %s:%s",
            settings.moderation_host,
            settings.moderation_port,
        )
    except Exception as exc:
        logger.warning("Could not start moderation server: %s", exc)

    retry_delay = 3
    while True:
        try:
            logger.info("Connecting to Telegram Bot API...")
            await bot.delete_webhook(drop_pending_updates=True)
            me = await bot.get_me()
            logger.info(
                "Bot @%s (id=%s) connected and listening for updates...",
                me.username,
                me.id,
            )
            retry_delay = 3
            await dispatcher.start_polling(bot, handle_signals=True, close_bot_session=False)
            break
        except (TelegramNetworkError, asyncio.TimeoutError, ConnectionError) as exc:
            logger.warning(
                "Network disconnected: %s. Reconnecting in %s seconds...",
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        except asyncio.CancelledError:
            logger.info("Bot shutting down...")
            break
        except Exception as exc:
            logger.error("Unexpected error in polling: %s. Retrying in 5s...", exc)
            await asyncio.sleep(5)

    await moderation.stop()
    await bot.session.close()


def main() -> None:
    from logging.handlers import RotatingFileHandler
    from pathlib import Path
    log_file = Path(__file__).resolve().parent.parent / "bot.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[file_handler, console_handler],
    )
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
