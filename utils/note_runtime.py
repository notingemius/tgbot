# D:\telegram_reminder_bot\utils\note_runtime.py
from typing import Dict, Tuple, Optional, Set

# ожидание «введи кастомный интервал» для (chat_id, user_id) -> note_id
_pending_custom: Dict[Tuple[int, int], int] = {}
# ожидание «введи текст новой заметки» для (chat_id, user_id)
_pending_create: Set[Tuple[int, int]] = set()

# --- кастомный snooze ---
def set_pending(chat_id: int, user_id: int, note_id: int) -> None:
    _pending_custom[(chat_id, user_id)] = note_id

def pop_pending(chat_id: int, user_id: int) -> Optional[int]:
    return _pending_custom.pop((chat_id, user_id), None)

def get_pending(chat_id: int, user_id: int) -> Optional[int]:
    return _pending_custom.get((chat_id, user_id))

# --- создание заметки ---
def set_create_wait(chat_id: int, user_id: int) -> None:
    _pending_create.add((chat_id, user_id))

def pop_create_wait(chat_id: int, user_id: int) -> bool:
    return _pending_create.discard((chat_id, user_id)) is None  # возвращает True/False неважно

def is_create_wait(chat_id: int, user_id: int) -> bool:
    return (chat_id, user_id) in _pending_create
