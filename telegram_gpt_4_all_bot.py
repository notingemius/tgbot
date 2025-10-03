#!/usr/bin/env python3
"""
Simple Telegram bot that uses a local GPT4All model (GGUF) to answer messages.

Usage:
  1) Set TELEGRAM_TOKEN environment variable (do NOT hardcode your token in the file).
     On Windows (temporary): set TELEGRAM_TOKEN=YOUR_TOKEN_HERE
     On Linux/macOS: export TELEGRAM_TOKEN=YOUR_TOKEN_HERE
  2) Set MODEL_PATH environment variable to your GGUF file path (optional). Example:
     MODEL_PATH=D:\telegram_reminder_bot\models\orca-mini-3b-gguf2-q4_0.gguf
  3) Install dependencies:
     pip install gpt4all python-telegram-bot==20.6
  4) Run: python telegram_gpt4all_bot.py

Notes:
 - This script loads the GPT4All model once at startup and serializes access with a lock to
   avoid concurrent generate() calls colliding.
 - The code uses run_in_executor to avoid blocking asyncio event loop while generating.
 - Keep your bot token secret. If you accidentally posted it anywhere public, revoke/regenerate it in BotFather immediately.

"""

import os
import asyncio
import logging
import threading
from gpt4all import GPT4All
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration: read from environment with sensible defaults
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MODEL_PATH = os.getenv("MODEL_PATH", r"D:\telegram_reminder_bot\models\orca-mini-3b-gguf2-q4_0.gguf")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable not set. Set it and restart the bot.")

# Global model and lock
MODEL = None
MODEL_LOCK = threading.Lock()


def load_model(path: str):
    """Load GPT4All model (only once).
    We keep the GPT4All instance in a global variable.
    """
    global MODEL
    if MODEL is None:
        logger.info("Loading GPT4All model from: %s", path)
        MODEL = GPT4All(path)
        logger.info("Model loaded.")
    return MODEL


def generate_response(prompt: str) -> str:
    """Blocking generation call. Use run_in_executor to call from async code.

    We use a lock to avoid concurrent generate() calls on the same model instance.
    """
    model = load_model(MODEL_PATH)
    with MODEL_LOCK:
        # open a chat session for nicer assistant-style behavior
        with model.chat_session():
            # You can tweak parameters here (max_tokens, temperature, etc.)
            reply = model.generate(prompt, max_tokens=MAX_TOKENS)
    # Ensure reply is a str
    return reply if isinstance(reply, str) else str(reply)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я локальный GPT (через GPT4All). Отправь сообщение — и я отвечу.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    chat_id = update.effective_chat.id
    logger.info("Message from %s (%s): %s", user.username or user.id, chat_id, text)

    # Very short messages can be answered with a quick prompt
    prompt = f"Пользователь: {text}\nАссистент:" 

    loop = asyncio.get_running_loop()
    try:
        # run blocking generation in default ThreadPoolExecutor
        reply = await loop.run_in_executor(None, generate_response, prompt)
    except Exception as e:
        logger.exception("Error during generation: %s", e)
        await update.message.reply_text("Ошибка при генерации ответа: %s" % str(e))
        return

    # Trim reply if too long for Telegram (max ~4096 chars)
    if len(reply) > 4000:
        reply = reply[:4000] + "\n\n...[ответ обрезан]"

    await update.message.reply_text(reply)


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running. Model path: %s" % MODEL_PATH)


def main():
    # load model in main thread (so startup cost occurs once)
    load_model(MODEL_PATH)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
