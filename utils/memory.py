# utils/memory.py
from collections import defaultdict, deque
from typing import Deque, Dict, List

# простая «память» в ОЗУ по chat_id
class _Mem:
    def __init__(self, max_msgs: int = 30, max_chars: int = 6000):
        self.max_msgs = max_msgs
        self.max_chars = max_chars
        self.store: Dict[int, Deque[dict]] = defaultdict(deque)

    def add(self, chat_id: int, role: str, content: str):
        q = self.store[chat_id]
        q.append({"role": role, "content": content or ""})
        while len(q) > self.max_msgs or sum(len(m["content"]) for m in q) > self.max_chars:
            q.popleft()

    def get(self, chat_id: int) -> List[dict]:
        return list(self.store.get(chat_id, []))

    def reset(self, chat_id: int):
        self.store.pop(chat_id, None)

memory = _Mem()
