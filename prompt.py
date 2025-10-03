# prompt.py
SYSTEM = "Ты — полезный ассистент. Отвечай по-русски кратко и по делу. Если используешь предоставленный контекст, указывай источник."

def build_prompt(history: list, retrieved: list, user_query: str, max_context_chars=3000):
    ctx = []
    chars = 0
    for r in retrieved:
        piece = f"### {r.get('title','')}\n{r.get('content')}\n"
        if chars + len(piece) > max_context_chars:
            break
        ctx.append(piece); chars += len(piece)
    context = "\n".join(ctx) if ctx else ""
    hist = "\n".join(history[-6:]) if history else ""
    prompt = f"{SYSTEM}\n\nCONTEXT:\n{context}\n\nHISTORY:\n{hist}\n\nUser: {user_query}\nAssistant:"
    return prompt
