import logging
import asyncio
import traceback
from telegram.ext import Application
from config import logger, TOKEN
from handlers import setup_handlers


def main():
    """Главная функция"""
    try:
        logger.info("🔹 Запускаем приложение бота...")

        # Создаем application
        application = Application.builder().token(TOKEN).build()

        # Настраиваем обработчики
        setup_handlers(application)

        logger.info("🔹 Бот запущен и готов к работе!")

        # Запускаем с обработкой ошибок
        application.run_polling(
            poll_interval=5,
            timeout=30,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        logger.error(f"Трассировка: {traceback.format_exc()}")
        print(f"Критическая ошибка: {e}")
        print("Подробности в логах")


if __name__ == "__main__":
    main()