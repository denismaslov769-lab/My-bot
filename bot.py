import json
import logging
import os
import sys
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

# Прямое указание API-ключей в коде
TELEGRAM_BOT_TOKEN = "8383663013:AAE_6uGkpAZmOEUOOjHDh39nPqV4CJSRzzs"
GEMINI_API_KEY ="AQ.Ab8RN6Idv66Ioyi1ULGLdiQBP4EzL7ccVf28pNc91udbzV9gow"

# Настройки хранения данных
DATA_FILE = "users_data.json"  # Файл создается автоматически на хостинге
MAX_HISTORY_LIMIT = 500       # Лимит контекста истории сообщений

# Настройка логирования в консоль
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Проверка присутствия обязательных ключей
if TELEGRAM_BOT_TOKEN == "ВАШ_TELEGRAM_BOT_TOKEN_ЗДЕСЬ" or GEMINI_API_KEY == "ВАШ_GEMINI_API_KEY_ЗДЕСЬ":
    logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Замените заглушки на ваши реальные ключи TELEGRAM_BOT_TOKEN и GEMINI_API_KEY!")
    sys.exit(1)

# Инициализация официального клиента Google GenAI
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as err:
    logger.critical(f"Ошибка при подключении к Gemini API: {err}")
    sys.exit(1)


def load_user_data() -> dict:
    """Загрузка данных пользователей и истории из JSON-файла."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения файла {DATA_FILE}: {e}")
            return {}
    return {}


def save_user_data(data: dict) -> None:
    """Сохранение данных пользователей в JSON-файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка записи в {DATA_FILE}: {e}")


def update_user_info(users_db: dict, user) -> None:
    """Обновление метаданных профиля пользователя."""
    user_id = str(user.id)
    if user_id not in users_db:
        users_db[user_id] = {
            "info": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
            },
            "history": [],
        }
    else:
        # Актуализация сведений о пользователе
        users_db[user_id]["info"]["first_name"] = user.first_name
        users_db[user_id]["info"]["last_name"] = user.last_name
        users_db[user_id]["info"]["username"] = user.username


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start (сбрасывает контекст переписки)."""
    user = update.effective_user
    if user:
        users_db = load_user_data()
        user_id = str(user.id)
        
        # Сброс истории диалога при перезапуске
        update_user_info(users_db, user)
        users_db[user_id]["history"] = []
        save_user_data(users_db)

    user_name = user.first_name if user else "пользователь"
    welcome_message = (
        f"Привет, {user_name}! 👋\n\n"
        "Я готов отвечать на твои вопросы с помощью **Gemini 2.5 Flash**! ⚡️\n\n"
        f"🧠 Я запоминаю контекст диалога (до {MAX_HISTORY_LIMIT} сообщений).\n"
        "Очистить историю переписки можно командами /start или /clear."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /clear (очищает только историю сообщений)."""
    user = update.effective_user
    if user:
        users_db = load_user_data()
        user_id = str(user.id)
        update_user_info(users_db, user)
        users_db[user_id]["history"] = []
        save_user_data(users_db)
        await update.message.reply_text("🧹 История диалога полностью очищена!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    help_text = (
        "🤖 **Как работать с ботом:**\n\n"
        "1. Задавай мне вопросы — я помню контекст текущего диалога.\n"
        f"2. Максимальный лимит истории: **{MAX_HISTORY_LIMIT} сообщений**.\n"
        "3. Очистить историю и начать заново: /clear или /start."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик входящих текстовых сообщений с поддержкой контекста."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = str(user.id)
    user_text = update.message.text

    # Показываем статус "печатает..." в чате Telegram
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Загрузка локальной БД
    users_db = load_user_data()
    update_user_info(users_db, user)

    # Формирование объекта истории для SDK Gemini
    raw_history = users_db[user_id].get("history", [])
    formatted_history = []
    for item in raw_history:
        formatted_history.append(
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])],
            )
        )

    try:
        # Создание сессии чата с переданной историей
        chat = gemini_client.chats.create(
            model="gemini-2.5-flash",
            history=formatted_history,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Ты — умный, вежливый и полезный ассистент в Telegram. "
                    "Отвечай структурированно, грамотно и понятно на языке пользователя."
                )
            ),
        )

        # Отправка текущего запроса
        response = chat.send_message(user_text)

        reply_text = (
            response.text
            if response.text
            else "К сожалению, модель не смогла сгенерировать ответ."
        )

        # Сохраняем новые сообщения в историю
        raw_history.append({"role": "user", "text": user_text})
        raw_history.append({"role": "model", "text": reply_text})

        # Обрезаем историю до MAX_HISTORY_LIMIT последних сообщений
        users_db[user_id]["history"] = raw_history[-MAX_HISTORY_LIMIT:]
        save_user_data(users_db)

        # Отправка ответа с учетом лимита длины Telegram (4096 символов)
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
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Бот успешно запущен и готов к работе...")
    app.run_polling()


if __name__ == "__main__":
    main()

