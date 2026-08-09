import logging
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Загрузка переменных окружения (из .env при локальном запуске или из настроек хостинга)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка логирования в консоль
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Проверка присутствия обязательных ключей
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    logger.critical("КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_BOT_TOKEN или GEMINI_API_KEY не заданы!")
    sys.exit(1)

# Инициализация официального клиента Google GenAI
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as err:
    logger.critical(f"Ошибка при подключении к Gemini API: {err}")
    sys.exit(1)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user_name = update.effective_user.first_name if update.effective_user else "пользователь"
    welcome_message = (
        f"Привет, {user_name}! 👋\n\n"
        "Я готов отвечать на любые твои вопросы с помощью сверхбыстрой модели **Gemini 2.5 Flash**! ⚡️\n\n"
        "Просто напиши мне сообщение, и я сформирую ответ."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    help_text = (
        "🤖 **Как работать с ботом:**\n\n"
        "1. Задавай мне любые вопросы текстом.\n"
        "2. Я умею писать код, переводить тексты и решать сложные задачи.\n"
        "3. Перезапустить разговор всегда можно командой /start."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик входящих текстовых сообщений."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text

    # Отображаем индикатор "печатает..." в чате
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        # Вызов модели Gemini 2.5 Flash
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Ты — умный, вежливый и полезный ассистент в Telegram. "
                    "Отвечай структурированно, грамотно и понятно на языке пользователя."
                )
            ),
        )

        reply_text = (
            response.text
            if response.text
            else "К сожалению, модель не смогла сгенерировать ответ."
        )

        # Обработка лимита Telegram на длину сообщения (4096 символов)
        if len(reply_text) > 4000:
            for i in range(0, len(reply_text), 4000):
                await update.message.reply_text(reply_text[i : i + 4000])
        else:
            await update.message.reply_text(reply_text)

    except Exception as error:
        logger.error(f"Ошибка при выполнении запроса к Gemini API: {error}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке ответа. Попробуйте еще раз позже."
        )


def main() -> None:
    """Инициализация и запуск Telegram-бота."""
    logger.info("Запуск Telegram-бота...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Бот успешно запущен и слушает сообщения...")
    app.run_polling()


if __name__ == "__main__":
    main()

