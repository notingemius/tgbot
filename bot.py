import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from gpt4all import GPT4All

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_PATH = r"D:\telegram_reminder_bot\models\orca-mini-3b-gguf2-q4_0.gguf"
BOT_TOKEN = "7941127926:AAH20Xt9Wsb-bApJWa_bFkg-h0N1NZXGvJk"

# Инициализация модели
model = GPT4All(MODEL_PATH)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    logger.info(f"Received message: {user_message}")
    
    # Отправка статуса "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Генерация ответа
    try:
        with model.chat_session():
            response = model.generate(user_message, max_tokens=200)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Извините, произошла ошибка: {str(e)}")

def main():
    # Создание приложения бота с отключенным job_queue
    application = Application.builder().token(BOT_TOKEN).job_queue(None).build()
    
    # Добавление обработчика сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()