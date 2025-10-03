import sqlite3
from datetime import datetime

def init_db(db_path):
    """Инициализация базы данных"""
    conn = sqlite3.connect(db_path)
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
    
    # Таблица контекста пользователя
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_context (
        user_id INTEGER PRIMARY KEY,
        last_messages TEXT,
        preferences TEXT,
        last_updated TEXT
    );
    """)
    
    # Добавляем базовые знания
    basic_knowledge = [
        (r"\b(привет|hello|hi|здравствуй|хай|ку)\b", "Привет! Как твои дела?", "greeting", None),
        (r"\b(как дела|как ты|как жизнь|как настроение)\b", "У меня всё отлично! Рад общению с тобой 😊", "small_talk", None),
        # Добавьте здесь другие базовые шаблоны...
    ]
    
    cur.execute("SELECT COUNT(*) FROM knowledge")
    if cur.fetchone()[0] == 0:
        for pattern, response, action_type, action_params in basic_knowledge:
            cur.execute(
                "INSERT INTO knowledge (pattern, response, action_type, action_params) VALUES (?, ?, ?, ?)",
                (pattern, response, action_type, action_params)
            )
    
    conn.commit()
    conn.close()