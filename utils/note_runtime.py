# D:\telegram_reminder_bot\utils\note_runtime.py
from typing import Dict, Tuple, Optional

# хранит ожидание «введи кастомный интервал» для (chat_id, user_id) -> note_id
_pending_custom: Dict[Tuple[int, int], int] = {}

def set_pending(chat_id: int, user_id: int, note_id: int) -> None:
    _pending_custom[(chat_id, user_id)] = note_id

def pop_pending(chat_id: int, user_id: int) -> Optional[int]:
    return _pending_custom.pop((chat_id, user_id), None)

def get_pending(chat_id: int, user_id: int) -> Optional[int]:
    return _pending_custom.get((chat_id, user_id))
