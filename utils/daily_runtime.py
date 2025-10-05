# D:\telegram_reminder_bot\utils\daily_runtime.py
from typing import Set, Tuple

_pending: Set[Tuple[int, int]] = set()

def set_pending(chat_id: int, user_id: int) -> None:
    _pending.add((chat_id, user_id))

def is_pending(chat_id: int, user_id: int) -> bool:
    return (chat_id, user_id) in _pending

def clear(chat_id: int, user_id: int) -> None:
    _pending.discard((chat_id, user_id))
