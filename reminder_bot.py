#!/usr/bin/env python3
"""
Умный бот-напоминалка с улучшенным ИИ и контекстным пониманием
"""
import os
import logging
import sqlite3
import re
import random
import json
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

# Настройки
DB_PATH = "bot.db"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальный словарь для хранения контекста разговора
conversation_context = {}

# ----------------- Database helpers -----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Таблица заметок
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        created_at TEXT
    );
    """)
    
    # Таблица задач
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        status TEXT,
        next_check TEXT,
        created_at TEXT
    );
    """)
    
    # Таблица знаний для ИИ
    cur.execute("""
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT,
        response TEXT,
        action_type TEXT,
        action_params TEXT,
        usage_count INTEGER DEFAULT 0
    );
    """)
    
    # Проверяем и добавляем отсутствующие столбцы
    try:
        cur.execute("SELECT action_type FROM knowledge LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Добавляем отсутствующие столбцы в таблицу knowledge...")
        cur.execute("ALTER TABLE knowledge ADD COLUMN action_type TEXT")
        cur.execute("ALTER TABLE knowledge ADD COLUMN action_params TEXT")
    
    # Таблица контекста пользователя
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_context (
        user_id INTEGER PRIMARY KEY,
        last_messages TEXT,
        preferences TEXT,
        last_updated TEXT
    );
    """)
    
    # Добавляем базовые знания с действиями
    basic_knowledge = [
        (r"\b(привет|hello|hi|здравствуй|хай|ку)\b", "Привет! Как твои дела?", "greeting", None),
        (r"\b(как дела|как ты|как жизнь|как настроение)\b", "У меня всё отлично! Рад общению с тобой 😊", "small_talk", None),
        (r"\b(что делаешь|чем занят|работаешь)\b", "Отвечаю на сообщения и напоминаю о важных делах!", "small_talk", None),
        (r"\b(спасибо|благодарю|пасиб|thanks)\b", "Всегда пожалуйста! Обращайся ещё 😊", "small_talk", None),
        (r"\b(пока|до свидания|прощай|увидимся|goodbye)\b", "До встречи! Буду ждать нашего следующего общения!", "small_talk", None),
        (r"\b(кто ты|что ты|расскажи о себе)\b", "Я твой личный помощник-бот! Я могу сохранять заметки, напоминать о делах и просто общаться с тобой.", "small_talk", None),
        (r"\b(что умеешь|команды|возможности)\b", "Я могу:\n• Сохранять заметки: /note\n• Создавать задачи: /task\n• Показывать список дел: /tasks\n• Устанавливать напоминания: /remind\n• И просто общаться!", "small_talk", None),
        (r"\b(хорошо|отлично|норм|нормально)\b", "Это здорово! Рад за тебя 😊", "small_talk", None),
        (r"\b(плохо|не очень|устал|устала|усталое)\b", "Мне жаль это слышать... Может, отдохнешь или сделаешь что-то приятное?", "small_talk", None),
        (r"\b(люблю тебя|ты лучший|молодец)\b", "Спасибо! Ты тоже замечательный! 😍", "small_talk", None),
        (r"\b(погода|на улице|дождь|солнце)\b", "К сожалению, я не могу проверить погоду, но советую выглянуть в окно или проверить прогноз в интернете!", "small_talk", None),
        (r"\b(время|который час|сколько времени)\b", "Сейчас {time}", "small_talk", None),
        (r"\b(дата|число|какое сегодня)\b", "Сегодня {date}", "small_talk", None),
        (r"\b(шутка|пошути|расскажи шутку)\b", "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!", "small_talk", None),
        (r"\b(совет|посоветуй|что делать)\b", "Советую составить список задач и расставить приоритеты. Я могу помочь с этим!", "small_talk", None),
        (r"\b(как тебя зовут|твое имя)\b", "Меня зовут Помощник! А тебя как зовут?", "small_talk", None),
        (r"\b(меня зовут|мое имя)\b", "Приятно познакомиться, {name}!", "small_talk", None),
        (r"\b(что нового|новости)\b", "У меня всё как всегда, а у тебя что нового?", "small_talk", None),
        (r"\b(скучно|нечего делать)\b", "Может, займешься чем-то полезным? Я могу помочь с задачами!", "small_talk", None),
        (r"\b(спокойной ночи|доброй ночи)\b", "Спокойной ночи! Хороших снов 💤", "small_talk", None),
        (r"\b(запиши|добавь|создай) заметку (.*)", "Заметка сохранена: {note_text}", "create_note", "{'note_text': '$2'}"),
        (r"\b(напомни|напомнить) через (\d+) (минут|минуты|час|часа|часов) (.*)", "Напоминание установлено: {reminder_text}", "create_reminder", "{'minutes': $2, 'reminder_text': '$4'}"),
        (r"\b(покажи|посмотреть|открой) заметки\b", "Вот ваши заметки:", "show_notes", None),
        (r"\b(что я писал|мои сообщения|история)\b", "Вот ваши последние сообщения:", "show_history", None),
    ]
    
    cur.execute("SELECT COUNT(*) FROM knowledge")
    if cur.fetchone()[0] == 0:
        for pattern, response, action_type, action_params in basic_knowledge:
            cur.execute(
                "INSERT INTO knowledge (pattern, response, action_type, action_params) VALUES (?, ?, ?, ?)",
                (pattern, response, action_type, action_params)
            )
        logger.info("Добавлены базовые знания в базу")
    
    conn.commit()
    conn.close()


def add_note(user_id: int, text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notes (user_id, text, created_at) VALUES (?, ?, ?)",
        (user_id, text, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def list_notes(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, text, created_at FROM notes WHERE user_id=? ORDER BY id DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_task(user_id: int, text: str, next_check: datetime):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (user_id, text, status, next_check, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, text, "pending", next_check.isoformat(), datetime.utcnow().isoformat())
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def get_task(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, text, status, next_check FROM tasks WHERE id=?",
        (task_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def set_task_done(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def update_task_next_check(task_id: int, next_check: datetime):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET next_check=? WHERE id=?", (next_check.isoformat(), task_id))
    conn.commit()
    conn.close()


def list_pending_tasks():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, text, status, next_check FROM tasks WHERE status='pending'")
    rows = cur.fetchall()
    conn.close()
    return rows


def save_user_context(user_id: int, message: str):
    """Сохраняет контекст пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Получаем текущий контекст
    cur.execute("SELECT last_messages FROM user_context WHERE user_id=?", (user_id,))
    result = cur.fetchone()
    
    if result:
        # Обновляем существующий контекст
        messages = json.loads(result[0])
        messages.append({"text": message, "time": datetime.now().isoformat()})
        # Ограничиваем историю 10 последними сообщениями
        if len(messages) > 10:
            messages = messages[-10:]
        
        cur.execute(
            "UPDATE user_context SET last_messages=?, last_updated=? WHERE user_id=?",
            (json.dumps(messages), datetime.now().isoformat(), user_id)
        )
    else:
        # Создаем новый контекст
        messages = [{"text": message, "time": datetime.now().isoformat()}]
        cur.execute(
            "INSERT INTO user_context (user_id, last_messages, last_updated) VALUES (?, ?, ?)",
            (user_id, json.dumps(messages), datetime.now().isoformat())
        )
    
    conn.commit()
    conn.close()


def get_user_context(user_id: int):
    """Получает контекст пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT last_messages FROM user_context WHERE user_id=?", (user_id,))
    result = cur.fetchone()
    conn.close()
    
    if result:
        return json.loads(result[0])
    return []


def find_response(text: str, user_id: int = None):
    """Ищет подходящий ответ в базе знаний и выполняет действия"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Проверяем, есть ли нужные столбцы
    try:
        cur.execute("SELECT id, pattern, response, action_type, action_params FROM knowledge")
    except sqlite3.OperationalError as e:
        if "no such column" in str(e):
            # Если столбцы отсутствуют, используем упрощенный запрос
            cur.execute("SELECT id, pattern, response FROM knowledge")
            rows = cur.fetchall()
            # Добавляем пустые значения для отсутствующих столбцов
            rows = [(row[0], row[1], row[2], None, None) for row in rows]
        else:
            raise
    else:
        rows = cur.fetchall()
    
    conn.close()
    
    text_lower = text.lower()
    
    # Сохраняем контекст пользователя
    if user_id:
        save_user_context(user_id, text)
    
    for row in rows:
        pattern, response, action_type, action_params = row[1], row[2], row[3], row[4]
        match = re.search(pattern, text_lower, re.IGNORECASE)
        
        if match:
            # Увеличиваем счетчик использования
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("UPDATE knowledge SET usage_count = usage_count + 1 WHERE id=?", (row[0],))
            conn.commit()
            conn.close()
            
            # Заменяем специальные шаблоны
            response = process_response_template(response, match, user_id)
            
            # Выполняем действие, если указано
            if action_type and user_id:
                response = execute_action(action_type, action_params, match, user_id, response)
                return response
            
            return response
    
    return None


def process_response_template(response: str, match: re.Match, user_id: int = None):
    """Обрабатывает шаблоны в ответах"""
    # Заменяем {time} и {date}
    if "{time}" in response:
        response = response.replace("{time}", datetime.now().strftime("%H:%M"))
    if "{date}" in response:
        response = response.replace("{date}", datetime.now().strftime("%d.%m.%Y"))
    
    # Заменяем группы из регулярного выражения
    for i in range(1, 10):
        if f"${i}" in response and i <= len(match.groups()):
            response = response.replace(f"${i}", match.group(i))
        if f"{{group{i}}}" in response and i <= len(match.groups()):
            response = response.replace(f"{{group{i}}}", match.group(i))
    
    # Обрабатываем специальные шаблоны
    if "{note_text}" in response and len(match.groups()) >= 1:
        response = response.replace("{note_text}", match.group(2 if len(match.groups()) >= 2 else 1))
    
    if "{reminder_text}" in response and len(match.groups()) >= 4:
        response = response.replace("{reminder_text}", match.group(4))
    
    return response


def execute_action(action_type: str, action_params: str, match: re.Match, user_id: int, response: str):
    """Выполняет действие на основе типа и параметров"""
    try:
        if action_type == "create_note":
            # Создаем заметку
            note_text = match.group(2) if len(match.groups()) >= 2 else match.group(1)
            add_note(user_id, note_text)
            
        elif action_type == "create_reminder":
            # Создаем напоминание
            minutes = int(match.group(2))
            reminder_text = match.group(4)
            
            # Конвертируем часы в минуты
            if match.group(3) in ["час", "часа", "часов"]:
                minutes *= 60
                
            next_check = datetime.utcnow() + timedelta(minutes=minutes)
            add_task(user_id, reminder_text, next_check)
            
        elif action_type == "show_notes":
            # Показываем заметки
            notes = list_notes(user_id)
            if notes:
                notes_text = "\n".join([f"{i+1}. {note[1]}" for i, note in enumerate(notes[:5])])
                response = f"📋 Ваши последние заметки:\n\n{notes_text}"
            else:
                response = "📋 У вас пока нет заметок."
                
        elif action_type == "show_history":
            # Показываем история сообщений
            history = get_user_context(user_id)
            if history:
                history_text = "\n".join([f"{i+1}. {msg['text']}" for i, msg in enumerate(history[-5:])])
                response = f"📝 Ваши последние сообщения:\n\n{history_text}"
            else:
                response = "📝 История сообщений пуста."
                
    except Exception as e:
        logger.error(f"Ошибка выполнения действия: {e}")
        response = "Произошла ошибка при выполнении команды."

    return response


def add_knowledge(pattern: str, response: str, action_type: str = None, action_params: str = None):
    """Добавляет новое знание в базу"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO knowledge (pattern, response, action_type, action_params) VALUES (?, ?, ?, ?)",
        (pattern, response, action_type, action_params)
    )
    conn.commit()
    conn.close()


# ----------------- Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я умный бот-помощник с улучшенным ИИ 🤖\n\n"
        "Я понимаю естественную речь и могу:\n"
        "• Сохранять заметки (например: 'запиши заметку сходить в магазин')\n"
        "• Создавать напоминания (например: 'напомни через 30 минут позвонить маме')\n"
        "• Показывать заметки и задачи\n"
        "• Запоминать контекст разговора\n\n"
        "Также я умею общаться на разные темы! Просто напиши мне что-нибудь 😊"
    )


async def note_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /note <текст заметки>")
        return
    text = " ".join(args)
    add_note(user.id, text)
    await update.message.reply_text("📝 Заметка сохранена!")


async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rows = list_notes(user.id)
    if not rows:
        await update.message.reply_text("📋 У вас пока нет заметок.")
        return
    
    lines = []
    for i, r in enumerate(rows[:10], 1):
        lines.append(f"{i}. {r[1]}  ({r[2][:10]})")
    
    await update.message.reply_text("📋 Ваши последние заметки:\n\n" + "\n".join(lines))


async def task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /task <минуты> <текст задачи>")
        return
    try:
        minutes = int(args[0])
    except ValueError:
        await update.message.reply_text("Первый аргумент должен быть числом (количество минут).")
        return
    text = " ".join(args[1:])
    next_check = datetime.utcnow() + timedelta(minutes=minutes)
    task_id = add_task(user.id, text, next_check)
    context.job_queue.run_once(send_task_check, when=minutes * 60, data={"task_id": task_id, "chat_id": update.effective_chat.id})
    await update.message.reply_text(f"✅ Задача сохранена! Напомню через {minutes} минут.")


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rows = [r for r in list_pending_tasks() if r[1] == user.id]
    if not rows:
        await update.message.reply_text("✅ У вас нет активных задач.")
        return
    
    lines = []
    for r in rows:
        nid, uid, text, status, next_check = r
        dt = datetime.fromisoformat(next_check)
        local_time = dt.strftime("%H:%M")
        lines.append(f"• {text} (в {local_time})")
    
    await update.message.reply_text("📝 Ваши активные задачи:\n\n" + "\n".join(lines))


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /remind <минуты> <текст>")
        return
    try:
        minutes = int(args[0])
    except ValueError:
        await update.message.reply_text("Первый аргумент должен быть числом (количество минут).")
        return
    text = " ".join(args[1:])
    context.job_queue.run_once(send_simple_reminder, when=minutes * 60, data={"chat_id": update.effective_chat.id, "text": text})
    await update.message.reply_text(f"⏰ Напоминание установлено на {minutes} минут.")


async def learn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для обучения бота новым ответам"""
    user = update.effective_user
    args = context.args
    
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Использование: /learn <шаблон> <ответ>\n\n"
            "Например: /learn какпогода Погоду я не знаю, посмотри в окно :)"
        )
        return
    
    # Разделяем аргументы: первый - шаблон, остальные - ответ
    pattern = args[0]
    response = " ".join(args[1:])
    
    add_knowledge(pattern, response)
    await update.message.reply_text("✅ Новый ответ добавлен в мою базу знаний!")


async def context_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает контекст пользователя"""
    user = update.effective_user
    user_context = get_user_context(user.id)
    
    if not user_context:
        await update.message.reply_text("Контекст разговора пуст.")
        return
    
    context_text = "\n".join([f"{i+1}. {msg['text']}" for i, msg in enumerate(user_context)])
    await update.message.reply_text(f"📝 История нашего разговора:\n\n{context_text}")


# job callbacks
async def send_simple_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    text = data["text"]
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")


async def send_task_check(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    task_id = data["task_id"]
    chat_id = data["chat_id"]
    row = get_task(task_id)
    if not row:
        return
    tid, user_id, text, status, next_check = row
    if status != "pending":
        return
    kb = [
        [InlineKeyboardButton("Да ✅", callback_data=f"task:{tid}:yes"),
         InlineKeyboardButton("Нет ❌", callback_data=f"task:{tid}:no")],
        [InlineKeyboardButton("Отложить 10m", callback_data=f"task:{tid}:snooze:10"),
         InlineKeyboardButton("Отложить 30m", callback_data=f"task:{tid}:snooze:30"),
         InlineKeyboardButton("Отложить 60m", callback_data=f"task:{tid}:snooze:60")],
    ]
    await context.bot.send_message(chat_id=chat_id, text=f"✅ Сделано? — {text}", reply_markup=InlineKeyboardMarkup(kb))


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split(":")
    if parts[0] != "task":
        await query.edit_message_text("Неизвестная команда.")
        return
    task_id = int(parts[1])
    action = parts[2]
    if action == "yes":
        set_task_done(task_id)
        await query.edit_message_text("✅ Отлично! Пометил как выполненное.")
    elif action == "no":
        await query.edit_message_text("❌ Понял, не выполнено. Можешь отложить напоминание или оставить как есть.")
    elif action == "snooze":
        minutes = int(parts[3])
        next_time = datetime.utcnow() + timedelta(minutes=minutes)
        update_task_next_check(task_id, next_time)
        context.job_queue.run_once(send_task_check, when=minutes * 60, data={"task_id": task_id, "chat_id": query.message.chat.id})
        await query.edit_message_text(f"⏰ Отложено на {minutes} минут.")
    else:
        await query.edit_message_text("Неизвестная опция.")


# Обработчик обычных сообщений
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id
    
    if not text:
        return
    
    # Пропускаем команды
    if text.startswith('/'):
        return
    
    # Ищем ответ в базе знаний
    response = find_response(text, user_id)
    
    if response:
        await update.message.reply_text(response)
        return
    
    # Автоматическое создание напоминаний (универсальный обработчик)
    remind_match = re.search(r"напомни\s+(мне\s+)?(через\s+)?(\d+)\s+(минут|минуты|час|часа|часов)\s+(.*)", text, re.IGNORECASE)
    if remind_match:
        minutes = int(remind_match.group(3))
        unit = remind_match.group(4)
        task_text = remind_match.group(5)
        
        if unit in ["час", "часа", "часов"]:
            minutes *= 60
            
        next_check = datetime.utcnow() + timedelta(minutes=minutes)
        task_id = add_task(user_id, task_text, next_check)
        context.job_queue.run_once(
            send_task_check, 
            when=minutes * 60, 
            data={"task_id": task_id, "chat_id": update.effective_chat.id}
        )
        
        await update.message.reply_text(f"✅ Хорошо, напомню о '{task_text}' через {minutes} минут.")
        return
    
    # Автоматическое создание заметок (универсальный обработчик)
    note_match = re.search(r"(запиши|добавь|создай)(\s+мне)?\s+заметку\s+(на\s+)?(.*)", text, re.IGNORECASE)
    if note_match:
        note_text = note_match.group(4)
        add_note(user_id, note_text)
        await update.message.reply_text(f"📝 Заметка сохранена: {note_text}")
        return
    
    # Если не нашли подходящий ответ, используем общие фразы
    general_responses = [
        "Извини, я не совсем понял. Можешь переформулировать?",
        "Интересно! Могу я помочь тебе с чем-то еще?",
        "Записал бы это, но я пока просто бот 😊",
        "Можем обсудить задачи или просто поболтать!",
        "Я еще учусь понимать людей, но стараюсь изо всех сил!",
        "К сожалению, я не совсем понимаю, что ты имеешь в виду. Может, сформулируешь иначе?",
        "Забавно! А что еще хочешь обсудить?",
        "Я бы с удовольствием поговорил об этом, но мои создатели пока не научили меня этой теме 😅"
    ]
    
    await update.message.reply_text(random.choice(general_responses))


def main():
    # Инициализация базы данных
    init_db()
    
    # Проверка токена
    token = TELEGRAM_TOKEN
    if not token:
        print("Ошибка: TELEGRAM_TOKEN не найден.")
        print("Установите переменную окружения перед запуском:")
        print("CMD: set TELEGRAM_TOKEN=ВАШ_ТОКЕН")
        print("PowerShell: $env:TELEGRAM_TOKEN = \"ВАШ_ТОКЕН\"")
        return

    # Создаем приложение
    application = Application.builder().token(token).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("note", note_cmd))
    application.add_handler(CommandHandler("notes", notes_cmd))
    application.add_handler(CommandHandler("task", task_cmd))
    application.add_handler(CommandHandler("tasks", tasks_cmd))
    application.add_handler(CommandHandler("remind", remind_cmd))
    application.add_handler(CommandHandler("learn", learn_cmd))
    application.add_handler(CommandHandler("context", context_cmd))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Запуск бота
    logger.info("Бот запущен (polling)...")
    application.run_polling()


if __name__ == "__main__":
    main()